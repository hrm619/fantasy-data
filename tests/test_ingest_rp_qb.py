"""Tests for the Reception Perception QB ingest.

Two hazards dominate: the QB exports carry no `Year` column, and RP ships the deep-middle
heat-map pair under each other's headers.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fantasy_data.ingest.ingest_rp_qb import (
    ALL_ALIASES,
    HEATMAP_SHARE_FIELDS,
    RpQbSeasonUnknown,
    ingest_rp_qb,
    season_for_file,
)
from fantasy_data.models import Base, Player, RpQbSeason

# Verbatim headers and Matthew Stafford's real row from data-dev/rp-site/csv/QB/.
BASIC_HEADER = "Player,Man Tar,Man SR,Zone Tar,Zone SR,SHORT Tar,SHORT SR,INTER Tar,INTER SR,DEEP Tar,DEEP SR"
BASIC_ROW = "Matthew Stafford,42.2%,73.0%,57.8%,77.1%,66.4%,80.7%,23.2%,63.3%,10.4%,68.2%"

HEATMAP_HEADER = (
    "Player,L. <LOS-9 %,L <LOS-9SR,MID <LOS-9 %,M <LOS-9SR,R. <LOS-9 %,R <LOS-9SR,"
    "L. 10-19 %,L 10-19 SR,MID 10-19 %,M 10-19 SR,R. 10-19 %,R 10-19 SR,"
    "L. 20+ %,L 20+ SR,M 20+ SR,MID 20+ %,R. 20+ %,R 20+ SR"
)
HEATMAP_ROW = (
    "Matthew Stafford,11.9%,84.0%,39.84%,76.5%,14.2%,90.0%,2.8%,50.0%,12.8%,66.7%,7.6%,62.5%,"
    "3.8%,75.0%,2.4%,80.0%,4.3%,55.6%"
)

ROUTE_HEADER = (
    "Player,CHK Tar,CHK SR,FLT Tar,FLT SR,CBK Tar,CBK SR,OUT Tar,OUT SR,CNR Tar,CNR SR,"
    "NIN Tar,NIN SR,PST Tar,PST SR,DIG Tar,DIG SR,CRL Tar,CRL SR,SLT Tar,SLT SR,"
    "SCR Tar,SCR SR,OTH Tar,OTH SR"
)
ROUTE_ROW = (
    "Matthew Stafford,6.3%,84.6%,13.5%,82.1%,2.9%,83.3%,17.4%,83.3%,3.9%,62.5%,6.3%,61.5%,"
    "5.8%,58.3%,4.4%,77.8%,18.8%,76.9%,8.7%,61.1%,10.6%,100.0%,1.5%,0.0%"
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Player(player_id="StafMa00", full_name="Matthew Stafford", position="QB"))
    db.commit()
    yield db
    db.close()


def write_all(directory):
    (directory / "qb-2024__basic-stats.csv").write_text(f"{BASIC_HEADER}\n{BASIC_ROW}\n")
    (directory / "qb-2024__heat-map-data.csv").write_text(f"{HEATMAP_HEADER}\n{HEATMAP_ROW}\n")
    (directory / "qb-2024__accuracy-by-route-data.csv").write_text(f"{ROUTE_HEADER}\n{ROUTE_ROW}\n")


class TestSeasonResolution:
    def test_parsed_from_the_site_export_filename(self, tmp_path):
        assert season_for_file(tmp_path / "qb-2024__basic-stats.csv") == 2024

    def test_explicit_override_wins(self, tmp_path):
        assert season_for_file(tmp_path / "qb-2024__basic-stats.csv", 2025) == 2025

    def test_refuses_to_guess_when_unknowable(self, tmp_path):
        """No Year column and no year in the name — fail loudly, never default."""
        with pytest.raises(RpQbSeasonUnknown, match="no Year column"):
            season_for_file(tmp_path / "qb_data.csv")

    def test_ingest_propagates_the_failure(self, session, tmp_path):
        (tmp_path / "qb_data.csv").write_text(f"{BASIC_HEADER}\n{BASIC_ROW}\n")
        with pytest.raises(RpQbSeasonUnknown):
            ingest_rp_qb(session, str(tmp_path), verbose=False)


class TestTransposedHeatmapHeaders:
    """RP ships the deep-middle pair under each other's names."""

    def test_share_and_rate_are_read_from_the_swapped_columns(self, session, tmp_path):
        write_all(tmp_path)
        ingest_rp_qb(session, str(tmp_path), verbose=False)
        qb = session.get(RpQbSeason, "StafMa00_2024")
        # 'M 20+ SR' holds 2.4 — that is the share, not a 2.4% success rate.
        assert qb.mid_20plus_tar_pct == 2.4
        # 'MID 20+ %' holds 80.0 — that is the rate.
        assert qb.mid_20plus_sr == 80.0

    def test_the_nine_shares_sum_to_100(self, session, tmp_path):
        """The check that proved the transposition: read as labelled this sums to ~177."""
        write_all(tmp_path)
        ingest_rp_qb(session, str(tmp_path), verbose=False)
        qb = session.get(RpQbSeason, "StafMa00_2024")
        total = sum(getattr(qb, f) for f in HEATMAP_SHARE_FIELDS)
        assert 99.0 <= total <= 101.0, f"heat-map shares sum to {total}"

    def test_mid_deep_values_are_not_interchanged_by_accident(self, session, tmp_path):
        """Guard the direction: a share must not land in the rate field."""
        write_all(tmp_path)
        ingest_rp_qb(session, str(tmp_path), verbose=False)
        qb = session.get(RpQbSeason, "StafMa00_2024")
        assert qb.mid_20plus_tar_pct < qb.mid_20plus_sr
        # ...and it should sit in the same range as its left/right siblings.
        assert qb.mid_20plus_tar_pct < 10.0
        assert qb.left_20plus_tar_pct < 10.0 and qb.right_20plus_tar_pct < 10.0


class TestThreeExportsMerge:
    def test_all_three_views_land_on_one_row(self, session, tmp_path):
        write_all(tmp_path)
        stats = ingest_rp_qb(session, str(tmp_path), verbose=False)

        assert stats["records"] == 1 and stats["files"] == 3
        assert session.query(RpQbSeason).count() == 1
        qb = session.get(RpQbSeason, "StafMa00_2024")
        assert qb.man_tar_pct == 42.2 and qb.man_sr == 73.0  # basic
        assert qb.left_los9_tar_pct == 11.9 and qb.mid_los9_sr == 76.5  # heat map
        assert qb.route_curl_tar_pct == 18.8 and qb.route_screen_sr == 100.0  # routes

    def test_zero_success_rate_is_preserved(self, session, tmp_path):
        """Stafford went 0-for on 'other' routes: 0.0, not NULL."""
        write_all(tmp_path)
        ingest_rp_qb(session, str(tmp_path), verbose=False)
        assert session.get(RpQbSeason, "StafMa00_2024").route_other_sr == 0.0

    def test_rerun_is_idempotent(self, session, tmp_path):
        write_all(tmp_path)
        ingest_rp_qb(session, str(tmp_path), verbose=False)
        ingest_rp_qb(session, str(tmp_path), verbose=False)
        assert session.query(RpQbSeason).count() == 1

    def test_coverage_and_depth_shares_each_sum_to_100(self, session, tmp_path):
        write_all(tmp_path)
        ingest_rp_qb(session, str(tmp_path), verbose=False)
        qb = session.get(RpQbSeason, "StafMa00_2024")
        assert 99.0 <= qb.man_tar_pct + qb.zone_tar_pct <= 101.0
        assert 99.0 <= qb.short_tar_pct + qb.intermediate_tar_pct + qb.deep_tar_pct <= 101.0


class TestAliasCoverage:
    def test_every_real_column_is_mapped(self):
        identity = {"Player"}
        mapped = {alias for aliases in ALL_ALIASES.values() for alias in aliases}
        for header in (BASIC_HEADER, HEATMAP_HEADER, ROUTE_HEADER):
            missing = [c for c in header.split(",") if c not in identity and c not in mapped]
            assert not missing, f"unmapped columns: {missing}"

    def test_no_field_maps_only_to_a_nonexistent_column(self):
        real = set(BASIC_HEADER.split(",")) | set(HEATMAP_HEADER.split(",")) | set(ROUTE_HEADER.split(","))
        unresolved = [f for f, aliases in ALL_ALIASES.items() if not (set(aliases) & real)]
        assert not unresolved, f"fields matching no real column: {unresolved}"

    def test_nine_heatmap_share_fields(self):
        assert len(HEATMAP_SHARE_FIELDS) == 9
