"""Tests for coaching continuity derivation."""

from fantasy_data.compute.compute_coaching_continuity import (
    compute_coaching_continuity,
    continuity_flags,
)
from fantasy_data.models import CoachingStaff


def _staff(team="LV", season=2025, hc="Pete Carroll", oc="Chip Kelly", play_caller=None):
    return CoachingStaff(
        staff_id=f"{team}_{season}",
        team=team,
        season=season,
        head_coach=hc,
        offensive_coordinator=oc,
        play_caller=play_caller,
    )


class TestContinuityFlags:
    def test_unchanged_staff_is_continuous(self):
        prev = _staff(hc="Andy Reid", oc="Matt Nagy", play_caller="Andy Reid")
        curr = _staff(season=2026, hc="Andy Reid", oc="Matt Nagy", play_caller="Andy Reid")
        flags = continuity_flags(curr, prev)
        assert flags["hc_continuity_flag"] == 1
        assert flags["oc_continuity_flag"] == 1

    def test_new_head_coach_breaks_hc_continuity(self):
        prev = _staff(season=2024, hc="Antonio Pierce")
        curr = _staff(season=2025, hc="Pete Carroll")
        assert continuity_flags(curr, prev)["hc_continuity_flag"] == 0

    def test_new_oc_under_same_play_caller_is_not_a_scheme_change(self):
        # KC 2026: Nagy -> Bieniemy, but Reid calls plays either way.
        prev = _staff(team="KC", season=2025, hc="Andy Reid", oc="Matt Nagy", play_caller="Andy Reid")
        curr = _staff(team="KC", season=2026, hc="Andy Reid", oc="Eric Bieniemy", play_caller="Andy Reid")
        flags = continuity_flags(curr, prev)
        assert flags["oc_continuity_flag"] == 1
        assert flags["oc_basis"] == "play_caller"

    def test_same_oc_taking_over_play_calling_is_a_scheme_change(self):
        # CAR 2026: identical names, but play-calling moved Canales -> Idzik.
        prev = _staff(team="CAR", season=2025, hc="Dave Canales", oc="Brad Idzik", play_caller="Dave Canales")
        curr = _staff(team="CAR", season=2026, hc="Dave Canales", oc="Brad Idzik", play_caller="Brad Idzik")
        flags = continuity_flags(curr, prev)
        assert flags["oc_continuity_flag"] == 0
        assert flags["oc_basis"] == "play_caller"

    def test_falls_back_to_oc_title_when_play_caller_unknown(self):
        prev = _staff(season=2025, oc="Greg Roman", play_caller=None)
        curr = _staff(season=2026, oc="Mike McDaniel", play_caller=None)
        flags = continuity_flags(curr, prev)
        assert flags["oc_continuity_flag"] == 0
        assert flags["oc_basis"] == "oc_title_fallback"

    def test_falls_back_when_only_one_season_knows_the_play_caller(self):
        prev = _staff(season=2025, oc="Joe Brady", play_caller=None)
        curr = _staff(season=2026, oc="Joe Brady", play_caller="Joe Brady")
        flags = continuity_flags(curr, prev)
        assert flags["oc_basis"] == "oc_title_fallback"
        assert flags["oc_continuity_flag"] == 1

    def test_first_observed_season_is_treated_as_continuous(self):
        flags = continuity_flags(_staff(), None)
        assert flags["hc_continuity_flag"] == 1
        assert flags["oc_continuity_flag"] == 1
        assert flags["oc_basis"] == "no_prior_season"


class TestComputeCoachingContinuity:
    def test_recomputes_flags_against_prior_season(self, session):
        # The real LV bug: 2024 staff carried into 2025 with continuity=1.
        session.add(_staff(team="LV", season=2024, hc="Antonio Pierce", oc="Luke Getsy"))
        wrong = _staff(team="LV", season=2025, hc="Pete Carroll", oc="Chip Kelly")
        wrong.hc_continuity_flag = 1
        wrong.oc_continuity_flag = 1
        session.add(wrong)
        session.commit()

        stats = compute_coaching_continuity(session, 2025, verbose=False)
        assert stats["hc_changes"] == 1
        assert wrong.hc_continuity_flag == 0
        assert wrong.oc_continuity_flag == 0

    def test_tenure_increments_on_continuity_and_resets_on_change(self, session):
        prior = _staff(team="KC", season=2025, hc="Andy Reid", oc="Matt Nagy", play_caller="Andy Reid")
        prior.hc_year_with_team = 13
        prior.oc_year_with_team = 3
        session.add(prior)
        session.add(_staff(team="KC", season=2026, hc="Andy Reid", oc="Eric Bieniemy", play_caller="Andy Reid"))
        session.add(_staff(team="LV", season=2025, hc="Antonio Pierce", oc="Luke Getsy"))
        session.add(_staff(team="LV", season=2026, hc="Klint Kubiak", oc="Andrew Janocko"))
        session.commit()

        compute_coaching_continuity(session, 2026, verbose=False)
        kc = session.get(CoachingStaff, "KC_2026")
        lv = session.get(CoachingStaff, "LV_2026")
        assert kc.hc_year_with_team == 14
        assert kc.oc_year_with_team == 4  # play caller unchanged, so the system carries on
        assert lv.hc_year_with_team == 1
        assert lv.oc_year_with_team == 1

    def test_counts_the_basis_used_per_team(self, session):
        session.add(_staff(team="KC", season=2025, hc="Andy Reid", oc="Matt Nagy", play_caller="Andy Reid"))
        session.add(_staff(team="KC", season=2026, hc="Andy Reid", oc="Eric Bieniemy", play_caller="Andy Reid"))
        session.add(_staff(team="LAC", season=2025, hc="Jim Harbaugh", oc="Greg Roman"))
        session.add(_staff(team="LAC", season=2026, hc="Jim Harbaugh", oc="Mike McDaniel"))
        session.commit()

        stats = compute_coaching_continuity(session, 2026, verbose=False)
        assert stats["play_caller_basis"] == 1
        assert stats["oc_title_fallback"] == 1
        assert stats["oc_changes"] == 1  # LAC only; KC's play caller never changed
