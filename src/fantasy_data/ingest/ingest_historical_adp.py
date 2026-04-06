"""Ingest historical ADP from Fantasy Football Calculator API.

Fetches pre-season ADP for 2017-2024 and populates adp_consensus and
adp_positional_rank on existing player_season_baseline records.

API: https://fantasyfootballcalculator.com/api/v1/adp/ppr?teams=12&year=YYYY
Returns JSON with player name, position, team, and ADP.

Only updates baselines where adp_consensus is currently NULL (does not
overwrite 2025 rankings-derived ADP).
"""

from datetime import datetime, timezone

import requests
import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player, PlayerSeasonBaseline
from fantasy_data.standardize import standardize_player_name, standardize_team

FFC_API_URL = "https://fantasyfootballcalculator.com/api/v1/adp/ppr"


def fetch_historical_adp(season: int, teams: int = 12) -> list[dict]:
    """Fetch ADP from Fantasy Football Calculator API for a single season."""
    resp = requests.get(FFC_API_URL, params={"teams": teams, "year": season})
    resp.raise_for_status()
    data = resp.json()
    return data.get("players", [])


def _build_name_map(session: Session) -> dict[str, str]:
    """Build normalized name → player_id for matching."""
    name_map: dict[str, str] = {}
    for p in session.query(Player).all():
        norm = standardize_player_name(p.full_name)
        if norm not in name_map:
            name_map[norm] = p.player_id
    return name_map


def ingest_historical_adp(
    session: Session,
    seasons: list[int],
    verbose: bool = True,
) -> dict[str, int]:
    """Fetch and ingest historical ADP for multiple seasons.

    Only sets adp_consensus and adp_positional_rank on baselines where
    those fields are currently NULL.
    """
    stats = {"seasons": 0, "matched": 0, "unmatched": 0, "skipped_existing": 0}
    name_map = _build_name_map(session)

    for season in seasons:
        if verbose:
            print(f"  Fetching ADP for {season}...")
        try:
            players = fetch_historical_adp(season)
        except Exception as e:
            if verbose:
                print(f"    Error: {e}")
            continue

        if verbose:
            print(f"    {len(players)} players")

        # Track positional ranks
        pos_counters: dict[str, int] = {}
        season_matched = 0

        for p in players:
            name = p.get("name", "")
            position = p.get("position", "")
            adp = p.get("adp")

            if not name or adp is None:
                continue

            # Match player
            norm = standardize_player_name(name)
            player_id = name_map.get(norm)
            if not player_id:
                stats["unmatched"] += 1
                continue

            # Get or skip baseline
            baseline_id = f"{player_id}_{season}"
            baseline = session.get(PlayerSeasonBaseline, baseline_id)
            if not baseline:
                stats["unmatched"] += 1
                continue

            # Only set if currently NULL
            if baseline.adp_consensus is not None:
                stats["skipped_existing"] += 1
                continue

            baseline.adp_consensus = float(adp)

            # Compute positional rank
            pos_counters[position] = pos_counters.get(position, 0) + 1
            baseline.adp_positional_rank = pos_counters[position]

            season_matched += 1

        stats["matched"] += season_matched
        stats["seasons"] += 1

        session.commit()
        if verbose:
            print(f"    Matched: {season_matched}")

    if verbose:
        print(f"\nHistorical ADP: {stats['seasons']} seasons, "
              f"{stats['matched']} matched, {stats['unmatched']} unmatched, "
              f"{stats['skipped_existing']} skipped (already had ADP)")

    return stats
