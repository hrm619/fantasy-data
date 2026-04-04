"""Rankings Variance Scatter — uncertainty map (Plotly)."""

import plotly.graph_objects as go

from fantasy_data.viz.theme import POSITION_COLORS, apply_plotly_theme


def plot_rankings_variance(results: list[dict], season: int) -> go.Figure:
    """Plot avg rank vs cross-source std dev scatter.

    Args:
        results: output of reports.rankings_variance.get_rankings_variance()
        season: NFL season year.
    """
    apply_plotly_theme()

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

    for pos, color in POSITION_COLORS.items():
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
        y=8.0, line_dash="dot", line_color="#AAAAAA",
        annotation_text="contested threshold",
        annotation_position="right",
    )

    fig.update_layout(
        title=f"Which Players Do Sharp Sources Disagree On Most? — {season}",
        xaxis_title="Average Positional Rank (lower = better)",
        yaxis_title="Cross-Source Std Dev (higher = more disagreement)",
        legend=dict(title="Position", orientation="h", y=-0.12),
        height=560,
    )
    return fig
