"""ADP divergence report — players where sharp consensus disagrees with ADP."""

from sqlalchemy.orm import Session
from tabulate import tabulate

from fantasy_data.models import Player, PlayerSeasonBaseline

# Sharp consensus is a mean of per-source positional ranks, so a player covered
# by few sources has a noisier mean and lands further from ADP for reasons that
# are variance, not disagreement. On the 2026 board, 2-source players averaged
# 30.5 absolute divergence against 5.0 for 4-source players — 6x — which put 9
# of the 11 two-source players in the top 20. Sorting by divergence alone
# therefore surfaces the least-supported players as the strongest edges.
DEFAULT_MIN_SOURCES = 3


def get_adp_divergence(
    session: Session,
    season: int,
    position: str | None = None,
    threshold: int = 12,
    limit: int = 50,
    min_sources: int = DEFAULT_MIN_SOURCES,
) -> list[dict]:
    """Get players with ADP divergence above threshold.

    Returns list of dicts sorted by absolute divergence descending.

    `min_sources` drops players whose sharp consensus rests on fewer than that
    many ranking sources. Pass 0 to disable and see every player.
    """
    query = (
        session.query(Player, PlayerSeasonBaseline)
        .join(PlayerSeasonBaseline, Player.player_id == PlayerSeasonBaseline.player_id)
        .filter(
            PlayerSeasonBaseline.season == season,
            PlayerSeasonBaseline.adp_divergence_pos.isnot(None),
        )
    )

    if position and position.upper() != "ALL":
        query = query.filter(Player.position == position.upper())

    if threshold:
        query = query.filter(PlayerSeasonBaseline.adp_divergence_flag == 1)

    if min_sources:
        query = query.filter(PlayerSeasonBaseline.rankings_source_count >= min_sources)

    rows = query.all()

    results = []
    for player, baseline in rows:
        div_pos = baseline.adp_divergence_pos
        direction = "UNDER" if div_pos and div_pos > 0 else "OVER"
        results.append(
            {
                "player": player.full_name,
                "pos": player.position,
                "team": player.team,
                "adp_rank": baseline.adp_positional_rank,
                "sharp_rank": round(baseline.sharp_pos_rank, 1) if baseline.sharp_pos_rank else None,
                "divergence": round(div_pos) if div_pos else None,
                "direction": direction,
                "sources": baseline.rankings_source_count,
            }
        )

    results.sort(key=lambda x: abs(x["divergence"] or 0), reverse=True)
    return results[:limit]


def count_below_min_sources(
    session: Session,
    season: int,
    position: str | None = None,
    threshold: int = 12,
    min_sources: int = DEFAULT_MIN_SOURCES,
) -> int:
    """Count players the min_sources filter excludes, so it can be reported."""
    if not min_sources:
        return 0

    query = (
        session.query(Player, PlayerSeasonBaseline)
        .join(PlayerSeasonBaseline, Player.player_id == PlayerSeasonBaseline.player_id)
        .filter(
            PlayerSeasonBaseline.season == season,
            PlayerSeasonBaseline.adp_divergence_pos.isnot(None),
            PlayerSeasonBaseline.rankings_source_count < min_sources,
        )
    )
    if position and position.upper() != "ALL":
        query = query.filter(Player.position == position.upper())
    if threshold:
        query = query.filter(PlayerSeasonBaseline.adp_divergence_flag == 1)

    return query.count()


def print_adp_divergence(
    session: Session,
    season: int,
    position: str | None = None,
    threshold: int = 12,
    min_sources: int = DEFAULT_MIN_SOURCES,
) -> None:
    """Print formatted ADP divergence report."""
    results = get_adp_divergence(session, season, position, threshold, min_sources=min_sources)
    excluded = count_below_min_sources(session, season, position, threshold, min_sources)

    if not results:
        print(f"No ADP divergences >= {threshold} positions found.")
        if excluded:
            print(f"({excluded} excluded for having fewer than {min_sources} ranking sources.)")
        return

    headers = ["Player", "Pos", "Team", "ADP Rank", "Sharp Rank", "Divergence", "Direction", "Sources"]
    rows = [
        [
            r["player"],
            r["pos"],
            r["team"],
            r["adp_rank"],
            r["sharp_rank"],
            r["divergence"],
            r["direction"],
            r["sources"],
        ]
        for r in results
    ]

    print(f"\nADP Divergence Report — {season} season (threshold: {threshold}+ positions)")
    print(tabulate(rows, headers=headers, tablefmt="simple"))
    print(f"\n{len(results)} players with significant divergence")
    if excluded:
        print(
            f"{excluded} excluded: fewer than {min_sources} ranking sources, "
            f"whose sharp consensus is too noisy to read as disagreement. "
            f"Use --min-sources 0 to include them."
        )
