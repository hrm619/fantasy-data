"""Bulk ingest PFF grades and stats from per-season CSVs.

Processes receiving_summary, rushing_summary, passing_summary,
offense_blocking, and defense_summary CSVs for 2014-2025.

Matches players by PFF ID first (fast), then name fallback.
Creates Player records for unmatched PFF players as is_active=0.

Usage:
    fantasy-data ingest pff-bulk --dir data-dev/pff-grades --start-season 2014 --end-season 2025
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.standardize import standardize_player_name, standardize_team

# --- Receiving CSV → baseline field mapping ---
RECEIVING_MAP = {
    "grades_offense": "pff_offense_grade",
    "grades_pass_route": "route_grade_pff",
    "grades_pass_block": "pff_pass_block_grade",
    "drop_rate": "drop_rate",
    "contested_catch_rate": "contested_target_rate",
    "avg_depth_of_target": "avg_depth_of_target",
    "yprr": "yards_per_route_run",
    "route_rate": "route_participation_rate",
    "yards_after_catch_per_reception": "yards_after_catch_per_rec",
    "player_game_count": "games_played",
}

# --- Rushing CSV → baseline field mapping ---
RUSHING_MAP = {
    "grades_run": "pff_rush_grade",
    "grades_run_block": "pff_run_blocking_grade",
    "grades_pass_block": "pff_pass_block_grade",
    "grades_pass_route": "pff_receiving_grade",
    "player_game_count": "games_played",
}

# --- Passing CSV → baseline field mapping ---
PASSING_MAP = {
    "grades_pass": "pff_passing_grade",
    "grades_offense": "pff_offense_grade",
    "player_game_count": "games_played",
}

# --- Blocking CSV → baseline field mapping ---
BLOCKING_MAP = {
    "grades_pass_block": "pff_pass_block_grade",
    "grades_run_block": "pff_run_blocking_grade",
}

# PFF position → our position mapping
PFF_POSITION_MAP = {
    "WR": "WR", "HB": "RB", "RB": "RB", "FB": "RB",
    "TE": "TE", "QB": "QB",
    "T": "OL", "G": "OL", "C": "OL",
    "CB": "CB", "S": "S", "LB": "LB",
    "DI": "DL", "ED": "EDGE",
}

# PFF team abbreviation overrides
PFF_TEAM_MAP = {
    "LA": "LAR", "LV": "LV", "OAK": "LV", "SD": "LAC", "STL": "LAR",
    "JAC": "JAX", "HST": "HOU", "CLT": "IND", "BLT": "BAL",
    "ARZ": "ARI",
}


def _normalize_team(team: str | None) -> str | None:
    if not team:
        return None
    team = team.strip().upper()
    team = PFF_TEAM_MAP.get(team, team)
    return standardize_team(team)


def _build_pff_id_map(session: Session) -> dict[str, str]:
    """Build PFF ID → pipeline player_id map from existing Player records."""
    players = session.query(Player).filter(Player.pff_id.isnot(None)).all()
    return {p.pff_id: p.player_id for p in players}


def _build_name_map(session: Session) -> dict[str, str]:
    """Build normalized name → pipeline player_id for fallback matching."""
    name_map: dict[str, str] = {}
    for p in session.query(Player).all():
        norm = standardize_player_name(p.full_name)
        if norm not in name_map:
            name_map[norm] = p.player_id
    return name_map


def _resolve_player(
    session: Session,
    pff_id: str,
    name: str,
    position: str,
    team: str,
    pff_id_map: dict[str, str],
    name_map: dict[str, str],
    now_iso: str,
) -> str | None:
    """Resolve PFF player to pipeline player_id. Creates if not found."""
    # Try PFF ID first
    player_id = pff_id_map.get(pff_id)
    if player_id:
        return player_id

    # Try name match
    norm = standardize_player_name(name)
    player_id = name_map.get(norm)
    if player_id:
        # Store PFF ID for future lookups
        player = session.get(Player, player_id)
        if player and not player.pff_id:
            player.pff_id = pff_id
            pff_id_map[pff_id] = player_id
        return player_id

    # Skip non-skill positions for player creation
    our_pos = PFF_POSITION_MAP.get(position, position)
    if our_pos not in ("QB", "RB", "WR", "TE"):
        return None

    return None


def _set_baseline_fields(baseline: PlayerSeasonBaseline, row: pd.Series, field_map: dict):
    """Set baseline fields from CSV row, only if currently NULL."""
    for csv_col, baseline_field in field_map.items():
        val = row.get(csv_col)
        if val is not None and pd.notna(val):
            if getattr(baseline, baseline_field, None) is None:
                try:
                    setattr(baseline, baseline_field, float(val))
                except (ValueError, TypeError):
                    pass


def ingest_pff_bulk(
    session: Session,
    data_dir: str,
    start_season: int = 2014,
    end_season: int = 2025,
    verbose: bool = True,
) -> dict[str, int]:
    """Bulk ingest PFF CSVs for multiple seasons.

    Processes receiving, rushing, passing, and blocking CSVs.
    """
    data_path = Path(data_dir)
    stats = {"enriched": 0, "created": 0, "unmatched": 0, "files": 0}
    now_iso = datetime.now(timezone.utc).isoformat()

    # Build lookup maps once
    pff_id_map = _build_pff_id_map(session)
    name_map = _build_name_map(session)
    if verbose:
        print(f"Lookup maps: {len(pff_id_map)} PFF IDs, {len(name_map)} names")

    csv_configs = [
        ("receiving_summary", RECEIVING_MAP),
        ("rushing_summary", RUSHING_MAP),
        ("passing_summary", PASSING_MAP),
        ("offense_blocking", BLOCKING_MAP),
    ]

    for season in range(start_season, end_season + 1):
        season_enriched = 0
        for prefix, field_map in csv_configs:
            csv_path = data_path / f"{prefix}_{season}.csv"
            if not csv_path.exists():
                continue

            df = pd.read_csv(csv_path)
            stats["files"] += 1

            for _, row in df.iterrows():
                pff_id = str(row.get("player_id", ""))
                name = str(row.get("player", ""))
                position = str(row.get("position", ""))
                team = _normalize_team(str(row.get("team_name", "")))

                if not pff_id or not name:
                    continue

                player_id = _resolve_player(
                    session, pff_id, name, position, team,
                    pff_id_map, name_map, now_iso,
                )
                if not player_id:
                    stats["unmatched"] += 1
                    continue

                # Get or create baseline
                baseline_id = f"{player_id}_{season}"
                baseline = session.get(PlayerSeasonBaseline, baseline_id)
                if not baseline:
                    baseline = PlayerSeasonBaseline(
                        baseline_id=baseline_id,
                        player_id=player_id,
                        season=season,
                        team=team,
                    )
                    session.add(baseline)
                    stats["created"] += 1

                _set_baseline_fields(baseline, row, field_map)
                season_enriched += 1

            # Also set receiving grade from receiving_summary
            if prefix == "receiving_summary":
                for _, row in df.iterrows():
                    pff_id = str(row.get("player_id", ""))
                    player_id = pff_id_map.get(pff_id)
                    if not player_id:
                        norm = standardize_player_name(str(row.get("player", "")))
                        player_id = name_map.get(norm)
                    if not player_id:
                        continue

                    baseline_id = f"{player_id}_{season}"
                    baseline = session.get(PlayerSeasonBaseline, baseline_id)
                    if baseline:
                        val = row.get("grades_pass_route")
                        if pd.notna(val) and baseline.pff_receiving_grade is None:
                            baseline.pff_receiving_grade = float(val)

        stats["enriched"] += season_enriched
        if verbose:
            print(f"  {season}: {season_enriched} player-records enriched")

        # Commit per season to avoid huge transactions
        session.commit()

    if verbose:
        print(f"\nPFF bulk ingest: {stats['files']} files, "
              f"{stats['enriched']} enriched, {stats['created']} baselines created, "
              f"{stats['unmatched']} unmatched")

    return stats
