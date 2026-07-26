"""Ingest Reception Perception quarterback charting.

Three exports per season join on player — coverage/depth ("Basic Stats"), a field heat map, and
accuracy by route type. Columns are disjoint across the three, so every alias map is applied to
every row and whichever fields are present get set; there is no need to classify the files.

Two things make this ingest different from the WR and RB ones:

1. **No `Year` column.** The QB tables carry only `Player` plus metrics. Season therefore comes
   from the source page — parsed from the site export's `qb-<year>__` filename, or passed in
   explicitly. It is never defaulted: a mislabelled season here is indistinguishable from
   correct data once stored.
2. **Two headers in the heat map are transposed at source.** See INVERTED_HEADERS.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.ingest.rp_common import (
    build_name_index,
    clean_pct,
    detect_source,
    first_present,
    match_player,
    set_if_present,
)
from fantasy_data.models import RpQbSeason

_SEASON_IN_FILENAME = re.compile(r"^qb-(\d{4})__")


class RpQbSeasonUnknown(ValueError):
    """Raised when a QB export's season can be neither parsed nor supplied."""


# Coverage/depth view.
BASIC_ALIASES: dict[str, tuple[str, ...]] = {
    "man_tar_pct": ("Man Tar",),
    "man_sr": ("Man SR",),
    "zone_tar_pct": ("Zone Tar",),
    "zone_sr": ("Zone SR",),
    "short_tar_pct": ("SHORT Tar",),
    "short_sr": ("SHORT SR",),
    "intermediate_tar_pct": ("INTER Tar",),
    "intermediate_sr": ("INTER SR",),
    "deep_tar_pct": ("DEEP Tar",),
    "deep_sr": ("DEEP SR",),
}

# Field heat map. RP's spacing is inconsistent ("L <LOS-9SR" has no space before SR, "L 10-19 SR"
# does), so each field lists the spellings actually seen.
HEATMAP_ALIASES: dict[str, tuple[str, ...]] = {
    "left_los9_tar_pct": ("L. <LOS-9 %",),
    "left_los9_sr": ("L <LOS-9SR", "L <LOS-9 SR"),
    "mid_los9_tar_pct": ("MID <LOS-9 %",),
    "mid_los9_sr": ("M <LOS-9SR", "M <LOS-9 SR"),
    "right_los9_tar_pct": ("R. <LOS-9 %",),
    "right_los9_sr": ("R <LOS-9SR", "R <LOS-9 SR"),
    "left_10_19_tar_pct": ("L. 10-19 %",),
    "left_10_19_sr": ("L 10-19 SR",),
    "mid_10_19_tar_pct": ("MID 10-19 %",),
    "mid_10_19_sr": ("M 10-19 SR",),
    "right_10_19_tar_pct": ("R. 10-19 %",),
    "right_10_19_sr": ("R 10-19 SR",),
    "left_20plus_tar_pct": ("L. 20+ %",),
    "left_20plus_sr": ("L 20+ SR",),
    "right_20plus_tar_pct": ("R. 20+ %",),
    "right_20plus_sr": ("R 20+ SR",),
}

# The deep-middle pair arrives under each other's names, and mapping by header would put a
# success rate in a share field for one of nine zones — plausible-looking and undetectable
# downstream. Proven by the shares, which must sum to ~100 across the nine zones: read as
# labelled they average 147 (up to 184) across the 19 charted QBs; with these two exchanged
# every QB lands between 99.4 and 100.5. Verify again if RP ever fixes the export.
INVERTED_HEADERS: dict[str, tuple[str, ...]] = {
    "mid_20plus_tar_pct": ("M 20+ SR",),  # labelled SR, holds the target share
    "mid_20plus_sr": ("MID 20+ %",),  # labelled %, holds the success rate
}

# Accuracy by route type. RP's three-letter codes, expanded.
ROUTE_CODES = {
    "check": "CHK",
    "flat": "FLT",
    "comeback": "CBK",
    "out": "OUT",
    "corner": "CNR",
    "nine": "NIN",
    "post": "PST",
    "dig": "DIG",
    "curl": "CRL",
    "slant": "SLT",
    "screen": "SCR",
    "other": "OTH",
}
ROUTE_ALIASES: dict[str, tuple[str, ...]] = {}
for _name, _code in ROUTE_CODES.items():
    ROUTE_ALIASES[f"route_{_name}_tar_pct"] = (f"{_code} Tar",)
    ROUTE_ALIASES[f"route_{_name}_sr"] = (f"{_code} SR",)

ALL_ALIASES: dict[str, tuple[str, ...]] = {
    **BASIC_ALIASES,
    **HEATMAP_ALIASES,
    **INVERTED_HEADERS,
    **ROUTE_ALIASES,
}

# The nine heat-map shares, which must sum to ~100 per player. Used by the ingest's own check.
HEATMAP_SHARE_FIELDS = [
    f for f in ALL_ALIASES if f.endswith("_tar_pct") and ("los9" in f or "_10_19" in f or "20plus" in f)
]


def season_for_file(path: Path, override: int | None = None) -> int:
    """Resolve the season for a QB export, or raise.

    Never guesses. The QB tables have no Year column, so the only honest sources are the
    caller and the site export's filename.
    """
    if override is not None:
        return override
    match = _SEASON_IN_FILENAME.match(path.name)
    if match:
        return int(match.group(1))
    raise RpQbSeasonUnknown(
        f"Cannot determine the season for {path.name}: the QB exports carry no Year column and "
        f"the filename has no 'qb-<year>__' prefix. Pass --season explicitly."
    )


def ingest_rp_qb(
    session: Session,
    data_dir: str,
    season: int | None = None,
    verbose: bool = True,
) -> dict[str, int]:
    """Load QB charting into `rp_qb_season`, merging the three exports on player."""
    stats = {"records": 0, "unmatched": 0, "files": 0}
    now_iso = datetime.now(timezone.utc).isoformat()
    name_index, name_fallback = build_name_index(session, "QB")
    unmatched: list[str] = []
    touched: set[str] = set()

    base = Path(data_dir)
    position_dir = base / "QB"
    search_dir = position_dir if position_dir.is_dir() else base

    for csv_path in sorted(search_dir.glob("*.csv")):
        df = pd.read_csv(csv_path)
        if "Player" not in df.columns:
            continue

        file_season = season_for_file(csv_path, season)
        source = detect_source(csv_path.name)
        stats["files"] += 1
        if verbose:
            print(f"  {csv_path.name}: {len(df)} rows (season={file_season}, source={source})")

        for _, row in df.iterrows():
            name = str(row.get("Player", "")).strip().rstrip("*")
            if not name:
                continue

            player_id = match_player(name, name_index, name_fallback)
            if not player_id:
                stats["unmatched"] += 1
                unmatched.append(f"{name} ({file_season})")
                continue

            rp_qb_id = f"{player_id}_{file_season}"
            qb = session.get(RpQbSeason, rp_qb_id)
            if not qb:
                qb = RpQbSeason(
                    rp_qb_id=rp_qb_id,
                    player_id=player_id,
                    season=file_season,
                    is_prospect=0,
                    created_at=now_iso,
                )
                session.add(qb)

            for field, aliases in ALL_ALIASES.items():
                set_if_present(qb, field, clean_pct(first_present(row, *aliases)))

            qb.source = source
            qb.updated_at = now_iso
            touched.add(rp_qb_id)

    session.commit()
    stats["records"] = len(touched)

    if verbose:
        for name in sorted(set(unmatched)):
            print(f"    RP QB unmatched: {name}")
        print(
            f"\nRP QB ingest: {stats['records']} player-seasons from {stats['files']} file(s), {stats['unmatched']} unmatched"
        )
        _report_share_sums(session, touched, verbose=verbose)

    return stats


def _report_share_sums(session: Session, ids: set[str], verbose: bool = True) -> None:
    """Sanity-check that each player's nine heat-map shares sum to ~100.

    This is the check that caught RP's transposed deep-middle headers; leaving it in the ingest
    means the next transposition shows up as a number on screen rather than a quiet wrong value.
    """
    off = []
    for rp_qb_id in sorted(ids):
        qb = session.get(RpQbSeason, rp_qb_id)
        if qb is None:
            continue
        values = [getattr(qb, f) for f in HEATMAP_SHARE_FIELDS]
        if any(v is None for v in values):
            continue
        total = sum(values)
        if not 97.0 <= total <= 103.0:
            off.append((rp_qb_id, round(total, 1)))
    if verbose:
        if off:
            print(f"  ⚠ {len(off)} player(s) whose heat-map shares do not sum to ~100: {off[:5]}")
        else:
            print("  heat-map shares sum to ~100 for every player ✓")
