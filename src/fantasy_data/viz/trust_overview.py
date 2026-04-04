"""Trust Overview — internal QC (Seaborn)."""

import seaborn as sns
import matplotlib.pyplot as plt

from fantasy_data.viz.theme import apply_seaborn_theme, COLORS


def plot_trust_weights(results: list[dict], season: int) -> plt.Figure:
    """Plot trust weight distribution for flagged players.

    Args:
        results: output of reports.trust_flags.get_trust_flags()
        season: NFL season year.
    """
    apply_seaborn_theme()

    if not results:
        fig, ax = plt.subplots()
        ax.text(0.5, 0.5, "No flagged players", ha="center", va="center",
                transform=ax.transAxes)
        return fig

    names = [r["player"] for r in results]
    weights = [r["trust_weight"] or 0 for r in results]
    reasons = [r["reasons"] for r in results]

    bar_colors = [
        COLORS["uncertain"] if "rookie" in r
        else COLORS["negative"] if "new OC" in r or "new HC" in r
        else COLORS["muted"]
        for r in reasons
    ]

    fig, ax = plt.subplots(figsize=(11, max(5, len(names) * 0.35)))
    bars = ax.barh(names, weights, color=bar_colors, alpha=0.85)

    for bar, reason in zip(bars, reasons):
        ax.text(
            bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
            reason, va="center", fontsize=9, color="#555555",
        )

    ax.axvline(x=0.7, linestyle="--", color="#AAAAAA", linewidth=1,
               label="min reliable threshold (0.70)")
    ax.set_xlim(0, 1.25)
    ax.set_xlabel("Data Trust Weight")
    ax.set_title(
        f"Projection-Uncertain Players — {season} "
        f"(below 0.70 threshold requires manual review)",
    )
    ax.legend(loc="lower right")
    ax.invert_yaxis()
    plt.tight_layout()
    return fig
