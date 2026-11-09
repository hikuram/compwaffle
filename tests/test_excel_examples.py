"""Portable Python-in-Excel snippets: size, numeric inputs and drawing sanity."""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pytest

from compwaffle import build_layout

EXCEL = Path(__file__).resolve().parents[1] / 'examples' / 'python_in_excel'


def _load_inline_engine():
    scope = {}
    for script in ('engine_part1.py', 'engine_part2.py'):
        code = (EXCEL / script).read_text(encoding='utf-8')
        assert len(code) < 8192
        exec(compile(code, script, 'exec'), scope)
    return scope


def test_inline_fractional_cells_match_core():
    engine = _load_inline_engine()
    values = [72.5, 17.5, 10]
    cells, value_per_cell, total = engine['_cw_fills'](
        np.asarray(values), mode=0, ncols=20,
        value_per_cell=5, ref_weights=np.zeros(3))
    baseline = build_layout(dict(zip(('A', 'B', 'C'), values)), columns=20)
    assert len(cells) == baseline.count
    assert value_per_cell == baseline.value_per_cell
    assert total == 100
    for i, parts in enumerate(cells):
        expected = baseline.fills_in_cell(i)
        assert len(parts) == len(expected)
        for (index, start, end), ref in zip(parts, expected):
            assert index == 'ABC'.index(ref.key)
            assert (start, end) == pytest.approx((ref.start, ref.end))


def test_inline_draw_and_swatch_use_numeric_inputs_only():
    engine = _load_inline_engine()
    opts = [0, 20, 1, .78, .12, .18, 5, .10, .55, 0, 32]
    fig = engine['cw_draw_row'](
        [72.5, 17.5, 10], [0x4477AA, 0x88AA77, 0xAA8866],
        [[.1, .1, .1], [.55, -.8, 0]], [0, 2, 12],
        [1, 0, 0], opts)
    fig.canvas.draw()
    plt.close(fig)
    sample = engine['cw_legend_swatch'](0x88AA77, [.10, -.80], 2, opts)
    sample.canvas.draw()
    plt.close(sample)
    with pytest.raises(ValueError, match='numbers only'):
        engine['_cw_nums'](['Category A', 10.0])


def test_excel_cell_references():
    row = (EXCEL / 'row_example.py.txt').read_text(encoding='utf-8')
    swatch = (EXCEL / 'swatch_example.py.txt').read_text(encoding='utf-8')
    assert 'table!$B2:$H2' in row
    assert 'waffle!$B$4:$H$5' in row
    assert 'waffle!$K$2:$K$12' in row
    assert 'waffle!B$4:B$5' in swatch
    assert 'waffle!$K$2:$K$12' in swatch
