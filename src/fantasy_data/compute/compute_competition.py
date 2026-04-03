"""Compute target competition analysis for roster construction.

Phase 2 — interface defined, requires manual route_tree_type seeding.
"""

from sqlalchemy.orm import Session

from fantasy_data.models import Player, TargetCompetition

# Route tree overlap scoring matrix
# Higher score = more direct competition for targets
ROUTE_OVERLAP_MATRIX = {
    ("OUTSIDE", "OUTSIDE"): 0.9,
    ("SLOT", "SLOT"): 0.9,
    ("OUTSIDE", "SLOT"): 0.3,
    ("SLOT", "OUTSIDE"): 0.3,
    ("FLEX", "OUTSIDE"): 0.6,
    ("FLEX", "SLOT"): 0.6,
    ("OUTSIDE", "FLEX"): 0.6,
    ("SLOT", "FLEX"): 0.6,
    ("INLINE_TE", "INLINE_TE"): 0.8,
    ("MOVE_TE", "SLOT"): 0.5,
    ("SLOT", "MOVE_TE"): 0.5,
    ("MOVE_TE", "MOVE_TE"): 0.8,
    ("INLINE_TE", "MOVE_TE"): 0.4,
    ("MOVE_TE", "INLINE_TE"): 0.4,
}


def compute_route_overlap(player_route: str | None, competitor_route: str | None) -> float:
    """Compute route tree overlap score between two players."""
    if not player_route or not competitor_route:
        return 0.0
    return ROUTE_OVERLAP_MATRIX.get((player_route, competitor_route), 0.1)


def compute_team_competition(
    session: Session,
    team: str,
    season: int,
    verbose: bool = True,
) -> dict[str, int]:
    """Compute target competition entries for all pass catchers on a team.

    Requires route_tree_type to be populated on Player records.
    """
    stats = {"entries_created": 0}

    pass_catchers = (
        session.query(Player)
        .filter(
            Player.team == team,
            Player.is_active == 1,
            Player.position.in_(["WR", "TE"]),
        )
        .all()
    )

    for player in pass_catchers:
        for competitor in pass_catchers:
            if player.player_id == competitor.player_id:
                continue

            overlap = compute_route_overlap(
                player.route_tree_type, competitor.route_tree_type
            )

            if overlap <= 0.1:
                comp_type = "NONE"
            elif overlap >= 0.6:
                comp_type = "DIRECT"
            else:
                comp_type = "VOLUME"

            comp_id = f"{player.player_id}_{season}_{competitor.player_id}"
            entry = session.get(TargetCompetition, comp_id)
            if not entry:
                entry = TargetCompetition(
                    competition_id=comp_id,
                    player_id=player.player_id,
                    season=season,
                    team=team,
                    competitor_player_id=competitor.player_id,
                    competitor_name=competitor.full_name,
                    competitor_position=competitor.position,
                    competitor_route_type=competitor.route_tree_type,
                    route_overlap_score=overlap,
                    competition_type=comp_type,
                )
                session.add(entry)
                stats["entries_created"] += 1

    session.commit()

    if verbose:
        print(f"Competition for {team}: {stats['entries_created']} entries created")

    return stats
