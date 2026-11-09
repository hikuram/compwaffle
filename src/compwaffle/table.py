"""Experimental composition table layout using Matplotlib."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.patches import Rectangle
from matplotlib.colors import is_color_like

from .colors import resolve_colors
from .core import build_layout
from .geometry import WaffleStyle, draw_waffle, draw_swatch
from .plotting import _axis_in_inches, _fmt_number, _locate_x
from .theme import adapt_cell_style, ui_ink


def _record_list(records: Any) -> list[dict]:
    if hasattr(records, "to_dict"):
        records = records.to_dict("records")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise TypeError("records must be a sequence of mappings or a DataFrame")
    output = []
    for rec in records:
        if not isinstance(rec, Mapping):
            raise TypeError("each record must be a mapping")
        output.append(dict(rec))
    if not output:
        raise ValueError("records must contain at least one entry")
    return output


def waffle_table(
    records: Any,
    *,
    composition: str = "composition",
    label: str = "label",
    comment: str | None = "comment",
    properties: Sequence[str] = (),
    property_labels: Mapping[str, str] | None = None,
    property_formats: Mapping[str, str] | None = None,
    mode: str = "percent",
    rows: int = 1,
    columns: int | str = 20,
    value_per_cell: float | None = None,
    unit: str | None = None,
    order: str = "row",
    style: WaffleStyle | str | None = None,
    cell_scale: float | None = None,
    colors: Mapping[str, str] | None = None,
    cmap: str = "tab20",
    title: str | None = None,
    show_title: bool = True,
    show_legend: bool = True,
    show_scale: bool = True,
    show_stripes: bool = True,
    stripe_color: str | None = None,
) -> tuple[Figure, Axes]:
    """Draw multiple composition waffles and right-hand properties.

    v0.1 preview: uniform row height, optional change comment and numeric or
    textual properties. All rows share the same value-per-cell and colors.
    For absolute variable-length rows use ``columns='auto'``.
    """
    if stripe_color is not None and not is_color_like(stripe_color):
        raise ValueError("stripe_color must be a Matplotlib color")
    data = _record_list(records)
    if isinstance(style, str):
        style = WaffleStyle.preset(style)
    style = adapt_cell_style(style or WaffleStyle())
    ink = ui_ink()
    layouts = []
    categories = []
    for rec in data:
        if composition not in rec:
            raise KeyError(f"missing composition: {composition}")
        layout = build_layout(rec[composition], mode=mode, rows=rows,
                              columns=columns, value_per_cell=value_per_cell,
                              unit=unit, order=order)
        layouts.append(layout)
        for name, _ in layout.values:
            if name not in categories:
                categories.append(name)
    if show_scale and rows != 1:
        raise ValueError("numeric table scale currently requires rows=1")
    palette = resolve_colors(categories, cmap=cmap,
                             colors=style.color_map if colors is None else colors)
    max_columns = max(layout.columns for layout in layouts)
    if cell_scale is not None and (not math.isfinite(cell_scale) or cell_scale <= 0):
        raise ValueError("cell_scale must be positive and finite")
    scale = cell_scale if cell_scale is not None else (.245 if max_columns <= 45 else .18)
    chart_width, chart_height = style.size(rows, max_columns, scale)

    margin = .44
    label_width = 1.0
    chart_padding = .30
    comment_width = 2.0 if comment is not None else 0
    prop_width = 1.35
    divider_gap = .13
    total_width = (2 * margin + label_width + chart_width + chart_padding +
                   comment_width + prop_width * len(properties) + divider_gap)
    total_width = max(8.2, total_width)
    title_height = .52 if show_title and title else 0
    legend_base_height = .50 if show_legend else 0
    legend_lines, legend_advance = 1, 0.0
    if show_legend:
        for name in palette:
            advance = .30 + max(.39, len(name) * .092)
            if legend_advance + advance > total_width - 2 * margin and legend_advance > 0:
                legend_lines += 1
                legend_advance = 0.0
            legend_advance += advance
    legend_height = legend_base_height + (legend_lines - 1) * .30 if show_legend else 0
    header_height = .44
    row_height = max(.59, chart_height + .26)
    scale_height = .36 if show_scale else 0
    total_height = (.35 + title_height + legend_height + header_height +
                    len(data) * row_height + scale_height + .34)

    fig = plt.figure(figsize=(total_width, total_height))
    ax = _axis_in_inches(fig)
    x_label = margin
    x_chart = x_label + label_width
    x_comment = x_chart + chart_width + chart_padding
    x_props = x_comment + comment_width
    y = total_height - .25
    if title_height:
        ax.text(margin, y, title, va="top", ha="left", fontweight="semibold",
                fontsize=15, color=ink["primary"])
        y -= title_height
    if legend_height:
        x = margin
        for name, rgba in palette.items():
            advance = .30 + max(.39, len(name) * .092)
            if x + advance > total_width - margin and x > margin:
                y -= .30
                x = margin
            draw_swatch(ax, name, rgba, x=x, y=y - .12,
                        width=.13, height=.13, style=style)
            ax.text(x + .20, y - .05, name, ha="left", va="center",
                    fontsize=8.4)
            x += advance
        y -= legend_base_height
    header_y = y - header_height / 2
    ax.text(x_label, header_y, "Sample", va="center", fontsize=9,
            fontweight="semibold", color=ink["secondary"])
    ax.text(x_chart, header_y, "Composition", va="center", fontsize=9,
            fontweight="semibold", color=ink["secondary"])
    if comment is not None:
        ax.text(x_comment, header_y, "Changes / notes", va="center", fontsize=9,
                fontweight="semibold", color=ink["secondary"])
    for i, name in enumerate(properties):
        shown = (property_labels or {}).get(name, name)
        ax.text(x_props + i * prop_width + .02, header_y, shown,
                va="center", fontsize=8.5, fontweight="semibold", color=ink["secondary"])
    top_of_rows = y - header_height
    ax.plot([margin, total_width - margin], [top_of_rows, top_of_rows],
            color=ink["rule"], lw=.9)

    for i, (rec, layout) in enumerate(zip(data, layouts)):
        cy = top_of_rows - (i + .5) * row_height
        row_bottom = top_of_rows - (i + 1) * row_height
        if show_stripes and i % 2 == 1:
            ax.add_patch(Rectangle((margin-.06, row_bottom),
                                   total_width - 2 * margin+.12, row_height,
                                   facecolor=ink["stripe"] if stripe_color is None else stripe_color,
                                   edgecolor="none", zorder=0))
        ax.text(x_label, cy, str(rec.get(label, i+1)), ha="left", va="center",
                fontsize=9.2, color=ink["primary"])
        draw_waffle(ax, layout, palette, x=x_chart,
                    y=cy-chart_height/2, scale=scale, style=style)
        if comment is not None:
            ax.text(x_comment, cy, str(rec.get(comment, "")), ha="left",
                    va="center", fontsize=8.0, color=ink["secondary"])
        for j, name in enumerate(properties):
            val = rec.get(name, "")
            spec = (property_formats or {}).get(name)
            if val == "" or val is None:
                shown = "–"
            elif spec is not None:
                shown = format(val, spec)
            elif isinstance(val, (float, int)):
                shown = f"{val:.3g}"
            else:
                shown = str(val)
            ax.text(x_props + j * prop_width + .02, cy, shown,
                    ha="left", va="center", fontsize=9.0, color=ink["primary"])
        ax.plot([margin, total_width - margin], [row_bottom, row_bottom],
                color=ink["subtle_rule"], lw=.5, zorder=1)

    if show_scale:
        bottom_y = top_of_rows - len(data) * row_height
        all_capacity = max(l.capacity for l in layouts)
        for i in range(5):
            value = i * all_capacity / 4
            cx = _locate_x(x_chart, value / layouts[0].value_per_cell,
                           style=style, scale=scale, count=max_columns)
            ax.plot([cx,cx], [bottom_y-.045, bottom_y-.105],
                    color=ink["muted"], lw=.65)
            ax.text(cx, bottom_y-.14, _fmt_number(value), ha="center",
                    va="top", fontsize=8, color=ink["secondary"])
        if layouts[0].unit:
            ax.text(x_chart + chart_width, bottom_y-.28, layouts[0].unit,
                    fontsize=8, ha="right", va="top", color=ink["secondary"])
    return fig, ax
