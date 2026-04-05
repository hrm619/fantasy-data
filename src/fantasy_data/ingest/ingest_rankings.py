"""Ingest rankings from fantasy_data_pipeline into player_season_baseline.

Wraps RankingsProcessor, maps output columns to the baseline schema,
computes format-neutral sharp consensus using position-first ranking
with ADP scarcity curve conversion, and creates Player records directly.
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.standardize import standardize_team

# Sharp sources used for sharp positional consensus (equal-weighted mean)
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
SHARP_POS_COLUMNS = [
    "fpts_POS RANK", "jj_POS RANK", "hw_POS RANK", "pff_POS RANK",
]

DIVERGENCE_THRESHOLD = 12


def _build_scarcity_curves(df: pd.DataFrame) -> dict[str, callable]:
    """Build ADP scarcity curves — map positional rank to ADP overall.

    For each position, creates an interpolation function that converts
    a (possibly fractional) positional rank to the ADP overall value
    that position typically goes at.

    E.g., if ADP says WR1 goes at pick 1, WR2 at pick 5, WR3 at pick 7,
    then the curve maps 2.5 → interpolated between 5 and 7.
    """
    curves = {}
    for pos in ["QB", "RB", "WR", "TE"]:
        pos_df = df[df["POS"] == pos][["POS ADP", "ADP"]].dropna()
        if len(pos_df) < 2:
            continue
        pos_df = pos_df.sort_values("POS ADP")
        x = pos_df["POS ADP"].values.astype(float)
        y = pos_df["ADP"].values.astype(float)

        def make_interp(x_vals, y_vals):
            def interp(pos_rank):
                return float(np.interp(pos_rank, x_vals, y_vals))
            return interp

        curves[pos] = make_interp(x, y)
    return curves


def compute_sharp_consensus(df: pd.DataFrame) -> pd.DataFrame:
    """Compute format-neutral sharp consensus using position-first ranking.

    Solves the 3WR format bias problem: Hayden Winks ranks in Underdog
    best ball format (3WR), which inflates WR overall ranks by 30-50
    positions. By anchoring on positional ranks (where format doesn't
    matter) and converting back to overall via ADP's scarcity curve,
    the sharp consensus is format-neutral.

    Step 1: Compute sharp_pos_rank per position = mean of 4 sharp source POS RANKs.
    Step 2: Build ADP scarcity curve per position (pos_rank → ADP overall).
    Step 3: Map each player's sharp_pos_rank through the curve → sharp_mapped_overall.
    Step 4: Re-rank the mapped values → sharp_consensus_rank.

    Sharp sources say WHO is best at each position.
    ADP scarcity curve says HOW positions interleave.
    """
    df = df.copy()

    # Step 1: Sharp positional consensus
    available_cols = [c for c in SHARP_POS_COLUMNS if c in df.columns]
    df["sharp_pos_rank"] = df[available_cols].mean(axis=1, skipna=True)
    df["sharp_source_count"] = df[available_cols].notna().sum(axis=1)

    # Step 2: Build ADP scarcity curves
    curves = _build_scarcity_curves(df)

    # Step 3: Map through scarcity curve
    def map_through_curve(row):
        pos = row.get("POS", "")
        spr = row.get("sharp_pos_rank")
        if pos in curves and pd.notna(spr):
            return curves[pos](spr)
        return None

    df["sharp_mapped_overall"] = df.apply(map_through_curve, axis=1)

    # Step 4: Re-rank
    df["sharp_consensus_rank"] = df["sharp_mapped_overall"].rank(method="min")

    # Positional divergence (cleaner signal — fully format-neutral)
    df["adp_divergence_pos"] = df.apply(
        lambda r: r["POS ADP"] - r["sharp_pos_rank"]
        if pd.notna(r.get("POS ADP")) and pd.notna(r.get("sharp_pos_rank"))
        else None,
        axis=1,
    )

    return df


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

    Computes format-neutral sharp consensus using position-first ranking
    with ADP scarcity curve conversion before storing.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    stats = {"created": 0, "existing": 0, "skipped": 0, "updated": 0}

    # Compute sharp consensus on the full DataFrame
    df = compute_sharp_consensus(df)

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

        # Store sharp consensus (position-first + scarcity-mapped)
        if pd.notna(row.get("sharp_pos_rank")):
            baseline.sharp_pos_rank = float(row["sharp_pos_rank"])
        baseline.rankings_source_count = int(row.get("sharp_source_count", 0))

        if pd.notna(row.get("sharp_consensus_rank")):
            baseline.sharp_consensus_rank = float(row["sharp_consensus_rank"])

        # Positional divergence (primary — format-neutral)
        if pd.notna(row.get("adp_divergence_pos")):
            div_pos = float(row["adp_divergence_pos"])
            baseline.adp_divergence_pos = div_pos
            baseline.adp_divergence_flag = 1 if abs(div_pos) >= DIVERGENCE_THRESHOLD else 0
        else:
            baseline.adp_divergence_pos = None
            baseline.adp_divergence_flag = 0

        # Overall divergence (supplemental — for draft ordering)
        adp_overall = row.get("ADP")
        sharp_overall = row.get("sharp_consensus_rank")
        if pd.notna(adp_overall) and pd.notna(sharp_overall):
            baseline.adp_divergence_rank = int(round(adp_overall - sharp_overall))
        else:
            baseline.adp_divergence_rank = None

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
    """Run the full rankings pipeline: process + ingest."""
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
