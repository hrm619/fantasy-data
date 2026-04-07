"""Player Profile — per-source rank breakdown bar chart (Plotly)."""

import plotly.graph_objects as go

from fantasy_data.viz.theme import COLORS, apply_theme, color_for_mode, format_axis

SHARP_SOURCES = {"FantasyPoints (fpts)", "LateRound (jj)", "Underdog (hw)", "PFF"}


def plot_player_source_breakdown(data: dict) -> go.Figure:
    """Plot per-source positional rank breakdown for a single player.

    Args:
        data: output of reports.rankings.get_player_rankings()
    """
    bg_color, hl_color = color_for_mode("spotlight")

    sources = data["sources"]
    source_names = list(sources.keys())
    source_ranks = list(sources.values())

    colors = [
        hl_color if name in SHARP_SOURCES else bg_color
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
        textfont=dict(size=10, color=COLORS["text_secondary"]),
        hovertemplate="%{y}: %{x}<extra></extra>",
    ))

    diverging = color_for_mode("diverging")
    if data["adp_positional"]:
        fig.add_vline(
            x=data["adp_positional"],
            line_dash="solid", line_color=diverging[0], line_width=1.5,
            annotation_text=f"ADP: {data['position']}{data['adp_positional']}",
            annotation_position="top right",
            annotation_font=dict(size=10, color=diverging[0]),
        )

    if data["sharp_consensus"]:
        fig.add_vline(
            x=data["sharp_consensus"],
            line_dash="dash", line_color=diverging[2], line_width=1.5,
            annotation_text=f"Sharp: {data['position']}{round(data['sharp_consensus'], 1)}",
            annotation_position="top left",
            annotation_font=dict(size=10, color=diverging[2]),
        )

    divergence = data.get("divergence")
    direction = "undervalued" if divergence and divergence > 0 else "overvalued"
    div_str = f"{divergence:+d} positions ({direction})" if divergence else "n/a"

    fig.update_layout(
        xaxis=dict(autorange="reversed"),
        height=300,
    )

    apply_theme(
        fig,
        title=f"{data['player']} — Divergence: {div_str}",
        subtitle=f"{data['position']}, {data['team']} — {data['season']} | Sharp sources highlighted",
    )
    format_axis(fig, "x", f"{data['position']} Positional Rank")

    return fig
