"""Tests for the Reception Perception RB run-concept ingest.

The risk here is the alias map: RP renames every metric between its pro and prospect exports
(`G/P Success%` vs `G/P SR`), so a field mapped to only one spelling goes silently NULL for half
the corpus. These tests pin both spellings of every field.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fantasy_data.ingest.ingest_rp_rb import COLUMN_ALIASES, ingest_rp_rb
from fantasy_data.models import Base, Player, RpRbSeason, WrReceptionPerception

# Verbatim headers from the real exports (data-dev/rp-site/csv/RB/).
PRO_HEADER = (
    "Player,Team,Year,Gun/Pistol Att%,G/P Success%,Under Center Att%,U/C Succes%,Man/Gap Att%,"
    "M/G Success%,Outside M/G%,Out M/G Success%,Inside M/G%,In M/G Success%,Zone Att%,Zone Success%,"
    "Outside Zone%,Out Zone Success%,Inside Zone%,In Zone Success%,Outside Att%,Out Success%,"
    "Inside Att%,In Success%,Loaded Box%,Loaded Success%,Unblocked Def%,UB Success%,Broken Tkl%,"
    "Explosive Plays%,Run Stuff%,Pass Block Success%"
)
PRO_ROW = (
    "Bijan Robinson,ATL,2024,68.97%,67.50%,30.17%,68.57%,22.41%,76.92%,2.59%,100.00%,19.83%,73.91%,"
    "77.59%,64.44%,56.90%,66.67%,20.69%,58.33%,59.48%,68.12%,40.52%,65.96%,23.28%,66.67%,16.38%,"
    "52.63%,29.31%,19.85%,19.83%,91.67%"
)

PROSPECT_HEADER = (
    "Player,Team,Year,OVR SR,Gun / Pistol%,G/P SR,Under Center%,U/C SR,Man/Gap Att%,M/G SR,"
    "Outside M/G%,Out M/G SR,Inside M/G%,In M/G SR,Zone Att%,Zone SR,Outside Zone%,Out Zone SR,"
    "Inside Zone%,In Zone SR,Outside Att%,Out SR,Inside Att%,In SR,Loaded Box%,Loaded SR,Unblocked%,"
    "UB SR,Broken Tkl%,Explosive%,Run Stuff%,Pass Block SR"
)
PROSPECT_ROW = (
    "Kaelon Black,Indiana,2025,66.3,100.0,66.3,0.0%,0.0,88.8,66.2,16.3,84.6,72.5,62.1,11.3,66.7,"
    "10.0,62.5,1.3,100.0,26.3,76.2,73.8,62.7,28.8,52.2,8.8,14.3,19.6,13.3,5.0,61.5"
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Player(player_id="RobiBi01", full_name="Bijan Robinson", position="RB"))
    db.add(Player(player_id="BlacKa01", full_name="Kaelon Black", position="RB"))
    db.commit()
    yield db
    db.close()


def write(directory, name, header, row):
    (directory / name).write_text(f"{header}\n{row}\n")


class TestProExport:
    def test_maps_every_metric(self, session, tmp_path):
        write(tmp_path, "rb-2024__2024-25-nfl-rb-data.csv", PRO_HEADER, PRO_ROW)
        stats = ingest_rp_rb(session, str(tmp_path), verbose=False)

        assert stats["records"] == 1 and stats["unmatched"] == 0
        rb = session.get(RpRbSeason, "RobiBi01_2024")
        assert rb is not None
        assert rb.team == "ATL"
        assert rb.is_prospect == 0
        assert rb.source == "site"
        # Percent signs stripped, stored 0-100.
        assert rb.gun_pistol_att_pct == 68.97
        assert rb.gun_pistol_success_pct == 67.50
        assert rb.under_center_success_pct == 68.57  # 'U/C Succes%' — RP's typo
        assert rb.outside_man_gap_success_pct == 100.0
        assert rb.zone_att_pct == 77.59
        assert rb.loaded_box_pct == 23.28
        assert rb.unblocked_def_success_pct == 52.63
        assert rb.broken_tackle_pct == 29.31
        assert rb.explosive_play_pct == 19.85
        assert rb.run_stuff_pct == 19.83
        assert rb.pass_block_success_pct == 91.67

    def test_pro_export_has_no_overall_success_rate(self, session, tmp_path):
        """Only the prospect table carries OVR SR; it is NULL for pros, not derived."""
        write(tmp_path, "rb-2024__2024-25-nfl-rb-data.csv", PRO_HEADER, PRO_ROW)
        ingest_rp_rb(session, str(tmp_path), verbose=False)
        assert session.get(RpRbSeason, "RobiBi01_2024").overall_success_pct is None


class TestProspectExport:
    def test_maps_the_renamed_columns(self, session, tmp_path):
        write(tmp_path, "rb-prospects-2026__rb-prospect-data-2025-26.csv", PROSPECT_HEADER, PROSPECT_ROW)
        stats = ingest_rp_rb(session, str(tmp_path), verbose=False)

        assert stats["records"] == 1
        rb = session.get(RpRbSeason, "BlacKa01_2025")
        assert rb is not None
        assert rb.is_prospect == 1
        assert rb.team == "Indiana"  # college, not an NFL club
        assert rb.overall_success_pct == 66.3
        # Every one of these arrives under a DIFFERENT header than the pro export.
        assert rb.gun_pistol_att_pct == 100.0  # 'Gun / Pistol%'
        assert rb.gun_pistol_success_pct == 66.3  # 'G/P SR'
        assert rb.man_gap_success_pct == 66.2  # 'M/G SR'
        assert rb.unblocked_def_pct == 8.8  # 'Unblocked%'
        assert rb.explosive_play_pct == 13.3  # 'Explosive%'
        assert rb.pass_block_success_pct == 61.5  # 'Pass Block SR'

    def test_zero_readings_survive(self, session, tmp_path):
        """Kaelon Black never lined up under center: 0.0, not NULL."""
        write(tmp_path, "rb-prospects-2026__rb-prospect-data-2025-26.csv", PROSPECT_HEADER, PROSPECT_ROW)
        ingest_rp_rb(session, str(tmp_path), verbose=False)
        rb = session.get(RpRbSeason, "BlacKa01_2025")
        assert rb.under_center_att_pct == 0.0
        assert rb.under_center_success_pct == 0.0


class TestAliasCoverage:
    def test_every_field_resolves_in_at_least_one_real_export(self):
        """No field may be mapped only to a spelling neither real export uses."""
        real_columns = set(PRO_HEADER.split(",")) | set(PROSPECT_HEADER.split(","))
        unresolved = [f for f, aliases in COLUMN_ALIASES.items() if not (set(aliases) & real_columns)]
        assert not unresolved, f"fields whose aliases match no real column: {unresolved}"

    def test_every_real_metric_column_is_mapped(self):
        """No column in either export is silently dropped."""
        identity = {"Player", "Team", "Year"}
        mapped = {alias for aliases in COLUMN_ALIASES.values() for alias in aliases}
        for header in (PRO_HEADER, PROSPECT_HEADER):
            missing = [c for c in header.split(",") if c not in identity and c not in mapped]
            assert not missing, f"unmapped columns: {missing}"


class TestIsolationAndIdempotence:
    def test_does_not_touch_the_wr_table(self, session, tmp_path):
        """RB charting is a different measurement; it must not write route-charting rows."""
        write(tmp_path, "rb-2024__2024-25-nfl-rb-data.csv", PRO_HEADER, PRO_ROW)
        ingest_rp_rb(session, str(tmp_path), verbose=False)
        assert session.query(WrReceptionPerception).count() == 0

    def test_rerun_is_idempotent(self, session, tmp_path):
        write(tmp_path, "rb-2024__2024-25-nfl-rb-data.csv", PRO_HEADER, PRO_ROW)
        ingest_rp_rb(session, str(tmp_path), verbose=False)
        ingest_rp_rb(session, str(tmp_path), verbose=False)
        assert session.query(RpRbSeason).count() == 1

    def test_reads_the_rb_subdirectory(self, session, tmp_path):
        (tmp_path / "RB").mkdir()
        write(tmp_path / "RB", "rb-2024__2024-25-nfl-rb-data.csv", PRO_HEADER, PRO_ROW)
        assert ingest_rp_rb(session, str(tmp_path), verbose=False)["records"] == 1

    def test_unmatched_player_counted_not_dropped(self, session, tmp_path):
        write(tmp_path, "rb-2024__x.csv", PRO_HEADER, PRO_ROW.replace("Bijan Robinson", "Nobody Here"))
        stats = ingest_rp_rb(session, str(tmp_path), verbose=False)
        assert stats["records"] == 0 and stats["unmatched"] == 1


class TestDirectoryAndPositionGuards:
    def test_wr_exports_in_the_directory_are_ignored(self, session, tmp_path):
        """Pointing this at the WR export directory used to write 141 all-NULL RB rows keyed on
        real WR player_ids — no error, no warning."""
        write(tmp_path, "rb-2024__2024-25-nfl-rb-data.csv", PRO_HEADER, PRO_ROW)
        (tmp_path / "WR Target Data 2024-25.csv").write_text("Year,Player,Catch Rate\n2024,Some Receiver,70.0\n")

        stats = ingest_rp_rb(session, str(tmp_path), verbose=False)

        assert stats["files"] == 1
        assert stats["records"] == 1

    def test_a_name_resolving_to_another_position_is_refused(self, session, tmp_path):
        session.add(Player(player_id="WrGuy001", full_name="Wideout Person", position="WR"))
        session.commit()
        write(tmp_path, "rb-2024__x.csv", PRO_HEADER, PRO_ROW.replace("Bijan Robinson", "Wideout Person"))

        stats = ingest_rp_rb(session, str(tmp_path), verbose=False)

        assert stats["records"] == 0 and stats["position_mismatch"] == 1
        assert session.query(RpRbSeason).count() == 0

    def test_records_counts_player_seasons_not_csv_rows(self, session, tmp_path):
        """The same player-season across two exports is one record, not two."""
        write(tmp_path, "rb-2024__a.csv", PRO_HEADER, PRO_ROW)
        write(tmp_path, "rb-2024__b.csv", PRO_HEADER, PRO_ROW)

        stats = ingest_rp_rb(session, str(tmp_path), verbose=False)

        assert stats["files"] == 2
        assert stats["records"] == 1
        assert session.query(RpRbSeason).count() == 1
