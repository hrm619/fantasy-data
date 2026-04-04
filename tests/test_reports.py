"""Tests for report modules."""

from fantasy_data.models import PlayerSeasonBaseline
from fantasy_data.reports.adp_divergence import get_adp_divergence
from fantasy_data.reports.rankings import get_player_rankings
from fantasy_data.reports.rankings_variance import get_rankings_variance
from fantasy_data.reports.trust_flags import get_trust_flags


class TestAdpDivergence:
    def test_returns_flagged_players(self, session, seed_players, seed_baselines):
        # Set up a divergence
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.sharp_consensus_rank = 3.0
        b.adp_positional_rank = 18
        b.adp_divergence_rank = 15
        b.adp_divergence_flag = 1
        session.commit()

        results = get_adp_divergence(session, 2024)
        assert len(results) == 1
        assert results[0]["player"] == "Tyreek Hill"
        assert results[0]["direction"] == "UNDER"

    def test_filters_by_position(self, session, seed_players, seed_baselines):
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.adp_divergence_rank = 15
        b.adp_divergence_flag = 1
        b.sharp_consensus_rank = 3.0
        session.commit()

        results = get_adp_divergence(session, 2024, position="QB")
        assert len(results) == 0

        results = get_adp_divergence(session, 2024, position="WR")
        assert len(results) == 1

    def test_no_divergence(self, session, seed_players, seed_baselines):
        results = get_adp_divergence(session, 2024)
        assert len(results) == 0


class TestPlayerRankings:
    def test_returns_source_breakdown(self, session, seed_players, seed_baselines):
        data = get_player_rankings(session, "MahomPa01", 2024)
        assert data is not None
        assert data["player"] == "Patrick Mahomes"
        assert data["sources"]["FantasyPoints (fpts)"] == 1
        assert data["sources"]["LateRound (jj)"] == 2
        assert data["source_count"] == 5

    def test_player_not_found(self, session):
        data = get_player_rankings(session, "NONEXISTENT", 2024)
        assert data is None


class TestRankingsVariance:
    def test_returns_variance_sorted(self, session, seed_players, seed_baselines):
        results = get_rankings_variance(session, 2024, min_sources=3)
        assert len(results) > 0
        # Results should be sorted by std_dev descending
        for i in range(len(results) - 1):
            assert results[i]["std_dev"] >= results[i + 1]["std_dev"]

    def test_filters_by_min_sources(self, session, seed_players, seed_baselines):
        results = get_rankings_variance(session, 2024, min_sources=6)
        assert len(results) == 0


class TestTrustFlags:
    def test_returns_uncertain_players(self, session, seed_players, seed_coaching, seed_baselines):
        from fantasy_data.compute.compute_trust_weights import compute_all_trust_weights
        compute_all_trust_weights(session, 2024, verbose=False)

        results = get_trust_flags(session, 2024)
        # Caleb Williams should be flagged (rookie + team change + new HC + new OC)
        names = [r["player"] for r in results]
        assert "Caleb Williams" in names

    def test_no_flags(self, session, seed_players, seed_baselines):
        results = get_trust_flags(session, 2024)
        assert len(results) == 0  # No flags set without running compute
