"""Shared helpers for the Reception Perception ingests (WR route charting, RB run concepts, QB).

Extracted so the three position ingests share one copy of the parsing and player-matching rules
rather than three drifting ones. Two of these encode fixes that were wrong for years, and
duplicating them is exactly how a fix ends up applied in one place and not the others:

  * `set_if_present` — only `None` means "the source said nothing"; a charted 0.0 is real data.
  * `match_player`   — RP's punctuation and the pipeline key dict's do not agree.
"""

from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player
from fantasy_data.standardize import standardize_player_name

# Precedence when the same player-season arrives from both capture schemes (highest wins).
# The site table is live; a hand-downloaded CSV is a point-in-time copy of it.
SOURCE_PRECEDENCE = {"csv-manual": 0, "site": 1}


def detect_source(filename: str) -> str:
    """Which capture produced a file. `fetch_rp.py` names exports `<page-key>__<type>.csv`."""
    return "site" if "__" in Path(filename).stem else "csv-manual"


def clean_pct(val) -> float | None:
    """Convert a percentage cell to float, tolerating '86.1', '86.1%' and blanks.

    RP is inconsistent about the sign even within one position: the pro RB export writes
    '68.97%' while the prospect export writes '66.3' — and its `Under Center%` column writes
    '0.0%'. Strip and parse rather than assuming either form.
    """
    if val is None or pd.isna(val):
        return None
    s = str(val).strip().rstrip("%")
    try:
        return float(s)
    except ValueError:
        return None


def clean_int(val) -> int | None:
    """Convert a count cell to int, tolerating '1,234', '12.0' and blanks."""
    if val is None or pd.isna(val):
        return None
    try:
        return int(float(str(val).strip().replace(",", "")))
    except ValueError:
        return None


def set_if_present(row_obj, field: str, value) -> None:
    """Assign a parsed value, treating only None as 'the source said nothing'.

    The original idiom was `obj.field = clean_pct(...) or obj.field`, which discards a genuine
    **0.0** because it is falsy — a charted zero silently became the old value, or NULL. Zero is
    a real and common reading in this data (a receiver who broke no tackles, a back who never
    lined up under center, a route type never run), so it has to survive.
    """
    if value is not None:
        setattr(row_obj, field, value)


def first_present(row, *names):
    """Return the first present, non-null cell among `names`.

    RP renames columns between seasons and between the pro and prospect exports of the same
    position — tackle-breaking counts are "Opportunities" in the 2024 WR export and "In Space
    Opportunities" in 2025; the RB pro export says "G/P Success%" where the prospect export says
    "G/P SR". Reading only one name silently NULLs the other file.
    """
    for name in names:
        val = row.get(name)
        if val is not None and not pd.isna(val):
            return val
    return None


def collapse_name(name: str) -> str:
    """Reduce a name to letters and digits only.

    `players.full_name` comes from the pipeline's key dict, which strips hyphens and periods
    ("Jaxon SmithNjigba", "AmonRa St Brown"), while RP publishes them ("Jaxon Smith-Njigba",
    "Amon-Ra St. Brown"). `standardize_player_name` preserves hyphens, so the two can never
    match exactly — which silently dropped two of the most-charted WRs in the dataset.
    """
    return "".join(ch for ch in name.lower() if ch.isalnum())


def build_name_index(session: Session, position: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return (exact index, punctuation-insensitive fallback index).

    Built once per ingest. A naive lookup runs two full table scans per *unmatched* name, which
    is O(players x names) on a miss — and misses are the common case for draft prospects.

    The fallback drops any key that collapses to more than one distinct player, so it can only
    ever resolve an unambiguous punctuation difference. It never guesses between two people.
    """
    exact: dict[str, str] = {}
    collapsed: dict[str, set[str]] = {}

    players = session.query(Player).all()
    for p in players:
        exact.setdefault(standardize_player_name(p.full_name), p.player_id)
        collapsed.setdefault(collapse_name(p.full_name), set()).add(p.player_id)
    for p in players:
        if p.position == position:
            exact[standardize_player_name(p.full_name)] = p.player_id

    unambiguous = {key: next(iter(ids)) for key, ids in collapsed.items() if len(ids) == 1}
    return exact, unambiguous


def match_player(name: str, index: dict[str, str], fallback: dict[str, str] | None = None) -> str | None:
    """Match an RP player name to a pipeline player_id: exact first, then punctuation-insensitive."""
    clean = name.strip().rstrip("*")
    hit = index.get(standardize_player_name(clean))
    if hit is not None:
        return hit
    return (fallback or {}).get(collapse_name(clean))
