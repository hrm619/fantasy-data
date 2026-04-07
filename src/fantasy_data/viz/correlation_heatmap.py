"""Signal Correlation Heatmap — EDA only (Plotly)."""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from fantasy_data.viz.theme import COLORS, apply_theme

ROLE_SIGNAL_FIELDS = [
    "snap_share", "target_share", "air_yards_share", "wopr",
    "yards_per_route_run", "catch_rate_over_expected",
    "racr", "rz_target_share", "adp_divergence_rank",
]


def plot_role_signal_correlations(df, position: str) -> go.Figure:
    """Plot lower-triangle correlation heatmap for role signal fields.

    Args:
        df: DataFrame filtered to one position with ROLE_SIGNAL_FIELDS columns.
        position: Position label for title.
    """
    available = [f for f in ROLE_SIGNAL_FIELDS if f in df.columns]
    subset = df[available].dropna(how="all")
    corr = subset.corr()

    # Mask upper triangle with NaN
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    corr_masked = corr.where(~mask)

    # Build annotation text
    text_matrix = []
    for i in range(len(available)):
        row = []
        for j in range(len(available)):
            if mask[i][j]:
                row.append("")
            else:
                row.append(f"{corr.iloc[i, j]:.2f}")
        text_matrix.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=corr_masked.values,
        x=available,
        y=available,
        colorscale="RdBu_r",
        zmid=0,
        zmin=-1,
        zmax=1,
        text=text_matrix,
        texttemplate="%{text}",
        textfont=dict(size=9, color=COLORS["text_secondary"]),
        hovertemplate="%{x} vs %{y}: %{z:.2f}<extra></extra>",
        colorbar=dict(
            title=dict(
                text="r",
                font=dict(size=11, color=COLORS["text_secondary"]),
            ),
            tickfont=dict(size=9, color=COLORS["text_tertiary"]),
        ),
    ))

    fig.update_layout(
        height=550,
        width=650,
        xaxis=dict(tickangle=-45),
        yaxis=dict(autorange="reversed"),
    )

    apply_theme(
        fig,
        title=f"Role Signal Correlations — {position}",
        subtitle="Lower triangle only — blue = positive, red = negative",
    )

    return fig
