import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pytest
from matplotlib.patches import Rectangle, PathPatch
from compwaffle import waffle, waffle_table, WaffleStyle


def test_rounded_patch_and_svg_pdf_export():
    fig, ax = waffle({"A": 72.5, "B": 27.5}, title="Test", show_scale=True)
    assert sum(isinstance(p, PathPatch) for p in ax.patches) >= 40
    assert any(isinstance(p, Rectangle) for p in ax.patches)
    fig.canvas.draw()
    for fmt in ("svg", "pdf", "png"):
        stream = io.BytesIO()
        fig.savefig(stream, format=fmt)
        assert len(stream.getvalue()) > 1000
    plt.close(fig)


def test_waffle_style_presets_and_validation():
    assert WaffleStyle.preset("square").corner_radius == 0
    assert WaffleStyle.preset("pill").corner_radius == pytest.approx(.39)
    with pytest.raises(ValueError):
        WaffleStyle(corner_radius=1)


def test_multirow_can_render_but_scale_requires_one_row():
    fig, _ = waffle({"A": 55, "B": 45}, rows=2, columns=10,
                    show_scale=False, show_legend=False)
    fig.canvas.draw()
    plt.close(fig)
    with pytest.raises(ValueError):
        waffle({"A": 55, "B": 45}, rows=2, columns=10, show_scale=True)


def test_absolute_table_with_varying_lengths():
    records = [
        {"label": "A", "composition": {"Cement": 100, "Water": 45},
         "comment": "W/C=.45", "strength": 42.1},
        {"label": "B", "composition": {"Cement": 100, "Water": 55, "SP": 6},
         "comment": "W/C=.55", "strength": 36.2},
    ]
    fig, ax = waffle_table(records, mode="absolute", columns="auto",
                           value_per_cell=10, unit="parts",
                           properties=["strength"], title="Example")
    assert len(ax.patches) > 20
    fig.canvas.draw()
    plt.close(fig)


def test_invalid_legend_scale_toggles():
    with pytest.raises(ValueError):
        waffle({"A": 100}, mode="absolute", columns="auto",
               value_per_cell=5, show_scale=True, scale_interval=-1)


def test_absolute_cell_size_and_wrapped_legend():
    many = {f"Material-{i:02d}": 1.0 for i in range(19)}
    fig, ax = waffle(many, columns=20, cell_scale=.26, show_scale=False)
    fig.canvas.draw()
    plt.close(fig)
    with pytest.raises(ValueError, match='cell_scale'):
        waffle({'A': 1}, cell_scale=0)
    records = [{'label': 'row', 'composition': many}]
    fig, ax = waffle_table(records, columns=20, cell_scale=.24, show_scale=False)
    fig.canvas.draw()
    plt.close(fig)
