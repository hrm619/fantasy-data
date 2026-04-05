"""Resolve nflverse player IDs to pipeline PLAYER ID.

Primary strategy: nflverse's own IDs table maps gsis_id → pfr_id, and pfr_id
IS the pipeline PLAYER ID format (e.g., "ChasJa00"). This gives us 7,500+
direct mappings without name matching.

Fallback: pipeline's player_name_to_key.json for players missing pfr_id.
Last resort: deterministic ID generation for historical-only players.
"""

import json
import re
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fantasy_data.models import Player
from fantasy_data.standardize import standardize_player_name, standardize_team

DEFAULT_NAME_KEY_PATH = (
    Path(__file__).resolve().parents[4]
    / "fantasy_data_pipeline"
    / "data"
    / "player_name_to_key.json"
)


def load_name_to_key(path: Path | None = None) -> dict[str, str]:
    """Load the pipeline's player name -> PLAYER ID mapping (normalized keys)."""
    path = path or DEFAULT_NAME_KEY_PATH
    with open(path) as f:
        raw = json.load(f)
    return {standardize_player_name(name): pid for name, pid in raw.items()}


def _generate_fallback_id(name: str, existing_ids: set[str]) -> str:
    """Generate a deterministic PLAYER ID for players not in any lookup.

    Format: first 4 of last + first 2 of first + sequence (e.g., SmitJo00).
    """
    parts = name.strip().split()
    if len(parts) < 2:
        last = parts[0] if parts else "Unkn"
        first = "Xx"
    else:
        first = parts[0]
        last = parts[-1]

    last_clean = re.sub(r"[^A-Za-z]", "", last)
    first_clean = re.sub(r"[^A-Za-z]", "", first)
    last_part = last_clean[:4].ljust(4, "x").capitalize()
    first_part = first_clean[:2].ljust(2, "x").capitalize()
    prefix = last_part + first_part

    for seq in range(100):
        candidate = f"{prefix}{seq:02d}"
        if candidate not in existing_ids:
            return candidate
    return f"{prefix}99"


def build_id_map_from_nflverse(
    ids_df: pd.DataFrame,
    name_to_key: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build gsis_id -> pipeline PLAYER ID mapping from nflverse IDs table.

    Uses pfr_id as the direct link (it IS the pipeline format).
    Falls back to name matching via player_name_to_key.json.

    Args:
        ids_df: DataFrame from nfl_data_py.import_ids().
        name_to_key: Optional name-based fallback dict.

    Returns:
        Dict mapping gsis_id -> pipeline PLAYER ID.
    """
    if name_to_key is None:
        try:
            name_to_key = load_name_to_key()
        except FileNotFoundError:
            name_to_key = {}

    all_known_ids = set(name_to_key.values())
    id_map: dict[str, str] = {}
    generated_ids: set[str] = set()

    for _, row in ids_df.iterrows():
        gsis_id = row.get("gsis_id")
        if not gsis_id or pd.isna(gsis_id):
            continue

        gsis_id = str(gsis_id)

        # Primary: pfr_id is the pipeline PLAYER ID format
        pfr_id = row.get("pfr_id")
        if pfr_id and pd.notna(pfr_id):
            id_map[gsis_id] = str(pfr_id)
            continue

        # Fallback: name matching
        name = row.get("name") or row.get("merge_name") or ""
        if name and pd.notna(name):
            norm = standardize_player_name(str(name))
            pid = name_to_key.get(norm)
            if pid:
                id_map[gsis_id] = pid
                continue

            # Last resort: generate ID
            pid = _generate_fallback_id(str(name), all_known_ids | generated_ids)
            generated_ids.add(pid)
            id_map[gsis_id] = pid

    return id_map


def build_pfr_snap_map(ids_df: pd.DataFrame) -> dict[str, str]:
    """Build pfr_player_id -> pipeline PLAYER ID for snap count data.

    Snap counts use pfr_player_id which is already in pipeline format,
    but some may differ. This builds the mapping for safety.
    """
    snap_map: dict[str, str] = {}
    for _, row in ids_df.iterrows():
        pfr_id = row.get("pfr_id")
        if pfr_id and pd.notna(pfr_id):
            snap_map[str(pfr_id)] = str(pfr_id)
    return snap_map


def ensure_player_exists(
    session: Session,
    player_id: str,
    full_name: str,
    position: str | None,
    team: str | None,
    gsis_id: str | None = None,
    is_active: int = 0,
) -> Player:
    """Get or create a Player record, storing gsis_id if provided."""
    player = session.get(Player, player_id)
    if player:
        if gsis_id and not player.gsis_id:
            player.gsis_id = gsis_id
        return player

    team = standardize_team(team)
    player = Player(
        player_id=player_id,
        full_name=full_name,
        position=position or "UNK",
        team=team,
        gsis_id=gsis_id,
        is_active=is_active,
    )
    session.add(player)
    return player
