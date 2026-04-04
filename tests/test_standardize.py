"""Tests for team, player, and coach name standardization."""

from fantasy_data.standardize import (
    standardize_team,
    standardize_player_name,
    standardize_coach_name,
    CANONICAL_TEAMS,
    TEAM_FULL_NAMES,
    TEAM_CITIES,
)


class TestStandardizeTeam:
    def test_canonical_unchanged(self):
        assert standardize_team("KC") == "KC"
        assert standardize_team("SF") == "SF"
        assert standardize_team("GB") == "GB"

    def test_common_variants(self):
        assert standardize_team("JAC") == "JAX"
        assert standardize_team("LA") == "LAR"
        assert standardize_team("OAK") == "LV"
        assert standardize_team("SD") == "LAC"
        assert standardize_team("STL") == "LAR"
        assert standardize_team("WSH") == "WAS"
        assert standardize_team("LVR") == "LV"

    def test_case_insensitive(self):
        assert standardize_team("kc") == "KC"
        assert standardize_team("jac") == "JAX"

    def test_strips_whitespace(self):
        assert standardize_team("  KC  ") == "KC"

    def test_none_returns_none(self):
        assert standardize_team(None) is None

    def test_empty_returns_none(self):
        assert standardize_team("") is None

    def test_unknown_passes_through(self):
        assert standardize_team("???") == "???"

    def test_all_32_canonical_teams_exist(self):
        assert len(CANONICAL_TEAMS) == 32

    def test_full_names_cover_all_teams(self):
        assert set(TEAM_FULL_NAMES.keys()) == CANONICAL_TEAMS

    def test_cities_cover_all_teams(self):
        assert set(TEAM_CITIES.keys()) == CANONICAL_TEAMS


class TestStandardizePlayerName:
    def test_removes_jr_suffix(self):
        assert standardize_player_name("Marvin Harrison Jr") == "marvin harrison"

    def test_removes_apostrophes(self):
        assert standardize_player_name("Ja'Marr Chase") == "jamarr chase"

    def test_removes_periods(self):
        assert standardize_player_name("D.K. Metcalf") == "dk metcalf"

    def test_collapses_whitespace(self):
        assert standardize_player_name("  Patrick  Mahomes  ") == "patrick mahomes"

    def test_removes_curly_apostrophe(self):
        assert standardize_player_name("Ja\u2019Marr Chase") == "jamarr chase"

    def test_removes_sr_suffix(self):
        assert standardize_player_name("Aaron Jones Sr") == "aaron jones"

    def test_removes_roman_numerals(self):
        assert standardize_player_name("Robert Griffin III") == "robert griffin"


class TestStandardizeCoachName:
    def test_title_cases(self):
        assert standardize_coach_name("andy reid") == "Andy Reid"

    def test_collapses_whitespace(self):
        assert standardize_coach_name("  Sean   McVay  ") == "Sean Mcvay"

    def test_none_returns_none(self):
        assert standardize_coach_name(None) is None

    def test_empty_returns_none(self):
        assert standardize_coach_name("") is None
