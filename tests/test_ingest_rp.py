"""Tests for Reception Perception classification and ingest.

Covers the two naming schemes, the position guard, and the two defects fixed alongside the
site-export work: falsy-zero assignment and the cross-season column rename.
"""

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fantasy_data.ingest.ingest_reception_perception import (
    _clean_int,
    _clean_pct,
    _detect_source,
    _first,
    _load_csvs,
    _merge_route_pct,
    _merge_tackle,
    _set,
    ingest_reception_perception,
)
from fantasy_data.ingest.rp_parse import (
    RPClassificationError,
    season_from_slug,
    classify_type,
    detect_position,
    is_prospect_file,
    matches_position,
    normalize_name,
)
from fantasy_data.models import Base, Player, WrReceptionPerception


def season_for_date(published_at: str) -> int:
    """Mirror of knowledge_base.seasons.season_for_date (separate repo, not importable).

    Kept here so the test can assert the two disagree — which is the whole reason profile
    seasons are parsed from the slug.
    """
    year, month = int(published_at[:4]), int(published_at[5:7])
    return year if month >= 3 else year - 1


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    yield db
    db.close()


class TestNormalizeName:
    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("WR Success Rate vs. Coverage Table 2024-25.csv", "wr success rate vs coverage table 2024 25"),
            ("wr-2024__success-rate-vs-coverage.csv", "wr 2024 success rate vs coverage"),
            ("WR Tackle Breaking data - 2023.csv", "wr tackle breaking data 2023"),
        ],
    )
    def test_both_schemes_normalize_to_shared_tokens(self, filename, expected):
        assert normalize_name(filename) == expected


class TestClassifyType:
    @pytest.mark.parametrize(
        "filename,expected",
        [
            # hand-downloaded
            ("WR Success Rate vs. Coverage Table 2024-25.csv", "coverage"),
            ("WR Success Rate by Route 2024-25.csv", "route_success"),
            ("WR Route Percentage 2024-25.csv", "route_pct"),
            ("WR Alignment Data 2024-25.csv", "alignment"),
            ("WR Contested Catch 2024-25.csv", "contested"),
            ("WR Tackle Breaking data 2024-25.csv", "tackle"),
            ("WR Target Data 2024-25.csv", "target"),
            # site exports
            ("wr-2025__success-rate-vs-coverage.csv", "coverage"),
            ("wr-2025__success-rate-by-route.csv", "route_success"),
            ("wr-2025__route-percentage.csv", "route_pct"),
            ("wr-2025__alignment-data.csv", "alignment"),
            ("wr-2025__contested-catch.csv", "contested"),
            ("wr-2025__tackle-breaking.csv", "tackle"),
            ("wr-2025__target.csv", "target"),
            # prospect exports carry no position token but still classify
            ("Target Data - 2026 Draft Prospects.csv", "target"),
        ],
    )
    def test_classifies_both_schemes(self, filename, expected):
        assert classify_type(filename) == expected

    def test_route_pct_and_route_success_never_collide(self):
        """These two files have byte-identical headers; only the name tells them apart."""
        assert classify_type("WR Route Percentage 2024-25.csv") == "route_pct"
        assert classify_type("WR Success Rate by Route 2024-25.csv") == "route_success"

    def test_unrelated_file_is_none(self):
        assert classify_type("WR RP Dynasty Rankings.csv") is None

    def test_ambiguous_name_raises_rather_than_guessing(self):
        with pytest.raises(RPClassificationError, match="multiple RP data types"):
            classify_type("Route Percentage and Success Rate by Route.csv")


class TestPositionGuard:
    def test_detects_declared_position(self):
        assert detect_position("WR Target Data 2024-25.csv") == "WR"
        assert detect_position("rb-2024__2024-25-nfl-rb-data.csv") == "RB"
        assert detect_position("qb-2024__basic-stats.csv") == "QB"

    def test_undeclared_position_is_none_not_a_guess(self):
        assert detect_position("Target Data - 2026 Draft Prospects.csv") is None

    def test_other_position_excluded_but_undeclared_allowed(self):
        assert matches_position("WR Target Data 2024-25.csv", "WR")
        assert not matches_position("rb-2024__2024-25-nfl-rb-data.csv", "WR")
        assert matches_position("Target Data - 2026 Draft Prospects.csv", "WR")

    def test_prospect_detection(self):
        assert is_prospect_file("Target Data - 2026 Draft Prospects.csv")
        assert not is_prospect_file("WR Target Data 2024-25.csv")


class TestLoadCsvsIsolatesPositions:
    def test_rb_file_does_not_contaminate_wr_frame(self, tmp_path):
        """The collision this guard exists for: same data type, different position, one dir."""
        (tmp_path / "WR Route Percentage 2024-25.csv").write_text("Year,Player,Screen\n2024,Real Receiver,10.0\n")
        (tmp_path / "rb-2024__route-percentage.csv").write_text("Year,Player,Screen\n2024,Some Runningback,90.0\n")
        df = _load_csvs(tmp_path, "route_pct", "WR")
        assert set(df["Player"]) == {"Real Receiver"}

    def test_reads_position_subdirectory(self, tmp_path):
        (tmp_path / "WR").mkdir()
        (tmp_path / "WR" / "wr-2025__target.csv").write_text("Year,Player,Catch Rate\n2025,Site Receiver,70.0\n")
        df = _load_csvs(tmp_path, "target", "WR")
        assert list(df["Player"]) == ["Site Receiver"]
        assert list(df["_source"]) == ["site"]

    def test_site_export_wins_over_hand_downloaded(self, tmp_path):
        (tmp_path / "WR Target Data 2024-25.csv").write_text("Year,Player,Catch Rate\n2024,Dup Player,60.0\n")
        (tmp_path / "wr-2024__target.csv").write_text("Year,Player,Catch Rate\n2024,Dup Player,65.0\n")
        df = _load_csvs(tmp_path, "target", "WR")
        assert len(df) == 1
        assert df.iloc[0]["Catch Rate"] == 65.0
        assert df.iloc[0]["_source"] == "site"

    def test_detect_source(self):
        assert _detect_source("wr-2024__target.csv") == "site"
        assert _detect_source("WR Target Data 2024-25.csv") == "csv-manual"


class TestSetPreservesZero:
    def test_zero_is_stored_not_discarded(self):
        rp = WrReceptionPerception(rp_id="x", player_id="p", season=2025)
        rp.two_plus_broken_tackle_pct = 12.5
        _set(rp, "two_plus_broken_tackle_pct", 0.0)
        assert rp.two_plus_broken_tackle_pct == 0.0

    def test_none_leaves_existing_value(self):
        rp = WrReceptionPerception(rp_id="x", player_id="p", season=2025)
        rp.two_plus_broken_tackle_pct = 12.5
        _set(rp, "two_plus_broken_tackle_pct", None)
        assert rp.two_plus_broken_tackle_pct == 12.5

    def test_zero_survives_a_real_merge(self):
        """A receiver who broke no tackles reads 0.0, not NULL."""
        rp = WrReceptionPerception(rp_id="x", player_id="p", season=2025)
        row = pd.Series({"Year": 2025, "Player": "A", "1 Broken Tackle": 0.0, "2+ Broken Tackle": 0.0})
        _merge_tackle(rp, row)
        assert rp.one_broken_tackle_pct == 0.0
        assert rp.two_plus_broken_tackle_pct == 0.0

    def test_zero_route_share_survives(self):
        rp = WrReceptionPerception(rp_id="x", player_id="p", season=2025)
        _merge_route_pct(rp, pd.Series({"Screen": 0.0, "Slant": 15.0}))
        assert rp.pct_screen == 0.0
        assert rp.pct_slant == 15.0


class TestCrossSeasonColumnRenames:
    def test_reads_2024_opportunities_column(self):
        rp = WrReceptionPerception(rp_id="x", player_id="p", season=2024)
        _merge_tackle(rp, pd.Series({"Opportunities": 12, "% of Routes": 5.5}))
        assert rp.tackle_break_opportunities == 12
        assert rp.in_space_pct_of_routes == 5.5
        assert rp.in_space_pct_of_catches is None

    def test_reads_2025_in_space_opportunities_column(self):
        rp = WrReceptionPerception(rp_id="x", player_id="p", season=2025)
        _merge_tackle(rp, pd.Series({"In Space Opportunities": 2, "% of Catches": 5.9}))
        assert rp.tackle_break_opportunities == 2
        assert rp.in_space_pct_of_catches == 5.9
        assert rp.in_space_pct_of_routes is None

    def test_the_two_denominators_never_share_a_column(self):
        """'% of Routes' and '% of Catches' measure different things; folding them would put a
        definitional break mid-column."""
        rp = WrReceptionPerception(rp_id="x", player_id="p", season=2025)
        _merge_tackle(rp, pd.Series({"% of Routes": 5.5}))
        _merge_tackle(rp, pd.Series({"% of Catches in space": 40.0}))
        assert rp.in_space_pct_of_routes == 5.5
        assert rp.in_space_pct_of_catches == 40.0

    def test_first_skips_missing_and_nan(self):
        row = pd.Series({"a": None, "b": float("nan"), "c": 7})
        assert _first(row, "a", "b", "c") == 7
        assert _first(row, "a", "b") is None


class TestCleaners:
    @pytest.mark.parametrize("raw,expected", [("86.1", 86.1), ("86.1%", 86.1), ("0.0", 0.0), ("", None), (None, None)])
    def test_clean_pct(self, raw, expected):
        assert _clean_pct(raw) == expected

    @pytest.mark.parametrize("raw,expected", [("12", 12), ("1,234", 1234), ("12.0", 12), ("", None), (None, None)])
    def test_clean_int(self, raw, expected):
        assert _clean_int(raw) == expected


class TestIngestEndToEnd:
    def _write(self, d, name, text):
        (d / name).write_text(text)

    def test_ingests_and_records_provenance(self, session, tmp_path):
        session.add(Player(player_id="AddiJo01", full_name="Jordan Addison", position="WR"))
        session.commit()

        self._write(
            tmp_path,
            "wr-2025__success-rate-vs-coverage.csv",
            "Player,Year,man atts.,Success Rate vs. Man,Routes\nJordan Addison,2025,182,75.8,309\n",
        )
        self._write(
            tmp_path,
            "wr-2025__tackle-breaking.csv",
            "Year,Player,In Space Opportunities,% of Catches,2+ Broken Tackle\n2025,Jordan Addison,2,5.9,0.0\n",
        )

        stats = ingest_reception_perception(session, str(tmp_path), verbose=False)

        assert stats["records"] == 1
        rp = session.get(WrReceptionPerception, "AddiJo01_2025")
        assert rp is not None
        assert rp.success_rate_man == 75.8
        assert rp.man_atts == 182
        assert rp.tackle_break_opportunities == 2
        assert rp.in_space_pct_of_catches == 5.9
        assert rp.two_plus_broken_tackle_pct == 0.0  # a real zero, not NULL
        assert rp.source == "site"
        assert rp.updated_at is not None

    def test_unmatched_player_is_counted_not_silently_dropped(self, session, tmp_path):
        self._write(
            tmp_path,
            "wr-2025__target.csv",
            "Year,Player,Catch Rate\n2025,Nobody Here,70.0\n",
        )
        stats = ingest_reception_perception(session, str(tmp_path), verbose=False)
        assert stats["records"] == 0
        assert stats["unmatched"] == 1

    def test_matches_across_punctuation_differences(self, session, tmp_path):
        """players stores pipeline-key names ('Jaxon SmithNjigba'); RP publishes hyphens."""
        session.add(Player(player_id="SmitJa06", full_name="Jaxon SmithNjigba", position="WR"))
        session.add(Player(player_id="StxxAm00", full_name="AmonRa St Brown", position="WR"))
        session.commit()
        self._write(
            tmp_path,
            "wr-2025__target.csv",
            "Year,Player,Catch Rate\n2025,Jaxon Smith-Njigba,70.0\n2025,Amon-Ra St. Brown,75.0\n",
        )
        stats = ingest_reception_perception(session, str(tmp_path), verbose=False)
        assert stats["unmatched"] == 0
        assert session.get(WrReceptionPerception, "SmitJa06_2025") is not None
        assert session.get(WrReceptionPerception, "StxxAm00_2025") is not None

    def test_fallback_refuses_to_guess_between_two_players(self, session, tmp_path):
        """Two people collapsing to the same key must stay unmatched, not pick one."""
        session.add(Player(player_id="A1", full_name="A.J. Brown", position="WR"))
        session.add(Player(player_id="A2", full_name="AJ Brown", position="RB"))
        session.commit()
        self._write(tmp_path, "wr-2025__target.csv", "Year,Player,Catch Rate\n2025,A-J Brown,70.0\n")
        stats = ingest_reception_perception(session, str(tmp_path), verbose=False)
        assert stats["unmatched"] == 1
        assert stats["records"] == 0

    def test_rerun_is_idempotent(self, session, tmp_path):
        session.add(Player(player_id="AddiJo01", full_name="Jordan Addison", position="WR"))
        session.commit()
        self._write(
            tmp_path,
            "wr-2025__target.csv",
            "Year,Player,Catch Rate\n2025,Jordan Addison,70.0\n",
        )
        ingest_reception_perception(session, str(tmp_path), verbose=False)
        ingest_reception_perception(session, str(tmp_path), verbose=False)
        assert session.query(WrReceptionPerception).count() == 1


class TestProfileSlugSeason:
    """Profile season comes from the slug, never the publication date."""

    @pytest.mark.parametrize(
        "slug,expected",
        [
            # pro seasons
            ("jordan-addison-2025-player-profile", (2025, "player")),
            ("a-j-brown-2024-player-profile", (2024, "player")),
            ("aaron-rodgers-2022-player-profile", (2022, "player")),
            # draft classes chart the PRIOR college season
            ("bhayshul-tuten-2025-prospect-profile", (2024, "prospect")),
            ("adam-randall-2026-prospect-profile", (2025, "prospect")),
            # RP's third slug shape — the 2024 QB draft class uses -nfl-draft-profile
            ("caleb-williams-2024-nfl-draft-profile", (2023, "prospect")),
            ("j-j-mccarthy-2024-nfl-draft-profile", (2023, "prospect")),
            ("michael-penix-jr-2024-nfl-draft-profile", (2023, "prospect")),
        ],
    )
    def test_season_and_kind_from_slug(self, slug, expected):
        assert season_from_slug(slug) == expected

    def test_publication_date_is_not_the_season(self):
        """The 2025 Addison profile was published 2026-07-13; it is 2025 content."""
        parsed = season_from_slug("jordan-addison-2025-player-profile")
        assert parsed is not None
        season, _ = parsed
        assert season == 2025
        assert season != season_for_date("2026-07-13")

    @pytest.mark.parametrize(
        "slug",
        ["player-profiles-2", "matt-harmons-dynasty-rankings-tool", "some-player-profile", "no-year-prospect-profile"],
    )
    def test_unparseable_slug_returns_none_rather_than_guessing(self, slug):
        assert season_from_slug(slug) is None
