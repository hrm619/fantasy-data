"""Signal Correlation Heatmap — EDA only (Seaborn)."""

import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

from fantasy_data.viz.theme import apply_seaborn_theme

ROLE_SIGNAL_FIELDS = [
    "snap_share", "target_share", "air_yards_share", "wopr",
    "yards_per_route_run", "catch_rate_over_expected",
    "racr", "rz_target_share", "adp_divergence_rank",
]


def plot_role_signal_correlations(df, position: str) -> plt.Figure:
    """Plot lower-triangle correlation heatmap for role signal fields.

    Args:
        df: DataFrame filtered to one position with ROLE_SIGNAL_FIELDS columns.
        position: Position label for title.
    """
    apply_seaborn_theme()

    available = [f for f in ROLE_SIGNAL_FIELDS if f in df.columns]
    subset = df[available].dropna(how="all")
    corr = subset.corr()
    mask = np.triu(np.ones_like(corr, dtype=bool))

    fig, ax = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        corr, mask=mask, annot=True, fmt=".2f",
        cmap="RdBu_r", center=0, vmin=-1, vmax=1,
        linewidths=0.4, ax=ax,
        annot_kws={"size": 9},
    )
    ax.set_title(
        f"Role Signal Correlations — {position} (lower triangle only)",
        fontsize=13,
    )
    plt.tight_layout()
    return fig
