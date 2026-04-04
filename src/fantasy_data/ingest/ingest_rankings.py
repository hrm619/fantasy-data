"""Ingest rankings from fantasy_data_pipeline into player_season_baseline.

Wraps RankingsProcessor, maps output columns to the baseline schema,
computes sharp_consensus_rank from the 4 sharp sources, and creates
Player records directly (pipeline PLAYER ID is the canonical ID).
"""

from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.standardize import standardize_team

# Sharp sources used for sharp_consensus_rank (equal-weighted mean)
SHARP_SOURCES = ["fpts", "jj", "hw", "pff"]

# Column mapping: pipeline output column -> baseline field
COLUMN_MAP = {
    "avg_RK": "rankings_avg_overall",
    "avg_POS RANK": "rankings_avg_positional",
    "hw_POS RANK": "rankings_hw_positional",
    "pff_POS RANK": "rankings_pff_positional",
    "ds_POS RANK": "rankings_ds_positional",
    "jj_POS RANK": "rankings_jj_positional",
    "fpts_POS RANK": "rankings_fpts_positional",
    "ADP": "adp_consensus",
    "POS ADP": "adp_positional_rank",
    "fp_POS RANK": "fp_positional_rank",
    "ECR ADP Delta": "ecr_adp_delta",
    "ECR Delta": "ecr_avg_rank_delta",
}

# Sharp source positional rank columns in the pipeline output
SHARP_RANK_COLUMNS = {
    "fpts": "fpts_POS RANK",
    "jj": "jj_POS RANK",
    "hw": "hw_POS RANK",
    "pff": "pff_POS RANK",
}

DIVERGENCE_THRESHOLD = 12


def compute_sharp_consensus(row: pd.Series) -> tuple[float | None, int]:
    """Compute sharp consensus rank from available sharp source positional ranks.

    Returns (sharp_consensus_rank, source_count).
    """
    ranks = []
    for source in SHARP_SOURCES:
        col = SHARP_RANK_COLUMNS[source]
        val = row.get(col)
        if pd.notna(val):
            ranks.append(float(val))
    if len(ranks) == 0:
        return None, 0
    return sum(ranks) / len(ranks), len(ranks)


def ingest_rankings(
    session: Session,
    df: pd.DataFrame,
    season: int,
    league_type: str = "redraft",
    verbose: bool = True,
) -> dict[str, int]:
    """Ingest a rankings DataFrame into player_season_baseline.

    Creates Player records directly from the pipeline output — the pipeline's
    PLAYER ID (e.g., McCaCh01) is the canonical player_id.

    Args:
        session: SQLAlchemy session.
        df: DataFrame from RankingsProcessor.process_rankings(return_dataframe=True).
        season: NFL season year.
        league_type: Pipeline league type used.
        verbose: Print progress info.

    Returns:
        Dict with counts: created, existing, skipped, updated.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    stats = {"created": 0, "existing": 0, "skipped": 0, "updated": 0}

    for _, row in df.iterrows():
        player_id = row.get("PLAYER ID")
        player_name = row.get("PLAYER NAME", "")
        position = row.get("POS", "")
        team = row.get("TEAM", "")

        if pd.isna(player_id) or not player_id:
            stats["skipped"] += 1
            continue

        player_id = str(player_id)
        team = standardize_team(str(team)) if pd.notna(team) else None

        # Create or update Player record
        player = session.get(Player, player_id)
        if not player:
            player = Player(
                player_id=player_id,
                full_name=str(player_name),
                position=str(position),
                team=team,
                created_at=now_iso,
            )
            session.add(player)
            stats["created"] += 1
        else:
            # Update team if changed
            if team:
                player.team = team
            player.updated_at = now_iso
            stats["existing"] += 1

        # Get or create baseline record
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

        # Map pipeline columns to baseline fields
        for pipeline_col, baseline_field in COLUMN_MAP.items():
            val = row.get(pipeline_col)
            if pd.notna(val):
                setattr(baseline, baseline_field, val)

        # Compute sharp consensus rank
        sharp_rank, source_count = compute_sharp_consensus(row)
        baseline.rankings_source_count = source_count
        baseline.sharp_consensus_rank = sharp_rank

        # Compute ADP divergence
        adp_pos_rank = baseline.adp_positional_rank
        if sharp_rank is not None and adp_pos_rank is not None:
            divergence = int(round(adp_pos_rank - sharp_rank))
            baseline.adp_divergence_rank = divergence
            baseline.adp_divergence_flag = 1 if abs(divergence) >= DIVERGENCE_THRESHOLD else 0
        else:
            baseline.adp_divergence_rank = None
            baseline.adp_divergence_flag = 0

        baseline.rankings_last_updated = now_iso
        stats["updated"] += 1

    session.commit()

    if verbose:
        print(f"Rankings ingest: {stats['created']} players created, "
              f"{stats['existing']} existing, {stats['skipped']} skipped, "
              f"{stats['updated']} baselines updated")

    return stats


def run_rankings_pipeline(
    session: Session,
    season: int,
    league_type: str = "redraft",
    data_path: str | None = None,
    verbose: bool = True,
) -> dict[str, int]:
    """Run the full rankings pipeline: process + ingest.

    Convenience wrapper that calls RankingsProcessor and then ingest_rankings.
    """
    from fantasy_pipeline import RankingsProcessor

    if verbose:
        print(f"Running rankings pipeline: {league_type} season {season}")

    proc = RankingsProcessor(league_type)
    kwargs = {"return_dataframe": True, "verbose": verbose}
    if data_path:
        kwargs["data_path"] = data_path

    df = proc.process_rankings(**kwargs)

    if not isinstance(df, pd.DataFrame):
        raise RuntimeError(
            f"Expected DataFrame from process_rankings, got {type(df)}. "
            "Ensure fantasy-pipeline is up to date."
        )

    return ingest_rankings(session, df, season, league_type, verbose)
