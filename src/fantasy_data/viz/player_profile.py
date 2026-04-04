"""Player Profile — per-source rank breakdown bar chart (Plotly)."""

import plotly.graph_objects as go

from fantasy_data.viz.theme import COLORS, apply_plotly_theme

SHARP_SOURCES = {"FantasyPoints (fpts)", "LateRound (jj)", "Underdog (hw)", "PFF"}


def plot_player_source_breakdown(data: dict) -> go.Figure:
    """Plot per-source positional rank breakdown for a single player.

    Args:
        data: output of reports.rankings.get_player_rankings()
    """
    apply_plotly_theme()

    sources = data["sources"]
    source_names = list(sources.keys())
    source_ranks = list(sources.values())

    colors = [
        COLORS["highlight"] if name in SHARP_SOURCES else COLORS["muted"]
        for name in source_names
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=source_ranks,
        y=source_names,
        orientation="h",
        marker_color=colors,
        text=[str(r) if r is not None else "" for r in source_ranks],
        textposition="outside",
        hovertemplate="%{y}: %{x}<extra></extra>",
    ))

    if data["adp_positional"]:
        fig.add_vline(
            x=data["adp_positional"],
            line_dash="solid", line_color=COLORS["overvalued"], line_width=2,
            annotation_text=f"ADP: {data['position']}{data['adp_positional']}",
            annotation_position="top right",
        )

    if data["sharp_consensus"]:
        fig.add_vline(
            x=data["sharp_consensus"],
            line_dash="dash", line_color=COLORS["undervalued"], line_width=2,
            annotation_text=f"Sharp: {data['position']}{round(data['sharp_consensus'], 1)}",
            annotation_position="top left",
        )

    divergence = data.get("divergence")
    direction = "undervalued" if divergence and divergence > 0 else "overvalued"
    div_str = f"{divergence:+d} positions" if divergence else "n/a"

    fig.update_layout(
        title=(
            f"{data['player']} ({data['position']}, {data['team']}) — "
            f"{data['season']} | Divergence: {div_str} ({direction})"
        ),
        xaxis_title=f"{data['position']} Positional Rank",
        xaxis=dict(autorange="reversed"),
        height=300,
        showlegend=False,
    )
    return fig
