"""Tests for visualization module."""

import pytest
import pandas as pd
import plotly.graph_objects as go
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for testing
import matplotlib.pyplot as plt


class TestTheme:
    def test_seaborn_theme_applies(self):
        from fantasy_data.viz.theme import apply_seaborn_theme
        apply_seaborn_theme()  # should not raise

    def test_plotly_theme_applies(self):
        from fantasy_data.viz.theme import apply_plotly_theme
        import plotly.io as pio
        apply_plotly_theme()
        assert "quant_edge" in pio.templates

    def test_palette_has_8_colors(self):
        from fantasy_data.viz.theme import PALETTE
        assert len(PALETTE) == 8

    def test_position_colors_has_4_positions(self):
        from fantasy_data.viz.theme import POSITION_COLORS
        assert set(POSITION_COLORS.keys()) == {"QB", "RB", "WR", "TE"}


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
    def test_returns_matplotlib_figure(self):
        from fantasy_data.viz.opportunity_dist import plot_opportunity_distributions
        df = pd.DataFrame({
            "position": ["WR", "WR", "RB", "RB", "QB", "QB"],
            "target_share": [0.25, 0.30, 0.08, 0.05, 0.0, 0.0],
            "air_yards_share": [0.30, 0.35, 0.02, 0.01, 0.0, 0.0],
            "wopr": [0.5, 0.6, 0.1, 0.08, 0.0, 0.0],
            "snap_share": [0.90, 0.85, 0.60, 0.55, 0.98, 0.95],
        })
        fig = plot_opportunity_distributions(df, 2024)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_sharp_vs_adp_scatter(self):
        from fantasy_data.viz.opportunity_dist import plot_sharp_vs_adp_scatter
        df = pd.DataFrame({
            "position": ["WR", "WR", "RB", "QB"],
            "adp_positional_rank": [5, 12, 3, 1],
            "sharp_consensus_rank": [3.0, 15.0, 1.5, 2.0],
            "full_name": ["A", "B", "C", "D"],
        })
        fig = plot_sharp_vs_adp_scatter(df, 2025)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestCorrelationHeatmap:
    def test_returns_matplotlib_figure(self):
        from fantasy_data.viz.correlation_heatmap import plot_role_signal_correlations
        df = pd.DataFrame({
            "snap_share": [0.9, 0.8, 0.7, 0.6, 0.5],
            "target_share": [0.25, 0.20, 0.15, 0.10, 0.30],
            "air_yards_share": [0.30, 0.25, 0.20, 0.15, 0.35],
            "wopr": [0.5, 0.4, 0.3, 0.2, 0.6],
        })
        fig = plot_role_signal_correlations(df, "WR")
        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestTrustOverview:
    def test_returns_matplotlib_figure(self):
        from fantasy_data.viz.trust_overview import plot_trust_weights
        results = [
            {"player": "Player A", "pos": "QB", "team": "CHI",
             "trust_weight": 0.05, "reasons": "rookie, new HC, new OC"},
            {"player": "Player B", "pos": "WR", "team": "CAR",
             "trust_weight": 0.40, "reasons": "new OC"},
        ]
        fig = plot_trust_weights(results, 2024)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_empty_results(self):
        from fantasy_data.viz.trust_overview import plot_trust_weights
        fig = plot_trust_weights([], 2024)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)
