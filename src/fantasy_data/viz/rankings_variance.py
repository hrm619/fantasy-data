"""Rankings Variance Scatter — uncertainty map (Plotly)."""

import plotly.graph_objects as go

from fantasy_data.viz.theme import COLORS, apply_theme, color_for_mode, format_axis

POSITION_ORDER = ["QB", "RB", "WR", "TE"]


def plot_rankings_variance(
    results: list[dict],
    season: int,
    highlight_players: list[str] | None = None,
) -> go.Figure:
    """Plot avg rank vs cross-source std dev scatter.

    Args:
        results: output of reports.rankings_variance.get_rankings_variance()
        season: NFL season year.
        highlight_players: Optional player IDs to spotlight.
    """
    cat_colors = color_for_mode("categorical", n=4)
    pos_colors = dict(zip(POSITION_ORDER, cat_colors))

    hover = [
        f"<b>{r['player']}</b> ({r['pos']}, {r['team']})<br>"
        f"Avg Rank: {r['avg_rank']}<br>"
        f"Std Dev: {r['std_dev']}<br>"
        f"Range: {r['range']}<br>"
        f"Sharp Consensus: {r['sharp_consensus']}<br>"
        f"Sources: {r['sources']}"
        for r in results
    ]

    fig = go.Figure()

    for pos in POSITION_ORDER:
        color = pos_colors[pos]
        pos_results = [(i, r) for i, r in enumerate(results) if r["pos"] == pos]
        if not pos_results:
            continue
        fig.add_trace(go.Scatter(
            x=[r["avg_rank"] for _, r in pos_results],
            y=[r["std_dev"] for _, r in pos_results],
            mode="markers",
            name=pos,
            marker=dict(
                color=color,
                size=10,
                opacity=0.75,
                line=dict(width=0.5, color="white"),
            ),
            hovertemplate="%{customdata}<extra></extra>",
            customdata=[hover[i] for i, _ in pos_results],
        ))

    fig.add_hline(
        y=8.0, line_dash="dot", line_color=COLORS["spine"],
        annotation_text="contested threshold",
        annotation_position="right",
        annotation_font=dict(size=10, color=COLORS["text_tertiary"]),
    )

    fig.update_layout(
        showlegend=True,
        legend=dict(title="Position", orientation="h", y=-0.12),
        height=560,
    )

    apply_theme(
        fig,
        title=f"Which Players Do Sharp Sources Disagree On Most?",
        subtitle=f"{season} season — higher std dev = more contested evaluation",
    )
    format_axis(fig, "x", "Average Positional Rank (lower = better)")
    format_axis(fig, "y", "Cross-Source Std Dev")

    return fig
