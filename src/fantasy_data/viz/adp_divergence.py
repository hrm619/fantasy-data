"""ADP Divergence Board — primary edge output (Plotly)."""

import plotly.graph_objects as go

from fantasy_data.viz.theme import COLORS, apply_plotly_theme


def plot_adp_divergence(
    results: list[dict], season: int, position: str = "All"
) -> go.Figure:
    """Plot ADP divergence as horizontal bar chart.

    Args:
        results: output of reports.adp_divergence.get_adp_divergence()
        season: NFL season year.
        position: Position filter label for title.
    """
    apply_plotly_theme()

    colors = [
        COLORS["undervalued"] if r["divergence"] and r["divergence"] > 0
        else COLORS["overvalued"]
        for r in results
    ]
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
            line_color="#CCCCCC" if x_val == 0 else "#AAAAAA",
            line_width=1,
        )

    fig.update_layout(
        title=(
            f"{len(results)} Players Where Sharp Consensus Diverges From ADP — "
            f"{season} {position} (green = undervalued, red = overvalued)"
        ),
        xaxis_title="Sharp Consensus Rank - ADP Rank  (positive = undervalued)",
        yaxis=dict(autorange="reversed"),
        height=max(400, len(results) * 22),
        showlegend=False,
    )
    return fig
