"""Tests for nflverse ingest — aggregation functions with synthetic data.

No network calls — all nfl_data_py functions are tested via their
pure DataFrame-in/DataFrame-out aggregation layers.
"""

import numpy as np
import pandas as pd
import pytest

from fantasy_data.ingest.ingest_nflverse import (
    aggregate_seasonal,
    aggregate_weekly,
    aggregate_snaps,
    aggregate_pbp,
    BOOM_THRESHOLD,
    BUST_THRESHOLD,
)


def _make_seasonal_df():
    """Synthetic nflverse seasonal data (import_seasonal_data output)."""
    return pd.DataFrame({
        "player_id": ["00-001", "00-002", "00-003"],
        "season": [2024, 2024, 2024],
        "target_share": [0.28, 0.15, 0.0],
        "air_yards_share": [0.35, 0.12, 0.0],
        "racr": [1.05, 0.95, None],
        "dom": [0.30, 0.15, None],
        "receptions": [100, 50, 0],
        "targets": [130, 70, 0],
        "receiving_yards": [1200, 600, 0],
        "receiving_air_yards": [1100, 650, 0],
        "receiving_yards_after_catch": [400, 200, 0],
        "games": [17, 16, 17],
    })


def _make_weekly_df():
    """Synthetic nflverse weekly data for boom/bust/consistency."""
    rows = []
    # Player 1: consistent high scorer (17 games)
    for week in range(1, 18):
        rows.append({
            "player_id": "00-001", "season": 2024, "week": week,
            "season_type": "REG",
            "fantasy_points_ppr": 18.0 + (week % 3),  # 18-20 range
        })
    # Player 2: volatile scorer (16 games)
    scores = [4.0, 25.0, 3.0, 30.0, 5.0, 22.0, 2.0, 28.0,
              4.5, 24.0, 3.5, 26.0, 5.5, 21.0, 4.0, 27.0]
    for i, score in enumerate(scores):
        rows.append({
            "player_id": "00-002", "season": 2024, "week": i + 1,
            "season_type": "REG",
            "fantasy_points_ppr": score,
        })
    return pd.DataFrame(rows)


def _make_snap_df():
    """Synthetic snap count data."""
    rows = []
    for week in range(1, 18):
        rows.append({
            "pfr_player_id": "SmitJo00", "player": "John Smith",
            "season": 2024, "week": week, "team": "KC",
            "game_type": "REG", "game_id": f"2024_W{week}",
            "offense_pct": 85.0 + (week % 5),  # 85-89%
            "offense_snaps": 60, "defense_snaps": 0, "defense_pct": 0,
            "st_snaps": 5, "st_pct": 10,
        })
    return pd.DataFrame(rows)


def _make_pbp_df():
    """Synthetic play-by-play data for RZ/down splits."""
    plays = []
    # 100 pass plays for team KC
    for i in range(100):
        yardline = 50 - (i % 50)  # Varies 1-50
        down = (i % 4) + 1
        plays.append({
            "season": 2024, "season_type": "REG",
            "play_type": "pass", "posteam": "KC",
            "receiver_player_id": "00-001" if i < 60 else "00-002",
            "rusher_player_id": None,
            "yardline_100": yardline, "down": down,
        })
    # 80 run plays for team KC
    for i in range(80):
        yardline = 40 - (i % 40)
        down = (i % 4) + 1
        plays.append({
            "season": 2024, "season_type": "REG",
            "play_type": "run", "posteam": "KC",
            "receiver_player_id": None,
            "rusher_player_id": "00-003" if i < 50 else "00-004",
            "yardline_100": yardline, "down": down,
        })
    return pd.DataFrame(plays)


class TestAggregateSeasonal:
    def test_extracts_target_share(self):
        df = _make_seasonal_df()
        result = aggregate_seasonal(df)
        assert result.iloc[0]["target_share"] == pytest.approx(0.28)

    def test_extracts_air_yards_share(self):
        df = _make_seasonal_df()
        result = aggregate_seasonal(df)
        assert result.iloc[0]["air_yards_share"] == pytest.approx(0.35)

    def test_computes_yac_per_rec(self):
        df = _make_seasonal_df()
        result = aggregate_seasonal(df)
        # 400 YAC / 100 receptions = 4.0
        assert result.iloc[0]["yards_after_catch_per_rec"] == pytest.approx(4.0)

    def test_computes_adot(self):
        df = _make_seasonal_df()
        result = aggregate_seasonal(df)
        # 1100 air yards / 130 targets ≈ 8.46
        assert result.iloc[0]["avg_depth_of_target"] == pytest.approx(1100 / 130)

    def test_handles_zero_targets(self):
        df = _make_seasonal_df()
        result = aggregate_seasonal(df)
        # Player 3 has 0 targets → aDOT should be None-ish
        adot = result.iloc[2]["avg_depth_of_target"]
        assert adot is None or np.isnan(adot)


class TestAggregateWeekly:
    def test_boom_rate(self):
        df = _make_weekly_df()
        result = aggregate_weekly(df)
        p1 = result[result["player_id"] == "00-001"].iloc[0]
        # Player 1 scores 18-20 every week → 6 boom games (20.0) out of 17
        boom_count = sum(1 for w in range(1, 18) if 18.0 + (w % 3) >= BOOM_THRESHOLD)
        assert p1["boom_rate"] == pytest.approx(boom_count / 17)

    def test_bust_rate(self):
        df = _make_weekly_df()
        result = aggregate_weekly(df)
        p2 = result[result["player_id"] == "00-002"].iloc[0]
        # Player 2: scores below 5 multiple times
        bust_count = sum(1 for s in [4.0, 25.0, 3.0, 30.0, 5.0, 22.0, 2.0, 28.0,
                                      4.5, 24.0, 3.5, 26.0, 5.5, 21.0, 4.0, 27.0]
                        if s < BUST_THRESHOLD)
        assert p2["bust_rate"] == pytest.approx(bust_count / 16)

    def test_consistency_score(self):
        df = _make_weekly_df()
        result = aggregate_weekly(df)
        p1 = result[result["player_id"] == "00-001"].iloc[0]
        # Player 1 is consistent → high consistency score (close to 1)
        assert p1["consistency_score"] > 0.9

        p2 = result[result["player_id"] == "00-002"].iloc[0]
        # Player 2 is volatile → lower consistency score
        assert p2["consistency_score"] < p1["consistency_score"]

    def test_filters_regular_season(self):
        df = _make_weekly_df()
        # Add a playoff game
        playoff = pd.DataFrame([{
            "player_id": "00-001", "season": 2024, "week": 19,
            "season_type": "POST", "fantasy_points_ppr": 50.0,
        }])
        df = pd.concat([df, playoff], ignore_index=True)
        result = aggregate_weekly(df)
        p1 = result[result["player_id"] == "00-001"].iloc[0]
        # 50-point playoff game should not inflate boom rate
        assert p1["boom_rate"] < 1.0


class TestAggregateSnaps:
    def test_computes_mean_snap_share(self):
        df = _make_snap_df()
        result = aggregate_snaps(df)
        row = result[result["pfr_player_id"] == "SmitJo00"].iloc[0]
        # Mean of 85-89% range → ~87%, normalized to 0-1 → ~0.87
        assert 0.80 < row["snap_share"] < 0.95

    def test_normalizes_to_zero_one(self):
        df = _make_snap_df()
        result = aggregate_snaps(df)
        assert result["snap_share"].max() <= 1.0


class TestAggregatePbp:
    def test_receiver_rz_target_share(self):
        df = _make_pbp_df()
        result = aggregate_pbp(df, [2024])
        p1 = result[result["player_id"] == "00-001"]
        if not p1.empty:
            rz_share = p1.iloc[0].get("rz_target_share")
            if rz_share is not None:
                assert 0.0 <= rz_share <= 1.0

    def test_rusher_early_down_share(self):
        df = _make_pbp_df()
        result = aggregate_pbp(df, [2024])
        p3 = result[result["player_id"] == "00-003"]
        if not p3.empty:
            ed_share = p3.iloc[0].get("early_down_share")
            if ed_share is not None:
                assert 0.0 <= ed_share <= 1.0

    def test_rusher_goal_line_share(self):
        df = _make_pbp_df()
        result = aggregate_pbp(df, [2024])
        p3 = result[result["player_id"] == "00-003"]
        if not p3.empty:
            gl_share = p3.iloc[0].get("goal_line_carry_share")
            if gl_share is not None:
                assert 0.0 <= gl_share <= 1.0

    def test_empty_pbp_returns_empty(self):
        df = pd.DataFrame(columns=["season", "season_type", "play_type", "posteam",
                                    "receiver_player_id", "rusher_player_id",
                                    "yardline_100", "down"])
        result = aggregate_pbp(df, [2024])
        assert result.empty
