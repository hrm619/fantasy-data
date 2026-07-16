"""Tests for compute modules (trust weights, baselines, competition)."""

import pytest
from fantasy_data.models import PlayerSeasonBaseline
from fantasy_data.compute.compute_trust_weights import (
    compute_trust_weight,
    compute_all_trust_weights,
)
from fantasy_data.compute.compute_baselines import (
    compute_all_baselines,
    compute_weighted_baseline,
)
from fantasy_data.compute.compute_competition import (
    compute_route_overlap,
)


class TestComputeTrustWeight:
    """Test the pure trust weight computation function."""

    def test_full_continuity(self):
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=1,
            oc_continuity=1,
            qb_continuity=1,
            injury_concern_flag=0,
            rookie_flag=0,
        )
        assert w == 1.0

    def test_oc_change(self):
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=1,
            oc_continuity=0,
            qb_continuity=1,
            injury_concern_flag=0,
            rookie_flag=0,
        )
        assert w == 0.40

    def test_hc_change(self):
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=0,
            oc_continuity=1,
            qb_continuity=1,
            injury_concern_flag=0,
            rookie_flag=0,
        )
        assert w == 0.65

    def test_team_change(self):
        w = compute_trust_weight(
            team_change_flag=1,
            hc_continuity=1,
            oc_continuity=1,
            qb_continuity=1,
            injury_concern_flag=0,
            rookie_flag=0,
        )
        assert w == 0.20

    def test_rookie(self):
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=1,
            oc_continuity=1,
            qb_continuity=1,
            injury_concern_flag=0,
            rookie_flag=1,
        )
        assert w == 0.50

    def test_all_flags(self):
        """Team change + HC + OC + QB + injury + rookie = floor at 0.05."""
        w = compute_trust_weight(
            team_change_flag=1,
            hc_continuity=0,
            oc_continuity=0,
            qb_continuity=0,
            injury_concern_flag=1,
            rookie_flag=1,
        )
        assert w == 0.05

    def test_injury_flag(self):
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=1,
            oc_continuity=1,
            qb_continuity=1,
            injury_concern_flag=1,
            rookie_flag=0,
        )
        assert w == 0.55

    def test_oc_and_hc_change(self):
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=0,
            oc_continuity=0,
            qb_continuity=1,
            injury_concern_flag=0,
            rookie_flag=0,
        )
        assert w == pytest.approx(0.26, abs=0.01)

    # --- QB continuity tests ---

    def test_qb_change_wr(self):
        """WR with QB change gets full ×0.50 penalty."""
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=1,
            oc_continuity=1,
            qb_continuity=0,
            injury_concern_flag=0,
            rookie_flag=0,
            position="WR",
        )
        assert w == 0.50

    def test_qb_change_te(self):
        """TE gets same full ×0.50 penalty as WR."""
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=1,
            oc_continuity=1,
            qb_continuity=0,
            injury_concern_flag=0,
            rookie_flag=0,
            position="TE",
        )
        assert w == 0.50

    def test_qb_change_rb(self):
        """RB gets reduced ×0.75 penalty."""
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=1,
            oc_continuity=1,
            qb_continuity=0,
            injury_concern_flag=0,
            rookie_flag=0,
            position="RB",
        )
        assert w == 0.75

    def test_qb_change_qb_unaffected(self):
        """QB position is not penalized by their own change."""
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=1,
            oc_continuity=1,
            qb_continuity=0,
            injury_concern_flag=0,
            rookie_flag=0,
            position="QB",
        )
        assert w == 1.0

    def test_qb_and_oc_change_wr(self):
        """OC + QB changes stack multiplicatively for WR."""
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=1,
            oc_continuity=0,
            qb_continuity=0,
            injury_concern_flag=0,
            rookie_flag=0,
            position="WR",
        )
        assert w == pytest.approx(0.40 * 0.50, abs=0.01)

    def test_qb_and_oc_change_rb(self):
        """OC + QB changes for RB: ×0.40 × ×0.75 = 0.30."""
        w = compute_trust_weight(
            team_change_flag=0,
            hc_continuity=1,
            oc_continuity=0,
            qb_continuity=0,
            injury_concern_flag=0,
            rookie_flag=0,
            position="RB",
        )
        assert w == pytest.approx(0.40 * 0.75, abs=0.01)


class TestComputeAllTrustWeights:
    def test_updates_baselines(self, session, seed_players, seed_coaching, seed_baselines):
        stats = compute_all_trust_weights(session, 2024, verbose=False)
        assert stats["updated"] == 5

        # KC: HC continuity=1, OC continuity=0 → weight = 0.40
        b_mahomes = session.get(PlayerSeasonBaseline, "MahomPa01_2024")
        assert b_mahomes.data_trust_weight == pytest.approx(0.40, abs=0.01)
        assert b_mahomes.oc_continuity == 0

        # MIA: full continuity → weight = 1.0
        b_hill = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        assert b_hill.data_trust_weight == 1.0

        # CHI: HC=0, OC=0, rookie=1, team_change=1 (no injury)
        # 1.0 * 0.40 * 0.65 * 0.20 = 0.052, min(0.052, 0.50) = 0.052
        b_caleb = session.get(PlayerSeasonBaseline, "WillCa01_2024")
        assert b_caleb.data_trust_weight == pytest.approx(0.052, abs=0.001)
        assert b_caleb.projection_uncertain_flag == 1


class TestComputeWeightedBaseline:
    def test_single_season(self, session, seed_players, seed_baselines):
        # Set trust weight so weighted average works
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.data_trust_weight = 1.0
        session.commit()

        result = compute_weighted_baseline(session, "HillTy01", 2025)
        assert result["target_share"] == pytest.approx(0.28)
        assert result["fpts_per_game_ppr"] == pytest.approx(17.5)

    def test_no_history(self, session, seed_players):
        result = compute_weighted_baseline(session, "MahomPa01", 2025)
        assert result == {}


class TestMissingTrustWeight:
    def test_zero_weight_is_honoured_not_treated_as_missing(self, session, seed_players, seed_baselines):
        # `or 0.5` would turn a real 0.0 into 0.5 — a 10x error on a field that
        # multiplies through every blended value.
        a = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        a.data_trust_weight = 0.0
        a.target_share = 0.40
        session.add(
            PlayerSeasonBaseline(
                baseline_id="HillTy01_2023",
                player_id="HillTy01",
                season=2023,
                data_trust_weight=1.0,
                target_share=0.10,
            )
        )
        session.commit()

        result = compute_weighted_baseline(session, "HillTy01", 2025)
        # 2024 contributes nothing at weight 0, so the blend is purely 2023.
        assert result["target_share"] == pytest.approx(0.10)

    def test_missing_weight_falls_back_and_is_counted(self, session, seed_players, seed_baselines):
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.data_trust_weight = None
        session.commit()

        stats = compute_all_baselines(session, 2025, verbose=False)
        assert stats["missing_trust_weight"] >= 1


class TestRecomputeBaselines:
    def _blend_inputs(self, session):
        """One prior season the blend can see, plus a target row to write into."""
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.data_trust_weight = 1.0
        b.target_share = 0.20
        session.commit()

    def test_rerun_without_recompute_keeps_a_stale_blend(self, session, seed_players, seed_baselines):
        # The trap: a blend computed before a lookback season's data landed
        # survives a plain re-run, because no-overwrite skips the populated field.
        self._blend_inputs(session)
        compute_all_baselines(session, 2025, verbose=False)
        assert session.get(PlayerSeasonBaseline, "HillTy01_2025").target_share == pytest.approx(0.20)

        # A lookback season's value changes...
        session.get(PlayerSeasonBaseline, "HillTy01_2024").target_share = 0.30
        session.commit()

        compute_all_baselines(session, 2025, verbose=False)
        assert session.get(PlayerSeasonBaseline, "HillTy01_2025").target_share == pytest.approx(0.20)

    def test_recompute_rebuilds_the_blend(self, session, seed_players, seed_baselines):
        self._blend_inputs(session)
        compute_all_baselines(session, 2025, verbose=False)
        session.get(PlayerSeasonBaseline, "HillTy01_2024").target_share = 0.30
        session.commit()

        compute_all_baselines(session, 2025, verbose=False, recompute=True)
        assert session.get(PlayerSeasonBaseline, "HillTy01_2025").target_share == pytest.approx(0.30)

    def test_recompute_rebuilds_derived_composites(self, session, seed_players, seed_baselines):
        # wopr derives from the shares, so it goes stale with them.
        b = session.get(PlayerSeasonBaseline, "HillTy01_2024")
        b.data_trust_weight = 1.0
        b.target_share, b.air_yards_share = 0.20, 0.10
        session.commit()
        compute_all_baselines(session, 2025, verbose=False)
        first = session.get(PlayerSeasonBaseline, "HillTy01_2025").wopr

        b.target_share = 0.40
        session.commit()
        compute_all_baselines(session, 2025, verbose=False, recompute=True)
        rebuilt = session.get(PlayerSeasonBaseline, "HillTy01_2025").wopr
        assert rebuilt != pytest.approx(first)
        assert rebuilt == pytest.approx(1.5 * 0.40 + 0.7 * 0.10)

    def test_recompute_leaves_non_aggregable_fields_alone(self, session, seed_players, seed_baselines):
        # Rankings/ADP are not the blend's to clear.
        self._blend_inputs(session)
        compute_all_baselines(session, 2025, verbose=False)
        target = session.get(PlayerSeasonBaseline, "HillTy01_2025")
        target.adp_consensus = 12.0
        session.commit()

        compute_all_baselines(session, 2025, verbose=False, recompute=True)
        assert session.get(PlayerSeasonBaseline, "HillTy01_2025").adp_consensus == 12.0


class TestComputeRouteOverlap:
    def test_same_route(self):
        assert compute_route_overlap("OUTSIDE", "OUTSIDE") == 0.9

    def test_different_route(self):
        assert compute_route_overlap("OUTSIDE", "SLOT") == 0.3

    def test_none_route(self):
        assert compute_route_overlap(None, "SLOT") == 0.0
