"""Full player profile — role signals, rankings, trust weight, signals."""

from sqlalchemy.orm import Session
from tabulate import tabulate

from fantasy_data.models import (
    Player, PlayerSeasonBaseline, TargetCompetition, QualitativeSignal,
)


def get_player_profile(
    session: Session,
    player_id: str,
    season: int,
) -> dict | None:
    """Get comprehensive player profile for a season."""
    player = session.get(Player, player_id)
    if not player:
        return None

    baseline = session.get(PlayerSeasonBaseline, f"{player_id}_{season}")

    competitors = (
        session.query(TargetCompetition)
        .filter(
            TargetCompetition.player_id == player_id,
            TargetCompetition.season == season,
        )
        .all()
    )

    signals = (
        session.query(QualitativeSignal)
        .filter(
            QualitativeSignal.player_id == player_id,
            QualitativeSignal.season == season,
        )
        .order_by(QualitativeSignal.confidence_score.desc())
        .limit(5)
        .all()
    )

    return {
        "player": player,
        "baseline": baseline,
        "competitors": competitors,
        "signals": signals,
    }


def print_player_profile(
    session: Session,
    player_id: str,
    season: int,
) -> None:
    """Print formatted player profile."""
    data = get_player_profile(session, player_id, season)
    if not data:
        print(f"Player {player_id} not found.")
        return

    p = data["player"]
    b = data["baseline"]

    print(f"\n{'=' * 60}")
    print(f"  {p.full_name} ({p.position}, {p.team})")
    print(f"  Age: {p.age}  |  Years Pro: {p.years_pro}  |  "
          f"Draft: Rd {p.draft_round or '—'}, Pick {p.draft_pick or '—'}")
    print(f"{'=' * 60}")

    if not b:
        print(f"\n  No baseline data for {season} season.")
        return

    # Trust & Context
    print(f"\n  Trust Weight: {b.data_trust_weight or '—'}")
    print(f"  HC Continuity: {'Yes' if b.hc_continuity else 'No'}  |  "
          f"OC Continuity: {'Yes' if b.oc_continuity else 'No'}  |  "
          f"Seasons in System: {b.seasons_in_system or '—'}")
    if b.projection_uncertain_flag:
        print("  ⚠ PROJECTION UNCERTAIN — insufficient trusted historical data")

    # Role Signals
    if any(getattr(b, f, None) is not None for f in
           ["snap_share", "target_share", "air_yards_share", "wopr"]):
        print(f"\n  --- Role Signals ---")
        rows = []
        for label, field in [
            ("Snap Share", "snap_share"),
            ("Target Share", "target_share"),
            ("Air Yards Share", "air_yards_share"),
            ("RZ Target Share", "rz_target_share"),
            ("WOPR", "wopr"),
            ("Yards/Route Run", "yards_per_route_run"),
            ("Catch Rate Over Expected", "catch_rate_over_expected"),
        ]:
            val = getattr(b, field, None)
            if val is not None:
                rows.append([label, f"{val:.3f}" if isinstance(val, float) else val])
        print(tabulate(rows, tablefmt="plain"))

    # Market Position
    print(f"\n  --- Market Position ---")
    market_rows = [
        ["ADP Consensus", b.adp_consensus],
        ["ADP Positional Rank", b.adp_positional_rank],
        ["Sharp Consensus Rank", f"{b.sharp_consensus_rank:.1f}" if b.sharp_consensus_rank else "—"],
        ["ADP Divergence", b.adp_divergence_rank],
        ["Sources", b.rankings_source_count],
    ]
    print(tabulate(market_rows, tablefmt="plain"))

    # Target Competition
    comps = data["competitors"]
    if comps:
        print(f"\n  --- Target Competition ({len(comps)} competitors) ---")
        comp_rows = []
        for c in sorted(comps, key=lambda x: x.route_overlap_score or 0, reverse=True):
            comp_rows.append([
                c.competitor_name,
                c.competitor_position,
                c.competitor_route_type or "—",
                f"{c.route_overlap_score:.2f}" if c.route_overlap_score else "—",
                c.competition_type,
            ])
        print(tabulate(comp_rows,
                       headers=["Competitor", "Pos", "Route", "Overlap", "Type"],
                       tablefmt="simple"))

    # Qualitative Signals
    sigs = data["signals"]
    if sigs:
        print(f"\n  --- Qualitative Signals (top {len(sigs)}) ---")
        for s in sigs:
            direction = s.signal_direction or "?"
            conf = f"{s.confidence_score:.1f}" if s.confidence_score else "?"
            print(f"  [{direction}] {s.signal_type} (conf: {conf}) — "
                  f"{s.source_name or '?'}")
            print(f"    {s.signal_summary}")

    print()
