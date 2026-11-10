"""compwaffle v0.1.2-compatible inline engine for Python in Excel.

This code accepts only numeric Excel inputs. Material and specimen names remain
in ordinary Excel cells, never passed through xl() to this engine.
Core path/clip/fractional-fill behavior adapted from compwaffle v0.1.2.
"""
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import PathPatch, Rectangle

_CW_HATCHES = ('', '/', '//', '\\', '\\\\', '|', '||', '-', '--', '+', '++', '.', '..', 'x', 'xx', 'o', 'oo')
_CW_ROUND = 4 * (math.sqrt(2) - 1) / 3


def _cw_nums(value):
    """Flatten xl() scalars, Series or DataFrames without accepting text."""
    if hasattr(value, 'to_numpy'):
        value = value.to_numpy()
    elif hasattr(value, 'values'):
        value = value.values
    arr = np.asarray(value, dtype=object).ravel()
    out = []
    for element in arr:
        if element is None or (isinstance(element, str) and element == ''):
            out.append(float('nan'))
        elif isinstance(element, (str, bytes)):
            raise ValueError('PY input must contain numbers only')
        else:
            out.append(float(element))
    return np.asarray(out, dtype=float)


def _cw_setting(value, fallback):
    return float(value) if np.isfinite(value) else float(fallback)


def _cw_rgb(packed):
    packed = int(packed)
    if packed < 0 or packed > 0xFFFFFF:
        raise ValueError('packed RGB outside 0..0xFFFFFF')
    return ((packed >> 16 & 255) / 255,
            (packed >> 8 & 255) / 255,
            (packed & 255) / 255)


def _cw_tone_rgb(rgb, shift):
    """RGB shade/tint for hatch ink; matches compwaffle.colors.shift_tone."""
    if not math.isfinite(shift) or not -100 <= shift <= 100:
        raise ValueError('hatch_tone_shift must be finite and in [-100, 100]')
    fraction = shift / 100.0
    if fraction < 0:
        return tuple(channel * (1 + fraction) for channel in rgb)
    return tuple(channel + (1 - channel) * fraction for channel in rgb)


def _cw_hatch_shift(options):
    # Older 11-element setting vectors are still supported.
    shift = _cw_setting(options[11], -30.0) if len(options) > 11 else -30.0
    if not -100 <= shift <= 100:
        raise ValueError('hatch_tone_shift must be in [-100, 100]')
    return shift


def _cw_path(left, bottom, width, height, span, bend):
    """v0.1.2 four-corner cubic mask; negative bend gives recesses."""
    span, bend = float(span), float(bend)
    if not (0 <= span <= 0.5 and -1 <= bend <= 1):
        raise ValueError('corner_span in [0,.5], corner_bend in [-1,1]')
    r = span * min(width, height)
    right, top = left + width, bottom + height
    if r == 0:
        return Path([(left,bottom),(right,bottom),(right,top),(left,top),(left,bottom)],
                    [Path.MOVETO,Path.LINETO,Path.LINETO,Path.LINETO,Path.CLOSEPOLY])
    start, end = (r,0), (0,r)
    if bend >= 0:
        c1, c2 = (r*(1-bend),0), (0,r*(1-bend))
    else:
        depth = -bend
        c1, c2 = (r,depth*r), (depth*r,r)
    tl = lambda p:(left+p[0],top-p[1])
    bl = lambda p:(left+p[0],bottom+p[1])
    br = lambda p:(right-p[0],bottom+p[1])
    tr = lambda p:(right-p[0],top-p[1])
    vertices = [tl(start)]
    codes = [Path.MOVETO]
    def curve(transform, reverse=False):
        seq = (c2,c1,start) if reverse else (c1,c2,end)
        vertices.extend(transform(p) for p in seq)
        codes.extend((Path.CURVE4,Path.CURVE4,Path.CURVE4))
    curve(tl)
    vertices.append(bl(end)); codes.append(Path.LINETO)
    curve(bl, reverse=True)
    vertices.append(br(start)); codes.append(Path.LINETO)
    curve(br)
    vertices.append(tr(end)); codes.append(Path.LINETO)
    curve(tr, reverse=True)
    vertices.append(tl(start)); codes.append(Path.CLOSEPOLY)
    return Path(vertices,codes)


def _cw_fills(raw, *, mode, ncols, value_per_cell, ref_weights):
    """Exact cumulative component boundaries, equivalent to v0.1.2 core."""
    if len(raw) == 0 or not np.all(np.isfinite(raw)) or np.any(raw < 0):
        raise ValueError('composition must contain finite nonnegative numbers')
    total = float(math.fsum(raw))
    if total <= 0:
        raise ValueError('composition total must be positive')
    if mode == 0:
        values = raw * (100.0 / total)
        amount_per_cell = 100 / ncols
        cell_count = ncols
    elif mode in (1,2):
        if value_per_cell <= 0:
            raise ValueError('value_per_cell must be positive')
        if mode == 2:
            denominator = float(np.dot(raw,ref_weights))
            if denominator <= 0:
                raise ValueError('reference basis total must be positive')
            values = raw * (100.0 / denominator)
        else:
            values = raw
        amount_per_cell = value_per_cell
        cell_count = max(1, math.ceil(math.nextafter(float(math.fsum(values)) / value_per_cell, -math.inf)))
    else:
        raise ValueError('mode must be 0, 1 or 2')
    if cell_count > 500:
        raise ValueError('too many cells (>500)')
    cells = [[] for _ in range(cell_count)]
    start = 0.0
    displayed_total = 100 if mode == 0 else float(math.fsum(values))
    nonzero = np.flatnonzero(values > 0)
    for j,v in enumerate(values):
        if v == 0: continue
        end = displayed_total if j == nonzero[-1] else min(displayed_total, math.fsum((start,float(v))))
        first_i = max(0,int(math.floor(start / amount_per_cell)))
        final_i = min(cell_count,int(math.ceil(end / amount_per_cell)))
        for i in range(first_i,final_i):
            lo = max(start,i*amount_per_cell)
            hi = min(end,(i+1)*amount_per_cell)
            if hi-lo <= amount_per_cell * 1e-12:continue
            a = max(0.0,min(1.0,(lo-i*amount_per_cell)/amount_per_cell))
            b = max(0.0,min(1.0,(hi-i*amount_per_cell)/amount_per_cell))
            cells[i].append((j,a,b))
        start = end
    return cells, amount_per_cell, displayed_total
