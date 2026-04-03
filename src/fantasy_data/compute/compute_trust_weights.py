"""Compute data_trust_weight for player-season baseline records.

Implements the trust decay formula from PRD Section 6.3:
  base_weight = 1.0
  if oc_continuity = 0: base_weight *= 0.40
  if hc_continuity = 0: base_weight *= 0.65
  if team_change_flag = 1: base_weight *= 0.20
  if injury_flag (4+ games missed): base_weight *= 0.55
  if rookie_flag = 1: base_weight = min(base_weight, 0.50)
  data_trust_weight = max(base_weight, 0.05)
"""

from sqlalchemy.orm import Session

from fantasy_data.models import Player, PlayerSeasonBaseline, CoachingStaff


def compute_trust_weight(
    team_change_flag: int,
    hc_continuity: int,
    oc_continuity: int,
    injury_concern_flag: int,
    rookie_flag: int,
) -> float:
    """Compute data_trust_weight from individual flags.

    Pure function — no database access. Testable in isolation.
    """
    weight = 1.0

    if not oc_continuity:
        weight *= 0.40
    if not hc_continuity:
        weight *= 0.65
    if team_change_flag:
        weight *= 0.20
    if injury_concern_flag:
        weight *= 0.55
    if rookie_flag:
        weight = min(weight, 0.50)

    return max(weight, 0.05)


def compute_all_trust_weights(
    session: Session,
    season: int,
    verbose: bool = True,
) -> dict[str, int]:
    """Compute and store data_trust_weight for all baselines in a season.

    Joins player flags with coaching_staff continuity data to determine
    each player-season's trust weight.
    """
    stats = {"updated": 0, "skipped": 0}

    baselines = session.query(PlayerSeasonBaseline).filter(
        PlayerSeasonBaseline.season == season
    ).all()

    for baseline in baselines:
        player = session.get(Player, baseline.player_id)
        if not player:
            stats["skipped"] += 1
            continue

        # Look up coaching continuity for this player's team in this season
        team = baseline.team or player.team
        staff = session.query(CoachingStaff).filter(
            CoachingStaff.team == team,
            CoachingStaff.season == season,
        ).first()

        hc_cont = staff.hc_continuity_flag if staff else 1
        oc_cont = staff.oc_continuity_flag if staff else 1

        weight = compute_trust_weight(
            team_change_flag=player.team_change_flag or 0,
            hc_continuity=hc_cont,
            oc_continuity=oc_cont,
            injury_concern_flag=player.injury_concern_flag or 0,
            rookie_flag=player.rookie_flag or 0,
        )

        baseline.data_trust_weight = weight
        baseline.hc_continuity = hc_cont
        baseline.oc_continuity = oc_cont

        # Compute seasons_in_system from OC tenure
        if staff and staff.oc_year_with_team:
            baseline.seasons_in_system = min(
                staff.oc_year_with_team, player.years_pro or 1
            )

        # Set projection_uncertain_flag
        baseline.projection_uncertain_flag = 1 if weight < 0.7 else 0

        stats["updated"] += 1

    session.commit()

    if verbose:
        print(f"Trust weights computed: {stats['updated']} updated, "
              f"{stats['skipped']} skipped")

    return stats
