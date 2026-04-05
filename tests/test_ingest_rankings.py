"""Tests for rankings ingest — position-first sharp consensus with ADP scarcity curve."""

import pandas as pd
import pytest

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.ingest.ingest_rankings import (
    compute_sharp_consensus,
    ingest_rankings,
    _build_scarcity_curves,
)


def _make_rankings_df():
    """Build a small but realistic DataFrame for testing the scarcity curve logic."""
    return pd.DataFrame({
        "PLAYER NAME": [
            "QB Star", "RB Alpha", "WR Alpha", "WR Beta",
            "RB Beta", "TE Alpha", "QB Backup", "WR Gamma", "TE Beta",
        ],
        "PLAYER ID": [
            "QBSt01", "RBal01", "WRal01", "WRbe01",
            "RBbe01", "TEal01", "QBba01", "WRga01", "TEbe01",
        ],
        "POS": ["QB", "RB", "WR", "WR", "RB", "TE", "QB", "WR", "TE"],
        "TEAM": ["KC", "ATL", "CIN", "DAL", "PHI", "ARI", "BUF", "DET", "MIA"],
        # ADP provides the scarcity curve
        "ADP": [5.0, 2.0, 1.0, 7.0, 6.0, 12.0, 20.0, 15.0, 25.0],
        "POS ADP": [1, 1, 1, 2, 2, 1, 2, 3, 2],
        # Sharp source positional ranks
        "fpts_POS RANK": [1, 1, 1, 2, 2, 1, 2, 3, 2],
        "jj_POS RANK": [1, 1, 1, 3, 2, 1, 2, 3, 2],
        "hw_POS RANK": [2, 2, 1, 2, 1, 1, 2, 3, 2],  # HW has different view
        "pff_POS RANK": [1, 1, 2, 2, 2, 1, 2, 4, 2],
        "ds_POS RANK": [1, 1, 1, 2, 2, 1, 2, 3, 2],
        "avg_RK": [5.0, 2.0, 1.0, 7.0, 6.0, 12.0, 20.0, 15.0, 25.0],
        "avg_POS RANK": [1.0, 1.0, 1.0, 2.0, 2.0, 1.0, 2.0, 3.0, 2.0],
        "fp_POS RANK": [1, 1, 1, 2, 2, 1, 2, 3, 2],
        "ECR ADP Delta": [0, 0, 0, 0, 0, 0, 0, 0, 0],
        "ECR Delta": [0, 0, 0, 0, 0, 0, 0, 0, 0],
    })


class TestBuildScarcityCurves:
    def test_builds_curves_for_all_positions(self):
        df = _make_rankings_df()
        curves = _build_scarcity_curves(df)
        assert set(curves.keys()) == {"QB", "RB", "WR", "TE"}

    def test_curve_interpolates(self):
        df = _make_rankings_df()
        curves = _build_scarcity_curves(df)
        # WR: POS ADP 1 → ADP 1.0, POS ADP 2 → ADP 7.0
        # WR pos rank 1.5 should interpolate to ~4.0
        result = curves["WR"](1.5)
        assert 3.0 <= result <= 5.0

    def test_curve_exact_match(self):
        df = _make_rankings_df()
        curves = _build_scarcity_curves(df)
        # QB1 goes at ADP 5.0
        assert curves["QB"](1) == pytest.approx(5.0)


class TestComputeSharpConsensus:
    def test_computes_sharp_pos_rank(self):
        df = _make_rankings_df()
        result = compute_sharp_consensus(df)
        # WR Alpha: fpts=1, jj=1, hw=1, pff=2 → mean = 1.25
        wr_alpha = result[result["PLAYER ID"] == "WRal01"].iloc[0]
        assert wr_alpha["sharp_pos_rank"] == pytest.approx(1.25)

    def test_source_count(self):
        df = _make_rankings_df()
        result = compute_sharp_consensus(df)
        # All players have all 4 sharp sources
        assert (result["sharp_source_count"] == 4).all()

    def test_source_count_with_missing(self):
        df = _make_rankings_df()
        df.loc[0, "hw_POS RANK"] = None
        df.loc[0, "pff_POS RANK"] = None
        result = compute_sharp_consensus(df)
        assert result.iloc[0]["sharp_source_count"] == 2

    def test_produces_overall_rank(self):
        df = _make_rankings_df()
        result = compute_sharp_consensus(df)
        # sharp_consensus_rank should exist and have no NaN for players with data
        assert result["sharp_consensus_rank"].notna().all()
        # It should be a rank (1, 2, 3...)
        assert result["sharp_consensus_rank"].min() == 1.0

    def test_positional_divergence(self):
        df = _make_rankings_df()
        result = compute_sharp_consensus(df)
        # QB Star: POS ADP = 1, sharp_pos_rank = mean(1,1,2,1) = 1.25
        # adp_divergence_pos = 1 - 1.25 = -0.25
        qb = result[result["PLAYER ID"] == "QBSt01"].iloc[0]
        assert qb["adp_divergence_pos"] == pytest.approx(-0.25)

    def test_hw_bias_neutralized(self):
        """HW's different positional view is averaged out, not amplified."""
        df = _make_rankings_df()
        result = compute_sharp_consensus(df)
        # RB Alpha: fpts=1, jj=1, hw=2, pff=1 → sharp_pos = 1.25
        # RB Beta:  fpts=2, jj=2, hw=1, pff=2 → sharp_pos = 1.75
        # HW disagrees on who's RB1 vs RB2, but the consensus still
        # favors RB Alpha because 3/4 sources agree
        rb_alpha = result[result["PLAYER ID"] == "RBal01"].iloc[0]
        rb_beta = result[result["PLAYER ID"] == "RBbe01"].iloc[0]
        assert rb_alpha["sharp_pos_rank"] < rb_beta["sharp_pos_rank"]


class TestIngestRankings:
    def test_creates_players_directly(self, session):
        df = _make_rankings_df()
        stats = ingest_rankings(session, df, 2025, verbose=False)
        assert stats["created"] == 9
        player = session.get(Player, "WRal01")
        assert player.full_name == "WR Alpha"

    def test_stores_sharp_pos_rank(self, session):
        df = _make_rankings_df()
        ingest_rankings(session, df, 2025, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "WRal01_2025")
        assert baseline.sharp_pos_rank == pytest.approx(1.25)

    def test_stores_sharp_consensus_rank(self, session):
        df = _make_rankings_df()
        ingest_rankings(session, df, 2025, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "WRal01_2025")
        assert baseline.sharp_consensus_rank is not None
        assert baseline.sharp_consensus_rank >= 1

    def test_stores_positional_divergence(self, session):
        df = _make_rankings_df()
        ingest_rankings(session, df, 2025, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "QBSt01_2025")
        assert baseline.adp_divergence_pos is not None

    def test_sets_divergence_flag_on_positional(self, session):
        """Large positional divergence sets the flag."""
        df = pd.DataFrame({
            "PLAYER NAME": ["Big Edge WR", "Control RB"],
            "PLAYER ID": ["BigEd01", "ConRB01"],
            "POS": ["WR", "RB"],
            "TEAM": ["KC", "SF"],
            "ADP": [30.0, 5.0],
            "POS ADP": [15, 2],
            "fpts_POS RANK": [1, 1],
            "jj_POS RANK": [1, 1],
            "hw_POS RANK": [1, 2],
            "pff_POS RANK": [2, 1],
            "ds_POS RANK": [1, 1],
            "avg_RK": [30.0, 5.0],
            "avg_POS RANK": [15.0, 2.0],
            "fp_POS RANK": [15, 2],
            "ECR ADP Delta": [0, 0],
            "ECR Delta": [0, 0],
        })
        ingest_rankings(session, df, 2025, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "BigEd01_2025")
        # ADP pos rank 15, sharp pos rank ~1.25 → divergence ~13.75
        assert baseline.adp_divergence_flag == 1

    def test_standardizes_team(self, session):
        df = pd.DataFrame({
            "PLAYER NAME": ["Test"], "PLAYER ID": ["Test01"],
            "POS": ["QB"], "TEAM": ["JAC"],
            "ADP": [1.0], "POS ADP": [1],
            "fpts_POS RANK": [1], "jj_POS RANK": [1],
            "hw_POS RANK": [1], "pff_POS RANK": [1],
            "ds_POS RANK": [1], "avg_RK": [1.0], "avg_POS RANK": [1.0],
            "fp_POS RANK": [1], "ECR ADP Delta": [0], "ECR Delta": [0],
        })
        ingest_rankings(session, df, 2025, verbose=False)
        assert session.get(Player, "Test01").team == "JAX"
