"""Shared matplotlib style for engineering plots (dashboard + offline scripts).

Palette and grid/spine treatment follow the project's dataviz skill reference
palette (categorical slots 1-3: blue/orange/aqua), adapted for static
technical plots rather than an interactive dashboard: thin lines, recessive
hairline grid, muted axes, legend always present for >=2 series.
"""

from __future__ import annotations

PALETTE = {
    "series1": "#2a78d6",  # blue
    "series2": "#eb6834",  # orange
    "series3": "#1baf7a",  # aqua
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
    "muted": "#898781",
    "text": "#0b0b0b",
}

# Consistent color per evidence label so MEASURED/EXPECTED/SYNTHETIC overlays
# are visually distinguishable the same way across every script.
LABEL_COLORS = {
    "MEASURED": PALETTE["series1"],
    "EXPECTED": PALETTE["series2"],
    "SYNTHETIC": PALETTE["series3"],
    "CALCULATED": PALETTE["series1"],
    "SIMULATED": PALETTE["series2"],
}


def style_axes(ax) -> None:
    ax.grid(True, color=PALETTE["grid"], linewidth=0.8, alpha=0.9, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(PALETTE["axis"])
    ax.tick_params(colors=PALETTE["muted"])
    ax.xaxis.label.set_color(PALETTE["text"])
    ax.yaxis.label.set_color(PALETTE["text"])
    ax.title.set_color(PALETTE["text"])
