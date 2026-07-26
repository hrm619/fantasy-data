"""Ingest Reception Perception run-concept charting for running backs.

One CSV per page (unlike WR, which splits seven data types across tabs), so there is no file
classification to do — every RB export is the same wide table.

The pro and prospect exports **rename every metric**: the 2024-25 NFL table says
`G/P Success%`, `Under Center Att%`, `Unblocked Def%`, `Pass Block Success%`; the 2026 prospect
table says `G/P SR`, `Under Center%`, `Unblocked%`, `Pass Block SR`. The prospect table also
carries an extra `OVR SR` the pro table lacks. `COLUMN_ALIASES` therefore maps each field to
every name RP has used for it, and `first_present` takes whichever is there — reading a single
name would silently NULL half the corpus.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.ingest.rp_common import (
    build_name_index,
    player_positions,
    clean_pct,
    detect_source,
    first_present,
    match_player,
    set_if_present,
)
from fantasy_data.ingest.rp_parse import matches_position
from fantasy_data.models import RpRbSeason

# field -> the column names RP has used for it, most recent first.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "overall_success_pct": ("OVR SR",),
    "gun_pistol_att_pct": ("Gun/Pistol Att%", "Gun / Pistol%", "Gun/Pistol%"),
    "gun_pistol_success_pct": ("G/P Success%", "G/P SR"),
    "under_center_att_pct": ("Under Center Att%", "Under Center%"),
    "under_center_success_pct": ("U/C Succes%", "U/C Success%", "U/C SR"),  # 'Succes%' is RP's typo
    "man_gap_att_pct": ("Man/Gap Att%",),
    "man_gap_success_pct": ("M/G Success%", "M/G SR"),
    "outside_man_gap_pct": ("Outside M/G%",),
    "outside_man_gap_success_pct": ("Out M/G Success%", "Out M/G SR"),
    "inside_man_gap_pct": ("Inside M/G%",),
    "inside_man_gap_success_pct": ("In M/G Success%", "In M/G SR"),
    "zone_att_pct": ("Zone Att%",),
    "zone_success_pct": ("Zone Success%", "Zone SR"),
    "outside_zone_pct": ("Outside Zone%",),
    "outside_zone_success_pct": ("Out Zone Success%", "Out Zone SR"),
    "inside_zone_pct": ("Inside Zone%",),
    "inside_zone_success_pct": ("In Zone Success%", "In Zone SR"),
    "outside_att_pct": ("Outside Att%",),
    "outside_success_pct": ("Out Success%", "Out SR"),
    "inside_att_pct": ("Inside Att%",),
    "inside_success_pct": ("In Success%", "In SR"),
    "loaded_box_pct": ("Loaded Box%",),
    "loaded_box_success_pct": ("Loaded Success%", "Loaded SR"),
    "unblocked_def_pct": ("Unblocked Def%", "Unblocked%"),
    "unblocked_def_success_pct": ("UB Success%", "UB SR"),
    "broken_tackle_pct": ("Broken Tkl%",),
    "explosive_play_pct": ("Explosive Plays%", "Explosive%"),
    "run_stuff_pct": ("Run Stuff%",),
    "pass_block_success_pct": ("Pass Block Success%", "Pass Block SR"),
}


def _rb_csvs(data_dir: Path) -> list[Path]:
    """Every RB export under `data_dir`, preferring a `RB/` subdirectory when present.

    Files that declare a different position are skipped. Without that guard, pointing this at
    the WR export directory globbed all 35 WR files and wrote 141 all-NULL rows keyed on real
    WR player_ids — no error, no warning, and they squat on `(player_id, season)`. The WR
    ingest has always had this guard; RB and QB were missing it.
    """
    position_dir = data_dir / "RB"
    search_dir = position_dir if position_dir.is_dir() else data_dir
    return [p for p in sorted(search_dir.glob("*.csv")) if matches_position(p.name, "RB")]


def ingest_rp_rb(session: Session, data_dir: str, verbose: bool = True) -> dict[str, int]:
    """Load RB run-concept charting into `rp_rb_season`, one row per player-season."""
    stats = {"records": 0, "unmatched": 0, "position_mismatch": 0, "files": 0}
    now_iso = datetime.now(timezone.utc).isoformat()
    name_index, name_fallback = build_name_index(session, "RB")
    positions = player_positions(session)
    unmatched: list[str] = []
    # Count player-seasons, not CSV rows: a player appearing in two exports is one record.
    touched: set[str] = set()

    for csv_path in _rb_csvs(Path(data_dir)):
        df = pd.read_csv(csv_path)
        if "Player" not in df.columns or "Year" not in df.columns:
            if verbose:
                print(f"  skipping {csv_path.name}: no Player/Year columns")
            continue

        stem = csv_path.stem.lower()
        is_prospect = 1 if ("prospect" in stem or "draft" in stem) else 0
        source = detect_source(csv_path.name)
        stats["files"] += 1
        if verbose:
            print(f"  {csv_path.name}: {len(df)} rows (prospect={is_prospect}, source={source})")

        for _, row in df.iterrows():
            name = str(row.get("Player", "")).strip().rstrip("*")
            year = row.get("Year")
            if not name or pd.isna(year):
                continue
            season = int(year)

            player_id = match_player(name, name_index, name_fallback)
            if not player_id:
                stats["unmatched"] += 1
                unmatched.append(f"{name} ({season})")
                continue
            matched_position = positions.get(player_id, "")
            if matched_position and matched_position != "RB":
                stats["position_mismatch"] += 1
                unmatched.append(f"{name} ({season}) -> {player_id} is a {matched_position}, not RB")
                continue

            rp_rb_id = f"{player_id}_{season}"
            rb = session.get(RpRbSeason, rp_rb_id)
            if not rb:
                rb = RpRbSeason(
                    rp_rb_id=rp_rb_id,
                    player_id=player_id,
                    season=season,
                    is_prospect=is_prospect,
                    created_at=now_iso,
                )
                session.add(rb)

            team = row.get("Team")
            if team is not None and not pd.isna(team):
                set_if_present(rb, "team", str(team).strip())

            for field, aliases in COLUMN_ALIASES.items():
                set_if_present(rb, field, clean_pct(first_present(row, *aliases)))

            rb.source = source
            rb.updated_at = now_iso
            touched.add(rp_rb_id)

    session.commit()
    stats["records"] = len(touched)

    if verbose:
        for name in unmatched:
            print(f"    RP RB unmatched: {name}")
        print(
            f"\nRP RB ingest: {stats['records']} records from {stats['files']} file(s), {stats['unmatched']} unmatched"
        )

    return stats
