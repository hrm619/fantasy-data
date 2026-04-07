"""Visualization module for fantasy-data platform.

Each plot_*() function receives pre-fetched data from the corresponding
reports.get_*() function. No database calls inside chart functions.

All charts use Plotly and the NYT-inspired theme from theme.py.
"""

from .theme import (
    COLORS,
    FONTS,
    LAYOUT,
    apply_theme,
    color_for_mode,
    annotate_point,
    label_endpoint,
    format_axis,
)
from .adp_divergence import plot_adp_divergence
from .rankings_variance import plot_rankings_variance
from .player_profile import plot_player_source_breakdown
from .opportunity_dist import plot_opportunity_distributions, plot_sharp_vs_adp_scatter
from .correlation_heatmap import plot_role_signal_correlations
from .trust_overview import plot_trust_weights

__all__ = [
    # Theme API
    "COLORS",
    "FONTS",
    "LAYOUT",
    "apply_theme",
    "color_for_mode",
    "annotate_point",
    "label_endpoint",
    "format_axis",
    # Chart functions
    "plot_adp_divergence",
    "plot_rankings_variance",
    "plot_player_source_breakdown",
    "plot_opportunity_distributions",
    "plot_sharp_vs_adp_scatter",
    "plot_role_signal_correlations",
    "plot_trust_weights",
]
