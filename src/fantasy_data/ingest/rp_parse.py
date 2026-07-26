"""Pure filename classification for Reception Perception CSV exports.

No I/O, no DB — just "what is this file?", so the rules are testable in isolation.

Two naming schemes have to resolve to the same seven data types:

    hand-downloaded   "WR Success Rate vs. Coverage Table 2024-25.csv"
    site export       "wr-2024__success-rate-vs-coverage.csv"   (scripts/fetch_rp.py)

Both normalize to a space-separated lowercase string, so one token set covers both.

Why this is a module and not a substring check at the call site: **`Route Percentage` and
`Success Rate by Route` have byte-identical headers** (`Year, Player, Total Routes, Screen,
Slant, …, Other`). One holds the share of routes run, the other the success rate on them. If a
filename is classified wrongly, nothing downstream can detect it — the columns parse, the
values are plausible percentages, and route-running rates land in the route-mix fields. The
filename is the *only* discriminator, so classification errors here must fail loudly.
"""

from __future__ import annotations

import re
from pathlib import Path

# Canonical data type -> the token that identifies it in either naming scheme.
# No token is a substring of another; `classify_type` enforces that no file matches two.
TYPE_TOKENS: dict[str, str] = {
    "coverage": "success rate vs coverage",
    "route_success": "success rate by route",
    "route_pct": "route percentage",
    "alignment": "alignment",
    "contested": "contested catch",
    "tackle": "tackle breaking",
    "target": "target",
}

POSITIONS = ("WR", "RB", "QB")


class RPClassificationError(ValueError):
    """Raised when a filename cannot be resolved to exactly one data type."""


def normalize_name(filename: str) -> str:
    """Lowercase a filename to space-separated words, dropping the extension.

    Collapses the punctuation the two schemes differ on — `-`, `_`, `.` — so that
    "WR Success Rate vs. Coverage Table 2024-25" and "wr-2024__success-rate-vs-coverage"
    both contain the token "success rate vs coverage".
    """
    stem = Path(filename).stem
    return " ".join(re.sub(r"[^a-z0-9]+", " ", stem.lower()).split())


def classify_type(filename: str) -> str | None:
    """Return the canonical data type for a file, or None if it is not an RP data export.

    Raises RPClassificationError if a name matches more than one type — silence there would
    mean route-mix and route-success data being merged into each other (see module docstring).
    """
    normalized = normalize_name(filename)
    matches = [name for name, token in TYPE_TOKENS.items() if token in normalized]
    if len(matches) > 1:
        raise RPClassificationError(f"{filename!r} matches multiple RP data types: {sorted(matches)}")
    return matches[0] if matches else None


def detect_position(filename: str) -> str | None:
    """Return the position a filename declares, or None when it doesn't declare one.

    Matches a standalone `wr`/`rb`/`qb` word, so "WR Target Data 2024-25" and
    "rb-2024__2024-25-nfl-rb-data" resolve, while a prospect export named
    "Target Data - 2026 Draft Prospects" honestly returns None rather than guessing.
    """
    words = set(normalize_name(filename).split())
    found = [p for p in POSITIONS if p.lower() in words]
    return found[0] if len(found) == 1 else None


def is_prospect_file(filename: str) -> bool:
    """True for college/draft-prospect exports rather than pro-season ones."""
    normalized = normalize_name(filename)
    return "prospect" in normalized or "draft" in normalized


# Profile post slugs. RP uses three suffixes, not two: `-player-profile` for a pro season,
# and BOTH `-prospect-profile` and `-nfl-draft-profile` for draft classes (the 2024 QB class —
# Caleb Williams, Jayden Daniels, Drake Maye — uses the latter).
_PROFILE_SLUG_RE = re.compile(r"^(?P<name>.+)-(?P<year>\d{4})-(?P<kind>player|prospect|nfl-draft)-profile$")
_PROSPECT_KINDS = {"prospect", "nfl-draft"}


def season_from_slug(slug: str) -> tuple[int, str] | None:
    """Return (season, kind) for a profile slug, or None if it has no parseable year.

    The season comes from the **slug**, never the publication date: RP publishes a season's
    profiles the following summer — the Jordan Addison *2025* profile went up on 2026-07-13 — so
    `knowledge_base.seasons.season_for_date` would file every one of them a year late. That
    failure is silent: the document embeds, searches, and answers questions about the wrong year.

    Prospect profiles resolve to the year **before** the draft class in the slug, since a 2026
    draft prospect was charted during the 2025 college season. That matches the quantitative
    layer, where the 2026 prospect tables carry `Year=2025`.

    Returns None rather than guessing for an unrecognized slug shape — callers skip and report,
    because an unlabelled corpus entry is recoverable while a confidently mislabelled one is not.
    """
    match = _PROFILE_SLUG_RE.match(slug)
    if not match:
        return None
    year = int(match.group("year"))
    is_prospect = match.group("kind") in _PROSPECT_KINDS
    return (year - 1 if is_prospect else year), ("prospect" if is_prospect else "player")


def matches_position(filename: str, position: str) -> bool:
    """Whether a file may be read when ingesting `position`.

    A file that declares a *different* position is excluded; one that declares none is
    allowed, because prospect exports carry no position token and are scoped by directory.

    This is the guard against the collision that made this module necessary: the previous
    loader globbed `*.csv` and selected on data type alone, so an `RB Route Percentage`
    export dropped into a WR directory merged into the WR frame — keyed only on
    (Player, Year), with nothing downstream able to tell the rows apart.
    """
    declared = detect_position(filename)
    return declared is None or declared == position.upper()
