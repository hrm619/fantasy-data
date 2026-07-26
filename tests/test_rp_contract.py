"""Contract tests for the Reception Perception exports.

The question these answer: **is the site export still the same artifact as the CSVs we already
trust, and does it still have the columns the ingest reads?**

That mattered enough to verify by hand once — all seven WR 2024 exports against the
hand-downloaded CSVs, headers byte-identical, 4,292 cells compared, zero mismatches. A one-off
check proves today; these tests re-prove it on every future re-fetch, which is when a
silent site-side change would actually bite. RP has already renamed columns between seasons
(`Opportunities` -> `In Space Opportunities`, `% of Routes` -> `% of Catches`), so this is a
demonstrated failure mode, not a hypothetical one.

Two layers:

  * fixture-backed (always runs, CI): pins the exact header of each data type and proves the
    two naming schemes parse to identical database rows.
  * integration (opt-in, `-m integration`): the real cell-by-cell comparison against
    `data-dev/`, skipped when those files aren't present.

Fixture values and player names are synthetic; the **headers are verbatim** from the real 2024
exports. The header is what a site-side change breaks, and inventing the numbers keeps a
subscriber dataset out of the repository.
"""

import csv
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fantasy_data.ingest.ingest_reception_perception import ingest_reception_perception
from fantasy_data.ingest.rp_parse import classify_type
from fantasy_data.models import Base, Player, WrReceptionPerception

FIXTURES = Path(__file__).parent / "fixtures" / "rp"
REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_SITE_DIR = REPO_ROOT / "data-dev" / "rp-site" / "csv" / "WR"
REAL_HAND_DIR = REPO_ROOT / "data-dev" / "Reception Perception WR Deep Dive"

# The header of each data type, verbatim from the 2024 exports. A rename upstream fails here
# with the old and new names side by side, rather than silently NULLing a column downstream.
EXPECTED_HEADERS: dict[str, list[str]] = {
    "coverage": [
        "Player",
        "Year",
        "man atts.",
        "Success Rate vs. Man",
        "zone atts.",
        "Success Rate vs. Zone",
        "dbl atts.",
        "Success Rate vs. Double",
        "press atts.",
        "Success Rate vs. Press",
        "Routes",
        "% Press",
        "% Man",
        "% Zone",
        "% Doubled",
    ],
    "route_pct": [
        "Year",
        "Player",
        "Total Routes",
        "Screen",
        "Slant",
        "Curl",
        "Dig",
        "Post",
        "Nine",
        "Corner",
        "Out",
        "Comeback",
        "Flat",
        "Other",
    ],
    "route_success": [
        "Year",
        "Player",
        "Total Routes",
        "Screen",
        "Slant",
        "Curl",
        "Dig",
        "Post",
        "Nine",
        "Corner",
        "Out",
        "Comeback",
        "Flat",
        "Other",
    ],
    "alignment": ["Year", "Player", "Snaps", "Outside", "LWR", "RWR", "Slot", "Backfield", "Behind LOS", "On LOS"],
    "contested": ["Year", "Player", "Targets", "Contested targets", "Contested Target Rate", "Contested Catch Rate"],
    "tackle": [
        "Year",
        "Player",
        "Opportunities",
        "% of Routes",
        "1st Contact Drop",
        "1 Broken Tackle",
        "2+ Broken Tackle",
    ],
    "target": [
        "Year",
        "Player",
        "Total Routes",
        "Route Target Rate",
        "Route Catch Rate",
        "Targets",
        "Catch Rate",
        "Drop Rate",
    ],
}

# Every field the merge functions populate from these seven files. If a column is renamed
# upstream and the mapping isn't updated, the field goes NULL — this is the list that proves
# it didn't.
CONTRACT_FIELDS = [
    "routes_charted",
    "success_rate_man",
    "success_rate_zone",
    "success_rate_press",
    "success_rate_double",
    "pct_man",
    "pct_zone",
    "pct_press",
    "pct_doubled",
    "man_atts",
    "zone_atts",
    "double_atts",
    "press_atts",
    "pct_screen",
    "pct_slant",
    "pct_curl",
    "pct_dig",
    "pct_post",
    "pct_nine",
    "pct_corner",
    "pct_out",
    "pct_comeback",
    "pct_flat",
    "pct_other",
    "success_rate_screen",
    "success_rate_slant",
    "success_rate_curl",
    "success_rate_dig",
    "success_rate_post",
    "success_rate_nine",
    "success_rate_corner",
    "success_rate_out",
    "success_rate_comeback",
    "success_rate_flat",
    "success_rate_other",
    "pct_outside",
    "pct_slot",
    "pct_backfield",
    "pct_lwr",
    "pct_rwr",
    "pct_behind_los",
    "pct_on_los",
    "snaps_charted",
    "route_target_rate",
    "route_catch_rate",
    "catch_rate_rp",
    "drop_rate_rp",
    "targets_rp",
    "contested_target_rate_rp",
    "contested_catch_rate_rp",
    "contested_targets_rp",
    "tackle_break_opportunities",
    "first_contact_drop_pct",
    "one_broken_tackle_pct",
    "two_plus_broken_tackle_pct",
    "in_space_pct_of_routes",
]


def _read_header(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return next(csv.reader(fh))


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _ingest_fixture_dir(directory: Path) -> dict[str, dict]:
    """Ingest one fixture directory and return {player_id: {field: value}}."""
    db = _session()
    try:
        db.add(Player(player_id="FixtAl01", full_name="Fixture Alpha", position="WR"))
        db.add(Player(player_id="FixtBr01", full_name="Fixture Bravo", position="WR"))
        db.commit()
        ingest_reception_perception(db, str(directory), verbose=False)
        return {
            rp.player_id: {field: getattr(rp, field) for field in CONTRACT_FIELDS}
            for rp in db.query(WrReceptionPerception).all()
        }
    finally:
        db.close()


class TestHeaderContract:
    @pytest.mark.parametrize("scheme", ["hand", "site"])
    def test_every_fixture_matches_its_pinned_header(self, scheme):
        files = sorted((FIXTURES / scheme).glob("*.csv"))
        assert files, f"no {scheme} fixtures found"
        for path in files:
            data_type = classify_type(path.name)
            assert data_type is not None, f"{path.name} no longer classifies"
            assert _read_header(path) == EXPECTED_HEADERS[data_type], f"header drift in {path.name}"

    def test_all_seven_types_are_covered_by_both_schemes(self):
        for scheme in ("hand", "site"):
            found = {classify_type(p.name) for p in (FIXTURES / scheme).glob("*.csv")}
            assert found == set(EXPECTED_HEADERS), f"{scheme} fixtures cover {found}"


class TestSchemesAreOneArtifact:
    def test_both_naming_schemes_parse_to_identical_rows(self):
        """The whole premise of the site fetcher: it emits what the CSVs already contained."""
        hand = _ingest_fixture_dir(FIXTURES / "hand")
        site = _ingest_fixture_dir(FIXTURES / "site")
        assert set(hand) == set(site) == {"FixtAl01", "FixtBr01"}
        for player_id in hand:
            assert hand[player_id] == site[player_id], f"parsed values differ for {player_id}"

    def test_every_contract_field_is_actually_populated(self):
        """Guards the mapping, not just the header: a renamed column would leave these NULL."""
        rows = _ingest_fixture_dir(FIXTURES / "site")
        unset = [f for f, v in rows["FixtAl01"].items() if v is None]
        assert not unset, f"fields the fixtures should populate but didn't: {unset}"

    def test_zero_values_survive_the_round_trip(self):
        """Fixture Bravo has genuine 0.0 readings; they must not come back as None."""
        rows = _ingest_fixture_dir(FIXTURES / "site")
        bravo = rows["FixtBr01"]
        assert bravo["pct_screen"] == 0.0
        assert bravo["two_plus_broken_tackle_pct"] == 0.0
        assert bravo["drop_rate_rp"] == 0.0
        assert bravo["success_rate_double"] == 0.0


@pytest.mark.integration
@pytest.mark.skipif(
    not REAL_SITE_DIR.is_dir() or not REAL_HAND_DIR.is_dir(),
    reason="requires the gitignored data-dev/ captures",
)
class TestRealExportsMatchHandDownloads:
    """The full cell-by-cell comparison, against the real captures when they're present.

    This is the check that catches a site-side change after a re-fetch. It compares only the
    2024 season, where both sources exist and were verified equal; 2025 is deliberately out of
    scope because RP renamed a tackle-breaking column there, which is a real divergence rather
    than a regression.
    """

    def test_all_seven_types_agree_cell_for_cell(self):
        compared = mismatched = 0
        details: list[str] = []

        for site_path in sorted(REAL_SITE_DIR.glob("wr-2024__*.csv")):
            data_type = classify_type(site_path.name)
            hand_paths = [
                p for p in REAL_HAND_DIR.glob("*.csv") if classify_type(p.name) == data_type and "2024-25" in p.stem
            ]
            assert hand_paths, f"no hand-downloaded counterpart for {site_path.name}"

            with site_path.open(encoding="utf-8-sig", newline="") as fh:
                site_rows = list(csv.DictReader(fh))
            with hand_paths[0].open(encoding="utf-8-sig", newline="") as fh:
                hand_rows = list(csv.DictReader(fh))

            assert list(site_rows[0]) == list(hand_rows[0]), f"header drift in {data_type}"

            hand_by_player = {r["Player"].strip(): r for r in hand_rows}
            for row in site_rows:
                counterpart = hand_by_player.get(row["Player"].strip())
                if counterpart is None:
                    continue
                for column, value in row.items():
                    compared += 1
                    if (value or "").strip() != (counterpart.get(column) or "").strip():
                        mismatched += 1
                        if len(details) < 5:
                            details.append(
                                f"{data_type}/{row['Player']}/{column}: {value!r} != {counterpart[column]!r}"
                            )

        assert compared > 1000, f"only compared {compared} cells — captures look incomplete"
        assert mismatched == 0, f"{mismatched}/{compared} cells differ; first few: {details}"
