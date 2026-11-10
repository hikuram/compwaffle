"""Cell masks and renderer for fractional, optionally patterned waffle cells.

Each cell mask is a single closed Matplotlib Path. The four corners are
restricted to a square of side ``corner_span * min(cell_width, cell_height)``.
Segment colors/hatches are clipped to the *whole cell*, preserving exact
fractional widths and preventing gaps at material transitions.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from matplotlib.axes import Axes
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Rectangle

from .core import WaffleLayout
from .colors import shift_tone


# Cubic Bezier control-distance ratio for a quarter-circle approximation.
ROUND_BEND = 4 * (math.sqrt(2) - 1) / 3


@dataclass(frozen=True)
class CornerShape:
    """Per-category corner mask: ``span`` is a fraction of the short cell side.

    ``bend`` is in [-1, 1]. 0 gives straight chamfers; positive values bend
    toward the outside corner (ROUND_BEND approximates a quarter-circle);
    negative values bow into the cell, making a concave corner indentation.
    The indented variant is continuous but has intentional changes in tangent
    at the joins to the straight sides.
    """

    span: float = 0.15
    bend: float = ROUND_BEND

    def __post_init__(self) -> None:
        if not math.isfinite(self.span) or not 0 <= self.span <= 0.5:
            raise ValueError("corner span must be finite and in [0, 0.5]")
        if not math.isfinite(self.bend) or not -1 <= self.bend <= 1:
            raise ValueError("corner bend must be finite and in [-1, 1]")


def _coerce_shape(value: CornerShape | tuple[float, float]) -> CornerShape:
    if isinstance(value, CornerShape):
        return value
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return CornerShape(float(value[0]), float(value[1]))
    raise TypeError("shape_map entries must be CornerShape or (corner_span, corner_bend)")


@dataclass(frozen=True)
class WaffleStyle:
    """Cell geometry in relative units; color/shape/hatch mappings independent.

    ``corner_radius`` remains for compatibility with v0.1.0 and is measured
    in cell units. If ``corner_span`` is set, it overrides the old radius and
    is relative to the shorter cell dimension; both use ``corner_bend``.
    Hatch ink is automatically shaded per resolved fill color using
    ``hatch_tone_shift``; ``hatch_color`` explicitly overrides it.
    """

    cell_width: float = 1.0
    cell_height: float = 0.78
    gap_x: float = 0.12
    gap_y: float = 0.18
    corner_radius: float = 0.14
    edgecolor: str = "white"
    linewidth: float = 0.55
    empty_color: str = "#EDF1F5"
    corner_span: float | None = None
    corner_bend: float = ROUND_BEND
    color_map: Mapping[str, str] | None = None
    shape_map: Mapping[str, CornerShape | tuple[float, float]] | None = None
    hatch_map: Mapping[str, str | None] | None = None
    hatch_color: str | None = None
    hatch_tone_shift: float = -30.0

    def __post_init__(self) -> None:
        names = ("cell_width", "cell_height", "gap_x", "gap_y",
                 "corner_radius", "linewidth")
        for attr in names:
            value = getattr(self, attr)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{attr} must be finite and nonnegative")
        if self.cell_width == 0 or self.cell_height == 0:
            raise ValueError("cell_width and cell_height must be positive")
        if self.corner_radius > min(self.cell_width, self.cell_height) / 2:
            raise ValueError("corner_radius exceeds half the smaller cell dimension")
        if self.corner_span is not None:
            CornerShape(self.corner_span, self.corner_bend)
        else:
            CornerShape(0, self.corner_bend)  # validate bend independently
        if self.color_map is not None and not isinstance(self.color_map, Mapping):
            raise TypeError("color_map must be a mapping")
        if self.shape_map is not None:
            if not isinstance(self.shape_map, Mapping):
                raise TypeError("shape_map must be a mapping")
            for value in self.shape_map.values():
                _coerce_shape(value)
        if self.hatch_map is not None:
            if not isinstance(self.hatch_map, Mapping):
                raise TypeError("hatch_map must be a mapping")
            for pattern in self.hatch_map.values():
                if pattern is not None and (
                    not isinstance(pattern, str)
                    or any(ch not in r"/\\|-+xoO.*" for ch in pattern)
                ):
                    raise ValueError("invalid hatch; use Matplotlib hatch characters")
        if not math.isfinite(self.hatch_tone_shift) or not -100 <= self.hatch_tone_shift <= 100:
            raise ValueError("hatch_tone_shift must be finite and in [-100, 100]")

    def default_shape(self) -> CornerShape:
        short = min(self.cell_width, self.cell_height)
        span = self.corner_radius / short if self.corner_span is None else self.corner_span
        return CornerShape(span, self.corner_bend)

    def shape_for(self, category: str) -> CornerShape:
        if self.shape_map is not None and category in self.shape_map:
            return _coerce_shape(self.shape_map[category])
        return self.default_shape()

    def hatch_for(self, category: str) -> str | None:
        if self.hatch_map is None:
            return None
        return self.hatch_map.get(category) or None

    def hatch_color_for(self, fill_color: object) -> object:
        """Use an explicit hatch color, or shade/tint the resolved fill color."""
        return (self.hatch_color if self.hatch_color is not None
                else shift_tone(fill_color, self.hatch_tone_shift))

    @classmethod
    def preset(cls, name: str) -> "WaffleStyle":
        presets = {
            "rounded": {},
            "square": {"corner_radius": 0.0},
            "compact": {"gap_x": 0.055, "gap_y": 0.08,
                        "cell_height": 0.65, "corner_radius": 0.09},
            "pill": {"corner_radius": 0.39},
        }
        if name not in presets:
            raise ValueError(f"unknown waffle preset: {name}")
        return cls(**presets[name])

    def size(self, rows: int, columns: int, scale: float = 1.0) -> tuple[float, float]:
        width = columns * self.cell_width + (columns - 1) * self.gap_x
        height = rows * self.cell_height + (rows - 1) * self.gap_y
        return width * scale, height * scale


def cell_path(left: float, bottom: float, width: float, height: float,
              shape: CornerShape) -> Path:
    """Return a closed four-corner Path contained in the cell bounding box.

    For positive bends the two cubic controls lie on the corresponding cell
    edges; for negative bends they move into the corner square to produce an
    inward recess. Straight central portions of each side are unchanged.
    """
    if not all(math.isfinite(v) for v in (left, bottom, width, height)):
        raise ValueError("cell coordinates must be finite")
    if width <= 0 or height <= 0:
        raise ValueError("cell width/height must be positive")
    if not isinstance(shape, CornerShape):
        raise TypeError("shape must be CornerShape")
    r = shape.span * min(width, height)
    right, top = left + width, bottom + height
    if r == 0:
        return Path([(left, bottom), (right, bottom), (right, top),
                     (left, top), (left, bottom)],
                    [Path.MOVETO, Path.LINETO, Path.LINETO,
                     Path.LINETO, Path.CLOSEPOLY])

    # Canonical top-left corner in local coordinates: top edge -> left edge.
    start, end = (r, 0), (0, r)
    if shape.bend >= 0:
        c1, c2 = (r * (1 - shape.bend), 0), (0, r * (1 - shape.bend))
    else:
        depth = -shape.bend
        c1, c2 = (r, depth * r), (depth * r, r)

    tl = lambda pt: (left + pt[0], top - pt[1])
    bl = lambda pt: (left + pt[0], bottom + pt[1])
    br = lambda pt: (right - pt[0], bottom + pt[1])
    tr = lambda pt: (right - pt[0], top - pt[1])
    vertices = [tl(start)]
    codes = [Path.MOVETO]

    def curve(transform, reverse=False):
        seq = (c2, c1, start) if reverse else (c1, c2, end)
        vertices.extend(transform(p) for p in seq)
        codes.extend((Path.CURVE4, Path.CURVE4, Path.CURVE4))

    curve(tl)
    vertices.append(bl(end))
    codes.append(Path.LINETO)
    curve(bl, reverse=True)
    vertices.append(br(start))
    codes.append(Path.LINETO)
    curve(br)
    vertices.append(tr(end))
    codes.append(Path.LINETO)
    curve(tr, reverse=True)
    vertices.append(tl(start))
    codes.append(Path.CLOSEPOLY)
    return Path(vertices, codes)


def draw_swatch(ax: Axes, category: str, color: object,
                *, x: float, y: float, width: float, height: float,
                style: WaffleStyle) -> None:
    """Legend swatch that reflects category color, shape *and* hatch."""
    path = cell_path(x, y, width, height, style.shape_for(category))
    hatch = style.hatch_for(category)
    ax.add_patch(PathPatch(
        path, facecolor=color,
        edgecolor=style.hatch_color_for(color) if hatch else "none",
        linewidth=0, hatch=hatch, zorder=3,
    ))
    ax.add_patch(PathPatch(
        path, facecolor="none", edgecolor=style.edgecolor,
        linewidth=style.linewidth, zorder=4,
    ))


def draw_waffle(
    ax: Axes,
    layout: WaffleLayout,
    palette: Mapping[str, object],
    *,
    x: float = 0,
    y: float = 0,
    scale: float = 1.0,
    style: WaffleStyle | None = None,
) -> list:
    """Draw a layout without changing Axes limits, returning editable artists.

    A completely full, single-category cell uses the category's shape.
    Fractionally filled or mixed-category cells use the common default shape:
    their material boundaries stay contiguous, and all fills share one mask.
    """
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("scale must be finite and positive")
    style = style or WaffleStyle()
    pitch_x = (style.cell_width + style.gap_x) * scale
    pitch_y = (style.cell_height + style.gap_y) * scale
    w = style.cell_width * scale
    h = style.cell_height * scale
    result = []
    cell_fills: dict[int, list] = {}
    for fill in layout.fills:
        cell_fills.setdefault(fill.index, []).append(fill)

    for index in range(layout.count):
        if layout.order == "row":
            row, column = divmod(index, layout.columns)
        else:
            row, column = index % layout.rows, index // layout.rows
        left = x + column * pitch_x
        bottom = y + (layout.rows - 1 - row) * pitch_y
        segments = cell_fills.get(index, ())
        single_full = (len(segments) == 1
                       and math.isclose(segments[0].start, 0, abs_tol=1e-10)
                       and math.isclose(segments[0].end, 1, abs_tol=1e-10))
        shape = style.shape_for(segments[0].key) if single_full else style.default_shape()
        path = cell_path(left, bottom, w, h, shape)

        background = PathPatch(
            path, facecolor=style.empty_color, edgecolor="none", zorder=2,
        )
        ax.add_patch(background)
        result.append(background)

        for segment in segments:
            hatch = style.hatch_for(segment.key)
            part = Rectangle(
                (left + segment.start * w, bottom),
                (segment.end - segment.start) * w, h,
                facecolor=palette[segment.key],
                edgecolor=style.hatch_color_for(palette[segment.key]) if hatch else "none",
                linewidth=0, hatch=hatch, zorder=3,
            )
            part.set_clip_path(background)
            ax.add_patch(part)
            result.append(part)

        outline = PathPatch(
            path, facecolor="none", edgecolor=style.edgecolor,
            linewidth=style.linewidth, zorder=4,
        )
        ax.add_patch(outline)
        result.append(outline)
    return result
