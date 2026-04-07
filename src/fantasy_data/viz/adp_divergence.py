"""ADP Divergence Board — primary edge output (Plotly)."""

import plotly.graph_objects as go

from fantasy_data.viz.theme import COLORS, apply_theme, color_for_mode, format_axis


def plot_adp_divergence(
    results: list[dict],
    season: int,
    position: str = "All",
    highlight_players: list[str] | None = None,
) -> go.Figure:
    """Plot ADP divergence as horizontal bar chart.

    Args:
        results: output of reports.adp_divergence.get_adp_divergence()
        season: NFL season year.
        position: Position filter label for title.
        highlight_players: Optional player IDs to spotlight.
    """
    neg, mid, pos = color_for_mode("diverging")

    colors = []
    for r in results:
        div = r["divergence"]
        if highlight_players and r.get("player_id") not in highlight_players:
            colors.append(COLORS["data_default"])
        elif div and div > 0:
            colors.append(pos)
        else:
            colors.append(neg)

    opacity = [
        min(1.0, 0.5 + (r["sources"] or 0) * 0.125)
        for r in results
    ]

    hover = [
        f"<b>{r['player']}</b> ({r['pos']}, {r['team']})<br>"
        f"ADP Rank: {r['adp_rank']}<br>"
        f"Sharp Consensus: {r['sharp_rank']}<br>"
        f"Divergence: {r['divergence']:+d}<br>"
        f"Sources: {r['sources']}"
        for r in results
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[r["divergence"] for r in results],
        y=[r["player"] for r in results],
        orientation="h",
        marker=dict(color=colors, opacity=opacity),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=hover,
    ))

    for x_val, dash in [
        (0, "solid"), (12, "dot"), (-12, "dot"), (20, "dash"), (-20, "dash"),
    ]:
        fig.add_vline(
            x=x_val,
            line_dash=dash,
            line_color=COLORS["spine"] if x_val == 0 else COLORS["gridline"],
            line_width=1,
        )

    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        height=max(400, len(results) * 22),
    )

    apply_theme(
        fig,
        title=f"{len(results)} Players Where Sharp Consensus Diverges From ADP",
        subtitle=f"{season} {position} — positive = undervalued by market",
        source="Source: FantasyPoints, LateRound, Underdog, PFF, DraftShark",
    )
    format_axis(fig, "x", "Sharp Consensus Rank − ADP Rank")

    return fig
