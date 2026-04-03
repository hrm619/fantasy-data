"""Bridge table between fantasy_data_pipeline PLAYER IDs and PFF player_ids."""

import re

from sqlalchemy.orm import Session

from fantasy_data.models import PipelineIdMap, UnmatchedPlayer, Player


def _normalize_name(name: str) -> str:
    """Normalize a player name for fuzzy matching."""
    name = name.strip()
    name = re.sub(r"[.'']", "", name)
    name = re.sub(r"\s+(Jr|Sr|II|III|IV|V)$", "", name)
    name = re.sub(r"\s+", " ", name)
    return name.lower()


def build_id_map(session: Session) -> dict[str, str]:
    """Build or refresh the pipeline-to-PFF ID mapping.

    Returns a dict mapping pipeline PLAYER ID -> PFF player_id.
    """
    existing = {m.pipeline_player_id: m.player_id
                for m in session.query(PipelineIdMap).all()}
    if existing:
        return existing

    # Build name lookup from players table
    players = session.query(Player).filter(Player.is_active == 1).all()
    name_to_pff: dict[str, str] = {}
    for p in players:
        name_to_pff[p.full_name.lower()] = p.player_id
        name_to_pff[_normalize_name(p.full_name)] = p.player_id

    return name_to_pff


def resolve_player_id(
    session: Session,
    pipeline_id: str,
    player_name: str,
    position: str | None = None,
    team: str | None = None,
) -> str | None:
    """Resolve a pipeline PLAYER ID to a PFF player_id.

    Checks the persisted mapping first, then attempts name-based matching.
    Logs unmatched players for manual resolution.
    """
    # Check persisted mapping
    existing = session.get(PipelineIdMap, pipeline_id)
    if existing:
        return existing.player_id

    # Attempt name-based matching
    normalized = _normalize_name(player_name)

    # Exact name match
    player = session.query(Player).filter(
        Player.full_name == player_name
    ).first()

    match_method = "exact"
    match_confidence = 1.0

    if not player:
        # Normalized match
        all_players = session.query(Player).filter(Player.is_active == 1).all()
        for p in all_players:
            if _normalize_name(p.full_name) == normalized:
                player = p
                match_method = "normalized"
                match_confidence = 0.9
                break

    if player:
        mapping = PipelineIdMap(
            pipeline_player_id=pipeline_id,
            player_id=player.player_id,
            match_method=match_method,
            match_confidence=match_confidence,
        )
        session.merge(mapping)
        session.flush()
        return player.player_id

    # Log unmatched
    unmatched = UnmatchedPlayer(
        pipeline_player_id=pipeline_id,
        player_name=player_name,
        position=position,
        team=team,
        source="rankings_ingest",
    )
    session.add(unmatched)
    session.flush()
    return None
