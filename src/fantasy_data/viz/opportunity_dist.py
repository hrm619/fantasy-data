"""Opportunity Distribution — role signal EDA (Plotly)."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import gaussian_kde

from fantasy_data.viz.theme import COLORS, apply_theme, color_for_mode, format_axis

POSITION_ORDER = ["QB", "RB", "WR", "TE"]


def _hex_to_rgba(hex_color: str, alpha: float) -> str:
    """Convert a hex color to rgba string."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {alpha})"


def _kde_trace(values: np.ndarray, color: str, name: str) -> go.Scatter:
    """Build a filled KDE scatter trace from raw values."""
    kde = gaussian_kde(values, bw_method="scott")
    x_grid = np.linspace(values.min(), values.max(), 200)
    y_grid = kde(x_grid)
    return go.Scatter(
        x=x_grid,
        y=y_grid,
        mode="lines",
        name=name,
        line=dict(color=color, width=1.5),
        fill="tozeroy",
        fillcolor=_hex_to_rgba(color, 0.2),
        showlegend=False,
    )


def plot_opportunity_distributions(df, season: int) -> go.Figure:
    """Plot KDE distributions of opportunity metrics by position.

    Args:
        df: DataFrame with columns [position, target_share, air_yards_share,
            wopr, snap_share].
        season: NFL season year.
    """
    metrics = ["target_share", "air_yards_share", "wopr", "snap_share"]
    labels = ["Target Share", "Air Yards Share", "WOPR", "Snap Share"]
    cat_colors = color_for_mode("categorical", n=4)
    pos_colors = dict(zip(POSITION_ORDER, cat_colors))

    fig = make_subplots(rows=2, cols=2, subplot_titles=labels, vertical_spacing=0.12, horizontal_spacing=0.1)

    for idx, (metric, label) in enumerate(zip(metrics, labels)):
        row, col = divmod(idx, 2)
        row += 1
        col += 1
        plot_df = df[df[metric].notna()]
        if plot_df.empty:
            continue
        for pos in POSITION_ORDER:
            pos_data = plot_df[plot_df["position"] == pos][metric].values
            if len(pos_data) < 2:
                continue
            trace = _kde_trace(pos_data, pos_colors[pos], pos)
            fig.add_trace(trace, row=row, col=col)

    fig.update_layout(height=650)

    apply_theme(
        fig,
        title="Opportunity Signal Distributions by Position",
        subtitle=f"{season} season — KDE smoothed density estimates",
    )

    return fig


def plot_sharp_vs_adp_scatter(df, season: int) -> go.Figure:
    """Plot sharp consensus rank vs ADP positional rank scatter.

    Points below the 1:1 line are undervalued by ADP.

    Args:
        df: DataFrame with [position, sharp_consensus_rank, adp_positional_rank,
            full_name].
        season: NFL season year.
    """
    cat_colors = color_for_mode("categorical", n=4)
    pos_colors = dict(zip(POSITION_ORDER, cat_colors))

    fig = go.Figure()

    for pos in POSITION_ORDER:
        subset = df[df["position"] == pos]
        if subset.empty:
            continue
        fig.add_trace(go.Scatter(
            x=subset["adp_positional_rank"],
            y=subset["sharp_consensus_rank"],
            mode="markers",
            name=pos,
            marker=dict(
                color=pos_colors[pos],
                size=8,
                opacity=0.75,
                line=dict(width=0.5, color="white"),
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "ADP Rank: %{x}<br>"
                "Sharp Rank: %{y}<extra></extra>"
            ),
            text=subset["full_name"] if "full_name" in subset.columns else None,
        ))

    max_val = max(
        df["adp_positional_rank"].max(),
        df["sharp_consensus_rank"].max(),
    ) + 2
    fig.add_trace(go.Scatter(
        x=[0, max_val],
        y=[0, max_val],
        mode="lines",
        line=dict(color=COLORS["spine"], width=1, dash="dash"),
        showlegend=False,
        hoverinfo="skip",
    ))

    fig.update_layout(
        xaxis=dict(autorange="reversed"),
        yaxis=dict(autorange="reversed"),
        showlegend=True,
        legend=dict(title="Position", orientation="h", y=-0.12),
        height=600,
    )

    apply_theme(
        fig,
        title="Players Below the Line Are Undervalued by ADP",
        subtitle=f"{season} — sharp consensus ranks them higher than the market",
    )
    format_axis(fig, "x", "ADP Positional Rank (market price)")
    format_axis(fig, "y", "Sharp Consensus Rank (true value estimate)")

    return fig
