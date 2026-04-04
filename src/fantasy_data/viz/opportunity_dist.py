"""Opportunity Distribution — role signal EDA (Seaborn)."""

import seaborn as sns
import matplotlib.pyplot as plt

from fantasy_data.viz.theme import apply_seaborn_theme, POSITION_COLORS


def plot_opportunity_distributions(df, season: int) -> plt.Figure:
    """Plot KDE distributions of opportunity metrics by position.

    Args:
        df: DataFrame with columns [position, target_share, air_yards_share,
            wopr, snap_share].
        season: NFL season year.
    """
    apply_seaborn_theme()
    metrics = ["target_share", "air_yards_share", "wopr", "snap_share"]
    labels = ["Target Share", "Air Yards Share", "WOPR", "Snap Share"]

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    axes = axes.flatten()

    for ax, metric, label in zip(axes, metrics, labels):
        plot_df = df[df[metric].notna()]
        if plot_df.empty:
            ax.set_title(f"{label} — no data")
            continue
        sns.kdeplot(
            data=plot_df,
            x=metric, hue="position",
            palette=POSITION_COLORS,
            fill=True, alpha=0.3, linewidth=1.5,
            ax=ax,
        )
        ax.set_title(f"{label} Distribution — {season}")
        ax.set_xlabel(label)
        ax.set_ylabel("Density")

    fig.suptitle(
        f"Opportunity Signal Distributions by Position — {season} Season",
        fontsize=15, fontweight="bold", y=1.01,
    )
    plt.tight_layout()
    return fig


def plot_sharp_vs_adp_scatter(df, season: int) -> plt.Figure:
    """Plot sharp consensus rank vs ADP positional rank scatter.

    The canonical preseason edge-hunting visual. Points below the 1:1 line
    are undervalued by ADP.

    Args:
        df: DataFrame with [position, sharp_consensus_rank, adp_positional_rank,
            full_name].
        season: NFL season year.
    """
    apply_seaborn_theme()
    fig, ax = plt.subplots(figsize=(11, 9))

    for pos, color in POSITION_COLORS.items():
        subset = df[df["position"] == pos]
        ax.scatter(
            subset["adp_positional_rank"],
            subset["sharp_consensus_rank"],
            c=color, label=pos, alpha=0.7, s=50, linewidths=0,
        )

    max_val = max(
        df["adp_positional_rank"].max(),
        df["sharp_consensus_rank"].max(),
    ) + 2
    ax.plot([0, max_val], [0, max_val], color="#CCCCCC",
            linewidth=1, linestyle="--", label="ADP = Sharp")

    ax.set_title(
        "Players Below the Line Are Undervalued by ADP — "
        "Sharp Consensus Ranks Them Higher",
        fontsize=12,
    )
    ax.set_xlabel("ADP Positional Rank (market price)")
    ax.set_ylabel("Sharp Consensus Rank (true value estimate)")
    ax.legend(title="Position", loc="upper left")
    ax.invert_xaxis()
    ax.invert_yaxis()
    return fig
