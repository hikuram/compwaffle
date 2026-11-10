"""Auto-derived hatch color stays consistent in plots, swatches and Excel."""

import matplotlib
matplotlib.use('Agg')
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle, PathPatch
import pytest

from compwaffle import WaffleStyle, waffle, waffle_table
from compwaffle.colors import shift_tone
from compwaffle.theme import adapt_cell_style
from test_excel_examples import _load_inline_engine


def _hatch_segments(ax):
    return [p for p in ax.patches if isinstance(p, Rectangle) and p.get_hatch()]


def _hatch_swatches(ax):
    return [p for p in ax.patches if isinstance(p, PathPatch) and p.get_hatch()]


@pytest.mark.parametrize('shift,expected', [
    (-100, '#000000'), (-30, '#305377'), (0, '#4477aa'),
    (50, '#a2bbd4'), (100, '#ffffff'),
])
def test_rgb_tone_shift(shift, expected):
    assert mcolors.to_hex(shift_tone('#4477aa', shift)) == expected
    rgba = shift_tone((68 / 255, 119 / 255, 170 / 255, .375), shift)
    assert rgba[-1] == .375


@pytest.mark.parametrize('shift', [-101, 101, float('nan'), float('inf')])
def test_invalid_shift(shift):
    with pytest.raises(ValueError, match='hatch_tone_shift'):
        WaffleStyle(hatch_tone_shift=shift)
    with pytest.raises(ValueError, match='hatch_tone_shift'):
        shift_tone('#ffffff', shift)


def test_waffle_uses_resolved_fill_color_in_cells_and_legend():
    style = WaffleStyle(
        color_map={'A': '#aaaaaa', 'B': '#cccccc'},
        hatch_map={'A': '/', 'B': 'xx'},
    )
    # colors= must override style.color_map BEFORE hatch color is derived.
    fig, ax = waffle({'A': 32.5, 'B': 67.5}, style=style,
                     colors={'A': '#4477aa', 'B': '#cc8844'},
                     show_legend=True)
    segments = _hatch_segments(ax)
    swatches = _hatch_swatches(ax)
    assert len(swatches) == 2
    assert len(segments) >= 20  # mixed cell includes two colored segments
    for group in (segments, swatches):
        for patch in group:
            target = shift_tone(patch.get_facecolor(), -30)
            assert patch.get_edgecolor() == pytest.approx(target)
    # It must not use a single fixed hatch color for different fill colors.
    assert swatches[0].get_edgecolor() != swatches[1].get_edgecolor()
    plt.close(fig)


def test_explicit_hatch_color_overrides_automatic_shift():
    style = WaffleStyle(hatch_map={'A': '//', 'B': '..'},
                       hatch_tone_shift=100, hatch_color='#5b2f8a')
    fig, ax = waffle({'A': 50, 'B': 50}, style=style, show_legend=True)
    for patch in _hatch_segments(ax) + _hatch_swatches(ax):
        assert mcolors.to_hex(patch.get_edgecolor()) == '#5b2f8a'
    plt.close(fig)


def test_dark_theme_preserves_auto_hatch_behavior():
    with plt.style.context('dark_background'):
        style = adapt_cell_style(WaffleStyle(hatch_map={'A': '/'}))
        assert style.hatch_color is None
        fig, ax = waffle({'A': 100}, style=style, show_legend=True)
        assert _hatch_segments(ax)[0].get_edgecolor() == pytest.approx(
            shift_tone(_hatch_segments(ax)[0].get_facecolor(), -30))
        plt.close(fig)


def test_table_legend_and_rows_use_same_tone():
    style = WaffleStyle(hatch_map={'A': '//', 'B': '..'},
                       hatch_tone_shift=35)
    rec = [{'label': '01', 'composition': {'A': 25, 'B': 75}}]
    fig, ax = waffle_table(rec, style=style,
                           colors={'A': '#4477aa', 'B': '#cc8844'},
                           show_legend=True)
    assert len(_hatch_swatches(ax)) == 2
    for patch in _hatch_segments(ax) + _hatch_swatches(ax):
        assert patch.get_edgecolor() == pytest.approx(
            shift_tone(patch.get_facecolor(), 35))
    plt.close(fig)


def test_excel_default_and_custom_tone_match_library():
    engine = _load_inline_engine()
    source = '#4477aa'
    packed = 0x4477AA
    rgb = engine['_cw_rgb'](packed)
    for shift in (-100, -30, 0, 40, 100):
        expected = shift_tone(source, shift)[:3]
        assert engine['_cw_tone_rgb'](rgb, shift) == pytest.approx(expected)

    opts = [0, 20, 1, .78, .12, .18, 5, .10, .55, 0, 32]
    for options, shift in ((opts, -30), (opts + [-65], -65),
                           (opts + [40], 40), (opts + [float('nan')], -30)):
        fig = engine['cw_draw_row']([100], [packed], [[.1], [.55]],
                                    [2], [1], options)
        swatch = engine['cw_legend_swatch'](packed, [.10, .55], 2, options)
        expected = shift_tone(source, shift)
        rects = _hatch_segments(fig.axes[0])
        assert len(rects) == 20
        assert rects[0].get_edgecolor() == pytest.approx(expected)
        swatch_patch = _hatch_swatches(swatch.axes[0])[0]
        assert swatch_patch.get_edgecolor() == pytest.approx(expected)
        fig.canvas.draw()
        swatch.canvas.draw()
        plt.close(fig)
        plt.close(swatch)

    for shift in (-101, 101):
        with pytest.raises(ValueError, match='hatch_tone_shift'):
            engine['cw_draw_row']([100], [packed], [[.1], [.55]],
                                  [2], [1], opts + [shift])
        with pytest.raises(ValueError, match='hatch_tone_shift'):
            engine['cw_legend_swatch'](packed, [.1, .55], 2, opts + [shift])
