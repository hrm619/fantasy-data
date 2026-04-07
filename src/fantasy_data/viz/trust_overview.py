"""Trust Overview — projection uncertainty QC (Plotly)."""

from __future__ import annotations

import plotly.graph_objects as go

from fantasy_data.viz.theme import COLORS, apply_theme, format_axis, color_for_mode


def plot_trust_weights(results: list[dict], season: int) -> go.Figure:
    """Plot trust weight distribution for flagged players.

    Args:
        results: output of reports.trust_flags.get_trust_flags()
        season: NFL season year.
    """
    if not results:
        fig = go.Figure()
        fig.add_annotation(
            text="No flagged players",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=COLORS["text_tertiary"]),
        )
        apply_theme(fig, title=f"No Projection-Uncertain Players — {season}")
        return fig

    names = [r["player"] for r in results]
    weights = [r["trust_weight"] or 0 for r in results]
    reasons = [r["reasons"] for r in results]

    diverging = color_for_mode("diverging")
    bar_colors = [
        COLORS["data_default"] if "rookie" in r
        else diverging[0] if "new OC" in r or "new HC" in r
        else COLORS["data_default"]
        for r in reasons
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=weights,
        y=names,
        orientation="h",
        marker_color=bar_colors,
        marker_opacity=0.85,
        text=reasons,
        textposition="outside",
        textfont=dict(size=9, color=COLORS["text_tertiary"]),
        hovertemplate="<b>%{y}</b><br>Trust Weight: %{x:.2f}<br>%{text}<extra></extra>",
    ))

    fig.add_vline(
        x=0.7, line_dash="dash", line_color=COLORS["spine"], line_width=1,
    )

    fig.update_layout(
        xaxis=dict(range=[0, 1.25]),
        yaxis=dict(autorange="reversed"),
        height=max(350, len(names) * 22),
    )

    apply_theme(
        fig,
        title=f"Projection-Uncertain Players Requiring Manual Review",
        subtitle=f"{season} — dashed line marks 0.70 reliability threshold",
    )
    format_axis(fig, "x", "Data Trust Weight")

    return fig
