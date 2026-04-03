"""ADP divergence report — players where sharp consensus disagrees with ADP."""

from sqlalchemy.orm import Session
from tabulate import tabulate

from fantasy_data.models import Player, PlayerSeasonBaseline


def get_adp_divergence(
    session: Session,
    season: int,
    position: str | None = None,
    threshold: int = 12,
    limit: int = 50,
) -> list[dict]:
    """Get players with ADP divergence above threshold.

    Returns list of dicts sorted by absolute divergence descending.
    """
    query = (
        session.query(Player, PlayerSeasonBaseline)
        .join(PlayerSeasonBaseline, Player.player_id == PlayerSeasonBaseline.player_id)
        .filter(
            PlayerSeasonBaseline.season == season,
            PlayerSeasonBaseline.adp_divergence_rank.isnot(None),
        )
    )

    if position and position.upper() != "ALL":
        query = query.filter(Player.position == position.upper())

    if threshold:
        query = query.filter(
            PlayerSeasonBaseline.adp_divergence_flag == 1
        )

    rows = query.all()

    results = []
    for player, baseline in rows:
        direction = "UNDER" if baseline.adp_divergence_rank > 0 else "OVER"
        results.append({
            "player": player.full_name,
            "pos": player.position,
            "team": player.team,
            "adp_rank": baseline.adp_positional_rank,
            "sharp_rank": round(baseline.sharp_consensus_rank, 1) if baseline.sharp_consensus_rank else None,
            "divergence": baseline.adp_divergence_rank,
            "direction": direction,
            "sources": baseline.rankings_source_count,
        })

    results.sort(key=lambda x: abs(x["divergence"] or 0), reverse=True)
    return results[:limit]


def print_adp_divergence(
    session: Session,
    season: int,
    position: str | None = None,
    threshold: int = 12,
) -> None:
    """Print formatted ADP divergence report."""
    results = get_adp_divergence(session, season, position, threshold)

    if not results:
        print(f"No ADP divergences >= {threshold} positions found.")
        return

    headers = ["Player", "Pos", "Team", "ADP Rank", "Sharp Rank",
               "Divergence", "Direction", "Sources"]
    rows = [[r["player"], r["pos"], r["team"], r["adp_rank"],
             r["sharp_rank"], r["divergence"], r["direction"],
             r["sources"]] for r in results]

    print(f"\nADP Divergence Report — {season} season "
          f"(threshold: {threshold}+ positions)")
    print(tabulate(rows, headers=headers, tablefmt="simple"))
    print(f"\n{len(results)} players with significant divergence")
