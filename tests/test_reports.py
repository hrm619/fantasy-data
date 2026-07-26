"""Tests for report modules."""

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.reports.adp_divergence import count_below_min_sources, get_adp_divergence
from fantasy_data.reports.rankings import get_player_rankings
from fantasy_data.reports.rankings_variance import get_rankings_variance
from fantasy_data.reports.trust_flags import get_trust_flags


class TestAdpDivergence:
    def test_returns_flagged_players(self, session, seed_players, seed_baselines):
        # Set up a divergence using positional fields
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.sharp_pos_rank = 3.0
        b.adp_positional_rank = 18
        b.adp_divergence_pos = 15.0
        b.adp_divergence_flag = 1
        session.commit()

        results = get_adp_divergence(session, 2024)
        assert len(results) == 1
        assert results[0]["player"] == "Tyreek Hill"
        assert results[0]["direction"] == "UNDER"

    def test_excludes_players_below_min_sources(self, session, seed_players, seed_baselines):
        # A 2-source consensus is a mean of two ranks, so it lands far from ADP on
        # variance rather than disagreement — and then sorts to the top.
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.sharp_pos_rank = 3.0
        b.adp_positional_rank = 40
        b.adp_divergence_pos = 37.0
        b.adp_divergence_flag = 1
        b.rankings_source_count = 2
        session.commit()

        assert get_adp_divergence(session, 2024) == []
        assert len(get_adp_divergence(session, 2024, min_sources=0)) == 1
        assert len(get_adp_divergence(session, 2024, min_sources=2)) == 1

    def test_min_sources_exclusions_are_counted_not_silent(self, session, seed_players, seed_baselines):
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.adp_divergence_pos = 37.0
        b.adp_divergence_flag = 1
        b.rankings_source_count = 2
        session.commit()

        assert count_below_min_sources(session, 2024) == 1
        assert count_below_min_sources(session, 2024, min_sources=0) == 0

    def test_well_sourced_players_survive_the_default_filter(self, session, seed_players, seed_baselines):
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.sharp_pos_rank = 3.0
        b.adp_positional_rank = 18
        b.adp_divergence_pos = 15.0
        b.adp_divergence_flag = 1
        b.rankings_source_count = 4
        session.commit()

        assert len(get_adp_divergence(session, 2024)) == 1

    def test_filters_by_position(self, session, seed_players, seed_baselines):
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.adp_divergence_pos = 15.0
        b.adp_divergence_flag = 1
        b.sharp_pos_rank = 3.0
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


class TestRankingsRequiresRankingData:
    """A baseline row exists for ~4x more players than any source ranks, so keying on the row's
    existence returned an all-null 'profile' for 795 players in 2026 alone."""

    def _seed(self, session, **ranking_fields):
        session.add(Player(player_id="P1", full_name="Test Player", position="WR", team="AAA"))
        session.add(PlayerSeasonBaseline(baseline_id="P1_2026", player_id="P1", season=2026, **ranking_fields))
        session.commit()

    def test_unranked_player_returns_none(self, session):
        self._seed(session)  # baseline row, no ranking data
        assert get_player_rankings(session, "P1", 2026) is None

    def test_ranked_player_still_returns_data(self, session):
        self._seed(session, sharp_pos_rank=4.0, rankings_source_count=4)
        data = get_player_rankings(session, "P1", 2026)
        assert data is not None
        assert data["player"] == "Test Player"

    def test_adp_only_player_still_returns_data(self, session):
        """Partial coverage is real coverage — don't require all three."""
        self._seed(session, adp_positional_rank=12)
        assert get_player_rankings(session, "P1", 2026) is not None
