"""Players with projection_uncertain_flag = 1 — review list."""

from sqlalchemy.orm import Session
from tabulate import tabulate

from fantasy_data.models import Player, PlayerSeasonBaseline


def get_trust_flags(
    session: Session,
    season: int,
    position: str | None = None,
) -> list[dict]:
    """Get players flagged as projection-uncertain."""
    query = (
        session.query(Player, PlayerSeasonBaseline)
        .join(PlayerSeasonBaseline, Player.player_id == PlayerSeasonBaseline.player_id)
        .filter(
            PlayerSeasonBaseline.season == season,
            PlayerSeasonBaseline.projection_uncertain_flag == 1,
        )
    )

    if position and position.upper() != "ALL":
        query = query.filter(Player.position == position.upper())

    results = []
    for player, baseline in query.all():
        reasons = []
        if baseline.data_trust_weight is not None and baseline.data_trust_weight < 0.3:
            reasons.append("very low trust")
        if baseline.hc_continuity == 0:
            reasons.append("new HC")
        if baseline.oc_continuity == 0:
            reasons.append("new OC")
        if player.team_change_flag:
            reasons.append("team change")
        if player.rookie_flag:
            reasons.append("rookie")

        results.append({
            "player": player.full_name,
            "pos": player.position,
            "team": player.team,
            "trust_weight": round(baseline.data_trust_weight, 3) if baseline.data_trust_weight else None,
            "reasons": ", ".join(reasons) if reasons else "low composite",
        })

    results.sort(key=lambda x: x["trust_weight"] or 0)
    return results


def print_trust_flags(
    session: Session,
    season: int,
    position: str | None = None,
) -> None:
    """Print formatted trust flags report."""
    results = get_trust_flags(session, season, position)

    if not results:
        print("No players flagged as projection-uncertain.")
        return

    headers = ["Player", "Pos", "Team", "Trust Weight", "Reasons"]
    rows = [[r["player"], r["pos"], r["team"], r["trust_weight"],
             r["reasons"]] for r in results]

    print(f"\nProjection Uncertain Players — {season} season")
    print(tabulate(rows, headers=headers, tablefmt="simple"))
    print(f"\n{len(results)} players require manual baseline review")
