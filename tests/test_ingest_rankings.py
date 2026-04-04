"""Tests for rankings ingest — direct player creation, no bridge table."""

import pandas as pd
import pytest

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.ingest.ingest_rankings import (
    compute_sharp_consensus,
    ingest_rankings,
)


class TestComputeSharpConsensus:
    def test_all_sources(self):
        row = pd.Series({
            "fpts_POS RANK": 3, "jj_POS RANK": 5,
            "hw_POS RANK": 2, "pff_POS RANK": 4,
        })
        rank, count = compute_sharp_consensus(row)
        assert rank == 3.5
        assert count == 4

    def test_missing_sources(self):
        row = pd.Series({
            "fpts_POS RANK": 3, "jj_POS RANK": None,
            "hw_POS RANK": 5, "pff_POS RANK": None,
        })
        rank, count = compute_sharp_consensus(row)
        assert rank == 4.0
        assert count == 2

    def test_no_sources(self):
        row = pd.Series({
            "fpts_POS RANK": None, "jj_POS RANK": None,
            "hw_POS RANK": None, "pff_POS RANK": None,
        })
        rank, count = compute_sharp_consensus(row)
        assert rank is None
        assert count == 0


class TestIngestRankings:
    def test_creates_players_directly(self, session, sample_rankings_df):
        """Rankings ingest should create Player records — no bridge table needed."""
        stats = ingest_rankings(session, sample_rankings_df, 2025, verbose=False)
        assert stats["created"] == 3  # all 3 are new
        assert stats["skipped"] == 0

        # Verify players were created with pipeline IDs
        mahomes = session.get(Player, "MahomPa01")
        assert mahomes is not None
        assert mahomes.full_name == "Patrick Mahomes"
        assert mahomes.position == "QB"
        assert mahomes.team == "KC"

    def test_creates_baselines(self, session, sample_rankings_df):
        ingest_rankings(session, sample_rankings_df, 2025, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "MahomPa01_2025")
        assert baseline is not None
        assert baseline.rankings_avg_overall == 2.0
        assert baseline.rankings_avg_positional == 1.0
        assert baseline.adp_consensus == 2.5

    def test_computes_sharp_consensus(self, session, sample_rankings_df):
        ingest_rankings(session, sample_rankings_df, 2025, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "MahomPa01_2025")
        # Sharp consensus = mean(fpts=1, jj=2, hw=1, pff=2) = 1.5
        assert baseline.sharp_consensus_rank == 1.5
        assert baseline.rankings_source_count == 4

    def test_computes_divergence(self, session, sample_rankings_df):
        ingest_rankings(session, sample_rankings_df, 2025, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "HillTy01_2025")
        # Sharp = mean(3,4,2,3) = 3.0; ADP pos = 5; divergence = 5 - 3 = 2
        assert baseline.adp_divergence_rank == 2
        assert baseline.adp_divergence_flag == 0  # < 12

    def test_sets_divergence_flag(self, session):
        """Large divergence sets the flag."""
        df = pd.DataFrame({
            "PLAYER NAME": ["Test Player"],
            "PLAYER ID": ["TestPl01"],
            "POS": ["QB"], "TEAM": ["KC"],
            "avg_RK": [1.0], "avg_POS RANK": [1.0],
            "fpts_POS RANK": [1], "jj_POS RANK": [1],
            "hw_POS RANK": [1], "pff_POS RANK": [1],
            "ds_POS RANK": [1],
            "ADP": [30.0], "POS ADP": [15],
            "fp_POS RANK": [1],
            "ECR ADP Delta": [0.0], "ECR Delta": [0.0],
        })
        ingest_rankings(session, df, 2025, verbose=False)
        baseline = session.get(PlayerSeasonBaseline, "TestPl01_2025")
        # Sharp = 1.0, ADP pos = 15, divergence = 14
        assert baseline.adp_divergence_rank == 14
        assert baseline.adp_divergence_flag == 1

    def test_updates_existing_player(self, session, seed_players, sample_rankings_df):
        """Existing players get updated, not duplicated."""
        stats = ingest_rankings(session, sample_rankings_df, 2025, verbose=False)
        assert stats["existing"] == 2  # Mahomes and Hill already seeded
        assert stats["created"] == 1  # NewPPl01 is new

    def test_skips_missing_player_id(self, session):
        df = pd.DataFrame({
            "PLAYER NAME": ["No ID Player"],
            "PLAYER ID": [None],
            "POS": ["WR"], "TEAM": ["DAL"],
            "avg_RK": [50.0], "avg_POS RANK": [25.0],
        })
        stats = ingest_rankings(session, df, 2025, verbose=False)
        assert stats["skipped"] == 1

    def test_standardizes_team(self, session):
        """Team abbreviation variants should be normalized."""
        df = pd.DataFrame({
            "PLAYER NAME": ["Test Player"],
            "PLAYER ID": ["TestPl01"],
            "POS": ["QB"], "TEAM": ["JAC"],  # variant for JAX
            "avg_RK": [1.0], "avg_POS RANK": [1.0],
        })
        ingest_rankings(session, df, 2025, verbose=False)
        player = session.get(Player, "TestPl01")
        assert player.team == "JAX"
