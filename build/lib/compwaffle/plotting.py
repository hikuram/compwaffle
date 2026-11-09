"""Standalone Matplotlib plots using the pure geometry backend."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any
import math

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .colors import resolve_colors
from .core import WaffleLayout, build_layout
from .geometry import WaffleStyle, draw_waffle, draw_swatch
from .theme import adapt_cell_style, ui_ink


def _locate_x(origin: float, position: float, *, style: WaffleStyle, scale: float,
              count: int) -> float:
    """Physical x-coordinate of an equivalent fractional cell index."""
    if position >= count:
        return origin + style.size(1, count, scale)[0]
    n = math.floor(position)
    fraction = position - n
    return origin + (n * (style.cell_width + style.gap_x)
                     + fraction * style.cell_width) * scale


def _fmt_number(n: float) -> str:
    return f"{n:.4g}"


def _axis_in_inches(fig: Figure) -> Axes:
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, fig.get_figwidth())
    ax.set_ylim(0, fig.get_figheight())
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    return ax


def waffle(
    data: Mapping[str, float],
    *,
    ax: Axes | None = None,
    mode: str = "percent",
    rows: int = 1,
    columns: int | str = 20,
    value_per_cell: float | None = None,
    unit: str | None = None,
    order: str = "row",
    style: WaffleStyle | str | None = None,
    cell_scale: float | None = None,
    cmap: str = "tab20",
    colors: Mapping[str, str] | None = None,
    show_title: bool = True,
    title: str | None = None,
    show_comment: bool = True,
    comment: str | None = None,
    show_legend: bool = True,
    show_scale: bool = False,
    scale_interval: float | None = None,
    show_labels: bool = False,
    font_size: float = 10.0,
) -> tuple[Figure, Axes]:
    """Draw a rounded waffle chart, returning ``(figure, axes)``.

    Supplying ``ax`` embeds into any Matplotlib figure; the axes itself is
    cleared and configured, but matplotlib rcParams are never modified.
    ``rows > 1`` are supported; the numeric x-scale is limited to one row.
    """
    layout = build_layout(data, mode=mode, rows=rows, columns=columns,
                          value_per_cell=value_per_cell, unit=unit, order=order)
    if show_scale and rows != 1:
        raise ValueError("numeric scale currently requires rows=1")
    if scale_interval is not None and (not math.isfinite(scale_interval) or scale_interval <= 0):
        raise ValueError("scale_interval must be positive and finite")
    if isinstance(style, str):
        style = WaffleStyle.preset(style)
    style = adapt_cell_style(style or WaffleStyle())
    ink = ui_ink()
    palette = resolve_colors([key for key, _ in layout.values], cmap=cmap,
                             colors=style.color_map if colors is None else colors)

    # Geometry uses inches rather than data fractions, preserving rounded radii
    # and cell gaps when the plot is exported to different vector backends.
    if cell_scale is not None and (not math.isfinite(cell_scale) or cell_scale <= 0):
        raise ValueError("cell_scale must be positive and finite")
    scale = cell_scale if cell_scale is not None else (0.31 if layout.columns < 46 else 0.25)
    width, height = style.size(layout.rows, layout.columns, scale)
    top_title = 0.55 if show_title and title else 0
    # Account for wrapped legends before allocating figure height.
    legend_width_available = max(4.6, width + 1.1) - .50
    n_legend_lines, advance_used = 1, 0.0
    if show_legend:
        for key in palette:
            advance = .34 + max(.40, len(key) * font_size * .0095)
            if advance_used + advance > legend_width_available and advance_used > 0:
                n_legend_lines += 1
                advance_used = 0.0
            advance_used += advance
    top_legend = (.44 + (n_legend_lines - 1) * .30) if show_legend else 0
    bottom_scale = 0.42 if show_scale else 0
    bottom_labels = 0.33 if show_labels else 0
    bottom_comment = 0.38 if show_comment and comment else 0
    fig_width = max(4.6, width + 1.1)
    fig_height = max(1.35, 0.44 + top_title + top_legend + height +
                     bottom_scale + bottom_labels + bottom_comment + 0.36)
    if ax is None:
        fig = plt.figure(figsize=(fig_width, fig_height))
        ax = _axis_in_inches(fig)
    else:
        fig = ax.figure
        ax.cla()
        ax.set_xlim(0, fig_width)
        ax.set_ylim(0, fig_height)
        ax.set_aspect("equal", adjustable="box")
        ax.axis("off")
    left = (fig_width - width) / 2
    cursor = fig_height - 0.30
    if top_title:
        ax.text(left, cursor, title, va="top", ha="left",
                fontsize=font_size + 5, fontweight="semibold")
        cursor -= top_title
    if top_legend:
        # Wrap color legend instead of relying on global axes legends.
        x = left
        for key, rgba in palette.items():
            advance = 0.34 + max(0.40, len(key) * font_size * 0.0095)
            if x + advance > fig_width - .25 and x > left:
                cursor -= .30
                x = left
            draw_swatch(ax, key, rgba, x=x, y=cursor - .15,
                        width=.15, height=.15, style=style)
            ax.text(x + .22, cursor - .077, key, ha="left", va="center",
                    fontsize=font_size - 1)
            x += advance
        cursor -= .44
    bottom = cursor - height
    draw_waffle(ax, layout, palette, x=left, y=bottom, scale=scale, style=style)

    if show_scale:
        maximum = layout.capacity
        if scale_interval is None:
            ticks = [maximum * i / 4 for i in range(5)]
        else:
            nticks = math.floor(maximum / scale_interval)
            if nticks > 100:
                raise ValueError("scale_interval generates >100 ticks")
            ticks = [i * scale_interval for i in range(nticks + 1)]
            if not math.isclose(ticks[-1], maximum):
                ticks.append(maximum)
        for tick in ticks:
            xp = _locate_x(left, tick / layout.value_per_cell,
                           style=style, scale=scale, count=layout.columns)
            ax.plot([xp, xp], [bottom - .035, bottom - .092],
                    color=ink["muted"], lw=.6)
            ax.text(xp, bottom - .16, _fmt_number(tick), va="top", ha="center",
                    fontsize=font_size - 2, color=ink["muted"])
        if layout.unit:
            ax.text(left + width, bottom - .34, layout.unit, ha="right",
                    va="top", fontsize=font_size - 2, color=ink["muted"])

    if show_labels:
        lower = bottom - (.52 if show_scale else .15)
        cumulative = 0.0
        for name, value in layout.values:
            center = cumulative + value / 2
            xtext = _locate_x(left, center / layout.value_per_cell,
                              style=style, scale=scale, count=layout.count)
            if value / layout.capacity * width >= .48:
                ax.text(xtext, lower, _fmt_number(value), ha="center",
                        va="top", fontsize=font_size - 2, color=palette[name])
            cumulative += value
    if bottom_comment:
        ax.text(left, .19, comment, ha="left", va="bottom",
                fontsize=font_size - 1, color=ink["muted"])
    return fig, ax
