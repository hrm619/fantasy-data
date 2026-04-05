"""Ingest Reception Perception WR film-graded metrics.

Reads 7 CSV types per season from Matt Harmon's RP data exports,
merges on player name + year, and stores in wr_reception_perception table.

Also auto-classifies Player.route_tree_type from alignment data.

CSV file naming conventions:
  - Pro WRs: "WR {Type} - 2023.csv" or "WR {Type} 2024-25.csv"
  - Draft prospects: "{Type} - 2025 Draft Prospects.csv"

The Year field in each CSV maps to the NFL season.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player, WrReceptionPerception
from fantasy_data.standardize import standardize_player_name


def _clean_pct(val) -> float | None:
    """Convert string percentages like '86.1' or '86.1%' to float."""
    if val is None or pd.isna(val):
        return None
    s = str(val).strip().rstrip("%")
    try:
        return float(s)
    except ValueError:
        return None


def _match_player(session: Session, name: str, name_cache: dict[str, str]) -> str | None:
    """Match RP player name to pipeline player_id."""
    # Strip injury markers
    clean = name.strip().rstrip("*")
    norm = standardize_player_name(clean)

    if norm in name_cache:
        return name_cache[norm]

    # Try DB lookup
    for p in session.query(Player).filter(Player.position == "WR").all():
        if standardize_player_name(p.full_name) == norm:
            name_cache[norm] = p.player_id
            return p.player_id

    # Broader search (TE, RB who play WR-like roles)
    for p in session.query(Player).all():
        if standardize_player_name(p.full_name) == norm:
            name_cache[norm] = p.player_id
            return p.player_id

    return None


def _load_csvs(data_dir: Path, data_type: str) -> pd.DataFrame:
    """Load all CSVs of a given type across seasons, normalizing column order."""
    frames = []
    for csv_file in sorted(data_dir.glob("*.csv")):
        name_lower = csv_file.stem.lower()
        if data_type.lower() not in name_lower:
            continue

        df = pd.read_csv(csv_file)

        # Normalize column order: ensure Player and Year are present
        if "Player" not in df.columns and "player" in df.columns:
            df = df.rename(columns={"player": "Player"})
        if "Year" not in df.columns and "year" in df.columns:
            df = df.rename(columns={"year": "Year"})

        # Detect prospect files
        is_prospect = "draft" in name_lower.lower() or "prospect" in name_lower.lower()
        df["_is_prospect"] = 1 if is_prospect else 0

        frames.append(df)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def ingest_reception_perception(
    session: Session,
    data_dir: str,
    verbose: bool = True,
) -> dict[str, int]:
    """Ingest all RP CSV data from a directory into wr_reception_perception.

    Merges 7 CSV types on (Player, Year) and creates one record per player-season.
    """
    data_path = Path(data_dir)
    stats = {"records": 0, "unmatched": 0, "route_types_set": 0}
    now_iso = datetime.now(timezone.utc).isoformat()
    name_cache: dict[str, str] = {}

    # Load all 7 data types
    coverage_df = _load_csvs(data_path, "Coverage")
    route_pct_df = _load_csvs(data_path, "Route Percentage")
    route_success_df = _load_csvs(data_path, "Success Rate by Route")
    alignment_df = _load_csvs(data_path, "Alignment")
    target_df = _load_csvs(data_path, "Target Data")
    contested_df = _load_csvs(data_path, "Contested Catch")
    tackle_df = _load_csvs(data_path, "Tackle Breaking")

    if verbose:
        for name, df in [("Coverage", coverage_df), ("Route%", route_pct_df),
                         ("RouteSuccess", route_success_df), ("Alignment", alignment_df),
                         ("Target", target_df), ("Contested", contested_df),
                         ("Tackle", tackle_df)]:
            print(f"  {name}: {len(df)} rows")

    # Build a set of all (player, year) pairs across all dataframes
    all_players = set()
    for df in [coverage_df, route_pct_df, alignment_df, target_df, contested_df, tackle_df]:
        if df.empty:
            continue
        for _, row in df.iterrows():
            player = str(row.get("Player", "")).strip().rstrip("*")
            year = row.get("Year")
            is_prospect = row.get("_is_prospect", 0)
            if player and pd.notna(year):
                all_players.add((player, int(year), int(is_prospect)))

    if verbose:
        print(f"  Unique player-seasons: {len(all_players)}")

    # Process each player-season
    for player_name, season, is_prospect in sorted(all_players):
        player_id = _match_player(session, player_name, name_cache)
        if not player_id:
            stats["unmatched"] += 1
            if verbose:
                print(f"    RP unmatched: {player_name} ({season})")
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

        # --- Coverage success rates ---
        _merge_coverage(rp, coverage_df, clean_name, season)

        # --- Route percentage ---
        _merge_route_pct(rp, route_pct_df, clean_name, season)

        # --- Route success rates ---
        _merge_route_success(rp, route_success_df, clean_name, season)

        # --- Alignment ---
        _merge_alignment(rp, alignment_df, clean_name, season)

        # --- Target data ---
        _merge_target(rp, target_df, clean_name, season)

        # --- Contested catch ---
        _merge_contested(rp, contested_df, clean_name, season)

        # --- Tackle breaking ---
        _merge_tackle(rp, tackle_df, clean_name, season)

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
        print(f"\nRP ingest: {stats['records']} records, "
              f"{stats['unmatched']} unmatched, "
              f"{stats['route_types_set']} route_tree_types set")

    return stats


def _find_row(df: pd.DataFrame, name: str, season: int) -> pd.Series | None:
    """Find a player's row in a DF by name + year."""
    if df.empty:
        return None
    mask = df["Year"].astype(int) == season
    for _, row in df[mask].iterrows():
        row_name = str(row.get("Player", "")).strip().rstrip("*")
        if standardize_player_name(row_name) == standardize_player_name(name):
            return row
    return None


def _merge_coverage(rp, df, name, season):
    row = _find_row(df, name, season)
    if row is None:
        return
    rp.routes_charted = int(row["Routes"]) if pd.notna(row.get("Routes")) else rp.routes_charted
    rp.success_rate_man = _clean_pct(row.get("Success Rate vs. Man")) or rp.success_rate_man
    rp.success_rate_zone = _clean_pct(row.get("Success Rate vs. Zone")) or rp.success_rate_zone
    rp.success_rate_press = _clean_pct(row.get("Success Rate vs. Press")) or rp.success_rate_press
    rp.success_rate_double = _clean_pct(row.get("Success Rate vs. Double")) or rp.success_rate_double
    rp.pct_man = _clean_pct(row.get("% Man")) or rp.pct_man
    rp.pct_zone = _clean_pct(row.get("% Zone")) or rp.pct_zone
    rp.pct_press = _clean_pct(row.get("% Press")) or rp.pct_press
    rp.pct_doubled = _clean_pct(row.get("% Doubled")) or rp.pct_doubled


def _merge_route_pct(rp, df, name, season):
    row = _find_row(df, name, season)
    if row is None:
        return
    rp.pct_screen = _clean_pct(row.get("Screen")) or rp.pct_screen
    rp.pct_slant = _clean_pct(row.get("Slant")) or rp.pct_slant
    rp.pct_curl = _clean_pct(row.get("Curl")) or rp.pct_curl
    rp.pct_dig = _clean_pct(row.get("Dig")) or rp.pct_dig
    rp.pct_post = _clean_pct(row.get("Post")) or rp.pct_post
    rp.pct_nine = _clean_pct(row.get("Nine")) or rp.pct_nine
    rp.pct_corner = _clean_pct(row.get("Corner")) or rp.pct_corner
    rp.pct_out = _clean_pct(row.get("Out")) or rp.pct_out
    rp.pct_comeback = _clean_pct(row.get("Comeback")) or rp.pct_comeback
    rp.pct_flat = _clean_pct(row.get("Flat")) or rp.pct_flat


def _merge_route_success(rp, df, name, season):
    row = _find_row(df, name, season)
    if row is None:
        return
    rp.success_rate_slant = _clean_pct(row.get("Slant")) or rp.success_rate_slant
    rp.success_rate_curl = _clean_pct(row.get("Curl")) or rp.success_rate_curl
    rp.success_rate_dig = _clean_pct(row.get("Dig")) or rp.success_rate_dig
    rp.success_rate_post = _clean_pct(row.get("Post")) or rp.success_rate_post
    rp.success_rate_nine = _clean_pct(row.get("Nine")) or rp.success_rate_nine
    rp.success_rate_corner = _clean_pct(row.get("Corner")) or rp.success_rate_corner
    rp.success_rate_out = _clean_pct(row.get("Out")) or rp.success_rate_out
    rp.success_rate_screen = _clean_pct(row.get("Screen")) or rp.success_rate_screen


def _merge_alignment(rp, df, name, season):
    row = _find_row(df, name, season)
    if row is None:
        return
    rp.pct_outside = _clean_pct(row.get("Outside")) or rp.pct_outside
    rp.pct_slot = _clean_pct(row.get("Slot")) or rp.pct_slot
    rp.pct_backfield = _clean_pct(row.get("Backfield")) or rp.pct_backfield
    # Inline not in WR data but check anyway
    rp.pct_inline = _clean_pct(row.get("Inline")) or rp.pct_inline


def _merge_target(rp, df, name, season):
    row = _find_row(df, name, season)
    if row is None:
        return
    rp.route_target_rate = _clean_pct(row.get("Route Target Rate")) or rp.route_target_rate
    rp.route_catch_rate = _clean_pct(row.get("Route Catch Rate")) or rp.route_catch_rate
    rp.catch_rate_rp = _clean_pct(row.get("Catch Rate")) or rp.catch_rate_rp
    rp.drop_rate_rp = _clean_pct(row.get("Drop Rate")) or rp.drop_rate_rp

    routes = row.get("Total Routes")
    if pd.notna(routes) and rp.routes_charted is None:
        rp.routes_charted = int(routes)


def _merge_contested(rp, df, name, season):
    row = _find_row(df, name, season)
    if row is None:
        return
    rp.contested_target_rate_rp = _clean_pct(row.get("Contested Target Rate")) or rp.contested_target_rate_rp
    rp.contested_catch_rate_rp = _clean_pct(row.get("Contested Catch Rate")) or rp.contested_catch_rate_rp


def _merge_tackle(rp, df, name, season):
    row = _find_row(df, name, season)
    if row is None:
        return
    opps = row.get("Opportunities")
    if pd.notna(opps):
        rp.tackle_break_opportunities = int(opps)
    rp.first_contact_drop_pct = _clean_pct(row.get("1st Contact Drop")) or rp.first_contact_drop_pct
    rp.one_broken_tackle_pct = _clean_pct(row.get("1 Broken Tackle")) or rp.one_broken_tackle_pct
    rp.two_plus_broken_tackle_pct = _clean_pct(row.get("2+ Broken Tackle")) or rp.two_plus_broken_tackle_pct
