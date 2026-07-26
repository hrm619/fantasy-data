"""Per-source positional rank breakdown for a player."""

from sqlalchemy.orm import Session
from tabulate import tabulate

from fantasy_data.models import Player, PlayerSeasonBaseline


def get_player_rankings(
    session: Session,
    player_id: str,
    season: int,
) -> dict | None:
    """Get per-source ranking breakdown for a specific player, or None if he has no ranking data.

    "No ranking data" is not the same as "no baseline row", and conflating them was the bug this
    guard fixes. A `player_season_baseline` row exists for far more players than any source ranks
    — 1,041 rows for 2026 against 246 ranked players — so keying only on the row's existence
    returned a successful result whose every ranking field was null, for 795 players. Callers
    reported those nulls as findings, and `player_profile`'s documented "raises for anyone outside
    the draft-relevant players" quietly stopped being true.
    """
    baseline = (
        session.query(PlayerSeasonBaseline)
        .filter(
            PlayerSeasonBaseline.player_id == player_id,
            PlayerSeasonBaseline.season == season,
        )
        .first()
    )
    if not baseline:
        return None

    # A row with none of these carries no ranking information at all. Checked together rather
    # than on source_count alone, so a partially-populated board still returns what it has.
    if (
        baseline.sharp_pos_rank is None
        and baseline.adp_positional_rank is None
        and baseline.rankings_source_count is None
    ):
        return None

    player = session.get(Player, player_id)

    return {
        "player": player.full_name if player else player_id,
        "position": player.position if player else "?",
        "team": player.team if player else "?",
        "season": season,
        "sources": {
            "FantasyPoints (fpts)": baseline.rankings_fpts_positional,
            "LateRound (jj)": baseline.rankings_jj_positional,
            "Underdog (hw)": baseline.rankings_hw_positional,
            "PFF": baseline.rankings_pff_positional,
            "DraftShark (ds)": baseline.rankings_ds_positional,
        },
        "avg_positional": baseline.rankings_avg_positional,
        "sharp_consensus": baseline.sharp_consensus_rank,
        "adp_positional": baseline.adp_positional_rank,
        "adp_consensus": baseline.adp_consensus,
        "divergence": baseline.adp_divergence_rank,
        "source_count": baseline.rankings_source_count,
    }


def print_player_rankings(
    session: Session,
    player_id: str,
    season: int,
) -> None:
    """Print formatted per-source ranking breakdown."""
    data = get_player_rankings(session, player_id, season)
    if not data:
        print(f"No rankings found for player {player_id} in {season}")
        return

    print(f"\n{data['player']} ({data['position']}, {data['team']}) — {season}")
    print("=" * 50)

    rows = []
    for source, rank in data["sources"].items():
        rows.append([source, rank if rank is not None else "—"])

    rows.append(["", ""])
    rows.append(["Avg Positional (all)", data["avg_positional"]])
    rows.append(["Sharp Consensus (4 sharp)", data["sharp_consensus"]])
    rows.append(["ADP Positional", data["adp_positional"]])
    rows.append(["ADP Divergence", data["divergence"]])

    print(tabulate(rows, headers=["Source", "Pos Rank"], tablefmt="simple"))
    print(f"\nSources available: {data['source_count']}")
