"""Ingest PFF CSV exports into players and player_season_baseline tables.

PFF data serves as the canonical identity layer (PFF player_id is the primary key)
and provides grade fields for the baseline table.
"""

from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player, PlayerSeasonBaseline

# Mapping: PFF CSV column -> Player model field
PLAYER_FIELD_MAP = {
    "player_id": "player_id",
    "player": "full_name",
    "position": "position",
    "team_abbr": "team",
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

# Mapping: PFF CSV column -> PlayerSeasonBaseline model field
BASELINE_GRADE_MAP = {
    "receiving_grade": "pff_receiving_grade",
    "run_block_grade": "pff_run_blocking_grade",
    "route_grade": "route_grade_pff",
    "rushing_grade": "pff_rush_grade",
    "target_quality_rating": "target_quality_rating",
    "snap_counts_offense": "snap_share",  # raw count — compute share downstream
    "games": "games_played",
    "games_started": "games_started",
    "targets_per_route_run": "yards_per_route_run",  # PFF sometimes labels differently
    "drop_rate": "drop_rate",
    "contested_catch_rate": "contested_target_rate",
}

POSITION_GROUP_MAP = {
    "QB": "QB",
    "RB": "BACKFIELD",
    "FB": "BACKFIELD",
    "WR": "PASS_CATCHER",
    "TE": "PASS_CATCHER",
    "K": "K",
}


def ingest_pff_players(
    session: Session,
    df: pd.DataFrame,
    season: int,
    verbose: bool = True,
) -> dict[str, int]:
    """Ingest PFF player data into the players table.

    This seeds the canonical identity layer. Must run before rankings ingest.

    Args:
        session: SQLAlchemy session.
        df: DataFrame from PFF CSV export.
        season: NFL season year.
        verbose: Print progress info.

    Returns:
        Dict with counts: created, updated.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    stats = {"created": 0, "updated": 0}

    for _, row in df.iterrows():
        pff_id = str(row.get("player_id", ""))
        if not pff_id:
            continue

        player = session.get(Player, pff_id)
        is_new = player is None

        if is_new:
            player = Player(player_id=pff_id, full_name="", position="")
            session.add(player)

        for csv_col, model_field in PLAYER_FIELD_MAP.items():
            val = row.get(csv_col)
            if val is not None and pd.notna(val):
                setattr(player, model_field, val)

        pos = str(row.get("position", ""))
        player.position_group = POSITION_GROUP_MAP.get(pos)
        player.updated_at = now_iso

        if is_new:
            player.created_at = now_iso
            stats["created"] += 1
        else:
            stats["updated"] += 1

    session.commit()

    if verbose:
        print(f"PFF players ingest: {stats['created']} created, "
              f"{stats['updated']} updated")

    return stats


def ingest_pff_grades(
    session: Session,
    df: pd.DataFrame,
    season: int,
    verbose: bool = True,
) -> dict[str, int]:
    """Ingest PFF grade data into player_season_baseline.

    Args:
        session: SQLAlchemy session.
        df: DataFrame from PFF CSV export with grade columns.
        season: NFL season year.
        verbose: Print progress info.

    Returns:
        Dict with counts: created, updated.
    """
    stats = {"created": 0, "updated": 0}

    for _, row in df.iterrows():
        pff_id = str(row.get("player_id", ""))
        if not pff_id:
            continue

        baseline_id = f"{pff_id}_{season}"
        baseline = session.get(PlayerSeasonBaseline, baseline_id)

        if not baseline:
            team = row.get("team_abbr")
            baseline = PlayerSeasonBaseline(
                baseline_id=baseline_id,
                player_id=pff_id,
                season=season,
                team=str(team) if pd.notna(team) else None,
            )
            session.add(baseline)
            stats["created"] += 1
        else:
            stats["updated"] += 1

        for csv_col, model_field in BASELINE_GRADE_MAP.items():
            val = row.get(csv_col)
            if val is not None and pd.notna(val):
                setattr(baseline, model_field, val)

    session.commit()

    if verbose:
        print(f"PFF grades ingest: {stats['created']} created, "
              f"{stats['updated']} updated")

    return stats
