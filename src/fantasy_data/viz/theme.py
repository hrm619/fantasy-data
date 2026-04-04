"""Global theme — import from this module at the top of every plotting file.

Never set style or color inline. All palettes are Okabe-Ito (colorblind-safe).
"""

import seaborn as sns
import matplotlib.pyplot as plt
import plotly.io as pio

# -- Palette (Okabe-Ito — colorblind-safe, 8 distinct colors) ----------------

PALETTE = {
    "orange":  "#E69F00",
    "sky":     "#56B4E9",
    "green":   "#009E73",
    "yellow":  "#F0E442",
    "blue":    "#0072B2",
    "red":     "#D55E00",
    "pink":    "#CC79A7",
    "black":   "#000000",
}

# Semantic color assignments — consistent across all charts
COLORS = {
    "undervalued": PALETTE["green"],
    "overvalued":  PALETTE["red"],
    "neutral":     PALETTE["sky"],
    "uncertain":   PALETTE["yellow"],
    "positive":    PALETTE["green"],
    "negative":    PALETTE["red"],
    "highlight":   PALETTE["orange"],
    "muted":       "#AAAAAA",
}

# Position colors — consistent across every position-colored chart
POSITION_COLORS = {
    "QB": PALETTE["orange"],
    "RB": PALETTE["green"],
    "WR": PALETTE["sky"],
    "TE": PALETTE["pink"],
}

# -- Seaborn global theme ----------------------------------------------------

def apply_seaborn_theme():
    sns.set_theme(
        style="whitegrid",
        font="sans-serif",
        font_scale=1.15,
        rc={
            "axes.spines.right": False,
            "axes.spines.top": False,
            "figure.dpi": 150,
            "figure.figsize": (11, 6),
            "axes.titlesize": 13,
            "axes.titleweight": "bold",
            "axes.titlepad": 12,
            "axes.labelpad": 8,
            "grid.alpha": 0.4,
        },
    )
    sns.set_palette(list(PALETTE.values()))

# -- Plotly global template ---------------------------------------------------

PLOTLY_BASE_LAYOUT = dict(
    font=dict(family="Inter, Arial, sans-serif", size=13, color="#222222"),
    plot_bgcolor="white",
    paper_bgcolor="white",
    margin=dict(t=70, l=60, r=40, b=60),
    colorway=list(PALETTE.values()),
    hoverlabel=dict(
        bgcolor="white",
        font_size=12,
        font_family="Inter, Arial, sans-serif",
    ),
    title=dict(
        font=dict(size=15),
        x=0.0,
        xanchor="left",
        pad=dict(l=0, t=8),
    ),
)


def apply_plotly_theme():
    """Register and set the quant-edge Plotly template globally."""
    import plotly.graph_objects as go
    pio.templates["quant_edge"] = go.layout.Template(
        layout=go.Layout(**PLOTLY_BASE_LAYOUT)
    )
    pio.templates.default = "plotly_white+quant_edge"
