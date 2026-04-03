"""Ingest Next Gen Stats data into player_season_baseline.

Phase 1 stub — defines the interface and column mapping.
Actual NGS data ingestion will be implemented when NGS CSV/API access is available.
"""

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import PlayerSeasonBaseline

# Mapping: NGS CSV column -> PlayerSeasonBaseline model field
NGS_FIELD_MAP = {
    "avg_cushion": "avg_cushion",
    "avg_separation": "avg_separation",
    "avg_intended_air_yards": "avg_depth_of_target",
    "catch_percentage": "catch_rate",
    "expected_catch_percentage": "expected_catch_rate",
    "catch_percentage_above_expectation": "catch_rate_over_expected",
    "avg_yac": "yards_after_catch_per_rec",
    "avg_expected_yards": "expected_yards_per_carry",
    "rush_yards_over_expected_per_att": "rush_yards_over_expected",
}


def ingest_ngs(
    session: Session,
    df: pd.DataFrame,
    season: int,
    verbose: bool = True,
) -> dict[str, int]:
    """Ingest NGS data into player_season_baseline.

    Requires that players and baseline records already exist (via PFF ingest).
    Matches on player_id (must be PFF ID in the DataFrame).
    """
    stats = {"updated": 0, "skipped": 0}

    for _, row in df.iterrows():
        player_id = str(row.get("player_id", ""))
        baseline_id = f"{player_id}_{season}"
        baseline = session.get(PlayerSeasonBaseline, baseline_id)

        if not baseline:
            stats["skipped"] += 1
            continue

        for csv_col, model_field in NGS_FIELD_MAP.items():
            val = row.get(csv_col)
            if val is not None and pd.notna(val):
                setattr(baseline, model_field, val)

        stats["updated"] += 1

    session.commit()

    if verbose:
        print(f"NGS ingest: {stats['updated']} updated, {stats['skipped']} skipped")

    return stats
