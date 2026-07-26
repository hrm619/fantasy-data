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

from fantasy_data.ingest.rp_common import (
    SOURCE_PRECEDENCE,
    build_name_index,
    clean_int,
    clean_pct,
    detect_source,
    first_present,
    match_player,
    set_if_present,
)
from fantasy_data.ingest.rp_parse import classify_type, matches_position
from fantasy_data.models import Player, WrReceptionPerception
from fantasy_data.standardize import standardize_player_name


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
            df["_source"] = detect_source(csv_file.name)
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

    name_index, name_fallback = build_name_index(session, position)

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
        player_id = match_player(player_name, name_index, name_fallback)
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
    set_if_present(rp, "routes_charted", clean_int(row.get("Routes")))
    set_if_present(rp, "success_rate_man", clean_pct(row.get("Success Rate vs. Man")))
    set_if_present(rp, "success_rate_zone", clean_pct(row.get("Success Rate vs. Zone")))
    set_if_present(rp, "success_rate_press", clean_pct(row.get("Success Rate vs. Press")))
    set_if_present(rp, "success_rate_double", clean_pct(row.get("Success Rate vs. Double")))
    set_if_present(rp, "pct_man", clean_pct(row.get("% Man")))
    set_if_present(rp, "pct_zone", clean_pct(row.get("% Zone")))
    set_if_present(rp, "pct_press", clean_pct(row.get("% Press")))
    set_if_present(rp, "pct_doubled", clean_pct(row.get("% Doubled")))
    # Sample sizes behind each rate.
    set_if_present(rp, "man_atts", clean_int(row.get("man atts.")))
    set_if_present(rp, "zone_atts", clean_int(row.get("zone atts.")))
    set_if_present(rp, "double_atts", clean_int(row.get("dbl atts.")))
    set_if_present(rp, "press_atts", clean_int(row.get("press atts.")))


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
        set_if_present(rp, field, clean_pct(row.get(column)))


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
        set_if_present(rp, field, clean_pct(row.get(column)))


def _merge_alignment(rp, row) -> None:
    if row is None:
        return
    set_if_present(rp, "pct_outside", clean_pct(row.get("Outside")))
    set_if_present(rp, "pct_slot", clean_pct(row.get("Slot")))
    set_if_present(rp, "pct_backfield", clean_pct(row.get("Backfield")))
    set_if_present(rp, "pct_inline", clean_pct(row.get("Inline")))
    set_if_present(rp, "pct_lwr", clean_pct(row.get("LWR")))
    set_if_present(rp, "pct_rwr", clean_pct(row.get("RWR")))
    set_if_present(rp, "pct_behind_los", clean_pct(row.get("Behind LOS")))
    set_if_present(rp, "pct_on_los", clean_pct(row.get("On LOS")))
    set_if_present(rp, "snaps_charted", clean_int(row.get("Snaps")))


def _merge_target(rp, row) -> None:
    if row is None:
        return
    set_if_present(rp, "route_target_rate", clean_pct(row.get("Route Target Rate")))
    set_if_present(rp, "route_catch_rate", clean_pct(row.get("Route Catch Rate")))
    set_if_present(rp, "catch_rate_rp", clean_pct(row.get("Catch Rate")))
    set_if_present(rp, "drop_rate_rp", clean_pct(row.get("Drop Rate")))
    set_if_present(rp, "targets_rp", clean_int(row.get("Targets")))
    if rp.routes_charted is None:
        set_if_present(rp, "routes_charted", clean_int(row.get("Total Routes")))


def _merge_contested(rp, row) -> None:
    if row is None:
        return
    set_if_present(rp, "contested_target_rate_rp", clean_pct(row.get("Contested Target Rate")))
    set_if_present(rp, "contested_catch_rate_rp", clean_pct(row.get("Contested Catch Rate")))
    set_if_present(rp, "contested_targets_rp", clean_int(row.get("Contested targets")))


def _merge_tackle(rp, row) -> None:
    if row is None:
        return
    set_if_present(
        rp, "tackle_break_opportunities", clean_int(first_present(row, "In Space Opportunities", "Opportunities"))
    )
    set_if_present(rp, "first_contact_drop_pct", clean_pct(row.get("1st Contact Drop")))
    set_if_present(rp, "one_broken_tackle_pct", clean_pct(row.get("1 Broken Tackle")))
    set_if_present(rp, "two_plus_broken_tackle_pct", clean_pct(row.get("2+ Broken Tackle")))
    # Two columns, not one: RP changed the denominator between seasons (see models.py).
    set_if_present(rp, "in_space_pct_of_routes", clean_pct(row.get("% of Routes")))
    set_if_present(
        rp, "in_space_pct_of_catches", clean_pct(first_present(row, "% of Catches in space", "% of Catches"))
    )
