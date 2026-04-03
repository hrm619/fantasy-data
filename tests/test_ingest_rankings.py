"""Tests for rankings ingest pipeline."""

import pandas as pd
import pytest

from fantasy_data.models import PlayerSeasonBaseline, PipelineIdMap
from fantasy_data.ingest.ingest_rankings import (
    compute_sharp_consensus,
    ingest_rankings,
    SHARP_RANK_COLUMNS,
    DIVERGENCE_THRESHOLD,
)
from fantasy_data.ingest.pipeline_id_map import resolve_player_id, _normalize_name


class TestNormalizeName:
    def test_strips_suffix(self):
        assert _normalize_name("Marvin Harrison Jr") == "marvin harrison"

    def test_removes_special_chars(self):
        assert _normalize_name("Ja'Marr Chase") == "jamarr chase"

    def test_strips_whitespace(self):
        assert _normalize_name("  Patrick  Mahomes  ") == "patrick mahomes"

    def test_removes_periods(self):
        assert _normalize_name("D.K. Metcalf") == "dk metcalf"


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


class TestResolvePlayerId:
    def test_exact_match(self, session, seed_players):
        result = resolve_player_id(session, "TestPipe01", "Patrick Mahomes")
        assert result == "PFF001"
        mapping = session.get(PipelineIdMap, "TestPipe01")
        assert mapping.match_method == "exact"

    def test_normalized_match(self, session, seed_players):
        # "JaMarr Chase" (no apostrophe) should match "Ja'Marr Chase" via normalization
        result = resolve_player_id(session, "TestPipe02", "JaMarr Chase")
        assert result == "PFF003"
        mapping = session.get(PipelineIdMap, "TestPipe02")
        assert mapping.match_method == "normalized"

    def test_no_match_logs_unmatched(self, session, seed_players):
        result = resolve_player_id(
            session, "TestPipe03", "Unknown Player",
            position="RB", team="???",
        )
        assert result is None

    def test_cached_mapping(self, session, seed_players):
        # First call creates mapping
        resolve_player_id(session, "TestPipe04", "Patrick Mahomes")
        session.flush()
        # Second call uses cache
        result = resolve_player_id(session, "TestPipe04", "Patrick Mahomes")
        assert result == "PFF001"


class TestIngestRankings:
    def test_ingests_matched_players(self, session, seed_players, sample_rankings_df):
        stats = ingest_rankings(session, sample_rankings_df, 2025, verbose=False)
        assert stats["matched"] == 2
        assert stats["unmatched"] == 1

    def test_maps_ranking_columns(self, session, seed_players, sample_rankings_df):
        ingest_rankings(session, sample_rankings_df, 2025, verbose=False)

        # Find baseline for Mahomes (should have been matched)
        mapping = session.get(PipelineIdMap, "MahomPa01")
        baseline = session.get(PlayerSeasonBaseline, f"{mapping.player_id}_2025")
        assert baseline is not None
        assert baseline.rankings_avg_overall == 2.0
        assert baseline.rankings_avg_positional == 1.0
        assert baseline.rankings_fpts_positional == 1
        assert baseline.adp_consensus == 2.5

    def test_computes_sharp_consensus(self, session, seed_players, sample_rankings_df):
        ingest_rankings(session, sample_rankings_df, 2025, verbose=False)

        mapping = session.get(PipelineIdMap, "MahomPa01")
        baseline = session.get(PlayerSeasonBaseline, f"{mapping.player_id}_2025")
        # Sharp consensus = mean(fpts=1, jj=2, hw=1, pff=2) = 1.5
        assert baseline.sharp_consensus_rank == 1.5
        assert baseline.rankings_source_count == 4

    def test_computes_divergence(self, session, seed_players, sample_rankings_df):
        ingest_rankings(session, sample_rankings_df, 2025, verbose=False)

        mapping = session.get(PipelineIdMap, "HillTy01")
        baseline = session.get(PlayerSeasonBaseline, f"{mapping.player_id}_2025")
        # Sharp = mean(3,4,2,3) = 3.0; ADP pos = 5; divergence = 5 - 3 = 2
        assert baseline.adp_divergence_rank == 2
        assert baseline.adp_divergence_flag == 0  # < 12

    def test_sets_divergence_flag(self, session, seed_players):
        """Test that large divergence sets the flag."""
        df = pd.DataFrame({
            "PLAYER NAME": ["Patrick Mahomes"],
            "PLAYER ID": ["MahomPa02"],
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

        mapping = session.get(PipelineIdMap, "MahomPa02")
        baseline = session.get(PlayerSeasonBaseline, f"{mapping.player_id}_2025")
        # Sharp = 1.0, ADP pos = 15, divergence = 14
        assert baseline.adp_divergence_rank == 14
        assert baseline.adp_divergence_flag == 1
