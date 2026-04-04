"""Visualization module for fantasy-data platform.

Each plot_*() function receives pre-fetched data from the corresponding
reports.get_*() function. No database calls inside chart functions.
"""

from .adp_divergence import plot_adp_divergence
from .rankings_variance import plot_rankings_variance
from .player_profile import plot_player_source_breakdown
from .opportunity_dist import plot_opportunity_distributions, plot_sharp_vs_adp_scatter
from .correlation_heatmap import plot_role_signal_correlations
from .trust_overview import plot_trust_weights

__all__ = [
    "plot_adp_divergence",
    "plot_rankings_variance",
    "plot_player_source_breakdown",
    "plot_opportunity_distributions",
    "plot_sharp_vs_adp_scatter",
    "plot_role_signal_correlations",
    "plot_trust_weights",
]
