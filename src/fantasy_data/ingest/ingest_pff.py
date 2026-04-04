"""Ingest PFF CSV exports as supplemental enrichment.

PFF data enriches existing Player records (created by rankings ingest) with
grade fields and biographical data. Matches on player name since PFF uses
its own ID system.
"""

from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.standardize import standardize_player_name, standardize_team

# Mapping: PFF CSV column -> PlayerSeasonBaseline model field
BASELINE_GRADE_MAP = {
    "receiving_grade": "pff_receiving_grade",
    "run_block_grade": "pff_run_blocking_grade",
    "route_grade": "route_grade_pff",
    "rushing_grade": "pff_rush_grade",
    "target_quality_rating": "target_quality_rating",
    "games": "games_played",
    "games_started": "games_started",
    "drop_rate": "drop_rate",
    "contested_catch_rate": "contested_target_rate",
}

# Mapping: PFF CSV column -> Player model field (biographical enrichment)
PLAYER_ENRICH_MAP = {
    "jersey_number": "jersey_number",
    "age": "age",
    "years_exp": "years_pro",
    "draft_year": "draft_year",
    "draft_round": "draft_round",
    "draft_pick": "draft_pick",
    "college": "college",
    "height": "height_inches",
    "weight": "weight_lbs",
}

POSITION_GROUP_MAP = {
    "QB": "QB",
    "RB": "BACKFIELD",
    "FB": "BACKFIELD",
    "WR": "PASS_CATCHER",
    "TE": "PASS_CATCHER",
    "K": "K",
}


def _match_player_by_name(session: Session, pff_name: str) -> Player | None:
    """Find an existing Player record by name matching."""
    # Exact match first
    player = session.query(Player).filter(Player.full_name == pff_name).first()
    if player:
        return player

    # Normalized match
    normalized = standardize_player_name(pff_name)
    all_players = session.query(Player).filter(Player.is_active == 1).all()
    for p in all_players:
        if standardize_player_name(p.full_name) == normalized:
            return p

    return None


def ingest_pff(
    session: Session,
    df: pd.DataFrame,
    season: int,
    verbose: bool = True,
) -> dict[str, int]:
    """Ingest PFF data as supplemental enrichment of existing players.

    Matches PFF rows to existing Player records by name. Stores PFF player ID
    as a secondary identifier. Populates grade fields in player_season_baseline.

    Players must already exist in the DB (created by rankings ingest).

    Args:
        session: SQLAlchemy session.
        df: DataFrame from PFF CSV export.
        season: NFL season year.
        verbose: Print progress info.

    Returns:
        Dict with counts: enriched, unmatched.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    stats = {"enriched": 0, "unmatched": 0}

    for _, row in df.iterrows():
        pff_id = str(row.get("player_id", ""))
        pff_name = str(row.get("player", ""))

        if not pff_id or not pff_name:
            continue

        player = _match_player_by_name(session, pff_name)

        if not player:
            stats["unmatched"] += 1
            if verbose:
                print(f"  PFF unmatched: {pff_name} ({pff_id})")
            continue

        # Store PFF ID as secondary identifier
        player.pff_id = pff_id

        # Enrich biographical fields
        for csv_col, model_field in PLAYER_ENRICH_MAP.items():
            val = row.get(csv_col)
            if val is not None and pd.notna(val):
                setattr(player, model_field, val)

        pos = str(row.get("position", ""))
        if pos:
            player.position_group = POSITION_GROUP_MAP.get(pos)

        player.updated_at = now_iso

        # Enrich baseline with grade fields
        baseline_id = f"{player.player_id}_{season}"
        baseline = session.get(PlayerSeasonBaseline, baseline_id)
        if not baseline:
            team = standardize_team(str(row.get("team_abbr", "")))
            baseline = PlayerSeasonBaseline(
                baseline_id=baseline_id,
                player_id=player.player_id,
                season=season,
                team=team,
            )
            session.add(baseline)

        for csv_col, model_field in BASELINE_GRADE_MAP.items():
            val = row.get(csv_col)
            if val is not None and pd.notna(val):
                setattr(baseline, model_field, val)

        stats["enriched"] += 1

    session.commit()

    if verbose:
        print(f"PFF ingest: {stats['enriched']} players enriched, "
              f"{stats['unmatched']} unmatched")

    return stats
