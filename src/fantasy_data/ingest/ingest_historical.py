"""Ingest historical box score stats from the fantasy_data_pipeline's combined_data.csv.

This is the fast path for populating PlayerSeasonBaseline records with basic
stats and fantasy scoring for 2014-2024. Uses pipeline PLAYER IDs directly
(no ID resolution needed).

Expected CSV columns:
    PLAYER NAME, PLAYER_ID (alias ID), POS, TEAM, SEASON,
    G, GS, PASS CMP, PASS ATT, PASS YDS, PASS TD, PASS INT,
    RUSH ATT, RUSH YDS, RUSH Y/A, RUSH TD,
    REC TGT, REC REC, REC YDS, REC Y/R, REC TD,
    FMB, FL, TOT TD, FANTPT, PPR, DKPT, FDPT, VBD, POS RANK
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.standardize import standardize_team

DEFAULT_HISTORICAL_PATH = (
    Path(__file__).resolve().parents[4]
    / "fantasy_data_pipeline"
    / "data"
    / "fpts historical"
    / "combined_data.csv"
)

# Column mapping: CSV column -> baseline field
COLUMN_MAP = {
    "G": "games_played",
    "GS": "games_started",
    "FANTPT": "fantasy_pts_std",
    "PPR": "fantasy_pts_ppr",
}


def _compute_derived_fields(row: pd.Series) -> dict[str, float | None]:
    """Compute derived baseline fields from raw box score stats."""
    fields: dict[str, float | None] = {}
    games = row.get("G")
    if not games or pd.isna(games) or games == 0:
        return fields

    g = float(games)

    # Fantasy points per game
    ppr = row.get("PPR")
    std = row.get("FANTPT")
    if pd.notna(ppr):
        fields["fpts_per_game_ppr"] = float(ppr) / g
    if pd.notna(std):
        fields["fpts_per_game_std"] = float(std) / g

    # Half-PPR: standard + 0.5 * receptions
    rec = row.get("REC REC")
    if pd.notna(std) and pd.notna(rec):
        fields["fantasy_pts_half"] = float(std) + 0.5 * float(rec)

    # Rushing
    rush_att = row.get("RUSH ATT")
    rush_yds = row.get("RUSH YDS")
    if pd.notna(rush_att) and g > 0:
        fields["carries_per_game"] = float(rush_att) / g
    if pd.notna(rush_att) and pd.notna(rush_yds) and float(rush_att) > 0:
        fields["yards_per_carry"] = float(rush_yds) / float(rush_att)

    # Receiving
    tgt = row.get("REC TGT")
    if pd.notna(tgt) and pd.notna(rec) and float(tgt) > 0:
        fields["catch_rate"] = float(rec) / float(tgt)

    # Total touches per game
    if pd.notna(rush_att) and pd.notna(rec):
        fields["total_touches_per_game"] = (float(rush_att) + float(rec)) / g

    # TD rate (total TDs / total touches)
    tot_td = row.get("TOT TD")
    if pd.notna(tot_td) and pd.notna(rush_att) and pd.notna(rec):
        total_touches = float(rush_att) + float(rec)
        if total_touches > 0:
            fields["td_rate"] = float(tot_td) / total_touches

    return fields


def ingest_historical(
    session: Session,
    df: pd.DataFrame,
    seasons: list[int] | None = None,
    verbose: bool = True,
) -> dict[str, int]:
    """Ingest historical box score data into player_season_baseline.

    Creates Player records for historical players (is_active=0) and
    populates baseline fields. Does NOT overwrite fields that already
    have values (e.g., from rankings ingest).

    Args:
        session: SQLAlchemy session.
        df: DataFrame from combined_data.csv.
        seasons: Optional filter to specific seasons.
        verbose: Print progress.

    Returns:
        Dict with counts: players_created, baselines_created, baselines_updated, skipped.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    stats = {"players_created": 0, "baselines_created": 0, "baselines_updated": 0, "skipped": 0}

    # Normalize column: CSV has 'ID' for player_id
    if "ID" in df.columns and "PLAYER_ID" not in df.columns:
        df = df.rename(columns={"ID": "PLAYER_ID"})

    if seasons:
        df = df[df["SEASON"].isin(seasons)]

    for _, row in df.iterrows():
        player_id = row.get("PLAYER_ID")
        if not player_id or pd.isna(player_id):
            stats["skipped"] += 1
            continue

        player_id = str(player_id).strip()
        season = int(row["SEASON"])
        name = str(row.get("PLAYER NAME", "")).strip()
        position = str(row.get("POS", "")).strip() or None
        team = standardize_team(str(row.get("TEAM", "")).strip() or None)

        # Ensure player exists
        player = session.get(Player, player_id)
        if not player:
            player = Player(
                player_id=player_id,
                full_name=name,
                position=position or "UNK",
                team=team,
                is_active=0,
                created_at=now_iso,
                updated_at=now_iso,
            )
            session.add(player)
            stats["players_created"] += 1

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
            stats["baselines_created"] += 1
        else:
            stats["baselines_updated"] += 1

        # Map direct columns (only if field is currently NULL)
        for csv_col, field in COLUMN_MAP.items():
            val = row.get(csv_col)
            if pd.notna(val) and getattr(baseline, field, None) is None:
                setattr(baseline, field, val)

        # Compute and set derived fields (only if NULL)
        derived = _compute_derived_fields(row)
        for field, val in derived.items():
            if val is not None and getattr(baseline, field, None) is None:
                setattr(baseline, field, val)

    session.commit()

    if verbose:
        total = stats["baselines_created"] + stats["baselines_updated"]
        print(f"Historical ingest: {stats['players_created']} players created, "
              f"{total} baselines ({stats['baselines_created']} new, "
              f"{stats['baselines_updated']} updated), {stats['skipped']} skipped")

    return stats


def run_historical_ingest(
    session: Session,
    file_path: str | None = None,
    seasons: list[int] | None = None,
    verbose: bool = True,
) -> dict[str, int]:
    """Load combined_data.csv and run historical ingest."""
    path = Path(file_path) if file_path else DEFAULT_HISTORICAL_PATH
    if verbose:
        print(f"Loading historical data from {path}")
    df = pd.read_csv(path)
    return ingest_historical(session, df, seasons=seasons, verbose=verbose)
