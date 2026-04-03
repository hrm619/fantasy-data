"""Tests for compute modules (trust weights, baselines, competition)."""

import pytest
from fantasy_data.models import Player, PlayerSeasonBaseline, CoachingStaff
from fantasy_data.compute.compute_trust_weights import (
    compute_trust_weight,
    compute_all_trust_weights,
)
from fantasy_data.compute.compute_baselines import (
    compute_weighted_baseline,
    compute_all_baselines,
)
from fantasy_data.compute.compute_competition import (
    compute_route_overlap,
    compute_team_competition,
)


class TestComputeTrustWeight:
    """Test the pure trust weight computation function."""

    def test_full_continuity(self):
        w = compute_trust_weight(
            team_change_flag=0, hc_continuity=1, oc_continuity=1,
            injury_concern_flag=0, rookie_flag=0,
        )
        assert w == 1.0

    def test_oc_change(self):
        w = compute_trust_weight(
            team_change_flag=0, hc_continuity=1, oc_continuity=0,
            injury_concern_flag=0, rookie_flag=0,
        )
        assert w == 0.40

    def test_hc_change(self):
        w = compute_trust_weight(
            team_change_flag=0, hc_continuity=0, oc_continuity=1,
            injury_concern_flag=0, rookie_flag=0,
        )
        assert w == 0.65

    def test_team_change(self):
        w = compute_trust_weight(
            team_change_flag=1, hc_continuity=1, oc_continuity=1,
            injury_concern_flag=0, rookie_flag=0,
        )
        assert w == 0.20

    def test_rookie(self):
        w = compute_trust_weight(
            team_change_flag=0, hc_continuity=1, oc_continuity=1,
            injury_concern_flag=0, rookie_flag=1,
        )
        assert w == 0.50

    def test_all_flags(self):
        """Team change + HC + OC + injury + rookie = floor at 0.05."""
        w = compute_trust_weight(
            team_change_flag=1, hc_continuity=0, oc_continuity=0,
            injury_concern_flag=1, rookie_flag=1,
        )
        assert w == 0.05

    def test_injury_flag(self):
        w = compute_trust_weight(
            team_change_flag=0, hc_continuity=1, oc_continuity=1,
            injury_concern_flag=1, rookie_flag=0,
        )
        assert w == 0.55

    def test_oc_and_hc_change(self):
        w = compute_trust_weight(
            team_change_flag=0, hc_continuity=0, oc_continuity=0,
            injury_concern_flag=0, rookie_flag=0,
        )
        assert w == pytest.approx(0.26, abs=0.01)


class TestComputeAllTrustWeights:
    def test_updates_baselines(self, session, seed_players, seed_coaching, seed_baselines):
        stats = compute_all_trust_weights(session, 2024, verbose=False)
        assert stats["updated"] == 5

        # KC: HC continuity=1, OC continuity=0 → weight = 0.40
        b_mahomes = session.get(PlayerSeasonBaseline, "PFF001_2024")
        assert b_mahomes.data_trust_weight == pytest.approx(0.40, abs=0.01)
        assert b_mahomes.oc_continuity == 0

        # MIA: full continuity → weight = 1.0
        b_hill = session.get(PlayerSeasonBaseline, "PFF002_2024")
        assert b_hill.data_trust_weight == 1.0

        # CHI: HC=0, OC=0, rookie=1, team_change=1 (no injury)
        # 1.0 * 0.40 * 0.65 * 0.20 = 0.052, min(0.052, 0.50) = 0.052
        b_caleb = session.get(PlayerSeasonBaseline, "PFF005_2024")
        assert b_caleb.data_trust_weight == pytest.approx(0.052, abs=0.001)
        assert b_caleb.projection_uncertain_flag == 1


class TestComputeWeightedBaseline:
    def test_single_season(self, session, seed_players, seed_baselines):
        # Set trust weight so weighted average works
        b = session.get(PlayerSeasonBaseline, "PFF002_2024")
        b.data_trust_weight = 1.0
        session.commit()

        result = compute_weighted_baseline(session, "PFF002", 2025)
        assert result["target_share"] == pytest.approx(0.28)
        assert result["fpts_per_game_ppr"] == pytest.approx(17.5)

    def test_no_history(self, session, seed_players):
        result = compute_weighted_baseline(session, "PFF001", 2025)
        assert result == {}


class TestComputeRouteOverlap:
    def test_same_route(self):
        assert compute_route_overlap("OUTSIDE", "OUTSIDE") == 0.9

    def test_different_route(self):
        assert compute_route_overlap("OUTSIDE", "SLOT") == 0.3

    def test_none_route(self):
        assert compute_route_overlap(None, "SLOT") == 0.0
