"""Multi-season trust-weighted baseline aggregation.

When multiple historical seasons exist for a player, computes a weighted
average of key metrics using data_trust_weight to discount seasons where
coaching/team continuity has broken.
"""

from sqlalchemy.orm import Session

from fantasy_data.models import PlayerSeasonBaseline

# Fields that should be trust-weighted across seasons
AGGREGABLE_FIELDS = [
    # Opportunity volume
    "snap_share",
    "route_participation_rate",
    "target_share",
    "air_yards_share",
    "rz_target_share",
    "ez_target_share",
    "carries_per_game",
    "rz_carry_share",
    "total_touches_per_game",
    # Efficiency
    "avg_depth_of_target",
    "yards_per_route_run",
    "catch_rate",
    "catch_rate_over_expected",
    "yards_after_catch_per_rec",
    "racr",
    "drop_rate",
    "broken_tackle_rate",
    "yards_per_carry",
    # NGS tracking
    "avg_cushion",
    "avg_separation",
    "expected_yards_per_carry",
    "rush_yards_over_expected",
    # Down splits
    "early_down_share",
    "third_down_carry_share",
    "third_down_target_share",
    "goal_line_carry_share",
    # FTN scheme context
    "play_action_target_pct",
    "screen_target_pct",
    "contested_ball_pct",
    "catchable_ball_pct",
    "created_reception_pct",
    "true_drop_rate",
    # Scoring & consistency
    "td_rate",
    "fpts_per_game_ppr",
    "fpts_per_game_std",
    "boom_rate",
    "bust_rate",
    "consistency_score",
]


def compute_weighted_baseline(
    session: Session,
    player_id: str,
    target_season: int,
    lookback_seasons: int = 3,
    verbose: bool = True,
) -> dict[str, float | None]:
    """Compute trust-weighted averages from historical seasons.

    Looks back up to `lookback_seasons` prior seasons and computes
    weighted averages of key metrics.

    Returns a dict of field -> weighted average value.
    """
    baselines = (
        session.query(PlayerSeasonBaseline)
        .filter(
            PlayerSeasonBaseline.player_id == player_id,
            PlayerSeasonBaseline.season < target_season,
            PlayerSeasonBaseline.season >= target_season - lookback_seasons,
        )
        .order_by(PlayerSeasonBaseline.season.desc())
        .all()
    )

    if not baselines:
        return {}

    result: dict[str, float | None] = {}

    for field in AGGREGABLE_FIELDS:
        values = []
        weights = []
        for b in baselines:
            val = getattr(b, field, None)
            w = b.data_trust_weight or 0.5
            if val is not None:
                values.append(val)
                weights.append(w)

        if values:
            total_weight = sum(weights)
            weighted_sum = sum(v * w for v, w in zip(values, weights))
            result[field] = weighted_sum / total_weight if total_weight > 0 else None
        else:
            result[field] = None

    return result


def compute_all_baselines(
    session: Session,
    target_season: int,
    lookback_seasons: int = 3,
    verbose: bool = True,
) -> dict[str, int]:
    """Compute weighted baselines for all players with historical data.

    Stores results as a new baseline record for the target season.
    Only populates the aggregable fields — does not overwrite existing
    rankings or PFF grade data.
    """
    stats = {"computed": 0, "no_history": 0}

    # Get all unique player_ids that have data in lookback window
    player_ids = (
        session.query(PlayerSeasonBaseline.player_id)
        .filter(
            PlayerSeasonBaseline.season < target_season,
            PlayerSeasonBaseline.season >= target_season - lookback_seasons,
        )
        .distinct()
        .all()
    )

    for (player_id,) in player_ids:
        weighted = compute_weighted_baseline(
            session, player_id, target_season, lookback_seasons, verbose=False
        )

        if not weighted:
            stats["no_history"] += 1
            continue

        # Get or create target season baseline
        baseline_id = f"{player_id}_{target_season}"
        baseline = session.get(PlayerSeasonBaseline, baseline_id)
        if not baseline:
            baseline = PlayerSeasonBaseline(
                baseline_id=baseline_id,
                player_id=player_id,
                season=target_season,
            )
            session.add(baseline)

        # Only set aggregable fields that don't already have current-season data
        for field, val in weighted.items():
            if val is not None and getattr(baseline, field, None) is None:
                setattr(baseline, field, val)

        # Compute composites if we have the inputs
        ts = baseline.target_share
        ays = baseline.air_yards_share
        rz_ts = baseline.rz_target_share

        if ts is not None and ays is not None:
            if baseline.wopr is None:
                baseline.wopr = (1.5 * ts) + (0.7 * ays)
            if rz_ts is not None and baseline.market_share_score is None:
                baseline.market_share_score = ts * 0.5 + ays * 0.3 + rz_ts * 0.2

        stats["computed"] += 1

    session.commit()

    if verbose:
        print(f"Baselines computed: {stats['computed']} players, "
              f"{stats['no_history']} with no history")

    return stats
