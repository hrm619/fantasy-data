"""Cross-source disagreement report — high variance = market uncertainty."""

import math

from sqlalchemy.orm import Session
from tabulate import tabulate

from fantasy_data.models import Player, PlayerSeasonBaseline


def get_rankings_variance(
    session: Session,
    season: int,
    position: str | None = None,
    min_sources: int = 3,
    limit: int = 50,
) -> list[dict]:
    """Get players ranked by cross-source standard deviation.

    High variance indicates market uncertainty — potential edge hunting ground.
    """
    query = (
        session.query(Player, PlayerSeasonBaseline)
        .join(PlayerSeasonBaseline, Player.player_id == PlayerSeasonBaseline.player_id)
        .filter(
            PlayerSeasonBaseline.season == season,
            PlayerSeasonBaseline.rankings_source_count >= min_sources,
        )
    )

    if position and position.upper() != "ALL":
        query = query.filter(Player.position == position.upper())

    results = []
    for player, baseline in query.all():
        ranks = [
            baseline.rankings_fpts_positional,
            baseline.rankings_jj_positional,
            baseline.rankings_hw_positional,
            baseline.rankings_pff_positional,
            baseline.rankings_ds_positional,
        ]
        valid_ranks = [r for r in ranks if r is not None]

        if len(valid_ranks) < min_sources:
            continue

        mean = sum(valid_ranks) / len(valid_ranks)
        variance = sum((r - mean) ** 2 for r in valid_ranks) / len(valid_ranks)
        std_dev = math.sqrt(variance)

        results.append({
            "player": player.full_name,
            "pos": player.position,
            "team": player.team,
            "avg_rank": round(mean, 1),
            "std_dev": round(std_dev, 1),
            "range": f"{min(valid_ranks)}-{max(valid_ranks)}",
            "sources": len(valid_ranks),
            "sharp_consensus": round(baseline.sharp_consensus_rank, 1) if baseline.sharp_consensus_rank else None,
        })

    results.sort(key=lambda x: x["std_dev"], reverse=True)
    return results[:limit]


def print_rankings_variance(
    session: Session,
    season: int,
    position: str | None = None,
    min_sources: int = 3,
) -> None:
    """Print formatted rankings variance report."""
    results = get_rankings_variance(session, season, position, min_sources)

    if not results:
        print("No players found with sufficient source coverage.")
        return

    headers = ["Player", "Pos", "Team", "Avg Rank", "Std Dev",
               "Range", "Sources", "Sharp"]
    rows = [[r["player"], r["pos"], r["team"], r["avg_rank"],
             r["std_dev"], r["range"], r["sources"],
             r["sharp_consensus"]] for r in results]

    pos_label = position.upper() if position and position.upper() != "ALL" else "All"
    print(f"\nRankings Variance Report — {season} season "
          f"({pos_label}, min {min_sources} sources)")
    print(tabulate(rows, headers=headers, tablefmt="simple"))
    print(f"\n{len(results)} players shown, sorted by cross-source disagreement")
