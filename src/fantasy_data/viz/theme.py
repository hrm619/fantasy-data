"""NYT-inspired visual theme for all Plotly charts.

Import from this module at the top of every plotting file.
Never set colors, fonts, margins, or gridlines inline — all conventions
live here and are applied via ``apply_theme``.
"""

from __future__ import annotations

import logging
import platform
import shutil
from pathlib import Path

import plotly.graph_objects as go

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Font installation (one-time, on first import)
# ---------------------------------------------------------------------------

_FONT_DIR = Path(__file__).parent / "fonts" / "Inter"
_FONT_FILE = _FONT_DIR / "InterVariable.ttf"


def _install_inter() -> None:
    """Copy bundled Inter to user font directory if not already present."""
    if not _FONT_FILE.exists():
        logger.warning("Bundled Inter font not found at %s — falling back to system sans-serif", _FONT_FILE)
        return

    system = platform.system()
    if system == "Darwin":
        dest_dir = Path.home() / "Library" / "Fonts"
    elif system == "Linux":
        dest_dir = Path.home() / ".local" / "share" / "fonts"
    elif system == "Windows":
        dest_dir = Path.home() / "AppData" / "Local" / "Microsoft" / "Windows" / "Fonts"
    else:
        logger.warning("Unknown platform %s — skipping Inter font install", system)
        return

    dest = dest_dir / "InterVariable.ttf"
    if dest.exists():
        return

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(_FONT_FILE, dest)
        logger.info("Installed Inter font for chart rendering → %s", dest)
        # Refresh font cache on Linux
        if system == "Linux":
            import subprocess
            subprocess.run(["fc-cache", "-f"], capture_output=True)  # noqa: S603, S607
    except OSError:
        logger.warning("Could not install Inter font (permissions?) — falling back to system sans-serif")


_install_inter()

# ---------------------------------------------------------------------------
# Color system
# ---------------------------------------------------------------------------

COLORS: dict[str, str] = {
    # Neutrals
    "background": "#FFFFFF",
    "text_primary": "#1A1A1A",
    "text_secondary": "#555555",
    "text_tertiary": "#888888",
    "spine": "#DDDDDD",
    "gridline": "#EEEEEE",

    # Default data color — warm gray
    "data_default": "#8B8685",

    # Spotlight accent — desaturated steel blue
    "spotlight": "#4A7C98",

    # Diverging pair
    "diverging_pos": "#4A7C98",
    "diverging_neg": "#C4756B",
    "diverging_mid": "#D8D8D8",

    # Categorical (max 4 groups, similar luminance)
    "cat_1": "#4A7C98",
    "cat_2": "#C4756B",
    "cat_3": "#7A9B76",
    "cat_4": "#B89968",
}

# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------

FONTS: dict[str, dict] = {
    "title": {
        "family": "Inter, sans-serif",
        "size": 16,
        "color": COLORS["text_primary"],
        "weight": 600,
    },
    "subtitle": {
        "family": "Inter, sans-serif",
        "size": 12,
        "color": COLORS["text_secondary"],
        "weight": 400,
    },
    "axis_label": {
        "family": "Inter, sans-serif",
        "size": 12,
        "color": COLORS["text_secondary"],
        "weight": 400,
    },
    "tick_label": {
        "family": "Inter, sans-serif",
        "size": 10,
        "color": COLORS["text_tertiary"],
        "weight": 400,
    },
    "annotation": {
        "family": "Inter, sans-serif",
        "size": 11,
        "color": COLORS["text_secondary"],
        "weight": 400,
    },
    "source": {
        "family": "Inter, sans-serif",
        "size": 9,
        "color": COLORS["text_tertiary"],
        "weight": 400,
        "style": "italic",
    },
}

# ---------------------------------------------------------------------------
# Layout defaults
# ---------------------------------------------------------------------------

LAYOUT: dict = {
    "paper_bgcolor": COLORS["background"],
    "plot_bgcolor": COLORS["background"],
    "margin": {"l": 70, "r": 80, "t": 80, "b": 60},
    "xaxis": {
        "showline": True,
        "linecolor": COLORS["spine"],
        "linewidth": 1,
        "showgrid": False,
        "zeroline": False,
        "ticks": "",
        "tickfont": FONTS["tick_label"],
        "title_font": FONTS["axis_label"],
        "title_standoff": 12,
    },
    "yaxis": {
        "showline": True,
        "linecolor": COLORS["spine"],
        "linewidth": 1,
        "showgrid": True,
        "gridcolor": COLORS["gridline"],
        "gridwidth": 1,
        "zeroline": False,
        "ticks": "",
        "tickfont": FONTS["tick_label"],
        "title_font": FONTS["axis_label"],
        "title_standoff": 12,
    },
    "showlegend": False,
    "hoverlabel": {
        "bgcolor": COLORS["background"],
        "bordercolor": COLORS["spine"],
        "font": FONTS["annotation"],
    },
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_theme(
    fig: go.Figure,
    title: str,
    subtitle: str | None = None,
    source: str | None = None,
) -> go.Figure:
    """Apply the full NYT-inspired theme to a Plotly figure.

    Sets layout, fonts, margins, spines, gridlines, and adds the title
    block (insight title + optional subtitle + optional source line).
    Returns the figure for chaining.
    """
    fig.update_layout(**LAYOUT)

    # Title annotation — left-aligned above the plot
    annotations: list[dict] = []
    annotations.append(
        dict(
            text=title,
            xref="paper",
            yref="paper",
            x=0,
            y=1.08,
            showarrow=False,
            font=FONTS["title"],
            xanchor="left",
            yanchor="bottom",
        )
    )

    if subtitle:
        annotations.append(
            dict(
                text=subtitle,
                xref="paper",
                yref="paper",
                x=0,
                y=1.03,
                showarrow=False,
                font=FONTS["subtitle"],
                xanchor="left",
                yanchor="bottom",
            )
        )

    if source:
        annotations.append(
            dict(
                text=f"<i>{source}</i>",
                xref="paper",
                yref="paper",
                x=0,
                y=-0.12,
                showarrow=False,
                font=FONTS["source"],
                xanchor="left",
                yanchor="top",
            )
        )

    # Merge with any existing annotations on the figure
    existing = list(fig.layout.annotations or [])
    fig.update_layout(annotations=existing + annotations)

    return fig


def color_for_mode(
    mode: str, n: int = 1, highlight_index: int | None = None
) -> list[str]:
    """Return a list of *n* hex colors for the given color mode.

    Modes
    -----
    - ``default``  — all warm gray
    - ``spotlight`` — warm gray + steel blue (background, then highlight)
    - ``diverging`` — [neg, mid, pos]
    - ``categorical`` — up to 4 distinct colors at similar luminance
    """
    if mode == "default":
        return [COLORS["data_default"]] * n

    if mode == "spotlight":
        return [COLORS["data_default"], COLORS["spotlight"]]

    if mode == "diverging":
        return [COLORS["diverging_neg"], COLORS["diverging_mid"], COLORS["diverging_pos"]]

    if mode == "categorical":
        if n > 4:
            raise ValueError(
                f"Categorical mode supports at most 4 groups, got {n}. "
                "Use a different encoding for more groups."
            )
        keys = ["cat_1", "cat_2", "cat_3", "cat_4"]
        return [COLORS[k] for k in keys[:n]]

    raise ValueError(f"Unknown color mode: {mode!r}")


def annotate_point(
    fig: go.Figure,
    x: float | str,
    y: float | str,
    text: str,
    position: str = "auto",
) -> go.Figure:
    """Add an NYT-style annotation: short text + thin segment to *(x, y)*.

    *position* controls label placement: ``'above'``, ``'below'``,
    ``'left'``, ``'right'``, or ``'auto'`` (defaults to above).
    """
    offsets = {
        "above": (0, 12),
        "below": (0, -12),
        "left": (-12, 0),
        "right": (12, 0),
        "auto": (0, 12),
    }
    ax_off, ay_off = offsets.get(position, (0, 12))

    fig.add_annotation(
        x=x,
        y=y,
        text=text,
        showarrow=True,
        arrowhead=0,
        arrowwidth=0.5,
        arrowcolor=COLORS["text_secondary"],
        ax=ax_off,
        ay=-ay_off,  # Plotly annotation ay is inverted
        font=FONTS["annotation"],
        bgcolor=COLORS["background"],
        borderpad=2,
    )
    return fig


def label_endpoint(
    fig: go.Figure, trace_index: int, label: str
) -> go.Figure:
    """Add a direct label at the rightmost point of a trace.

    Used as a replacement for legends when there are <=5 series.
    """
    trace = fig.data[trace_index]
    if trace.x is None or len(trace.x) == 0:
        return fig

    # Find rightmost point
    x_vals = list(trace.x)
    y_vals = list(trace.y)
    idx = len(x_vals) - 1
    color = trace.marker.color if hasattr(trace.marker, "color") and trace.marker.color else COLORS["text_secondary"]

    fig.add_annotation(
        x=x_vals[idx],
        y=y_vals[idx],
        text=label,
        showarrow=False,
        xanchor="left",
        xshift=6,
        font=dict(
            family=FONTS["annotation"]["family"],
            size=FONTS["annotation"]["size"],
            color=color,
        ),
    )
    return fig


def format_axis(
    fig: go.Figure,
    axis: str,
    title: str,
    tickformat: str | None = None,
) -> go.Figure:
    """Apply themed axis formatting.

    *axis* is ``'x'`` or ``'y'``. Removes tick marks, sets label font,
    and applies *tickformat* if provided.
    """
    update = {
        "title_text": title,
        "title_font": FONTS["axis_label"],
        "tickfont": FONTS["tick_label"],
        "ticks": "",
    }
    if tickformat:
        update["tickformat"] = tickformat

    if axis == "x":
        fig.update_xaxes(**update)
    elif axis == "y":
        fig.update_yaxes(**update)
    else:
        raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")

    return fig
