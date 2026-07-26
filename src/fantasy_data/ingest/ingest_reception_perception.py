"""Ingest Reception Perception film-graded metrics.

Reads 7 CSV types per season from Matt Harmon's RP exports, merges on player name + year,
and stores in the wr_reception_perception table. Also auto-classifies Player.route_tree_type
from alignment data.

Two naming schemes are accepted, and may sit side by side:

  - hand-downloaded:  "WR Success Rate vs. Coverage Table 2024-25.csv"
  - site export:      "wr-2024__success-rate-vs-coverage.csv"  (scripts/fetch_rp.py)

File classification lives in `rp_parse` — see that module for why getting it wrong is
undetectable downstream. Where both schemes supply the same player-season, the site export
wins: it is the live table, while a hand-downloaded CSV is a point-in-time copy of it.

The Year column in each CSV maps to the NFL season.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.ingest.rp_parse import classify_type, matches_position
from fantasy_data.models import Player, WrReceptionPerception
from fantasy_data.standardize import standardize_player_name

# Precedence when the same player-season arrives from both schemes (highest wins).
SOURCE_PRECEDENCE = {"csv-manual": 0, "site": 1}


def _detect_source(filename: str) -> str:
    """Which capture produced a file. `fetch_rp.py` names exports `<page-key>__<type>.csv`."""
    return "site" if "__" in Path(filename).stem else "csv-manual"


def _clean_pct(val) -> float | None:
    """Convert string percentages like '86.1' or '86.1%' to float."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip().rstrip("%")
    try:
        return float(s)
    except ValueError:
        return None


def _clean_int(val) -> int | None:
    """Convert a count cell to int, tolerating '1,234' and blank cells."""
    if val is None or pd.isna(val):
        return None
    try:
        return int(float(str(val).strip().replace(",", "")))
    except ValueError:
        return None


def _set(rp, field: str, value) -> None:
    """Assign a parsed value, treating only None as 'the source said nothing'.

    The previous idiom was `rp.field = _clean_pct(...) or rp.field`, which discards a genuine
    **0.0** because it is falsy — a charted zero silently became the old value, or NULL. Zero
    is a real and common reading in this data (a receiver who broke no tackles, ran no screens,
    faced no double coverage), so it has to survive.
    """
    if value is not None:
        setattr(rp, field, value)


def _first(row, *names):
    """Return the first present, non-null cell among `names`.

    RP renames columns between seasons — tackle-breaking counts are "Opportunities" in the 2024
    export and "In Space Opportunities" in 2025. Reading only one name silently NULLs the other
    season; that is exactly how `tackle_break_opportunities` ended up populated for 115 of 126
    rows, missing precisely the 11 rows from 2025.
    """
    for name in names:
        val = row.get(name)
        if val is not None and not pd.isna(val):
            return val
    return None


def _collapse(name: str) -> str:
    """Reduce a name to letters and digits only.

    `players.full_name` comes from the pipeline's key dict, which strips hyphens and periods
    ("Jaxon SmithNjigba", "AmonRa St Brown"), while RP publishes them ("Jaxon Smith-Njigba",
    "Amon-Ra St. Brown"). `standardize_player_name` preserves hyphens, so the two can never
    match exactly — which silently dropped two of the most-charted WRs in the dataset.
    """
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _build_name_index(session: Session, position: str) -> tuple[dict[str, str], dict[str, str]]:
    """Return (exact index, punctuation-insensitive fallback index).

    Built once per ingest. The previous lookup ran two full table scans per *unmatched* name,
    which is O(players x names) on a miss — and misses are the common case for prospects.

    The fallback drops any key that collapses to more than one distinct player, so it can only
    ever resolve an unambiguous punctuation difference. It never guesses between two people.
    """
    exact: dict[str, str] = {}
    collapsed: dict[str, set[str]] = {}

    players = session.query(Player).all()
    for p in players:
        exact.setdefault(standardize_player_name(p.full_name), p.player_id)
        collapsed.setdefault(_collapse(p.full_name), set()).add(p.player_id)
    for p in players:
        if p.position == position:
            exact[standardize_player_name(p.full_name)] = p.player_id

    unambiguous = {key: next(iter(ids)) for key, ids in collapsed.items() if len(ids) == 1}
    return exact, unambiguous


def _match_player(name: str, index: dict[str, str], fallback: dict[str, str] | None = None) -> str | None:
    """Match an RP player name to a pipeline player_id, exact first then punctuation-insensitive."""
    clean = name.strip().rstrip("*")
    hit = index.get(standardize_player_name(clean))
    if hit is not None:
        return hit
    return (fallback or {}).get(_collapse(clean))


def _load_csvs(data_dir: Path, data_type: str, position: str = "WR") -> pd.DataFrame:
    """Load every CSV of one data type for one position, newest-source-wins.

    Looks in `data_dir` and, if present, `data_dir/<POSITION>/` — the layout `fetch_rp.py`
    writes. Files declaring a different position are skipped, so a mixed directory cannot
    cross-contaminate (see `rp_parse.matches_position`).
    """
    search_dirs = [data_dir]
    position_dir = data_dir / position.upper()
    if position_dir.is_dir():
        search_dirs.append(position_dir)

    frames = []
    for directory in search_dirs:
        for csv_file in sorted(directory.glob("*.csv")):
            if classify_type(csv_file.name) != data_type:
                continue
            if not matches_position(csv_file.name, position):
                continue

            df = pd.read_csv(csv_file)
            if "Player" not in df.columns and "player" in df.columns:
                df = df.rename(columns={"player": "Player"})
            if "Year" not in df.columns and "year" in df.columns:
                df = df.rename(columns={"year": "Year"})

            name_lower = csv_file.stem.lower()
            df["_is_prospect"] = 1 if ("draft" in name_lower or "prospect" in name_lower) else 0
            df["_source"] = _detect_source(csv_file.name)
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    if "Player" not in combined.columns or "Year" not in combined.columns:
        return combined

    # One row per player-season: order by source precedence and keep the winner.
    combined["_precedence"] = combined["_source"].map(SOURCE_PRECEDENCE).fillna(0)
    combined["_key"] = combined["Player"].astype(str).map(lambda n: standardize_player_name(n.strip().rstrip("*")))
    combined = (
        combined.sort_values("_precedence", kind="stable")
        .drop_duplicates(subset=["_key", "Year", "_is_prospect"], keep="last")
        .drop(columns=["_precedence"])
        .reset_index(drop=True)
    )
    return combined


def ingest_reception_perception(
    session: Session,
    data_dir: str,
    verbose: bool = True,
    position: str = "WR",
) -> dict[str, int]:
    """Ingest all RP CSV data from a directory into wr_reception_perception.

    Merges 7 CSV types on (Player, Year) and creates one record per player-season.
    """
    data_path = Path(data_dir)
    stats = {"records": 0, "unmatched": 0, "route_types_set": 0, "from_site": 0, "from_csv_manual": 0}
    now_iso = datetime.now(timezone.utc).isoformat()

    frames = {
        "coverage": _load_csvs(data_path, "coverage", position),
        "route_pct": _load_csvs(data_path, "route_pct", position),
        "route_success": _load_csvs(data_path, "route_success", position),
        "alignment": _load_csvs(data_path, "alignment", position),
        "target": _load_csvs(data_path, "target", position),
        "contested": _load_csvs(data_path, "contested", position),
        "tackle": _load_csvs(data_path, "tackle", position),
    }

    if verbose:
        for name, df in frames.items():
            print(f"  {name}: {len(df)} rows")

    name_index, name_fallback = _build_name_index(session, position)

    # Every (player, season, is_prospect) seen across all seven types.
    all_players: set[tuple[str, int, int]] = set()
    for df in frames.values():
        if df.empty or "Player" not in df.columns:
            continue
        for _, row in df.iterrows():
            player = str(row.get("Player", "")).strip().rstrip("*")
            year = row.get("Year")
            if player and pd.notna(year):
                all_players.add((player, int(year), int(row.get("_is_prospect", 0))))

    if verbose:
        print(f"  Unique player-seasons: {len(all_players)}")

    unmatched: list[str] = []

    for player_name, season, is_prospect in sorted(all_players):
        player_id = _match_player(player_name, name_index, name_fallback)
        if not player_id:
            stats["unmatched"] += 1
            unmatched.append(f"{player_name} ({season})")
            continue

        rp_id = f"{player_id}_{season}"
        rp = session.get(WrReceptionPerception, rp_id)
        if not rp:
            rp = WrReceptionPerception(
                rp_id=rp_id,
                player_id=player_id,
                season=season,
                is_prospect=is_prospect,
                created_at=now_iso,
            )
            session.add(rp)

        clean_name = player_name.strip().rstrip("*")
        rows = {key: _find_row(df, clean_name, season) for key, df in frames.items()}

        _merge_coverage(rp, rows["coverage"])
        _merge_route_pct(rp, rows["route_pct"])
        _merge_route_success(rp, rows["route_success"])
        _merge_alignment(rp, rows["alignment"])
        _merge_target(rp, rows["target"])
        _merge_contested(rp, rows["contested"])
        _merge_tackle(rp, rows["tackle"])

        sources = sorted({str(r["_source"]) for r in rows.values() if r is not None and "_source" in r})
        if sources:
            rp.source = "+".join(sources)
            for src in sources:
                stats[f"from_{src.replace('-', '_')}"] = stats.get(f"from_{src.replace('-', '_')}", 0) + 1
        rp.updated_at = now_iso

        # Auto-set route_tree_type on Player from alignment
        if not is_prospect and rp.pct_outside is not None:
            player = session.get(Player, player_id)
            if player and not player.route_tree_type:
                if (rp.pct_outside or 0) >= 70:
                    player.route_tree_type = "OUTSIDE"
                elif (rp.pct_slot or 0) >= 50:
                    player.route_tree_type = "SLOT"
                else:
                    player.route_tree_type = "FLEX"
                stats["route_types_set"] += 1

        stats["records"] += 1

    session.commit()

    if verbose:
        for name in unmatched:
            print(f"    RP unmatched: {name}")
        print(
            f"\nRP ingest: {stats['records']} records, "
            f"{stats['unmatched']} unmatched, "
            f"{stats['route_types_set']} route_tree_types set"
        )

    return stats


def _find_row(df: pd.DataFrame, name: str, season: int) -> pd.Series | None:
    """Find a player's row in a DF by name + year."""
    if df.empty or "Year" not in df.columns or "Player" not in df.columns:
        return None
    target = standardize_player_name(name)
    mask = df["Year"].astype(int) == season
    for _, row in df[mask].iterrows():
        row_name = str(row.get("Player", "")).strip().rstrip("*")
        if standardize_player_name(row_name) == target:
            return row
    return None


def _merge_coverage(rp, row) -> None:
    if row is None:
        return
    _set(rp, "routes_charted", _clean_int(row.get("Routes")))
    _set(rp, "success_rate_man", _clean_pct(row.get("Success Rate vs. Man")))
    _set(rp, "success_rate_zone", _clean_pct(row.get("Success Rate vs. Zone")))
    _set(rp, "success_rate_press", _clean_pct(row.get("Success Rate vs. Press")))
    _set(rp, "success_rate_double", _clean_pct(row.get("Success Rate vs. Double")))
    _set(rp, "pct_man", _clean_pct(row.get("% Man")))
    _set(rp, "pct_zone", _clean_pct(row.get("% Zone")))
    _set(rp, "pct_press", _clean_pct(row.get("% Press")))
    _set(rp, "pct_doubled", _clean_pct(row.get("% Doubled")))
    # Sample sizes behind each rate.
    _set(rp, "man_atts", _clean_int(row.get("man atts.")))
    _set(rp, "zone_atts", _clean_int(row.get("zone atts.")))
    _set(rp, "double_atts", _clean_int(row.get("dbl atts.")))
    _set(rp, "press_atts", _clean_int(row.get("press atts.")))


def _merge_route_pct(rp, row) -> None:
    if row is None:
        return
    for field, column in (
        ("pct_screen", "Screen"),
        ("pct_slant", "Slant"),
        ("pct_curl", "Curl"),
        ("pct_dig", "Dig"),
        ("pct_post", "Post"),
        ("pct_nine", "Nine"),
        ("pct_corner", "Corner"),
        ("pct_out", "Out"),
        ("pct_comeback", "Comeback"),
        ("pct_flat", "Flat"),
        ("pct_other", "Other"),
    ):
        _set(rp, field, _clean_pct(row.get(column)))


def _merge_route_success(rp, row) -> None:
    # Same column names as _merge_route_pct — the discriminator is the FILE, not the header.
    if row is None:
        return
    for field, column in (
        ("success_rate_screen", "Screen"),
        ("success_rate_slant", "Slant"),
        ("success_rate_curl", "Curl"),
        ("success_rate_dig", "Dig"),
        ("success_rate_post", "Post"),
        ("success_rate_nine", "Nine"),
        ("success_rate_corner", "Corner"),
        ("success_rate_out", "Out"),
        ("success_rate_comeback", "Comeback"),
        ("success_rate_flat", "Flat"),
        ("success_rate_other", "Other"),
    ):
        _set(rp, field, _clean_pct(row.get(column)))


def _merge_alignment(rp, row) -> None:
    if row is None:
        return
    _set(rp, "pct_outside", _clean_pct(row.get("Outside")))
    _set(rp, "pct_slot", _clean_pct(row.get("Slot")))
    _set(rp, "pct_backfield", _clean_pct(row.get("Backfield")))
    _set(rp, "pct_inline", _clean_pct(row.get("Inline")))
    _set(rp, "pct_lwr", _clean_pct(row.get("LWR")))
    _set(rp, "pct_rwr", _clean_pct(row.get("RWR")))
    _set(rp, "pct_behind_los", _clean_pct(row.get("Behind LOS")))
    _set(rp, "pct_on_los", _clean_pct(row.get("On LOS")))
    _set(rp, "snaps_charted", _clean_int(row.get("Snaps")))


def _merge_target(rp, row) -> None:
    if row is None:
        return
    _set(rp, "route_target_rate", _clean_pct(row.get("Route Target Rate")))
    _set(rp, "route_catch_rate", _clean_pct(row.get("Route Catch Rate")))
    _set(rp, "catch_rate_rp", _clean_pct(row.get("Catch Rate")))
    _set(rp, "drop_rate_rp", _clean_pct(row.get("Drop Rate")))
    _set(rp, "targets_rp", _clean_int(row.get("Targets")))
    if rp.routes_charted is None:
        _set(rp, "routes_charted", _clean_int(row.get("Total Routes")))


def _merge_contested(rp, row) -> None:
    if row is None:
        return
    _set(rp, "contested_target_rate_rp", _clean_pct(row.get("Contested Target Rate")))
    _set(rp, "contested_catch_rate_rp", _clean_pct(row.get("Contested Catch Rate")))
    _set(rp, "contested_targets_rp", _clean_int(row.get("Contested targets")))


def _merge_tackle(rp, row) -> None:
    if row is None:
        return
    _set(rp, "tackle_break_opportunities", _clean_int(_first(row, "In Space Opportunities", "Opportunities")))
    _set(rp, "first_contact_drop_pct", _clean_pct(row.get("1st Contact Drop")))
    _set(rp, "one_broken_tackle_pct", _clean_pct(row.get("1 Broken Tackle")))
    _set(rp, "two_plus_broken_tackle_pct", _clean_pct(row.get("2+ Broken Tackle")))
    # Two columns, not one: RP changed the denominator between seasons (see models.py).
    _set(rp, "in_space_pct_of_routes", _clean_pct(row.get("% of Routes")))
    _set(rp, "in_space_pct_of_catches", _clean_pct(_first(row, "% of Catches in space", "% of Catches")))
