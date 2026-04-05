"""Tests for historical box score ingest from combined_data.csv."""

import pandas as pd
import pytest

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.ingest.ingest_historical import ingest_historical, _compute_derived_fields


def _make_historical_df():
    """Small synthetic combined_data.csv DataFrame."""
    return pd.DataFrame({
        "PLAYER NAME": ["Saquon Barkley", "Derrick Henry", "Patrick Mahomes"],
        "ID": ["BarkSa00", "HenrDe00", "MahomPa01"],
        "POS": ["RB", "RB", "QB"],
        "TEAM": ["PHI", "BAL", "KC"],
        "SEASON": [2024, 2024, 2024],
        "G": [16, 17, 17],
        "GS": [16, 17, 17],
        "PASS CMP": [0, 0, 401],
        "PASS ATT": [0, 0, 588],
        "PASS YDS": [0, 0, 4800],
        "PASS TD": [0, 0, 38],
        "PASS INT": [0, 0, 12],
        "RUSH ATT": [287, 325, 35],
        "RUSH YDS": [1387, 1450, 210],
        "RUSH Y/A": [4.83, 4.46, 6.0],
        "RUSH TD": [15, 16, 2],
        "REC TGT": [42, 18, 0],
        "REC REC": [33, 12, 0],
        "REC YDS": [310, 95, 0],
        "REC Y/R": [9.39, 7.92, 0],
        "REC TD": [2, 1, 0],
        "FMB": [1, 2, 3],
        "FL": [0, 1, 2],
        "TOT TD": [17, 17, 40],
        "FANTPT": [280.7, 272.0, 320.0],
        "PPR": [313.7, 284.0, 320.0],
        "DKPT": [300.0, 285.0, 340.0],
        "FDPT": [290.0, 280.0, 330.0],
        "VBD": [130, 120, 150],
        "POS RANK": [1, 2, 1],
        "OVERALL RK": [2, 5, 1],
        "RK": [2, 5, 1],
    })


class TestComputeDerivedFields:
    def test_fpts_per_game(self):
        row = pd.Series({"G": 16, "PPR": 320.0, "FANTPT": 280.0, "RUSH ATT": 200, "REC REC": 30, "REC TGT": 40, "TOT TD": 15, "RUSH YDS": 1000})
        fields = _compute_derived_fields(row)
        assert fields["fpts_per_game_ppr"] == pytest.approx(20.0)
        assert fields["fpts_per_game_std"] == pytest.approx(17.5)

    def test_carries_per_game(self):
        row = pd.Series({"G": 17, "RUSH ATT": 340, "PPR": None, "FANTPT": None, "REC REC": None, "REC TGT": None, "TOT TD": None, "RUSH YDS": None})
        fields = _compute_derived_fields(row)
        assert fields["carries_per_game"] == pytest.approx(20.0)

    def test_catch_rate(self):
        row = pd.Series({"G": 16, "REC TGT": 100, "REC REC": 70, "RUSH ATT": 0, "PPR": None, "FANTPT": None, "TOT TD": None, "RUSH YDS": None})
        fields = _compute_derived_fields(row)
        assert fields["catch_rate"] == pytest.approx(0.70)

    def test_total_touches_per_game(self):
        row = pd.Series({"G": 16, "RUSH ATT": 200, "REC REC": 40, "REC TGT": 50, "PPR": None, "FANTPT": None, "TOT TD": None, "RUSH YDS": None})
        fields = _compute_derived_fields(row)
        assert fields["total_touches_per_game"] == pytest.approx(15.0)

    def test_td_rate(self):
        row = pd.Series({"G": 16, "RUSH ATT": 200, "REC REC": 50, "TOT TD": 25, "REC TGT": 60, "PPR": None, "FANTPT": None, "RUSH YDS": None})
        fields = _compute_derived_fields(row)
        assert fields["td_rate"] == pytest.approx(0.10)

    def test_zero_games_returns_empty(self):
        row = pd.Series({"G": 0})
        fields = _compute_derived_fields(row)
        assert fields == {}

    def test_half_ppr(self):
        row = pd.Series({"G": 16, "FANTPT": 200.0, "REC REC": 60, "RUSH ATT": 0, "REC TGT": 80, "PPR": 260.0, "TOT TD": 5, "RUSH YDS": 0})
        fields = _compute_derived_fields(row)
        assert fields["fantasy_pts_half"] == pytest.approx(230.0)


class TestIngestHistorical:
    def test_creates_players_and_baselines(self, session):
        df = _make_historical_df()
        stats = ingest_historical(session, df, verbose=False)
        assert stats["players_created"] == 3
        assert stats["baselines_created"] == 3

        player = session.get(Player, "BarkSa00")
        assert player is not None
        assert player.full_name == "Saquon Barkley"
        assert player.position == "RB"
        assert player.is_active == 0

    def test_populates_baseline_fields(self, session):
        df = _make_historical_df()
        ingest_historical(session, df, verbose=False)

        baseline = session.get(PlayerSeasonBaseline, "BarkSa00_2024")
        assert baseline.games_played == 16
        assert baseline.games_started == 16
        assert baseline.fantasy_pts_ppr == pytest.approx(313.7)
        assert baseline.fantasy_pts_std == pytest.approx(280.7)
        assert baseline.fpts_per_game_ppr == pytest.approx(313.7 / 16)

    def test_computes_derived_fields(self, session):
        df = _make_historical_df()
        ingest_historical(session, df, verbose=False)

        baseline = session.get(PlayerSeasonBaseline, "BarkSa00_2024")
        assert baseline.carries_per_game == pytest.approx(287 / 16)
        assert baseline.catch_rate == pytest.approx(33 / 42)
        assert baseline.yards_per_carry == pytest.approx(1387 / 287)

    def test_filters_by_season(self, session):
        df = _make_historical_df()
        # Add a 2023 row
        extra = pd.DataFrame({
            "PLAYER NAME": ["Saquon Barkley"], "ID": ["BarkSa00"],
            "POS": ["RB"], "TEAM": ["NYG"], "SEASON": [2023],
            "G": [14], "GS": [14], "FANTPT": [200.0], "PPR": [240.0],
            "RUSH ATT": [200], "RUSH YDS": [900], "RUSH Y/A": [4.5], "RUSH TD": [8],
            "REC TGT": [30], "REC REC": [20], "REC YDS": [150], "REC Y/R": [7.5], "REC TD": [1],
            "TOT TD": [9], "PASS CMP": [0], "PASS ATT": [0], "PASS YDS": [0],
            "PASS TD": [0], "PASS INT": [0], "FMB": [0], "FL": [0],
            "DKPT": [0], "FDPT": [0], "VBD": [0], "POS RANK": [5],
            "OVERALL RK": [20], "RK": [20],
        })
        full = pd.concat([df, extra], ignore_index=True)
        stats = ingest_historical(session, full, seasons=[2024], verbose=False)
        assert stats["baselines_created"] == 3  # Only 2024

    def test_does_not_overwrite_existing_values(self, session, seed_players, seed_baselines):
        """Existing baseline fields from rankings should not be overwritten."""
        df = pd.DataFrame({
            "PLAYER NAME": ["Patrick Mahomes"], "ID": ["MahomPa01"],
            "POS": ["QB"], "TEAM": ["KC"], "SEASON": [2024],
            "G": [17], "GS": [17], "FANTPT": [999.0], "PPR": [999.0],
            "RUSH ATT": [35], "RUSH YDS": [210], "RUSH Y/A": [6.0], "RUSH TD": [2],
            "REC TGT": [0], "REC REC": [0], "REC YDS": [0], "REC Y/R": [0], "REC TD": [0],
            "TOT TD": [40], "PASS CMP": [0], "PASS ATT": [0], "PASS YDS": [0],
            "PASS TD": [0], "PASS INT": [0], "FMB": [0], "FL": [0],
            "DKPT": [0], "FDPT": [0], "VBD": [0], "POS RANK": [1],
            "OVERALL RK": [1], "RK": [1],
        })
        ingest_historical(session, df, verbose=False)

        baseline = session.get(PlayerSeasonBaseline, "MahomPa01_2024")
        # games_played was already set to 17 in seed, should stay
        assert baseline.games_played == 17
        # fantasy_pts_ppr was set to 350.0 in seed, should NOT be overwritten
        assert baseline.fantasy_pts_ppr == pytest.approx(350.0)

    def test_standardizes_team(self, session):
        df = pd.DataFrame({
            "PLAYER NAME": ["Test Player"], "ID": ["TestPl01"],
            "POS": ["WR"], "TEAM": ["JAC"], "SEASON": [2024],
            "G": [16], "GS": [16], "FANTPT": [100.0], "PPR": [130.0],
            "RUSH ATT": [0], "RUSH YDS": [0], "RUSH Y/A": [0], "RUSH TD": [0],
            "REC TGT": [50], "REC REC": [35], "REC YDS": [400], "REC Y/R": [11.4], "REC TD": [3],
            "TOT TD": [3], "PASS CMP": [0], "PASS ATT": [0], "PASS YDS": [0],
            "PASS TD": [0], "PASS INT": [0], "FMB": [0], "FL": [0],
            "DKPT": [0], "FDPT": [0], "VBD": [0], "POS RANK": [20],
            "OVERALL RK": [50], "RK": [50],
        })
        ingest_historical(session, df, verbose=False)
        player = session.get(Player, "TestPl01")
        assert player.team == "JAX"
