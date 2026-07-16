"""Compute data_trust_weight for player-season baseline records.

Implements the trust decay formula from PRD Section 6.3, extended with
QB continuity (position-weighted):

  base_weight = 1.0
  if oc_continuity = 0: base_weight *= 0.40
  if hc_continuity = 0: base_weight *= 0.65
  if qb_continuity = 0:
      WR/TE: base_weight *= 0.50
      RB:    base_weight *= 0.75
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
    qb_continuity: int,
    injury_concern_flag: int,
    rookie_flag: int,
    position: str = "WR",
) -> float:
    """Compute data_trust_weight from individual flags.

    Pure function — no database access. Testable in isolation.
    QB continuity is position-weighted: full penalty for WR/TE, half for RB.
    """
    weight = 1.0

    if not oc_continuity:
        weight *= 0.40
    if not hc_continuity:
        weight *= 0.65
    if not qb_continuity and position != "QB":
        if position in ("WR", "TE"):
            weight *= 0.50
        elif position == "RB":
            weight *= 0.75
    if team_change_flag:
        weight *= 0.20
    if injury_concern_flag:
        weight *= 0.55
    if rookie_flag:
        weight = min(weight, 0.50)

    return max(weight, 0.05)


def populate_starting_qbs(session: Session, season: int) -> int:
    """Detect starting QBs and set qb_continuity_flag on coaching_staff.

    For each team, finds the QB with the most games_started (or snap_share)
    in that season's baselines. Compares to the prior season's starter.
    Sets qb_continuity_flag = 0 if the starter changed.

    Returns the number of QB changes detected.
    """
    changes = 0
    staffs = session.query(CoachingStaff).filter(CoachingStaff.season == season).all()

    for staff in staffs:
        team = staff.team

        # Find this season's starting QB
        current_qb = _find_starting_qb(session, team, season)
        if current_qb:
            staff.starting_qb = current_qb.full_name

        # Find prior season's starting QB
        prior_qb = _find_starting_qb(session, team, season - 1)

        # Compare
        if current_qb and prior_qb:
            if current_qb.player_id != prior_qb.player_id:
                staff.qb_continuity_flag = 0
                changes += 1
            else:
                staff.qb_continuity_flag = 1
        elif current_qb and not prior_qb:
            # No prior data — check if starter is already set from seed data
            if staff.qb_continuity_flag is None:
                staff.qb_continuity_flag = 1  # Assume continuity if unknown
        # If no current QB data, leave existing flag untouched

    session.flush()
    return changes


def _find_starting_qb(session: Session, team: str, season: int) -> Player | None:
    """Find the starting QB for a team-season by games_started, then snap_share."""
    result = (
        session.query(Player)
        .join(PlayerSeasonBaseline, Player.player_id == PlayerSeasonBaseline.player_id)
        .filter(
            Player.position == "QB",
            PlayerSeasonBaseline.season == season,
            PlayerSeasonBaseline.team == team,
        )
        .order_by(
            PlayerSeasonBaseline.games_started.desc().nulls_last(),
            PlayerSeasonBaseline.snap_share.desc().nulls_last(),
        )
        .first()
    )
    return result


def compute_team_tenure(session: Session, season: int) -> dict[str, int]:
    """Consecutive seasons each player has spent with their `season` team.

    Caps `seasons_in_system`: a system can be a decade old, but a player who
    arrived this year has been in it for one season. The previous formula capped
    by `players.years_pro` instead, which is wrong twice over — it measures
    league experience rather than time on the team (a 12-year veteran joining a
    10-year-old system would score 10), and it is a single static value applied
    to every season of a player's career. It was also never populated, so
    `min(system_years, years_pro or 1)` returned 1 for every player in every
    season since inception.

    A player's team for a season is already recorded per row, so no new source
    is needed. A gap or a team change ends the run.
    """
    rows = (
        session.query(
            PlayerSeasonBaseline.player_id,
            PlayerSeasonBaseline.season,
            PlayerSeasonBaseline.team,
        )
        .filter(PlayerSeasonBaseline.season <= season)
        .all()
    )

    teams_by_player: dict[str, dict[int, str | None]] = {}
    for player_id, row_season, team in rows:
        teams_by_player.setdefault(player_id, {})[row_season] = team

    tenure: dict[str, int] = {}
    for player_id, seasons in teams_by_player.items():
        current_team = seasons.get(season)
        if not current_team:
            continue  # unknown team — leave seasons_in_system NULL rather than guess
        years, cursor = 0, season
        while seasons.get(cursor) == current_team:
            years += 1
            cursor -= 1
        tenure[player_id] = years

    return tenure


def compute_all_trust_weights(
    session: Session,
    season: int,
    verbose: bool = True,
) -> dict[str, int]:
    """Compute and store data_trust_weight for all baselines in a season.

    Joins player flags with coaching_staff continuity data to determine
    each player-season's trust weight. Auto-detects QB changes.
    """
    stats = {"updated": 0, "skipped": 0}

    # Auto-detect QB changes before computing weights
    qb_changes = populate_starting_qbs(session, season)
    if verbose and qb_changes:
        print(f"  QB changes detected: {qb_changes} teams")

    team_tenure = compute_team_tenure(session, season)
    baselines = session.query(PlayerSeasonBaseline).filter(PlayerSeasonBaseline.season == season).all()

    for baseline in baselines:
        player = session.get(Player, baseline.player_id)
        if not player:
            stats["skipped"] += 1
            continue

        # Look up coaching continuity for this player's team in this season
        team = baseline.team or player.team
        staff = (
            session.query(CoachingStaff)
            .filter(
                CoachingStaff.team == team,
                CoachingStaff.season == season,
            )
            .first()
        )

        # Coalesce a missing flag (None) to the column default of 1 ("continuity"),
        # but preserve a real 0 (a discontinuity), so `is not None` rather than `or 1`.
        hc_cont = staff.hc_continuity_flag if staff and staff.hc_continuity_flag is not None else 1
        oc_cont = staff.oc_continuity_flag if staff and staff.oc_continuity_flag is not None else 1
        qb_cont = staff.qb_continuity_flag if staff and staff.qb_continuity_flag is not None else 1

        weight = compute_trust_weight(
            team_change_flag=player.team_change_flag or 0,
            hc_continuity=hc_cont,
            oc_continuity=oc_cont,
            qb_continuity=qb_cont,
            injury_concern_flag=player.injury_concern_flag or 0,
            rookie_flag=player.rookie_flag or 0,
            position=player.position or "WR",
        )

        baseline.data_trust_weight = weight
        baseline.hc_continuity = hc_cont
        baseline.oc_continuity = oc_cont

        # Seasons this player has spent in this offensive system: the system's
        # own tenure, capped by how long the player has actually been on the team.
        system_years = staff.system_year_with_team if staff else None
        player_years = team_tenure.get(baseline.player_id)
        if system_years and player_years:
            baseline.seasons_in_system = min(system_years, player_years)

        # Set projection_uncertain_flag
        baseline.projection_uncertain_flag = 1 if weight < 0.7 else 0

        stats["updated"] += 1

    session.commit()

    if verbose:
        print(f"Trust weights computed: {stats['updated']} updated, {stats['skipped']} skipped")

    return stats
