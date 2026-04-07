"""Tests for visualization module."""

import pytest
import pandas as pd
import plotly.graph_objects as go


class TestTheme:
    def test_colors_has_required_keys(self):
        from fantasy_data.viz.theme import COLORS
        required = {
            "background", "text_primary", "text_secondary", "text_tertiary",
            "spine", "gridline", "data_default", "spotlight",
            "diverging_pos", "diverging_neg", "diverging_mid",
            "cat_1", "cat_2", "cat_3", "cat_4",
        }
        assert required.issubset(COLORS.keys())

    def test_fonts_has_required_keys(self):
        from fantasy_data.viz.theme import FONTS
        required = {"title", "subtitle", "axis_label", "tick_label", "annotation", "source"}
        assert required.issubset(FONTS.keys())

    def test_apply_theme_returns_figure(self):
        from fantasy_data.viz.theme import apply_theme
        fig = go.Figure()
        result = apply_theme(fig, title="Test Title")
        assert result is fig

    def test_apply_theme_sets_title_annotation(self):
        from fantasy_data.viz.theme import apply_theme
        fig = go.Figure()
        apply_theme(fig, title="My Insight Title", subtitle="A subtitle")
        texts = [a.text for a in fig.layout.annotations]
        assert "My Insight Title" in texts
        assert "A subtitle" in texts

    def test_color_for_mode_default(self):
        from fantasy_data.viz.theme import color_for_mode
        colors = color_for_mode("default", n=3)
        assert len(colors) == 3
        assert all(c == colors[0] for c in colors)

    def test_color_for_mode_spotlight(self):
        from fantasy_data.viz.theme import color_for_mode
        colors = color_for_mode("spotlight")
        assert len(colors) == 2

    def test_color_for_mode_diverging(self):
        from fantasy_data.viz.theme import color_for_mode
        colors = color_for_mode("diverging")
        assert len(colors) == 3

    def test_color_for_mode_categorical_raises_above_4(self):
        from fantasy_data.viz.theme import color_for_mode
        with pytest.raises(ValueError, match="at most 4"):
            color_for_mode("categorical", n=5)

    def test_color_for_mode_unknown_raises(self):
        from fantasy_data.viz.theme import color_for_mode
        with pytest.raises(ValueError, match="Unknown color mode"):
            color_for_mode("fancy")

    def test_annotate_point(self):
        from fantasy_data.viz.theme import annotate_point
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2], y=[3, 4]))
        result = annotate_point(fig, 2, 4, "Peak")
        assert result is fig
        assert len(fig.layout.annotations) == 1

    def test_format_axis(self):
        from fantasy_data.viz.theme import format_axis
        fig = go.Figure()
        result = format_axis(fig, "x", "My X Axis")
        assert result is fig


class TestAdpDivergencePlot:
    def test_returns_plotly_figure(self):
        from fantasy_data.viz.adp_divergence import plot_adp_divergence
        results = [
            {"player": "Player A", "pos": "WR", "team": "KC",
             "adp_rank": 15, "sharp_rank": 5.0, "divergence": 10,
             "direction": "UNDER", "sources": 4},
            {"player": "Player B", "pos": "RB", "team": "SF",
             "adp_rank": 5, "sharp_rank": 18.0, "divergence": -13,
             "direction": "OVER", "sources": 4},
        ]
        fig = plot_adp_divergence(results, 2025)
        assert isinstance(fig, go.Figure)

    def test_empty_results(self):
        from fantasy_data.viz.adp_divergence import plot_adp_divergence
        fig = plot_adp_divergence([], 2025)
        assert isinstance(fig, go.Figure)


class TestPlayerProfilePlot:
    def test_returns_plotly_figure(self):
        from fantasy_data.viz.player_profile import plot_player_source_breakdown
        data = {
            "player": "Patrick Mahomes", "position": "QB", "team": "KC",
            "season": 2025,
            "sources": {
                "FantasyPoints (fpts)": 1, "LateRound (jj)": 2,
                "Underdog (hw)": 1, "PFF": 3, "DraftShark (ds)": 2,
            },
            "avg_positional": 1.8, "sharp_consensus": 1.75,
            "adp_positional": 1, "adp_consensus": 2.5,
            "divergence": 0, "source_count": 5,
        }
        fig = plot_player_source_breakdown(data)
        assert isinstance(fig, go.Figure)


class TestRankingsVariancePlot:
    def test_returns_plotly_figure(self):
        from fantasy_data.viz.rankings_variance import plot_rankings_variance
        results = [
            {"player": "Player A", "pos": "WR", "team": "KC",
             "avg_rank": 8.0, "std_dev": 5.2, "range": "3-15",
             "sources": 5, "sharp_consensus": 6.0},
            {"player": "Player B", "pos": "QB", "team": "SF",
             "avg_rank": 3.0, "std_dev": 1.1, "range": "2-5",
             "sources": 4, "sharp_consensus": 2.5},
        ]
        fig = plot_rankings_variance(results, 2025)
        assert isinstance(fig, go.Figure)


class TestOpportunityDistPlot:
    def test_returns_plotly_figure(self):
        from fantasy_data.viz.opportunity_dist import plot_opportunity_distributions
        df = pd.DataFrame({
            "position": ["WR"] * 10 + ["RB"] * 10 + ["QB"] * 10,
            "target_share": [0.25, 0.30, 0.22, 0.18, 0.28, 0.15, 0.20, 0.27, 0.23, 0.26,
                             0.08, 0.05, 0.06, 0.07, 0.09, 0.04, 0.10, 0.03, 0.06, 0.08,
                             0.0, 0.0, 0.01, 0.0, 0.02, 0.0, 0.01, 0.0, 0.0, 0.01],
            "air_yards_share": [0.30, 0.35, 0.28, 0.25, 0.33, 0.20, 0.27, 0.32, 0.29, 0.31,
                                0.02, 0.01, 0.03, 0.02, 0.01, 0.04, 0.02, 0.01, 0.03, 0.02,
                                0.0, 0.0, 0.01, 0.0, 0.0, 0.01, 0.0, 0.0, 0.01, 0.0],
            "wopr": [0.5, 0.6, 0.45, 0.4, 0.55, 0.35, 0.48, 0.58, 0.52, 0.54,
                     0.1, 0.08, 0.12, 0.09, 0.11, 0.07, 0.13, 0.06, 0.10, 0.09,
                     0.0, 0.0, 0.01, 0.0, 0.02, 0.0, 0.01, 0.0, 0.0, 0.01],
            "snap_share": [0.90, 0.85, 0.88, 0.82, 0.92, 0.78, 0.86, 0.91, 0.87, 0.89,
                           0.60, 0.55, 0.58, 0.52, 0.62, 0.50, 0.57, 0.53, 0.59, 0.56,
                           0.98, 0.95, 0.97, 0.96, 0.99, 0.94, 0.96, 0.95, 0.98, 0.97],
        })
        fig = plot_opportunity_distributions(df, 2024)
        assert isinstance(fig, go.Figure)

    def test_sharp_vs_adp_scatter(self):
        from fantasy_data.viz.opportunity_dist import plot_sharp_vs_adp_scatter
        df = pd.DataFrame({
            "position": ["WR", "WR", "RB", "QB"],
            "adp_positional_rank": [5, 12, 3, 1],
            "sharp_consensus_rank": [3.0, 15.0, 1.5, 2.0],
            "full_name": ["A", "B", "C", "D"],
        })
        fig = plot_sharp_vs_adp_scatter(df, 2025)
        assert isinstance(fig, go.Figure)


class TestCorrelationHeatmap:
    def test_returns_plotly_figure(self):
        from fantasy_data.viz.correlation_heatmap import plot_role_signal_correlations
        df = pd.DataFrame({
            "snap_share": [0.9, 0.8, 0.7, 0.6, 0.5],
            "target_share": [0.25, 0.20, 0.15, 0.10, 0.30],
            "air_yards_share": [0.30, 0.25, 0.20, 0.15, 0.35],
            "wopr": [0.5, 0.4, 0.3, 0.2, 0.6],
        })
        fig = plot_role_signal_correlations(df, "WR")
        assert isinstance(fig, go.Figure)


class TestTrustOverview:
    def test_returns_plotly_figure(self):
        from fantasy_data.viz.trust_overview import plot_trust_weights
        results = [
            {"player": "Player A", "pos": "QB", "team": "CHI",
             "trust_weight": 0.05, "reasons": "rookie, new HC, new OC"},
            {"player": "Player B", "pos": "WR", "team": "CAR",
             "trust_weight": 0.40, "reasons": "new OC"},
        ]
        fig = plot_trust_weights(results, 2024)
        assert isinstance(fig, go.Figure)

    def test_empty_results(self):
        from fantasy_data.viz.trust_overview import plot_trust_weights
        fig = plot_trust_weights([], 2024)
        assert isinstance(fig, go.Figure)
