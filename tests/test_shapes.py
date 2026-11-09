"""Corner masks, independent visual encodings and stripe controls (v0.1.1)."""
import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path
import pytest

from compwaffle import CornerShape, WaffleStyle, build_layout, cell_path, waffle, waffle_table
from compwaffle.geometry import ROUND_BEND, draw_waffle


def _area(path):
    areas = []
    for polygon in path.to_polygons(closed_only=True):
        areas.append(abs(np.dot(polygon[:, 0], np.roll(polygon[:, 1], -1)) -
                         np.dot(polygon[:, 1], np.roll(polygon[:, 0], -1))) / 2)
    return sum(areas)


def test_corner_curvature_signed_and_area_bounds():
    assert ROUND_BEND == pytest.approx(0.5522847498307936)
    # Equal maximum geometry; all actual paths stay inside the rectangle.
    for bend in (-1, -.8, -.3, 0, ROUND_BEND, 1):
        path = cell_path(1.2, 2.1, 1.0, .78, CornerShape(.10, bend))
        verts = path.vertices[:-1]  # CLOSEPOLY vertex has no geometry
        assert np.all(verts[:, 0] >= 1.2 - 1e-12)
        assert np.all(verts[:, 0] <= 2.2 + 1e-12)
        assert np.all(verts[:, 1] >= 2.1 - 1e-12)
        assert np.all(verts[:, 1] <= 2.88 + 1e-12)
        # With a corner region limited to 10% of the short side,
        # even extreme bend variations remove at most ~3.2% of cell area.
        assert .968 < _area(path) / .78 <= 1.000001
        assert Path.CURVE4 in path.codes


def test_inward_corner_is_more_recessed_than_chamfer():
    p_convex = cell_path(0, 0, 1, 1, CornerShape(.15, +ROUND_BEND))
    p_chamfer = cell_path(0, 0, 1, 1, CornerShape(.15, 0))
    p_concave = cell_path(0, 0, 1, 1, CornerShape(.15, -.75))
    assert _area(p_convex) > _area(p_chamfer) > _area(p_concave)
    # The straight top/left/right/bottom side endpoints stay fixed.
    assert np.array_equal(p_convex.vertices[0], p_concave.vertices[0])
    assert np.array_equal(p_convex.vertices[3], p_concave.vertices[3])


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.001, 1.001])
def test_invalid_bend_rejected(bad):
    with pytest.raises(ValueError):
        CornerShape(.1, bad)
    with pytest.raises(ValueError):
        WaffleStyle(corner_bend=bad)


def test_invalid_style_and_shapes():
    with pytest.raises(ValueError):
        CornerShape(.51, .5)
    with pytest.raises(TypeError):
        WaffleStyle(shape_map={"A": "ellipse"})
    with pytest.raises(ValueError):
        WaffleStyle(shape_map={"A": (.1, -2.0)})
    with pytest.raises(ValueError):
        WaffleStyle(hatch_map={"A": "not-hatch"})
    assert WaffleStyle.preset('rounded').default_shape().span == pytest.approx(.14/.78)
    assert WaffleStyle(corner_span=.10).default_shape().span == pytest.approx(.10)
    assert WaffleStyle.preset('square').default_shape().span == 0


def test_mixed_cell_keeps_single_mask_but_independent_hatches():
    style = WaffleStyle(
        corner_span=.10, corner_bend=ROUND_BEND,
        color_map={"A": "#808080", "B": "#dddddd"},
        shape_map={"A": (.10, -.8), "B": (.10, .8)},
        hatch_map={"A": "//", "B": ".."},
    )
    fig, ax = plt.subplots()
    layout = build_layout({"A": 72.5, "B": 27.5}, columns=20)
    artists = draw_waffle(ax, layout, {"A": "grey", "B": "lightgrey"}, style=style)
    backgrounds = [a for a in artists if isinstance(a, PathPatch) and a.get_zorder() == 2]
    segments = [a for a in artists if isinstance(a, Rectangle) and a.get_zorder() == 3]
    assert len(backgrounds) == 20
    assert backgrounds[0].get_path().vertices.tolist() != backgrounds[14].get_path().vertices.tolist()
    assert backgrounds[14].get_path().vertices.tolist() == cell_path(14 * 1.12, 0, 1, .78, style.default_shape()).vertices.tolist()
    assert any(s.get_hatch() == "//" for s in segments)
    assert any(s.get_hatch() == ".." for s in segments)
    assert all(s.get_clip_path() is not None for s in segments)
    plt.close(fig)


def test_color_shape_hatch_independent_and_vector_export():
    style = WaffleStyle(
        corner_span=.10,
        color_map={"A": "#113355", "B": "#ddeeff"},
        shape_map={"A": (.10, -.65), "B": (.10, .75)},
        hatch_map={"A": "//", "B": "xx"},
    )
    fig, ax = waffle({"A": 30, "B": 70}, style=style, show_legend=True)
    segments = [p for p in ax.patches if isinstance(p, Rectangle)]
    assert any(p.get_hatch() == "//" for p in segments)
    assert any(p.get_hatch() == "xx" for p in segments)
    assert mcolors.to_hex(segments[0].get_facecolor()) == "#113355"
    for fmt in ("png", "svg", "pdf"):
        dest = io.BytesIO()
        fig.savefig(dest, format=fmt)
        assert len(dest.getvalue()) > 1500
        if fmt == "svg":
            assert b"<pattern" in dest.getvalue()
    plt.close(fig)


def test_colors_arg_overrides_style_palette_only():
    style = WaffleStyle(
        color_map={"A": "#aabbcc"},
        shape_map={"A": (.10, -.5)}, hatch_map={"A": ".."},
    )
    fig, ax = waffle({"A": 100}, style=style, colors={"A": "#123456"},
                     show_legend=False)
    segments = [p for p in ax.patches if isinstance(p, Rectangle)]
    assert mcolors.to_hex(segments[0].get_facecolor()) == "#123456"
    assert segments[0].get_hatch() == ".."
    plt.close(fig)


def test_table_stripes_on_off_color():
    rec = [{"label": str(i), "composition": {"A": 100}} for i in range(3)]
    def stripes(ax):
        return [p for p in ax.patches if isinstance(p, Rectangle) and p.get_zorder() == 0]
    fig, ax = waffle_table(rec, show_stripes=False)
    assert not stripes(ax)
    plt.close(fig)
    fig, ax = waffle_table(rec, show_stripes=True, stripe_color="#ff0000")
    assert len(stripes(ax)) == 1
    assert mcolors.to_hex(stripes(ax)[0].get_facecolor()) == "#ff0000"
    plt.close(fig)
    with pytest.raises(ValueError, match="stripe_color"):
        waffle_table(rec, stripe_color="notacolor")
