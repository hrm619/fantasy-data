"""Film-vs-market divergence — where Reception Perception disagrees with the draft board.

`adp_divergence` asks where sharp experts disagree with the public. This asks a different
question: **where does the film disagree with the market?** A player can be well-liked by both
expert consensus and ADP and still have charted badly, or vice versa.

Both sides are converted to within-position percentiles before comparing, because the two scales
are not commensurable — a success rate is 0-100 and a positional rank is 1..N with the good end
at 1. Percentiles also keep the comparison honest across positions, where charted-player counts
differ by an order of magnitude (WR 48, RB 15, QB 19 for the most recent season).

Two limits are deliberate and stated in the output rather than hidden:

  * **RP trails the board.** WR film reaches 2025, RB and QB only 2024, while the market ranks are
    for the season being drafted. The report names the charted season per position; it is never
    the same season as the ranks.
  * **The film pool is not the draft pool.** Percentiles are computed among *charted* players
    only, so "80th percentile" means "top fifth of the players RP charted", not of the position.
"""

from sqlalchemy.orm import Session
from tabulate import tabulate

from fantasy_data.models import Player, PlayerSeasonBaseline, RpQbSeason, RpRbSeason, WrReceptionPerception

# Sharp consensus resting on few sources is noisy — see adp_divergence for the measured effect.
DEFAULT_MIN_SOURCES = 3

# Default percentile-point gap worth showing. Below ~20 the ordering is mostly sampling noise
# given how few players RP charts per position.
DEFAULT_THRESHOLD = 20


def _weighted(pairs: list[tuple[float | None, float | None]]) -> float | None:
    """Attempt-weighted success rate: sum(share x rate) / sum(share).

    Each RP view pairs a usage share with the success rate on that usage, so weighting by the
    player's own mix gives one number without pretending every split matters equally. Returns
    None unless at least one complete pair is present — a partially-charted row should not be
    ranked against fully-charted ones.
    """
    num = 0.0
    den = 0.0
    for share, rate in pairs:
        if share is None or rate is None:
            continue
        num += share * rate
        den += share
    return num / den if den > 0 else None


def _film_score(row) -> float | None:
    """One comparable 'how well did this player chart' number, per position.

    Composed from the source's own splits rather than invented: the WR figure is coverage-mix
    weighted, RB is scheme-mix weighted (falling back to RP's own `OVR SR` where it exists —
    only the prospect export publishes one), QB is depth-mix weighted.
    """
    if isinstance(row, WrReceptionPerception):
        return _weighted([(row.pct_man, row.success_rate_man), (row.pct_zone, row.success_rate_zone)])
    if isinstance(row, RpRbSeason):
        if row.overall_success_pct is not None:
            return row.overall_success_pct
        return _weighted(
            [
                (row.man_gap_att_pct, row.man_gap_success_pct),
                (row.zone_att_pct, row.zone_success_pct),
            ]
        )
    if isinstance(row, RpQbSeason):
        return _weighted(
            [
                (row.short_tar_pct, row.short_sr),
                (row.intermediate_tar_pct, row.intermediate_sr),
                (row.deep_tar_pct, row.deep_sr),
            ]
        )
    return None


def _percentile_ranks(values: dict[str, float], higher_is_better: bool = True) -> dict[str, float]:
    """Map {key: value} to {key: percentile 0-100}, where 100 is best.

    Ties share the same percentile. With N charted players a percentile is coarse — at N=15 each
    step is ~7 points — which is exactly why the default threshold is not small.
    """
    if not values:
        return {}
    # Sort WORST-first in both directions, so one formula serves both: for a success rate the
    # worst value is the smallest, for a positional rank it is the largest. Getting this
    # backwards is silent — every number still looks like a percentile — so the direction is
    # pinned by tests rather than by reading the arithmetic.
    ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=not higher_is_better)
    n = len(ordered)
    out: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and ordered[j + 1][1] == ordered[i][1]:
            j += 1
        # Midpoint of the tied block, as "percent of the field at or below this".
        pct = 100.0 * ((i + j) / 2 + 0.5) / n
        for k in range(i, j + 1):
            out[ordered[k][0]] = round(pct, 1)
        i = j + 1
    return out


def get_rp_divergence(
    session: Session,
    season: int,
    position: str | None = None,
    threshold: int = DEFAULT_THRESHOLD,
    limit: int = 50,
    min_sources: int = DEFAULT_MIN_SOURCES,
) -> list[dict]:
    """Players whose film percentile diverges most from their market percentile.

    `season` is the board season (the one being drafted). Film comes from the most recent charted
    season at or before it, per position, and that season is reported on every row.
    """
    positions = [position.upper()] if position and position.upper() != "ALL" else ["WR", "RB", "QB"]
    models = {"WR": WrReceptionPerception, "RB": RpRbSeason, "QB": RpQbSeason}

    results: list[dict] = []
    for pos in positions:
        model = models.get(pos)
        if model is None:
            continue

        # The newest charted season for this position that is not after the board season.
        charted_season = (
            session.query(model.season)
            .filter(model.season <= season, model.is_prospect == 0)
            .order_by(model.season.desc())
            .limit(1)
            .scalar()
        )
        if charted_season is None:
            continue

        rows = (
            session.query(Player, model, PlayerSeasonBaseline)
            .join(model, Player.player_id == model.player_id)
            .join(
                PlayerSeasonBaseline,
                (PlayerSeasonBaseline.player_id == Player.player_id) & (PlayerSeasonBaseline.season == season),
            )
            .filter(
                model.season == charted_season,
                model.is_prospect == 0,
                PlayerSeasonBaseline.sharp_pos_rank.isnot(None),
            )
            .all()
        )
        if min_sources:
            rows = [r for r in rows if (r[2].rankings_source_count or 0) >= min_sources]

        film = {}
        market = {}
        meta = {}
        for player, charting, baseline in rows:
            score = _film_score(charting)
            if score is None:
                continue
            film[player.player_id] = score
            market[player.player_id] = float(baseline.sharp_pos_rank)
            meta[player.player_id] = (player, baseline)

        # A handful of charted players cannot support percentiles that mean anything.
        if len(film) < 5:
            continue

        film_pct = _percentile_ranks(film, higher_is_better=True)
        market_pct = _percentile_ranks(market, higher_is_better=False)  # rank 1 is best

        for player_id, (player, baseline) in meta.items():
            gap = film_pct[player_id] - market_pct[player_id]
            if threshold and abs(gap) < threshold:
                continue
            results.append(
                {
                    "player": player.full_name,
                    "pos": pos,
                    "team": player.team,
                    "charted": charted_season,
                    "film_score": round(film[player_id], 1),
                    "film_pct": film_pct[player_id],
                    "sharp_rank": round(market[player_id], 1),
                    "market_pct": market_pct[player_id],
                    "gap": round(gap, 1),
                    # FILM_HIGH: charted better than the board rates him.
                    "direction": "FILM_HIGH" if gap > 0 else "FILM_LOW",
                    "sources": baseline.rankings_source_count,
                }
            )

    results.sort(key=lambda r: abs(r["gap"]), reverse=True)
    return results[:limit]


def format_rp_divergence(rows: list[dict], season: int) -> str:
    """Render the report, stating the caveats that make the numbers readable."""
    if not rows:
        return (
            f"No film-vs-market divergence found for {season}.\n"
            "Either nothing cleared the threshold, or no charted player at these positions has "
            "ranking data for this season."
        )

    charted = sorted({(r["pos"], r["charted"]) for r in rows})
    seasons_note = ", ".join(f"{pos} {yr}" for pos, yr in charted)

    table = tabulate(
        [
            [
                r["player"],
                r["pos"],
                r["team"],
                r["charted"],
                r["film_score"],
                r["film_pct"],
                r["sharp_rank"],
                r["market_pct"],
                r["gap"],
                r["direction"],
                r["sources"],
            ]
            for r in rows
        ],
        headers=["Player", "Pos", "Tm", "Film yr", "Film", "Film %ile", "Sharp", "Mkt %ile", "Gap", "Read", "Src"],
        tablefmt="simple",
    )

    return (
        f"Film vs market divergence — {season} board\n"
        f"Film charted: {seasons_note} (Reception Perception, 8-game samples)\n\n"
        f"{table}\n\n"
        "FILM_HIGH = charted better than the board rates him; FILM_LOW = the reverse.\n"
        "Percentiles are among CHARTED players only — RP charts a fraction of each position, so\n"
        "these are not percentiles of the draft pool. The film season is never the board season:\n"
        "RP publishes a season's charting the following year."
    )
