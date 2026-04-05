"""Ingest advanced metrics from nflverse via nfl_data_py.

Populates PlayerSeasonBaseline fields that the pipeline's combined_data.csv
doesn't cover: target_share, snap_share, air_yards_share, RZ/EZ shares,
down splits, boom/bust rates, consistency scores, and composites.

Uses three nflverse data sources:
- seasonal_data: target_share, air_yards_share, racr, receiving_air_yards
- weekly_data: boom/bust rates, consistency scores (game-level aggregation)
- snap_counts: snap_share (weekly offense_pct averaged to season)
- pbp_data: RZ/EZ target shares, down splits, goal-line carries, aDOT

Player ID resolution: nflverse gsis_id → pipeline PLAYER ID via pfr_id
from nfl_data_py.import_ids().
"""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.standardize import standardize_team
from fantasy_data.ingest.id_resolver import (
    build_id_map_from_nflverse,
    ensure_player_exists,
)

# Boom/bust thresholds (PPR points)
BOOM_THRESHOLD = 20.0
BUST_THRESHOLD = 5.0

# Minimum games to compute per-game and rate stats
MIN_GAMES = 4


# ---------------------------------------------------------------------------
# Fetching (thin wrappers)
# ---------------------------------------------------------------------------

def _fetch_seasonal(seasons: list[int]) -> pd.DataFrame:
    import nfl_data_py as nfl
    return nfl.import_seasonal_data(seasons, "REG")


def _fetch_weekly(seasons: list[int]) -> pd.DataFrame:
    import nfl_data_py as nfl
    return nfl.import_weekly_data(seasons)


def _fetch_snap_counts(seasons: list[int]) -> pd.DataFrame:
    import nfl_data_py as nfl
    return nfl.import_snap_counts(seasons)


def _fetch_pbp(seasons: list[int]) -> pd.DataFrame:
    import nfl_data_py as nfl
    return nfl.import_pbp_data(seasons)


def _fetch_ids() -> pd.DataFrame:
    import nfl_data_py as nfl
    return nfl.import_ids()


def _fetch_ngs_receiving(seasons: list[int]) -> pd.DataFrame:
    import nfl_data_py as nfl
    valid = [s for s in seasons if s >= 2016]
    if not valid:
        return pd.DataFrame()
    return nfl.import_ngs_data("receiving", valid)


def _fetch_ngs_rushing(seasons: list[int]) -> pd.DataFrame:
    import nfl_data_py as nfl
    valid = [s for s in seasons if s >= 2016]
    if not valid:
        return pd.DataFrame()
    return nfl.import_ngs_data("rushing", valid)


def aggregate_ngs_receiving(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weekly NGS receiving data to season-level.

    Input: nfl_data_py.import_ngs_data('receiving') output (weekly rows).
    Output: One row per (player_gsis_id, season) with season averages.
    """
    if df.empty:
        return pd.DataFrame()

    # Filter to regular season, full-season summary (week 0) if available
    if "week" in df.columns:
        # Week 0 = full season summary in NGS data
        season_rows = df[df["week"] == 0]
        if season_rows.empty:
            # Fall back to averaging weekly data
            season_rows = df[df["season_type"] == "REG"] if "season_type" in df.columns else df

    if season_rows.empty:
        return pd.DataFrame()

    # If using week-0 summaries, they're already season-level
    if season_rows["week"].iloc[0] == 0:
        out = season_rows[["player_gsis_id", "season"]].copy()
        out["avg_cushion"] = season_rows["avg_cushion"]
        out["avg_separation"] = season_rows["avg_separation"]
        out["avg_intended_air_yards_ngs"] = season_rows["avg_intended_air_yards"]
        out["avg_yac_above_expectation"] = season_rows.get("avg_yac_above_expectation")
        out["avg_expected_yac"] = season_rows.get("avg_expected_yac")
        return out

    # Otherwise aggregate weekly to season
    grouped = season_rows.groupby(["player_gsis_id", "season"]).agg(
        avg_cushion=("avg_cushion", "mean"),
        avg_separation=("avg_separation", "mean"),
        avg_intended_air_yards_ngs=("avg_intended_air_yards", "mean"),
        avg_yac_above_expectation=("avg_yac_above_expectation", "mean"),
        avg_expected_yac=("avg_expected_yac", "mean"),
    ).reset_index()
    return grouped


def aggregate_ngs_rushing(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate weekly NGS rushing data to season-level."""
    if df.empty:
        return pd.DataFrame()

    if "week" in df.columns:
        season_rows = df[df["week"] == 0]
        if season_rows.empty:
            season_rows = df[df["season_type"] == "REG"] if "season_type" in df.columns else df

    if season_rows.empty:
        return pd.DataFrame()

    if season_rows["week"].iloc[0] == 0:
        out = season_rows[["player_gsis_id", "season"]].copy()
        out["expected_yards_per_carry"] = season_rows.get("efficiency")  # expected YPC
        out["rush_yards_over_expected"] = season_rows.get("rush_yards_over_expected_per_att")
        return out

    grouped = season_rows.groupby(["player_gsis_id", "season"]).agg(
        expected_yards_per_carry=("efficiency", "mean"),
        rush_yards_over_expected=("rush_yards_over_expected_per_att", "mean"),
    ).reset_index()
    return grouped


def _fetch_ftn(seasons: list[int]) -> pd.DataFrame:
    import nfl_data_py as nfl
    valid = [s for s in seasons if s >= 2022]
    if not valid:
        return pd.DataFrame()
    return nfl.import_ftn_data(valid)


def aggregate_ftn(ftn_df: pd.DataFrame, pbp_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate FTN charting data to player-season metrics.

    Joins FTN play-level flags with PBP to get receiver/rusher IDs,
    then computes per-player rates for scheme context and efficiency.

    Returns one row per (player_id, season) with:
    - play_action_target_pct: % of targets on play-action passes
    - screen_target_pct: % of targets on screen passes
    - true_drop_rate: FTN-charted drops / catchable balls targeted
    - contested_ball_pct: % of targets that were contested
    - catchable_ball_pct: % of targets that were catchable
    - created_reception_pct: % of receptions that were WR-created
    """
    if ftn_df.empty or pbp_df.empty:
        return pd.DataFrame()

    # Join FTN flags to PBP for receiver/rusher IDs
    merged = ftn_df.merge(
        pbp_df[["game_id", "play_id", "receiver_player_id", "play_type", "season"]],
        left_on=["nflverse_game_id", "nflverse_play_id"],
        right_on=["game_id", "play_id"],
        how="inner",
        suffixes=("_ftn", ""),
    )

    # Filter to pass plays with a receiver
    passes = merged[
        (merged["play_type"] == "pass") & merged["receiver_player_id"].notna()
    ].copy()

    if passes.empty:
        return pd.DataFrame()

    # Use PBP season (more reliable)
    season_col = "season" if "season" in passes.columns else "season_ftn"

    grouped = passes.groupby(["receiver_player_id", season_col])
    results = []

    for (pid, season), group in grouped:
        n_targets = len(group)
        if n_targets < 10:
            continue

        row = {"player_id": pid, "season": int(season)}

        row["play_action_target_pct"] = group["is_play_action"].mean()
        row["screen_target_pct"] = group["is_screen_pass"].mean()
        row["contested_ball_pct"] = group["is_contested_ball"].mean()
        row["catchable_ball_pct"] = group["is_catchable_ball"].mean()
        row["created_reception_pct"] = group["is_created_reception"].mean()

        # True drop rate = drops / catchable balls
        catchable = group[group["is_catchable_ball"] == True]
        if len(catchable) > 0:
            row["true_drop_rate"] = catchable["is_drop"].mean()
        else:
            row["true_drop_rate"] = None

        results.append(row)

    return pd.DataFrame(results) if results else pd.DataFrame()


def _fetch_pfr_receiving(seasons: list[int]) -> pd.DataFrame:
    import nfl_data_py as nfl
    valid = [s for s in seasons if s >= 2018]
    if not valid:
        return pd.DataFrame()
    return nfl.import_seasonal_pfr("rec", valid)


def _fetch_pfr_rushing(seasons: list[int]) -> pd.DataFrame:
    import nfl_data_py as nfl
    valid = [s for s in seasons if s >= 2018]
    if not valid:
        return pd.DataFrame()
    return nfl.import_seasonal_pfr("rush", valid)


# ---------------------------------------------------------------------------
# Aggregation (pure functions, DataFrame in/out)
# ---------------------------------------------------------------------------

def aggregate_seasonal(df: pd.DataFrame) -> pd.DataFrame:
    """Extract fields from nflverse seasonal aggregates.

    Input: nfl_data_py.import_seasonal_data() output.
    Output: One row per (player_id, season) with baseline-ready fields.
    """
    out = df[["player_id", "season"]].copy()
    out["target_share"] = df.get("target_share")
    out["air_yards_share"] = df.get("air_yards_share")
    out["racr"] = df.get("racr")
    out["dominator_rating"] = df.get("dom")

    # YAC per reception
    yac = df.get("receiving_yards_after_catch")
    rec = df.get("receptions")
    if yac is not None and rec is not None:
        out["yards_after_catch_per_rec"] = np.where(rec > 0, yac / rec, None)

    # aDOT from receiving air yards / targets
    air = df.get("receiving_air_yards")
    tgt = df.get("targets")
    if air is not None and tgt is not None:
        out["avg_depth_of_target"] = np.where(tgt > 0, air / tgt, None)

    return out


def aggregate_weekly(df: pd.DataFrame) -> pd.DataFrame:
    """Compute boom/bust rates and consistency from weekly game logs.

    Input: nfl_data_py.import_weekly_data() output.
    Output: One row per (player_id, season).
    """
    # Filter to regular season
    if "season_type" in df.columns:
        df = df[df["season_type"] == "REG"]

    grouped = df.groupby(["player_id", "season"])

    results = []
    for (pid, season), group in grouped:
        games = len(group)
        if games < MIN_GAMES:
            continue

        fpts = group["fantasy_points_ppr"].dropna()
        if len(fpts) < MIN_GAMES:
            continue

        mean_pts = fpts.mean()
        std_pts = fpts.std()
        boom_rate = (fpts >= BOOM_THRESHOLD).mean()
        bust_rate = (fpts < BUST_THRESHOLD).mean()
        consistency = 1 - (std_pts / mean_pts) if mean_pts > 0 else None

        results.append({
            "player_id": pid,
            "season": season,
            "boom_rate": boom_rate,
            "bust_rate": bust_rate,
            "consistency_score": consistency,
        })

    return pd.DataFrame(results) if results else pd.DataFrame(
        columns=["player_id", "season", "boom_rate", "bust_rate", "consistency_score"]
    )


def aggregate_snaps(df: pd.DataFrame) -> pd.DataFrame:
    """Average weekly snap share to season-level.

    Input: nfl_data_py.import_snap_counts() output.
    Output: One row per (player, team, season) with mean snap_share.
    """
    # Filter to regular season if game_type available
    if "game_type" in df.columns:
        df = df[df["game_type"] == "REG"]

    # offense_pct is 0-100 in some versions, 0-1 in others
    snap_col = "offense_pct"
    if snap_col not in df.columns:
        return pd.DataFrame(columns=["player", "team", "season", "snap_share", "pfr_player_id"])

    grouped = df.groupby(["pfr_player_id", "season"]).agg(
        snap_share=(snap_col, "mean"),
        player=("player", "first"),
        team=("team", "first"),
    ).reset_index()

    # Normalize to 0-1 if values are percentages
    if grouped["snap_share"].max() > 1.0:
        grouped["snap_share"] = grouped["snap_share"] / 100.0

    return grouped


def aggregate_pbp(df: pd.DataFrame, seasons: list[int]) -> pd.DataFrame:
    """Aggregate play-by-play for RZ/EZ shares, down splits, goal-line carries.

    This is the most expensive aggregation — processes raw plays.
    """
    # Filter to regular season, real plays
    df = df[
        (df["season_type"] == "REG")
        & (df["play_type"].isin(["pass", "run"]))
    ].copy()

    results = []
    for season in seasons:
        season_df = df[df["season"] == season]
        if season_df.empty:
            continue

        # Build team-level denominators
        team_stats = _compute_team_denominators(season_df)

        # Receiver stats
        rec_stats = _aggregate_receiver_pbp(season_df, team_stats)
        # Rusher stats
        rush_stats = _aggregate_rusher_pbp(season_df, team_stats)

        # Merge receiver and rusher stats
        if not rec_stats.empty and not rush_stats.empty:
            merged = pd.merge(rec_stats, rush_stats, on=["player_id", "season"], how="outer")
        elif not rec_stats.empty:
            merged = rec_stats
        elif not rush_stats.empty:
            merged = rush_stats
        else:
            continue

        results.append(merged)

    if not results:
        return pd.DataFrame()
    return pd.concat(results, ignore_index=True)


def _compute_team_denominators(df: pd.DataFrame) -> dict:
    """Compute team-level totals for share calculations."""
    teams = {}
    for team in df["posteam"].dropna().unique():
        team_df = df[df["posteam"] == team]
        pass_plays = team_df[team_df["play_type"] == "pass"]
        run_plays = team_df[team_df["play_type"] == "run"]
        rz = team_df[team_df["yardline_100"] <= 20]
        ez = team_df[team_df["yardline_100"] <= 10]
        gl = team_df[team_df["yardline_100"] <= 5]

        teams[team] = {
            "total_targets": len(pass_plays),
            "total_carries": len(run_plays),
            "rz_targets": len(rz[rz["play_type"] == "pass"]),
            "rz_carries": len(rz[rz["play_type"] == "run"]),
            "ez_targets": len(ez[ez["play_type"] == "pass"]),
            "gl_carries": len(gl[gl["play_type"] == "run"]),
            "early_down_carries": len(run_plays[run_plays["down"].isin([1, 2])]),
            "third_down_carries": len(run_plays[run_plays["down"] == 3]),
            "third_down_targets": len(pass_plays[pass_plays["down"] == 3]),
        }
    return teams


def _aggregate_receiver_pbp(df: pd.DataFrame, team_stats: dict) -> pd.DataFrame:
    """Aggregate receiver-level PBP stats."""
    pass_plays = df[df["play_type"] == "pass"].copy()
    if pass_plays.empty:
        return pd.DataFrame()

    # Group targets by receiver
    receiver_groups = pass_plays.groupby(["receiver_player_id", "posteam", "season"])
    results = []

    for (pid, team, season), group in receiver_groups:
        if not pid or pd.isna(pid):
            continue

        ts = team_stats.get(team, {})
        row = {"player_id": pid, "season": int(season)}

        # RZ target share
        rz_tgts = len(group[group["yardline_100"] <= 20])
        team_rz_tgts = ts.get("rz_targets", 0)
        if team_rz_tgts > 0:
            row["rz_target_share"] = rz_tgts / team_rz_tgts

        # EZ target share
        ez_tgts = len(group[group["yardline_100"] <= 10])
        team_ez_tgts = ts.get("ez_targets", 0)
        if team_ez_tgts > 0:
            row["ez_target_share"] = ez_tgts / team_ez_tgts

        # 3rd down target share
        td_tgts = len(group[group["down"] == 3])
        team_3d_tgts = ts.get("third_down_targets", 0)
        if team_3d_tgts > 0:
            row["third_down_target_share"] = td_tgts / team_3d_tgts

        results.append(row)

    return pd.DataFrame(results) if results else pd.DataFrame()


def _aggregate_rusher_pbp(df: pd.DataFrame, team_stats: dict) -> pd.DataFrame:
    """Aggregate rusher-level PBP stats."""
    run_plays = df[df["play_type"] == "run"].copy()
    if run_plays.empty:
        return pd.DataFrame()

    rusher_groups = run_plays.groupby(["rusher_player_id", "posteam", "season"])
    results = []

    for (pid, team, season), group in rusher_groups:
        if not pid or pd.isna(pid):
            continue

        ts = team_stats.get(team, {})
        row = {"player_id": pid, "season": int(season)}

        # RZ carry share
        rz_carries = len(group[group["yardline_100"] <= 20])
        team_rz = ts.get("rz_carries", 0)
        if team_rz > 0:
            row["rz_carry_share"] = rz_carries / team_rz

        # Goal-line carry share
        gl_carries = len(group[group["yardline_100"] <= 5])
        team_gl = ts.get("gl_carries", 0)
        if team_gl > 0:
            row["goal_line_carry_share"] = gl_carries / team_gl

        # Early-down share
        ed_carries = len(group[group["down"].isin([1, 2])])
        team_ed = ts.get("early_down_carries", 0)
        if team_ed > 0:
            row["early_down_share"] = ed_carries / team_ed

        # 3rd-down carry share
        td_carries = len(group[group["down"] == 3])
        team_3d = ts.get("third_down_carries", 0)
        if team_3d > 0:
            row["third_down_carry_share"] = td_carries / team_3d

        results.append(row)

    return pd.DataFrame(results) if results else pd.DataFrame()


# ---------------------------------------------------------------------------
# Ingest (writes to DB)
# ---------------------------------------------------------------------------

def ingest_nflverse(
    session: Session,
    seasons: list[int],
    skip_pbp: bool = False,
    verbose: bool = True,
) -> dict[str, int]:
    """Orchestrate full nflverse ingest for given seasons.

    Args:
        session: SQLAlchemy session.
        seasons: List of seasons to process.
        skip_pbp: Skip play-by-play aggregation (faster, fewer fields).
        verbose: Print progress.

    Returns:
        Stats dict with counts.
    """
    stats = {"players_created": 0, "baselines_updated": 0, "unmatched": 0}
    now_iso = datetime.now(timezone.utc).isoformat()

    # Step 1: Build ID mapping
    if verbose:
        print("Fetching nflverse IDs table...")
    ids_df = _fetch_ids()
    id_map = build_id_map_from_nflverse(ids_df)
    if verbose:
        print(f"  ID map: {len(id_map)} gsis_id -> player_id mappings")

    # Also build name lookup from IDs table for snap counts (which use pfr_player_id)
    ids_name_map = {}
    for _, row in ids_df.iterrows():
        pfr_id = row.get("pfr_id")
        name = row.get("name")
        pos = row.get("position")
        team = row.get("team")
        if pfr_id and pd.notna(pfr_id):
            ids_name_map[str(pfr_id)] = {
                "name": str(name) if pd.notna(name) else "Unknown",
                "position": str(pos) if pd.notna(pos) else None,
                "team": str(team) if pd.notna(team) else None,
            }

    # Step 2: Fetch and aggregate seasonal data
    if verbose:
        print(f"Fetching seasonal data for {seasons[0]}-{seasons[-1]}...")
    seasonal_df = _fetch_seasonal(seasons)
    seasonal_agg = aggregate_seasonal(seasonal_df)

    # Step 3: Fetch and aggregate weekly data (boom/bust)
    if verbose:
        print("Fetching weekly data for boom/bust rates...")
    weekly_df = _fetch_weekly(seasons)
    weekly_agg = aggregate_weekly(weekly_df)

    # Step 4: Fetch and aggregate snap counts
    if verbose:
        print("Fetching snap counts...")
    try:
        snap_df = _fetch_snap_counts(seasons)
        snap_agg = aggregate_snaps(snap_df)
    except Exception as e:
        if verbose:
            print(f"  Snap counts unavailable: {e}")
        snap_agg = pd.DataFrame()

    # Step 5: Fetch NGS tracking data (2016+ only)
    ngs_seasons = [s for s in seasons if s >= 2016]
    ngs_rec = pd.DataFrame()
    ngs_rush = pd.DataFrame()
    if ngs_seasons:
        if verbose:
            print("Fetching NGS tracking data (receiving + rushing)...")
        try:
            ngs_rec_raw = _fetch_ngs_receiving(ngs_seasons)
            ngs_rec = aggregate_ngs_receiving(ngs_rec_raw)
            ngs_rush_raw = _fetch_ngs_rushing(ngs_seasons)
            ngs_rush = aggregate_ngs_rushing(ngs_rush_raw)
            if verbose:
                print(f"  NGS receiving: {len(ngs_rec)} rows, rushing: {len(ngs_rush)} rows")
        except Exception as e:
            if verbose:
                print(f"  NGS data unavailable: {e}")

    # Step 6: Fetch PFR advanced stats (2018+ only)
    pfr_seasons = [s for s in seasons if s >= 2018]
    pfr_rec = pd.DataFrame()
    pfr_rush = pd.DataFrame()
    if pfr_seasons:
        if verbose:
            print("Fetching PFR advanced stats (receiving + rushing)...")
        try:
            pfr_rec = _fetch_pfr_receiving(pfr_seasons)
            pfr_rush = _fetch_pfr_rushing(pfr_seasons)
            if verbose:
                print(f"  PFR receiving: {len(pfr_rec)} rows, rushing: {len(pfr_rush)} rows")
        except Exception as e:
            if verbose:
                print(f"  PFR data unavailable: {e}")

    # Step 6: Optional PBP aggregation
    pbp_agg = pd.DataFrame()
    ftn_agg = pd.DataFrame()
    if not skip_pbp:
        if verbose:
            print("Fetching play-by-play data (this may take a while)...")

        # Pre-fetch FTN data (2022+) for joining with PBP
        ftn_seasons = [s for s in seasons if s >= 2022]
        ftn_raw = pd.DataFrame()
        if ftn_seasons:
            if verbose:
                print("  Fetching FTN charting data...")
            try:
                ftn_raw = _fetch_ftn(ftn_seasons)
                if verbose:
                    print(f"  FTN: {len(ftn_raw)} charted plays")
            except Exception as e:
                if verbose:
                    print(f"  FTN data unavailable: {e}")

        # Process PBP in batches
        for batch_start in range(0, len(seasons), 3):
            batch = seasons[batch_start:batch_start + 3]
            if verbose:
                print(f"  Processing PBP for {batch}...")
            pbp_df = _fetch_pbp(batch)
            batch_agg = aggregate_pbp(pbp_df, batch)
            if not batch_agg.empty:
                pbp_agg = pd.concat([pbp_agg, batch_agg], ignore_index=True)

            # FTN aggregation (join with PBP for this batch)
            if not ftn_raw.empty:
                ftn_batch = ftn_raw[ftn_raw["season"].isin(batch)] if "season" in ftn_raw.columns else pd.DataFrame()
                if ftn_batch.empty:
                    # FTN may not have season col; filter by game_id prefix
                    for s in batch:
                        if s >= 2022:
                            mask = ftn_raw["nflverse_game_id"].str.startswith(str(s))
                            ftn_batch = pd.concat([ftn_batch, ftn_raw[mask]])
                if not ftn_batch.empty:
                    batch_ftn = aggregate_ftn(ftn_batch, pbp_df)
                    if not batch_ftn.empty:
                        ftn_agg = pd.concat([ftn_agg, batch_ftn], ignore_index=True)

            del pbp_df  # Free memory

    # Step 6: Write to DB
    if verbose:
        print("Writing to database...")

    # Process seasonal + weekly data (keyed by gsis_id)
    for _, row in seasonal_agg.iterrows():
        gsis_id = row.get("player_id")
        season = int(row["season"])

        player_id = id_map.get(str(gsis_id))
        if not player_id:
            stats["unmatched"] += 1
            continue

        info = ids_name_map.get(player_id, {})
        player = ensure_player_exists(
            session, player_id,
            full_name=info.get("name", "Unknown"),
            position=info.get("position"),
            team=info.get("team"),
            gsis_id=str(gsis_id),
        )
        if player.created_at is None:
            player.created_at = now_iso
            stats["players_created"] += 1

        baseline_id = f"{player_id}_{season}"
        baseline = session.get(PlayerSeasonBaseline, baseline_id)
        if not baseline:
            baseline = PlayerSeasonBaseline(
                baseline_id=baseline_id,
                player_id=player_id,
                season=season,
            )
            session.add(baseline)

        # Set seasonal fields (only if NULL)
        for field in ["target_share", "air_yards_share", "racr",
                       "yards_after_catch_per_rec", "avg_depth_of_target",
                       "dominator_rating"]:
            val = row.get(field)
            if val is not None and not (isinstance(val, float) and np.isnan(val)):
                if getattr(baseline, field, None) is None:
                    setattr(baseline, field, float(val))

        # Compute WOPR if we have inputs
        if baseline.target_share and baseline.air_yards_share:
            if baseline.wopr is None:
                baseline.wopr = (1.5 * baseline.target_share) + (0.7 * baseline.air_yards_share)

        stats["baselines_updated"] += 1

    # Merge weekly boom/bust data
    if not weekly_agg.empty:
        for _, row in weekly_agg.iterrows():
            gsis_id = row.get("player_id")
            season = int(row["season"])
            player_id = id_map.get(str(gsis_id))
            if not player_id:
                continue

            baseline_id = f"{player_id}_{season}"
            baseline = session.get(PlayerSeasonBaseline, baseline_id)
            if not baseline:
                continue

            for field in ["boom_rate", "bust_rate", "consistency_score"]:
                val = row.get(field)
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    if getattr(baseline, field, None) is None:
                        setattr(baseline, field, float(val))

    # Merge snap count data (keyed by pfr_player_id = pipeline PLAYER ID)
    if not snap_agg.empty:
        for _, row in snap_agg.iterrows():
            player_id = row.get("pfr_player_id")
            season = int(row["season"])
            if not player_id or pd.isna(player_id):
                continue

            baseline_id = f"{player_id}_{season}"
            baseline = session.get(PlayerSeasonBaseline, baseline_id)
            if not baseline:
                continue

            snap_val = row.get("snap_share")
            if snap_val is not None and not (isinstance(snap_val, float) and np.isnan(snap_val)):
                if baseline.snap_share is None:
                    baseline.snap_share = float(snap_val)

    # Merge NGS receiving tracking data (keyed by gsis_id)
    if not ngs_rec.empty:
        for _, row in ngs_rec.iterrows():
            gsis_id = row.get("player_gsis_id")
            season = int(row["season"])
            if not gsis_id or pd.isna(gsis_id):
                continue

            player_id = id_map.get(str(gsis_id))
            if not player_id:
                continue

            baseline_id = f"{player_id}_{season}"
            baseline = session.get(PlayerSeasonBaseline, baseline_id)
            if not baseline:
                continue

            for ngs_col, field in [
                ("avg_cushion", "avg_cushion"),
                ("avg_separation", "avg_separation"),
            ]:
                val = row.get(ngs_col)
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    if getattr(baseline, field, None) is None:
                        setattr(baseline, field, float(val))

    # Merge NGS rushing tracking data (keyed by gsis_id)
    if not ngs_rush.empty:
        for _, row in ngs_rush.iterrows():
            gsis_id = row.get("player_gsis_id")
            season = int(row["season"])
            if not gsis_id or pd.isna(gsis_id):
                continue

            player_id = id_map.get(str(gsis_id))
            if not player_id:
                continue

            baseline_id = f"{player_id}_{season}"
            baseline = session.get(PlayerSeasonBaseline, baseline_id)
            if not baseline:
                continue

            for ngs_col, field in [
                ("expected_yards_per_carry", "expected_yards_per_carry"),
                ("rush_yards_over_expected", "rush_yards_over_expected"),
            ]:
                val = row.get(ngs_col)
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    if getattr(baseline, field, None) is None:
                        setattr(baseline, field, float(val))

    # Merge PFR advanced receiving stats (keyed by pfr_id = pipeline PLAYER ID)
    if not pfr_rec.empty:
        for _, row in pfr_rec.iterrows():
            pfr_id = row.get("pfr_id")
            season = int(row["season"])
            if not pfr_id or pd.isna(pfr_id):
                continue

            baseline_id = f"{pfr_id}_{season}"
            baseline = session.get(PlayerSeasonBaseline, baseline_id)
            if not baseline:
                continue

            # drop_rate from PFR (film-verified, better than PBP-derived)
            drop_pct = row.get("drop_percent")
            if pd.notna(drop_pct) and baseline.drop_rate is None:
                baseline.drop_rate = float(drop_pct)

            # broken_tackle_rate = broken tackles / receptions
            brk = row.get("brk_tkl")
            rec = row.get("rec")
            if pd.notna(brk) and pd.notna(rec) and rec > 0 and baseline.broken_tackle_rate is None:
                baseline.broken_tackle_rate = float(brk) / float(rec)

    # Merge PFR advanced rushing stats
    if not pfr_rush.empty:
        for _, row in pfr_rush.iterrows():
            pfr_id = row.get("pfr_id")
            season = int(row["season"])
            if not pfr_id or pd.isna(pfr_id):
                continue

            baseline_id = f"{pfr_id}_{season}"
            baseline = session.get(PlayerSeasonBaseline, baseline_id)
            if not baseline:
                continue

            # RB broken_tackle_rate from rushing = broken tackles / attempts
            brk = row.get("brk_tkl")
            att = row.get("att")
            if pd.notna(brk) and pd.notna(att) and att > 0 and baseline.broken_tackle_rate is None:
                baseline.broken_tackle_rate = float(brk) / float(att)

    # Merge PBP data (keyed by gsis_id)
    if not pbp_agg.empty:
        pbp_fields = [
            "rz_target_share", "ez_target_share", "third_down_target_share",
            "rz_carry_share", "goal_line_carry_share", "early_down_share",
            "third_down_carry_share",
        ]
        for _, row in pbp_agg.iterrows():
            gsis_id = row.get("player_id")
            season = int(row["season"])
            player_id = id_map.get(str(gsis_id))
            if not player_id:
                continue

            baseline_id = f"{player_id}_{season}"
            baseline = session.get(PlayerSeasonBaseline, baseline_id)
            if not baseline:
                continue

            for field in pbp_fields:
                val = row.get(field)
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    if getattr(baseline, field, None) is None:
                        setattr(baseline, field, float(val))

    # Merge FTN charting data (keyed by gsis_id)
    if not ftn_agg.empty:
        ftn_fields = [
            "play_action_target_pct", "screen_target_pct", "contested_ball_pct",
            "catchable_ball_pct", "created_reception_pct", "true_drop_rate",
        ]
        for _, row in ftn_agg.iterrows():
            gsis_id = row.get("player_id")
            season = int(row["season"])
            player_id = id_map.get(str(gsis_id))
            if not player_id:
                continue

            baseline_id = f"{player_id}_{season}"
            baseline = session.get(PlayerSeasonBaseline, baseline_id)
            if not baseline:
                continue

            for field in ftn_fields:
                val = row.get(field)
                if val is not None and not (isinstance(val, float) and np.isnan(val)):
                    if getattr(baseline, field, None) is None:
                        setattr(baseline, field, float(val))

    session.commit()

    if verbose:
        print(f"nflverse ingest: {stats['players_created']} players created, "
              f"{stats['baselines_updated']} baselines updated, "
              f"{stats['unmatched']} unmatched")

    return stats
