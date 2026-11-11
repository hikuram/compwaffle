#!/usr/bin/env python3
"""Create a template-free Python in Excel workbook from a CSV.

The generated workbook contains a standalone compwaffle drawing engine and
requires Microsoft 365 Python in Excel to calculate its PY plots. No template
XLSX is needed and Excel does not import the local compwaffle package.

Requires the optional local dependency lxml (pip install compwaffle[excel]).

Python API::

    from dataclasses import replace
    from compwaffle.excel import ExcelSettings, build_excel_workbook
    settings = replace(ExcelSettings(), composition_range="B2:H",
                       evaluation_columns=("I", "J", "K"))
    build_excel_workbook("input.csv", "output.xlsx", settings)

CLI::

    compwaffle-excel input.csv -o output.xlsx
"""

from __future__ import annotations

import argparse
import csv
import io
import math
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zipfile import ZipFile, ZIP_DEFLATED

from lxml import etree


# ---------------------------------------------------------------------------
# DEFAULT SETTINGS -- override with ExcelSettings(...) in your own script.
# CSV coordinates refer to the copied 'table' worksheet.
# ---------------------------------------------------------------------------
COMPOSITION_RANGE = "B2:H"           # e.g. B2:Q257 for 16 components / 256 rows
SAMPLE_ID_COLUMN = "A"              # None: number the rows sequentially
EVALUATION_COLUMNS = ("I", "J", "K")  # None or (): no additional columns
EVALUATION_LABELS = None            # e.g. ("Torque", "Density", "Strength")
HEADER_ROW = 1                      # first line of CSV, or None

# Applied to selected component columns, from left to right.
FILL_COLORS = (
    "#4477AA", "#66A6A0", "#DDAA55", "#88B4D8",
    "#8DBA87", "#BB88B8", "#B19A72", "#7E96A8",
    "#D67F7C", "#6E9FCA", "#B8C777", "#D29DAB",
    "#77B9AB", "#C4A16D", "#A29BC8", "#AAB7C4",
)
HATCHES = ("//", "..") + ("",) * 14
CORNER_SPANS = None                 # e.g. (None, 0.1, None, ...)
CORNER_BENDS = None                 # e.g. (None, -0.2, None, ...)
REFERENCE_WEIGHTS = None            # default: first component has weight 1

OPTIONS = {
    "mode": 0,                       # 0 normalized, 1 raw, 2 reference-normalized
    "cells_per_100": 20,
    "cell_width": 1.0,
    "cell_height": 0.78,
    "horizontal_gap": 0.12,
    "vertical_gap": 0.18,            # currently reserved by v0.1.2 engine
    "value_per_cell": 100.0,
    "corner_span": 0.15,
    "corner_bend": 0.5522847498,
    "show_scale": 0,
    "canvas_columns": 32,
    "hatch_tone_shift": -30,         # -100 black, 0 unchanged, +100 white
}

CSV_ENCODING = None                 # None: UTF-8 BOM, UTF-8, then CP932
CSV_DELIMITER = ","
MAX_COMPONENTS = 16
MAX_DRAW_ROWS = 256


# ---------------------------------------------------------------------------
# Embedded Python-in-Excel engine; maintained here, not read from a template.
# ---------------------------------------------------------------------------
PY_ENGINE = r'''"""compwaffle v0.1.2-compatible inline engine for Python in Excel.

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
    return cells, amount_per_cell, displayed_total'''

PY_DRAW_FUNCTIONS = r'''def cw_draw_row(values_input, colors_input, shapes_input, hatches_input,
                basis_input, options_input):
    """One isolated figure, no title, text labels or category names in Python."""
    raw = _cw_nums(values_input)
    packed = _cw_nums(colors_input)
    corners = _cw_nums(shapes_input)
    hatch_codes = _cw_nums(hatches_input)
    basis = _cw_nums(basis_input)
    opts = _cw_nums(options_input)
    count = raw.size
    if packed.size != count or hatch_codes.size != count or basis.size != count or corners.size != 2*count:
        raise ValueError('component and setting array widths differ')
    if opts.size < 11:
        raise ValueError('missing global numeric settings')
    mode = int(opts[0]); ncols = int(opts[1])
    cell_w = _cw_setting(opts[2],1.0)
    cell_h = _cw_setting(opts[3],0.78)
    gap = _cw_setting(opts[4],0.12)
    value_per_cell = _cw_setting(opts[6],100)
    default_span = _cw_setting(opts[7],0.15)
    default_bend = _cw_setting(opts[8],_CW_ROUND)
    show_scale = int(_cw_setting(opts[9],0))
    canvas_cols = int(_cw_setting(opts[10],32))
    hatch_shift = _cw_hatch_shift(opts)
    if ncols < 1 or canvas_cols < 1 or cell_w <= 0 or cell_h <= 0 or gap < 0:
        raise ValueError('invalid waffle size settings')
    corners = corners.reshape(2,count)
    cells, amount_per_cell, displayed_total = _cw_fills(
        raw,mode=mode,ncols=ncols,value_per_cell=value_per_cell,ref_weights=basis)
    if mode == 0:
        canvas_cols = ncols
    elif len(cells) > canvas_cols:
        raise ValueError('composition exceeds canvas columns; increase canvas_columns')
    fig,ax=plt.subplots(figsize=(7.65,0.54 if not show_scale else 0.76),dpi=130)
    fig.patch.set_facecolor('white')
    ax.set_position([0.012, 0.23 if show_scale else 0.08,
                     0.976, 0.69 if show_scale else 0.84])
    pitch = cell_w+gap
    ax.set_xlim(-0.04,canvas_cols*pitch-gap+0.04)
    ax.set_ylim(-0.30 if show_scale else -0.05,cell_h+0.05)
    ax.axis('off')
    for i,seg in enumerate(cells):
        single = (len(seg)==1 and math.isclose(seg[0][1],0,abs_tol=1e-10)
                  and math.isclose(seg[0][2],1,abs_tol=1e-10))
        j=seg[0][0] if single else None
        span = _cw_setting(corners[0,j],default_span) if single else default_span
        bend = _cw_setting(corners[1,j],default_bend) if single else default_bend
        left=i*pitch
        path=_cw_path(left,0,cell_w,cell_h,span,bend)
        bg=PathPatch(path,facecolor='#EDF1F5',edgecolor='none',zorder=2)
        ax.add_patch(bg)
        for k,a,b in seg:
            hidx=int(_cw_setting(hatch_codes[k],0))
            hatch = _CW_HATCHES[hidx] if 0<=hidx<len(_CW_HATCHES) else ''
            rgb = _cw_rgb(packed[k])
            rect=Rectangle((left+a*cell_w,0),(b-a)*cell_w,cell_h,
                           facecolor=rgb,
                           edgecolor=_cw_tone_rgb(rgb,hatch_shift) if hatch else 'none',
                           linewidth=0,hatch=hatch or None,zorder=3)
            rect.set_clip_path(bg)
            ax.add_patch(rect)
        ax.add_patch(PathPatch(path,facecolor='none',edgecolor='white',linewidth=0.45,zorder=4))
    if show_scale:
        tick_count=min(canvas_cols, 100)
        step=max(1,math.ceil(tick_count/5))
        for i in range(0,tick_count+1,step):
            x=i*pitch
            ax.plot([x,x],[-0.05,-0.12],color='#667085',lw=0.4)
            ax.text(x,-0.16,f'{i*amount_per_cell:.4g}',ha='center',va='top',
                    fontsize=6,color='#4B5563')
    return fig


def cw_legend_swatch(color_input, shape_input, hatch_input, options_input):
    rgb=_cw_nums(color_input)[0]
    shape=_cw_nums(shape_input)
    hatch_code=int(_cw_setting(_cw_nums(hatch_input)[0],0))
    opts=_cw_nums(options_input)
    if opts.size < 11:
        raise ValueError('missing global numeric settings')
    hatch_shift=_cw_hatch_shift(opts)
    span=_cw_setting(shape[0],_cw_setting(opts[7],0.15))
    bend=_cw_setting(shape[1],_cw_setting(opts[8],_CW_ROUND))
    hatch = _CW_HATCHES[hatch_code] if 0 <= hatch_code < len(_CW_HATCHES) else ''
    fig,ax=plt.subplots(figsize=(0.38,0.38),dpi=100)
    fig.patch.set_facecolor('white')
    ax.set_position([0,0,1,1])
    path=_cw_path(0.04,0.04,0.92,0.92,span,bend)
    fill_rgb=_cw_rgb(rgb)
    ax.add_patch(PathPatch(path,facecolor=fill_rgb,
                           edgecolor=_cw_tone_rgb(fill_rgb,hatch_shift) if hatch else 'none',
                           linewidth=0,hatch=hatch or None))
    ax.set(xlim=(0,1),ylim=(0,1))
    ax.axis('off')
    return fig'''

# Excel-authored Python initialization compatibility profile.
#
# In an actual Microsoft 365 Excel test, an arbitrary newly generated
# environment ID plus shortened startup code was reported as "Unsupported
# Python environment" (#BLOCKED!).  Restoring *only* the Excel-authored
# environmentDefinition (test A) was verified by the tester to execute.
# Tests B/C additionally copied Excel workbook/worksheet metadata, but did
# not establish that those extra changes were necessary.  Preserve this
# known-working environment definition, including its original GUID and
# initialization source, rather than inventing a new one per workbook.
#
# This is a compatibility profile, NOT a way to enable Python on an account
# where Microsoft 365 Python in Excel is unavailable or disabled.  Microsoft
# may revise what it accepts, so this is pinned to the verified profile.
PY_EXCEL_ENVIRONMENT_ID = "{882DD1B0-6546-4DFA-8A08-902A380B44EA}"
PY_ENV_INIT = """import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import statsmodels as sm
import excel
import warnings

warnings.simplefilter('ignore')

excel.set_xl_scalar_conversion(excel.convert_to_scalar)
excel.set_xl_array_conversion(excel.convert_to_dataframe)
"""
PY_LEGEND = """cw_legend_swatch(
    xl(%P2%, headers=False),
    xl(%P3%, headers=False),
    xl(%P4%, headers=False),
    xl(%P5%, headers=False),
)"""
PY_DRAW = """cw_draw_row(
    xl(%P2%, headers=False),
    xl(%P3%, headers=False),
    xl(%P4%, headers=False),
    xl(%P5%, headers=False),
    xl(%P6%, headers=False),
    xl(%P7%, headers=False),
)"""


# ---------------------------------------------------------------------------
# OOXML namespaces and general helpers
# ---------------------------------------------------------------------------
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
PY = "http://schemas.microsoft.com/office/spreadsheetml/2023/python"
XDA = "http://schemas.microsoft.com/office/spreadsheetml/2017/dynamicarray"
CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC = "http://purl.org/dc/elements/1.1/"
DCTERMS = "http://purl.org/dc/terms/"
VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
APP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
Q = lambda ns, tag: "{%s}%s" % (ns, tag)
NUMERIC = re.compile(r"^[+-]?(?:(?:\d+\.?\d*)|(?:\.\d+))(?:[Ee][+-]?\d+)?$")
COMP_REF = re.compile(r"^([A-Z]+)([1-9]\d*):([A-Z]+)([1-9]\d*)?$", re.I)
HATCH_CODES = ("", "/", "//", "\\", "\\\\", "|", "||", "-", "--",
               "+", "++", ".", "..", "x", "xx", "o", "oo")
DEFAULT_HELP = {
    "mode": "0 = normalized to 100%; 1 = raw amounts; 2 = reference basis",
    "cells_per_100": "Waffle cell count in normalized mode",
    "cell_width": "Cell width (relative units)",
    "cell_height": "Cell height (relative units)",
    "horizontal_gap": "Horizontal gap between cells",
    "vertical_gap": "Reserved for compatible engine versions",
    "value_per_cell": "Amount represented by one cell (raw/reference modes)",
    "corner_span": "Default corner span (0.0 to 0.5)",
    "corner_bend": "Default corner bend (-1.0 to +1.0)",
    "show_scale": "0 = no scale; 1 = show scale",
    "canvas_columns": "Available width in raw/reference modes",
    "hatch_tone_shift": "-100 = black; 0 = fill color; +100 = white",
}


@dataclass(frozen=True)
class Settings:
    composition_range: str = COMPOSITION_RANGE
    sample_id_column: str | None = SAMPLE_ID_COLUMN
    evaluation_columns: tuple[str, ...] = EVALUATION_COLUMNS
    evaluation_labels: tuple[str, ...] | None = EVALUATION_LABELS
    header_row: int | None = HEADER_ROW
    fill_colors: tuple[str, ...] = FILL_COLORS
    hatches: tuple[str, ...] = HATCHES
    corner_spans: tuple[float | None, ...] | None = CORNER_SPANS
    corner_bends: tuple[float | None, ...] | None = CORNER_BENDS
    reference_weights: tuple[float, ...] | None = REFERENCE_WEIGHTS
    options: dict[str, float] = field(default_factory=lambda: dict(OPTIONS))
    csv_encoding: str | None = CSV_ENCODING
    csv_delimiter: str = CSV_DELIMITER


def col_index(letter: str) -> int:
    if not re.fullmatch(r"[A-Za-z]+", letter):
        raise ValueError(f"Invalid Excel column: {letter!r}")
    result = 0
    for char in letter.upper():
        result = result * 26 + ord(char) - 64
    if not 1 <= result <= 16384:
        raise ValueError(f"Excel column out of range: {letter!r}")
    return result


def col_letter(number: int) -> str:
    if not 1 <= number <= 16384:
        raise ValueError(f"Invalid column index: {number}")
    result = ""
    while number:
        number, mod = divmod(number - 1, 26)
        result = chr(65 + mod) + result
    return result


def read_csv(path: Path, settings: Settings) -> list[list[str]]:
    raw = path.read_bytes()
    encodings = [settings.csv_encoding] if settings.csv_encoding else ["utf-8-sig", "utf-8", "cp932"]
    decoded = None
    for encoding in encodings:
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            pass
    if decoded is None:
        raise ValueError(f"CSV cannot be decoded using {encodings!r}")
    if len(settings.csv_delimiter) != 1:
        raise ValueError("CSV_DELIMITER must be one character")
    data = list(csv.reader(io.StringIO(decoded, newline=""), delimiter=settings.csv_delimiter))
    if not data or not any(data):
        raise ValueError("CSV contains no data")
    width = max(map(len, data))
    if len(data) > 1_048_576 or width > 16_384:
        raise ValueError("CSV exceeds Excel worksheet limits")
    data = [row + [""] * (width - len(row)) for row in data]
    if settings.header_row is not None and not 1 <= settings.header_row <= len(data):
        raise ValueError("HEADER_ROW is outside CSV")
    return data


def numeric(raw: str) -> float | None:
    text = raw.strip()
    if not text or not NUMERIC.fullmatch(text):
        return None
    content = text.lstrip("+-")
    # IDs such as 0002 must not turn into the number 2.
    if len(content) > 1 and content[0] == "0" and content[1].isdigit():
        return None
    try:
        value = Decimal(text)
        if len(value.normalize().as_tuple().digits) > 15:
            return None
        number = float(value)
        return number if math.isfinite(number) else None
    except (InvalidOperation, OverflowError, ValueError):
        return None


def valid_text(value: Any) -> str:
    text = str(value)
    if len(text) > 32767:
        raise ValueError("A cell exceeds the Excel string length limit (32767)")
    if any(ord(ch) < 32 and ch not in "\r\n\t" for ch in text):
        raise ValueError("Invalid control character in a CSV cell")
    # XML 1.0 also excludes surrogate code points and FFFE/FFFF.
    if any(0xD800 <= ord(ch) <= 0xDFFF or ord(ch) in (0xFFFE, 0xFFFF) for ch in text):
        raise ValueError("Invalid Unicode character in CSV")
    return text


def composition_range(rows: list[list[str]], settings: Settings):
    match = COMP_REF.fullmatch(settings.composition_range.strip())
    if not match:
        raise ValueError("COMPOSITION_RANGE must look like 'B2:Q' or 'B2:Q257'")
    a, first, b, last = match.groups()
    left, right = col_index(a), col_index(b)
    start, end = int(first), int(last) if last else len(rows)
    if left > right or start > end or end > len(rows):
        raise ValueError("Reversed or out-of-bounds composition range")
    if right > len(rows[0]):
        raise ValueError("Composition columns exceed CSV width")
    count, length = right - left + 1, end - start + 1
    if not 1 <= count <= MAX_COMPONENTS:
        raise ValueError(f"Composition must contain 1..{MAX_COMPONENTS} columns; got {count}")
    if not 1 <= length <= MAX_DRAW_ROWS:
        raise ValueError(f"Composition must contain 1..{MAX_DRAW_ROWS} rows; got {length}")
    for row_idx in range(start, end + 1):
        values = []
        for col in range(left, right + 1):
            text = rows[row_idx - 1][col - 1]
            val = numeric(text)
            if val is None or val < 0:
                raise ValueError(f"Nonnegative numeric composition required at {col_letter(col)}{row_idx}: {text!r}")
            values.append(val)
        if not any(values):
            raise ValueError(f"Composition row {row_idx} has a zero sum")
    return left, right, start, end, count, length


def prepare(rows: list[list[str]], settings: Settings):
    left, right, start, end, count, length = composition_range(rows, settings)
    width = len(rows[0])
    if settings.sample_id_column and col_index(settings.sample_id_column) > width:
        raise ValueError("SAMPLE_ID_COLUMN exceeds CSV width")
    metrics = tuple(col_index(s) for s in settings.evaluation_columns)
    if len(set(metrics)) != len(metrics) or any(j > width for j in metrics):
        raise ValueError("EVALUATION_COLUMNS contain duplicates or exceed CSV width")
    if settings.evaluation_labels is not None and len(settings.evaluation_labels) != len(metrics):
        raise ValueError("EVALUATION_LABELS must match EVALUATION_COLUMNS")
    colors = settings.fill_colors[:count]
    hatches = settings.hatches[:count]
    if len(colors) != count or len(hatches) != count:
        raise ValueError("Provide a fill color and hatch for every component")
    if any(not re.fullmatch(r"#[0-9A-Fa-f]{6}", color) for color in colors):
        raise ValueError("Fill colors must be #RRGGBB")
    if any(h not in HATCH_CODES for h in hatches):
        raise ValueError("Unsupported hatch pattern")
    spans = settings.corner_spans[:count] if settings.corner_spans is not None else (None,) * count
    bends = settings.corner_bends[:count] if settings.corner_bends is not None else (None,) * count
    weights = settings.reference_weights[:count] if settings.reference_weights is not None else (1,) + (0,) * (count - 1)
    if min(len(spans), len(bends), len(weights)) < count:
        raise ValueError("Per-component option arrays must cover every component")
    for value in spans:
        if value is not None and (not math.isfinite(float(value)) or not 0 <= float(value) <= 0.5):
            raise ValueError("Corner spans must be in [0, 0.5]")
    for value in bends:
        if value is not None and (not math.isfinite(float(value)) or not -1 <= float(value) <= 1):
            raise ValueError("Corner bends must be in [-1, +1]")
    if any(not math.isfinite(float(w)) for w in weights):
        raise ValueError("Reference weights must be finite")
    if tuple(settings.options) != tuple(OPTIONS):
        raise ValueError("OPTIONS must contain the documented 12 keys in the same order")
    if any(isinstance(v, (str, bytes)) or not math.isfinite(float(v)) for v in settings.options.values()):
        raise ValueError("Global options must be finite numeric values")
    if settings.options["mode"] not in (0, 1, 2):
        raise ValueError("mode must be 0, 1 or 2")
    if not -100 <= settings.options["hatch_tone_shift"] <= 100:
        raise ValueError("hatch_tone_shift must be within -100..+100")
    if settings.options["cells_per_100"] < 1 or settings.options["canvas_columns"] < 1:
        raise ValueError("cells_per_100 and canvas_columns must be positive")
    if settings.options["cell_width"] <= 0 or settings.options["cell_height"] <= 0 or settings.options["horizontal_gap"] < 0:
        raise ValueError("Invalid cell size or gap")
    if settings.options["value_per_cell"] <= 0:
        raise ValueError("value_per_cell must be positive")
    if not 0 <= settings.options["corner_span"] <= 0.5 or not -1 <= settings.options["corner_bend"] <= 1:
        raise ValueError("Invalid global corner shape")
    if settings.options["mode"] == 2:
        for row_number in range(start, end + 1):
            values = [numeric(rows[row_number - 1][j - 1]) for j in range(left, right + 1)]
            if math.fsum(v * float(w) for v, w in zip(values, weights)) <= 0:
                raise ValueError(f"Reference-weighted total must be positive in CSV row {row_number}")
    # Be generous about non-component data columns: the CSV sheet is always full.
    return {"left": left, "right": right, "start": start, "end": end,
            "count": count, "length": length, "metrics": metrics,
            "colors": colors, "hatches": hatches, "spans": spans,
            "bends": bends, "weights": weights}


def xml_bytes(root: etree._Element) -> bytes:
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True, standalone=True)


def cell(row: etree._Element, column: int, number: int, value: Any = None,
         *, style: int = 0, formula: str | None = None,
         cached: Any = None, py_cell: bool = False,
         array: bool = False) -> etree._Element:
    ref = f"{col_letter(column)}{number}"
    attributes = {"r": ref}
    if style:
        attributes["s"] = str(style)
    if py_cell:
        attributes["cm"] = "1"  # dynamic-array metadata, xl/metadata.xml
    c = etree.SubElement(row, Q(S, "c"), **attributes)
    if formula is not None:
        fattrs = {"t": "array", "ref": ref} if array else {}
        etree.SubElement(c, Q(S, "f"), **fattrs).text = formula
        if cached is not None:
            if isinstance(cached, str):
                c.set("t", "str")
            etree.SubElement(c, Q(S, "v")).text = str(cached)
    elif value is None or value == "":
        pass
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(float(value)):
            raise ValueError("Numeric cell cannot be NaN or infinite")
        etree.SubElement(c, Q(S, "v")).text = str(value)
    else:
        c.set("t", "inlineStr")
        is_el = etree.SubElement(c, Q(S, "is"))
        t = etree.SubElement(is_el, Q(S, "t"))
        text = valid_text(value)
        if text[:1].isspace() or text[-1:].isspace():
            t.set(XML_SPACE, "preserve")
        t.text = text
    return c


def section(sheetdata: etree._Element, row_number: int, label: str, last_col: int, merges: list[str]):
    row = etree.SubElement(sheetdata, Q(S, "row"), r=str(row_number), ht="28", customHeight="1")
    cell(row, 1, row_number, label, style=1)
    merges.append(f"A{row_number}:{col_letter(last_col)}{row_number}")


def common_sheet(*, last_ref: str, active: bool):
    root = etree.Element(Q(S, "worksheet"), nsmap={None: S})
    etree.SubElement(root, Q(S, "dimension"), ref=f"A1:{last_ref}")
    views = etree.SubElement(root, Q(S, "sheetViews"))
    etree.SubElement(views, Q(S, "sheetView"), workbookViewId="0", showGridLines="0",
                     **({"tabSelected": "1"} if active else {}))
    etree.SubElement(root, Q(S, "sheetFormatPr"), defaultRowHeight="16")
    return root


def make_table(rows: list[list[str]], settings: Settings) -> bytes:
    width = len(rows[0])
    root = common_sheet(last_ref=f"{col_letter(width)}{len(rows)}", active=False)
    cols = etree.SubElement(root, Q(S, "cols"))
    for j in range(1, width + 1):
        header = rows[settings.header_row - 1][j - 1] if settings.header_row else ""
        size = min(36, max(12, len(header) + 3))
        etree.SubElement(cols, Q(S, "col"), min=str(j), max=str(j), width=str(size), customWidth="1")
    data = etree.SubElement(root, Q(S, "sheetData"))
    for i, values in enumerate(rows, 1):
        header = (i == settings.header_row)
        row = etree.SubElement(data, Q(S, "row"), r=str(i), **({"ht": "26", "customHeight": "1"} if header else {}))
        for j, raw in enumerate(values, 1):
            if raw == "":
                continue
            number = numeric(raw) if not header else None
            cell(row, j, i, number if number is not None else raw, style=2 if header else 3)
    if settings.header_row == 1 and len(rows) > 1:
        etree.SubElement(root, Q(S, "autoFilter"), ref=f"A1:{col_letter(width)}{len(rows)}")
    etree.SubElement(root, Q(S, "pageMargins"), left="0.4", right="0.4", top="0.6",
                     bottom="0.6", header="0.3", footer="0.3")
    return xml_bytes(root)


def hatch_formula(col: str) -> str:
    pairs = ",".join('"' + h.replace('"', '""') + '",' + str(i) for i, h in enumerate(HATCH_CODES))
    return f"IFERROR(_xlfn.SWITCH({col}24,{pairs},0),0)"


def make_waffle(rows: list[list[str]], settings: Settings, info: dict) -> bytes:
    count, length = info["count"], info["length"]
    metric_cols = info["metrics"]
    last_col = max(1 + count, 2 + len(metric_cols))
    root = common_sheet(last_ref=f"{col_letter(last_col)}{36 + length}", active=True)
    cols = etree.SubElement(root, Q(S, "cols"))
    etree.SubElement(cols, Q(S, "col"), min="1", max="1", width="24", customWidth="1")
    etree.SubElement(cols, Q(S, "col"), min="2", max="2", width="48", customWidth="1")
    for i in range(3, last_col + 1):
        etree.SubElement(cols, Q(S, "col"), min=str(i), max=str(i), width="16", customWidth="1")
    data = etree.SubElement(root, Q(S, "sheetData"))
    merges = []
    section(data, 1, "COMPWAFFLE  |  PYTHON IN EXCEL", last_col, merges)
    row3 = etree.SubElement(data, Q(S, "row"), r="3", ht="24", customHeight="1")
    cell(row3, 1, 3, "Drawing engine", style=4)
    cell(row3, 2, 3, formula="_xlfn._xlws.PY(0,1)", cached=0, style=9, py_cell=True, array=True)
    cell(row3, 4, 3, "Python code is embedded. Recalculate with Python in Excel enabled.", style=6)
    for row_no, (name, val) in enumerate(settings.options.items(), start=4):
        r = etree.SubElement(data, Q(S, "row"), r=str(row_no), ht="21", customHeight="1")
        cell(r, 1, row_no, name, style=4)
        cell(r, 2, row_no, val, style=5)
        cell(r, 4, row_no, DEFAULT_HELP[name], style=6)
    r17 = etree.SubElement(data, Q(S, "row"), r="17", ht="24", customHeight="1")
    cell(r17, 1, 17, "Drawing functions", style=4)
    cell(r17, 2, 17, formula="_xlfn._xlws.PY(1,1)", cached=0, style=9, py_cell=True, array=True)
    cell(r17, 4, 17, "Functions are defined here for downstream PY cells.", style=6)
    section(data, 19, "COMPONENT SETTINGS", last_col, merges)
    component_labels = {
        20: "Component", 21: "Fill color (#RRGGBB)",
        22: "Corner span override", 23: "Corner bend override",
        24: "Hatch pattern", 25: "Packed RGB (calculated)",
        26: "Hatch code (calculated)", 28: "Reference weight",
    }
    for rn in [20,21,22,23,24,25,26,28]:
        r = etree.SubElement(data, Q(S, "row"), r=str(rn), ht="23", customHeight="1")
        cell(r, 1, rn, component_labels[rn], style=4)
        for i in range(count):
            col = 2 + i
            letter = col_letter(col)
            src_col = info["left"] + i
            head = rows[settings.header_row - 1][src_col - 1] if settings.header_row else ""
            name = head or f"Component {i + 1}"
            if rn == 20:
                cell(r,col,rn,name,style=13)
            elif rn == 21:
                cell(r,col,rn,info["colors"][i],style=12)
            elif rn == 22:
                cell(r,col,rn,info["spans"][i],style=12)
            elif rn == 23:
                cell(r,col,rn,info["bends"][i],style=12)
            elif rn == 24:
                cell(r,col,rn,info["hatches"][i],style=12)
            elif rn == 25:
                cell(r,col,rn,formula=f"IFERROR(HEX2DEC(RIGHT({letter}21,6)),0)",
                     cached=int(info["colors"][i][1:],16),style=14)
            elif rn == 26:
                cell(r,col,rn,formula=hatch_formula(letter),
                     cached=HATCH_CODES.index(info["hatches"][i]),style=14)
            elif rn == 28:
                cell(r,col,rn,info["weights"][i],style=12)
    section(data, 30, "LEGEND", last_col, merges)
    r32 = etree.SubElement(data, Q(S, "row"), r="32", ht="24", customHeight="1")
    cell(r32, 1, 32, "Component", style=4)
    r33 = etree.SubElement(data, Q(S, "row"), r="33", ht="46", customHeight="1")
    cell(r33, 1, 33, "Color / hatch", style=4)
    for i in range(count):
        col = 2 + i
        letter = col_letter(col)
        source_name = rows[settings.header_row-1][info["left"]+i-1] if settings.header_row else ""
        cell(r32, col, 32, formula=f"{letter}20", cached=source_name or f"Component {i + 1}",style=13)
        formula = (f"_xlfn._xlws.PY(2,0,waffle!{letter}$25,"
                   f"waffle!{letter}$22:{letter}$23,waffle!{letter}$26,"
                   f"waffle!$B$4:$B$15)")
        cell(r33,col,33,formula=formula,py_cell=True,style=15)
    section(data, 35, "COMPOSITION VISUALIZATION", last_col, merges)
    header_row = etree.SubElement(data, Q(S, "row"), r="36", ht="29", customHeight="1")
    id_label = (rows[settings.header_row-1][col_index(settings.sample_id_column)-1]
                if settings.header_row and settings.sample_id_column else "Sample")
    cell(header_row, 1, 36, id_label or "Sample", style=7)
    cell(header_row, 2, 36, "Waffle", style=7)
    for i, src_col in enumerate(metric_cols):
        header = (settings.evaluation_labels[i] if settings.evaluation_labels is not None else
                  rows[settings.header_row-1][src_col-1] if settings.header_row else col_letter(src_col))
        cell(header_row, 3+i, 36, header, style=7)
    for i in range(length):
        row_no = 37 + i
        src_row = info["start"] + i
        r = etree.SubElement(data, Q(S, "row"), r=str(row_no), ht="52", customHeight="1")
        if settings.sample_id_column:
            source_id = rows[src_row - 1][col_index(settings.sample_id_column) - 1]
            id_number = numeric(source_id)
            cell(r, 1, row_no, formula=f"table!{settings.sample_id_column.upper()}{src_row}",
                 cached=(id_number if id_number is not None else source_id or None), style=11)
        else:
            cell(r, 1, row_no, i + 1, style=11)
        last_component = col_letter(count + 1)
        src_first, src_last = col_letter(info["left"]), col_letter(info["right"])
        py_formula = (
            f"_xlfn._xlws.PY(3,0,"
            f"table!${src_first}{src_row}:${src_last}{src_row},"
            f"waffle!$B$25:${last_component}$25,"
            f"waffle!$B$22:${last_component}$23,"
            f"waffle!$B$26:${last_component}$26,"
            f"waffle!$B$28:${last_component}$28,"
            f"waffle!$B$4:$B$15)"
        )
        cell(r, 2, row_no, formula=py_formula, style=9, py_cell=True)
        for j, src_col in enumerate(metric_cols):
            source_metric = rows[src_row - 1][src_col - 1]
            metric_number = numeric(source_metric)
            cell(r, j+3, row_no, formula=f"table!{col_letter(src_col)}{src_row}",
                 cached=(metric_number if metric_number is not None else source_metric or None), style=11)
    if merges:
        el = etree.SubElement(root, Q(S, "mergeCells"), count=str(len(merges)))
        for rng in merges:
            etree.SubElement(el, Q(S, "mergeCell"), ref=rng)
    etree.SubElement(root, Q(S, "pageMargins"), left="0.4", right="0.4", top="0.6",
                     bottom="0.6", header="0.3", footer="0.3")
    return xml_bytes(root)


def make_python() -> bytes:
    root = etree.Element(Q(PY, "python"), nsmap={None: PY})
    env = etree.SubElement(root, Q(PY, "environmentDefinition"), id=PY_EXCEL_ENVIRONMENT_ID)
    init = etree.SubElement(env, Q(PY, "initialization"))
    init_code = etree.SubElement(init, Q(PY, "code"))
    init_code.set(XML_SPACE, "preserve")
    init_code.text = PY_ENV_INIT
    scripts = etree.SubElement(root, Q(PY, "pythonScripts"))
    for script in (PY_ENGINE, PY_DRAW_FUNCTIONS, PY_LEGEND, PY_DRAW):
        node = etree.SubElement(scripts, Q(PY, "pythonScript"))
        etree.SubElement(node, Q(PY, "code")).text = script
    return xml_bytes(root)


def make_metadata() -> bytes:
    root = etree.Element(Q(S, "metadata"), nsmap={None: S, "xda": XDA})
    mt = etree.SubElement(root, Q(S, "metadataTypes"), count="1")
    etree.SubElement(mt, Q(S,"metadataType"), name="XLDAPR", minSupportedVersion="120000",
                     copy="1", pasteAll="1", pasteValues="1", merge="1", splitFirst="1",
                     rowColShift="1", clearFormats="1", clearComments="1", assign="1",
                     coerce="1", cellMeta="1")
    fm = etree.SubElement(root, Q(S,"futureMetadata"), name="XLDAPR", count="1")
    bk = etree.SubElement(fm, Q(S,"bk"))
    extlist = etree.SubElement(bk, Q(S,"extLst"))
    ext = etree.SubElement(extlist, Q(S,"ext"), uri="{bdbb8cdc-fa1e-496e-a857-3c3f30c029c3}")
    etree.SubElement(ext, Q(XDA,"dynamicArrayProperties"), fDynamic="1", fCollapsed="0")
    cm = etree.SubElement(root, Q(S,"cellMetadata"), count="1")
    rc = etree.SubElement(etree.SubElement(cm, Q(S,"bk")),Q(S,"rc"), t="1",v="0")
    return xml_bytes(root)


def make_workbook() -> bytes:
    root = etree.Element(Q(S,"workbook"), nsmap={None:S,"r":R})
    views = etree.SubElement(root, Q(S,"bookViews"))
    etree.SubElement(views,Q(S,"workbookView"),activeTab="1")
    sheets = etree.SubElement(root,Q(S,"sheets"))
    etree.SubElement(sheets,Q(S,"sheet"),name="table",sheetId="1", **{Q(R,"id"):"rId1"})
    etree.SubElement(sheets,Q(S,"sheet"),name="waffle",sheetId="2",**{Q(R,"id"):"rId2"})
    etree.SubElement(root,Q(S,"calcPr"),calcMode="auto",fullCalcOnLoad="1",forceFullCalc="1")
    return xml_bytes(root)


def make_styles() -> bytes:
    root = etree.Element(Q(S,"styleSheet"), nsmap={None:S})
    fonts = etree.SubElement(root,Q(S,"fonts"),count="6")
    font_specs = [
        ("172C3A", False, 11), # 0 body
        ("FFFFFF", True, 12),  # 1 navy title / section
        ("FFFFFF", True, 10),  # 2 header
        ("2D815C", False, 10), # 3 imported CSV data
        ("34465B", True, 10),  # 4 labels
        ("2054A0", False, 10), # 5 editable numeric/text settings
    ]
    for color,bold,size in font_specs:
        f=etree.SubElement(fonts,Q(S,"font"))
        if bold: etree.SubElement(f,Q(S,"b"))
        etree.SubElement(f,Q(S,"sz"),val=str(size))
        etree.SubElement(f,Q(S,"color"),rgb="FF"+color)
        etree.SubElement(f,Q(S,"name"),val="Aptos")
    fills=etree.SubElement(root,Q(S,"fills"),count="6")
    for pattern,color in [("none",None),("gray125",None),("solid","233E56"),
                          ("solid","EAF3F0"),("solid","F0F5FC"),("solid","F5F7F9")]:
        fill=etree.SubElement(fills,Q(S,"fill"))
        pf=etree.SubElement(fill,Q(S,"patternFill"),patternType=pattern)
        if color:
            etree.SubElement(pf,Q(S,"fgColor"),rgb="FF"+color)
            etree.SubElement(pf,Q(S,"bgColor"),indexed="64")
    borders=etree.SubElement(root,Q(S,"borders"),count="2")
    etree.SubElement(borders,Q(S,"border"))
    border=etree.SubElement(borders,Q(S,"border"))
    bottom=etree.SubElement(border,Q(S,"bottom"),style="hair")
    etree.SubElement(bottom,Q(S,"color"),rgb="FFDEE5EA")
    etree.SubElement(border,Q(S,"diagonal"))
    sxfs=etree.SubElement(root,Q(S,"cellStyleXfs"),count="1")
    etree.SubElement(sxfs,Q(S,"xf"),numFmtId="0",fontId="0",fillId="0",borderId="0")
    xfs=etree.SubElement(root,Q(S,"cellXfs"),count="16")
    # Format IDs used by make_table / make_waffle.
    definitions=[
        (0,0,0,"left"),  # 0 normal
        (1,2,0,"left"),  # 1 heading
        (2,2,0,"left"),  # 2 CSV header
        (3,0,0,"general"), # 3 imported data
        (4,5,0,"left"),  # 4 label
        (5,4,0,"general"), # 5 editable input
        (0,5,0,"left"),  # 6 hint
        (2,2,0,"left"),  # 7 report header
        (4,3,0,"left"),  # 8 component label
        (0,0,0,"center"),# 9 PY result
        (0,5,0,"general"),# 10 computed numeric
        (0,0,1,"general"),# 11 output linked data
        (5,4,0,"right"),  # 12 per-component editable values
        (4,3,0,"right"),  # 13 component / legend labels
        (0,5,0,"right"),  # 14 per-component calculated numeric values
        (0,0,0,"right"),  # 15 Python legend swatches
    ]
    for style_id, (font,fill,border,halign) in enumerate(definitions):
        xf=etree.SubElement(xfs,Q(S,"xf"),numFmtId="0",fontId=str(font),fillId=str(fill),
                            borderId=str(border),xfId="0",applyFont="1",applyFill="1",
                            applyBorder="1",applyAlignment="1")
        alignment = {"horizontal": halign, "vertical": "center"}
        if style_id == 6:
            # Setting hints in column D should stay on a single line.
            alignment["wrapText"] = "0"
        elif halign == "left" or style_id == 13:
            # Keep wrapped component names while changing their alignment.
            alignment["wrapText"] = "1"
        etree.SubElement(xf, Q(S, "alignment"), **alignment)
    cstyles=etree.SubElement(root,Q(S,"cellStyles"),count="1")
    etree.SubElement(cstyles,Q(S,"cellStyle"),name="Normal",xfId="0",builtinId="0")
    return xml_bytes(root)


def make_relationships() -> dict[str,bytes]:
    # Package root relationships
    relroot=etree.Element(Q(PKG,"Relationships"),nsmap={None:PKG})
    for ident, typ, target in [
        ("rId1","http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument","xl/workbook.xml"),
        ("rId2","http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties","docProps/core.xml"),
        ("rId3","http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties","docProps/app.xml"),
    ]:
        etree.SubElement(relroot,Q(PKG,"Relationship"),Id=ident,Type=typ,Target=target)
    wbroot=etree.Element(Q(PKG,"Relationships"),nsmap={None:PKG})
    entries=[
        ("rId1", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", "worksheets/sheet1.xml"),
        ("rId2", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet", "worksheets/sheet2.xml"),
        ("rId3", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "styles.xml"),
        ("rId4", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/sheetMetadata", "metadata.xml"),
        ("rId5", "http://schemas.microsoft.com/office/2023/09/relationships/Python", "python.xml"),
    ]
    for ident, typ, target in entries:
        etree.SubElement(wbroot,Q(PKG,"Relationship"),Id=ident,Type=typ,Target=target)
    return {"_rels/.rels":xml_bytes(relroot),
            "xl/_rels/workbook.xml.rels":xml_bytes(wbroot)}


def make_content_types() -> bytes:
    root=etree.Element(Q(CT,"Types"),nsmap={None:CT})
    for extension,content in [
        ("rels","application/vnd.openxmlformats-package.relationships+xml"),
        ("xml","application/xml"),
    ]:
        etree.SubElement(root,Q(CT,"Default"),Extension=extension,ContentType=content)
    for path,content in [
        ("xl/workbook.xml","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"),
        ("xl/worksheets/sheet1.xml","application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
        ("xl/worksheets/sheet2.xml","application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"),
        ("xl/styles.xml","application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"),
        ("xl/metadata.xml","application/vnd.openxmlformats-officedocument.spreadsheetml.sheetMetadata+xml"),
        ("xl/python.xml","application/vnd.ms-excel.python+xml"),
        ("docProps/core.xml","application/vnd.openxmlformats-package.core-properties+xml"),
        ("docProps/app.xml","application/vnd.openxmlformats-officedocument.extended-properties+xml"),
    ]:
        etree.SubElement(root,Q(CT,"Override"),PartName="/"+path,ContentType=content)
    return xml_bytes(root)


def make_properties() -> dict[str, bytes]:
    core=etree.Element(Q(CP,"coreProperties"),nsmap={"cp":CP,"dc":DC,"dcterms":DCTERMS})
    etree.SubElement(core,Q(DC,"creator")).text="compwaffle CSV builder"
    etree.SubElement(core,Q(DC,"title")).text="compwaffle - Python in Excel visualization"
    etree.SubElement(core,Q(DC,"description")).text="Generated from CSV without an XLSX template"
    app=etree.Element(Q(APP,"Properties"),nsmap={None:APP,"vt":VT})
    etree.SubElement(app,Q(APP,"Application")).text="Microsoft Excel"
    etree.SubElement(app,Q(APP,"Company")).text=""
    return {"docProps/core.xml":xml_bytes(core),"docProps/app.xml":xml_bytes(app)}



# ---------------------------------------------------------------------------
# Excel-native Python result metadata (rich values and cached image placeholders)
# Reconstructs the same relationship graph used by Microsoft Excel, without
# depending on a template workbook or on openpyxl's non-preserving roundtrip.
# ---------------------------------------------------------------------------
RD = "http://schemas.microsoft.com/office/spreadsheetml/2017/richdata"
RD2 = "http://schemas.microsoft.com/office/spreadsheetml/2017/richdata2"
RVR = "http://schemas.microsoft.com/office/spreadsheetml/2022/richvaluerel"
XLRD = "http://schemas.microsoft.com/office/spreadsheetml/2017/richdata"
XCALCF = "http://schemas.microsoft.com/office/spreadsheetml/2018/calcfeatures"


def patch_python_cells(waffle_xml: bytes) -> tuple[bytes,int]:
    """Mark every PY expression as a native single-cell array formula and
    attach Excel rich-value metadata references for object/image outputs."""
    root = etree.fromstring(waffle_xml)
    count = 0
    for c in root.iter(Q(S,'c')):
        f = c.find(Q(S,'f'))
        if f is None or not (f.text or '').startswith('_xlfn._xlws.PY('):
            continue
        f.set('t','array')
        f.set('ref',c.get('r'))
        c.set('cm','1')
        v = c.find(Q(S,'v'))
        if c.get('r') in {'B3','B17'}:
            c.set('vm','1')
            c.attrib.pop('t',None)
            if v is None: v = etree.SubElement(c,Q(S,'v'))
            v.text = '0'
        else:
            count+=1
            c.set('vm',str(count+1))
            c.set('t','e')
            if v is None: v = etree.SubElement(c,Q(S,'v'))
            v.text = '#VALUE!'  # normal uncached placeholder in Excel-saved PY plots
    return xml_bytes(root), count


def make_metadata_full(plot_count: int) -> bytes:
    root = etree.Element(Q(S, 'metadata'), nsmap={None:S,'xda':XDA,'xlrd':XLRD})
    mtypes = etree.SubElement(root,Q(S,'metadataTypes'),count='2')
    etree.SubElement(mtypes,Q(S,'metadataType'),name='XLDAPR',minSupportedVersion='120000',
        copy='1',pasteAll='1',pasteValues='1',merge='1',splitFirst='1',
        rowColShift='1',clearFormats='1',clearComments='1',assign='1',coerce='1',cellMeta='1')
    etree.SubElement(mtypes,Q(S,'metadataType'),name='XLRICHVALUE',minSupportedVersion='120000',
        copy='1',pasteAll='1',pasteValues='1',merge='1',splitFirst='1',
        rowColShift='1',clearFormats='1',clearComments='1',assign='1',coerce='1')
    fmd = etree.SubElement(root,Q(S,'futureMetadata'),name='XLDAPR',count='1')
    ext = etree.SubElement(etree.SubElement(etree.SubElement(fmd,Q(S,'bk')),
       Q(S,'extLst')),Q(S,'ext'),uri='{bdbb8cdc-fa1e-496e-a857-3c3f30c029c3}')
    etree.SubElement(ext,Q(XDA,'dynamicArrayProperties'),fDynamic='1',fCollapsed='0')
    fmd2 = etree.SubElement(root,Q(S,'futureMetadata'),name='XLRICHVALUE',count=str(plot_count+1))
    for i in range(plot_count+1):
        bk = etree.SubElement(fmd2,Q(S,'bk'))
        ext = etree.SubElement(etree.SubElement(bk,Q(S,'extLst')),
           Q(S,'ext'),uri='{3e2802c4-a4d2-4d8b-9148-e3be6c30e623}')
        etree.SubElement(ext,Q(XLRD,'rvb'),i=str(i+1))
    cm = etree.SubElement(root,Q(S,'cellMetadata'),count='1')
    etree.SubElement(etree.SubElement(cm,Q(S,'bk')),Q(S,'rc'),t='1',v='0')
    vm = etree.SubElement(root,Q(S,'valueMetadata'),count=str(plot_count+1))
    for i in range(plot_count+1):
        etree.SubElement(etree.SubElement(vm,Q(S,'bk')),Q(S,'rc'),t='2',v=str(i))
    return xml_bytes(root)


def make_richparts(plot_count: int) -> dict[str,bytes]:
    files={}
    # Structures: formattednumber, Python object, local image, as in a workbook
    # produced by current Excel.
    st=etree.Element(Q(RD,'rvStructures'),nsmap={None:RD},count='3')
    for name,fields in (
        ('_formattednumber',[('_Format','spb')]),
        ('_python',[('Python_type','s'),('Python_typeName','s'),('Python_str','s'),
                    ('preview','r'),('_Provider','spb')]),
        ('_localImage',[('_rvRel:LocalImageIdentifier','i'),('CalcOrigin','i'),('Text','s')]),
    ):
        node=etree.SubElement(st,Q(RD,'s'),t=name)
        for fname,ftype in fields:
            etree.SubElement(node,Q(RD,'k'),n=fname,t=ftype)
    files['xl/richData/rdrichvaluestructure.xml']=xml_bytes(st)

    rv = etree.Element(Q(RD,'rvData'),nsmap={None:RD},count=str(plot_count+2))
    fmt = etree.SubElement(rv,Q(RD,'rv'),s='0')
    etree.SubElement(fmt,Q(RD,'fb')).text='0'
    etree.SubElement(fmt,Q(RD,'v')).text='0'
    pyob = etree.SubElement(rv,Q(RD,'rv'),s='1')
    etree.SubElement(pyob,Q(RD,'fb')).text='0'
    for val in ["<class 'NoneType'>",'NoneType','None','0','1']:
        etree.SubElement(pyob,Q(RD,'v')).text=val
    for i in range(plot_count):
        img=etree.SubElement(rv,Q(RD,'rv'),s='2')
        for val in [str(i),'9','Python-generated image; recalculate to display']:
            etree.SubElement(img,Q(RD,'v')).text=val
    files['xl/richData/rdrichvalue.xml']=xml_bytes(rv)

    st2=etree.Element(Q(RD2,'spbStructures'),nsmap={None:RD2},count='2')
    a=etree.SubElement(st2,Q(RD2,'s'))
    etree.SubElement(a,Q(RD2,'k'),n='_Self',t='i')
    b=etree.SubElement(st2,Q(RD2,'s'))
    for fname in ('link','logo','name'):
        etree.SubElement(b,Q(RD2,'k'),n=fname,t='s')
    files['xl/richData/rdsupportingpropertybagstructure.xml']=xml_bytes(st2)
    sb=etree.Element(Q(RD2,'supportingPropertyBags'),nsmap={None:RD2})
    data=etree.SubElement(sb,Q(RD2,'spbData'),count='2')
    first=etree.SubElement(data,Q(RD2,'spb'),s='0')
    etree.SubElement(first,Q(RD2,'v')).text='1'
    provider=etree.SubElement(data,Q(RD2,'spb'),s='1')
    for val in ('https://www.anaconda.com/excel',
                'https://res.cdn.office.net/officepysvc/prod-service/anacondalogo.png',
                'Python provided by Anaconda'):
        etree.SubElement(provider,Q(RD2,'v')).text=val
    files['xl/richData/rdsupportingpropertybag.xml']=xml_bytes(sb)

    styles=etree.Element(Q(RD2,'richStyleSheet'),nsmap={None:RD2,'x':S})
    dxfs=etree.SubElement(styles,Q(RD2,'dxfs'),count='1')
    dxf=etree.SubElement(dxfs,Q(S,'dxf'))
    etree.SubElement(dxf,Q(S,'numFmt'),numFmtId='0',formatCode='General')
    prop=etree.SubElement(styles,Q(RD2,'richProperties'))
    etree.SubElement(prop,Q(RD2,'rPr'),n='NumberFormat',t='s')
    richstyles=etree.SubElement(styles,Q(RD2,'richStyles'))
    rsty=etree.SubElement(richstyles,Q(RD2,'rSty'),dxfid='0')
    etree.SubElement(rsty,Q(RD2,'rpv'),i='0').text='0;-0;"None"'
    files['xl/richData/richStyles.xml']=xml_bytes(styles)
    types=etree.Element(Q(RD2,'rvTypesInfo'),nsmap={None:RD2})
    flags=etree.SubElement(etree.SubElement(types,Q(RD2,'global')),Q(RD2,'keyFlags'))
    for name in ('_Self','_DisplayString','_Flags','_Format','_SubLabel','_Attribution',
                 '_Icon','_Display','_CanonicalPropertyNames','_ClassificationId'):
        key=etree.SubElement(flags,Q(RD2,'key'),name=name)
        if name=='_Self':
            etree.SubElement(key,Q(RD2,'flag'),name='ExcludeFromFile',value='1')
        etree.SubElement(key,Q(RD2,'flag'),name='ExcludeFromCalcComparison',value='1')
    files['xl/richData/rdRichValueTypes.xml']=xml_bytes(types)

    relations=etree.Element(Q(RVR,'richValueRels'),nsmap={None:RVR,'r':R})
    rels=etree.Element(Q(PKG,'Relationships'),nsmap={None:PKG})
    for i in range(1,plot_count+1):
        etree.SubElement(relations,Q(RVR,'rel'),**{Q(R,'id'):'rId'+str(i)})
        etree.SubElement(rels,Q(PKG,'Relationship'),Id='rId'+str(i),
            Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/image',
            Target='../media/image1.png')
    files['xl/richData/richValueRel.xml']=xml_bytes(relations)
    files['xl/richData/_rels/richValueRel.xml.rels']=xml_bytes(rels)

    # Minimal transparent PNG generated with Python standard library; no image
    # package dependency, and deliberately no old data in the preview.
    import struct, zlib
    def png_chunk(tag,content):
        return (struct.pack('>I',len(content))+tag+content+
                struct.pack('>I',zlib.crc32(tag+content)&0xFFFFFFFF))
    ihdr=struct.pack('>IIBBBBB',1,1,8,6,0,0,0)
    scan=b'\x00\x00\x00\x00\x00' # row filter plus 1 transparent RGBA pixel
    files['xl/media/image1.png']=(b'\x89PNG\r\n\x1a\n'+
      png_chunk(b'IHDR',ihdr)+png_chunk(b'IDAT',zlib.compress(scan))+
      png_chunk(b'IEND',b''))
    return files


def rich_relationships() -> bytes:
    wbroot=etree.Element(Q(PKG,'Relationships'),nsmap={None:PKG})
    entries=[
        ('rId1','http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet','worksheets/sheet1.xml'),
        ('rId2','http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet','worksheets/sheet2.xml'),
        ('rId3','http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles','styles.xml'),
        ('rId4','http://schemas.openxmlformats.org/officeDocument/2006/relationships/sheetMetadata','metadata.xml'),
        ('rId5','http://schemas.microsoft.com/office/2023/09/relationships/Python','python.xml'),
    ]
    for i,typ in enumerate((
        ('rdRichValue','http://schemas.microsoft.com/office/2017/06/relationships/rdRichValue','richData/rdrichvalue.xml'),
        ('rdRichValueStructure','http://schemas.microsoft.com/office/2017/06/relationships/rdRichValueStructure','richData/rdrichvaluestructure.xml'),
        ('rdRichValueTypes','http://schemas.microsoft.com/office/2017/06/relationships/rdRichValueTypes','richData/rdRichValueTypes.xml'),
        ('rdSupportingPropertyBag','http://schemas.microsoft.com/office/2017/06/relationships/rdSupportingPropertyBag','richData/rdsupportingpropertybag.xml'),
        ('rdSupportingPropertyBagStructure','http://schemas.microsoft.com/office/2017/06/relationships/rdSupportingPropertyBagStructure','richData/rdsupportingpropertybagstructure.xml'),
        ('richValueRel','http://schemas.microsoft.com/office/2022/10/relationships/richValueRel','richData/richValueRel.xml'),
        ('richStyles','http://schemas.microsoft.com/office/2017/06/relationships/richStyles','richData/richStyles.xml'),
    ),6):
        entries.append(('rId'+str(i),typ[1],typ[2]))
    for ident,kind,target in entries:
        etree.SubElement(wbroot,Q(PKG,'Relationship'),Id=ident,Type=kind,Target=target)
    return xml_bytes(wbroot)


def rich_content_types(original: bytes) -> bytes:
    root=etree.fromstring(original)
    etree.SubElement(root,Q(CT,'Default'),Extension='png',ContentType='image/png')
    for path,kind in (
        ('xl/richData/richValueRel.xml','application/vnd.ms-excel.richvaluerel+xml'),
        ('xl/richData/rdrichvalue.xml','application/vnd.ms-excel.rdrichvalue+xml'),
        ('xl/richData/rdrichvaluestructure.xml','application/vnd.ms-excel.rdrichvaluestructure+xml'),
        ('xl/richData/richStyles.xml','application/vnd.ms-excel.richstyles+xml'),
        ('xl/richData/rdsupportingpropertybagstructure.xml','application/vnd.ms-excel.rdsupportingpropertybagstructure+xml'),
        ('xl/richData/rdsupportingpropertybag.xml','application/vnd.ms-excel.rdsupportingpropertybag+xml'),
        ('xl/richData/rdRichValueTypes.xml','application/vnd.ms-excel.rdrichvaluetypes+xml'),
    ):
        etree.SubElement(root,Q(CT,'Override'),PartName='/'+path,ContentType=kind)
    return xml_bytes(root)


def workbook_calc_features(original: bytes) -> bytes:
    root=etree.fromstring(original)
    cp=root.find(Q(S,'calcPr'))
    if cp is not None:
        cp.attrib.clear()
        cp.set('calcId','191029')
        cp.set('calcMode','auto')
    extlist=etree.SubElement(root,Q(S,'extLst'))
    ext=etree.SubElement(extlist,Q(S,'ext'),uri='{B58B0392-4F1F-4190-BB64-5DF3571DCE5F}')
    f=etree.SubElement(ext,Q(XCALCF,'calcFeatures'))
    for name in ('RD','Single','FV','CNMTM','LET_WF','LAMBDA_WF','ARRAYTEXT_WF'):
        etree.SubElement(f,Q(XCALCF,'feature'),name='microsoft.com:'+name)
    return xml_bytes(root)


def build(csv_file: Path | str, output_file: Path | str, settings: Settings | None = None) -> dict:
    settings = settings if settings is not None else Settings()
    csv_file, output_file = Path(csv_file), Path(output_file)
    if csv_file.resolve() == output_file.resolve():
        raise ValueError("Output XLSX must differ from input CSV")
    data = read_csv(csv_file, settings)
    info = prepare(data, settings)
    files = {
        "[Content_Types].xml": make_content_types(),
        "xl/workbook.xml": make_workbook(),
        "xl/worksheets/sheet1.xml": make_table(data, settings),
        "xl/worksheets/sheet2.xml": make_waffle(data, settings, info),
        "xl/styles.xml": make_styles(),
        "xl/metadata.xml": make_metadata(),
        "xl/python.xml": make_python(),
        **make_relationships(),
        **make_properties(),
    }
    # PY cells and rich cached-result structures must agree. This is essential
    # for Excel to recognize image-producing PY formulas as native Python cells.
    # The Python environment itself uses the Excel-authored compatibility
    # profile above, verified by the user in the controlled A/B/C workbooks.
    files['xl/worksheets/sheet2.xml'], plot_count = patch_python_cells(files['xl/worksheets/sheet2.xml'])
    assert plot_count == info['count'] + info['length']
    files['xl/metadata.xml'] = make_metadata_full(plot_count)
    files.update(make_richparts(plot_count))
    files['xl/_rels/workbook.xml.rels'] = rich_relationships()
    files['[Content_Types].xml'] = rich_content_types(files['[Content_Types].xml'])
    files['xl/workbook.xml'] = workbook_calc_features(files['xl/workbook.xml'])
    output_file.parent.mkdir(parents=True, exist_ok=True)
    # No external workbook content or old data are packaged; the only image is
    # a transparent placeholder that is discarded by Excel when PY recalculates.
    with ZipFile(output_file,"w",compression=ZIP_DEFLATED,compresslevel=6) as archive:
        for name, blob in files.items():
            archive.writestr(name, blob)
    with ZipFile(output_file) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("Generated ZIP/XLSX integrity check failed")
    return {"rows":len(data),"columns":len(data[0]),
            "components":info["count"],"draw_rows":info["length"],
            "python_cells":info["count"]+info["length"]+2,
            "output":str(output_file)}


# Public API names; old stand-alone aliases remain available.
ExcelSettings = Settings
build_excel_workbook = build


def main(argv=None):
    """Command-line workbook generator; detailed styles use ExcelSettings."""
    from dataclasses import replace

    parser = argparse.ArgumentParser(description=
        "Generate an English Python in Excel waffle workbook from a CSV, "
        "without an XLSX template.")
    parser.add_argument("csv", type=Path,
                        help="Input CSV; all its columns are copied to the table sheet")
    parser.add_argument("-o", "--output", type=Path,
                        default=Path("compwaffle_output.xlsx"))
    parser.add_argument("--composition-range",
                        help="CSV range to visualize, e.g. B2:H or B2:Q257")
    parser.add_argument("--sample-id-column",
                        help="Sample ID column letter, e.g. A; use '-' for sequential IDs")
    parser.add_argument("--evaluation-columns",
                        help="Comma-separated metric column letters, e.g. I,J,K; use '-' for none")
    parser.add_argument("--header-row", type=int,
                        help="CSV header row number (default: 1); use 0 for no header")
    parser.add_argument("--csv-encoding", help="Input CSV encoding (default: auto)")
    parser.add_argument("--csv-delimiter", help="CSV separator (default: comma)")
    args = parser.parse_args(argv)

    overrides = {}
    if args.composition_range is not None:
        overrides["composition_range"] = args.composition_range
    if args.sample_id_column is not None:
        overrides["sample_id_column"] = (None if args.sample_id_column == "-"
                                          else args.sample_id_column)
    if args.evaluation_columns is not None:
        overrides["evaluation_columns"] = (
            () if args.evaluation_columns in ("", "-") else
            tuple(item.strip() for item in args.evaluation_columns.split(","))
        )
    if args.header_row is not None:
        overrides["header_row"] = args.header_row or None
    if args.csv_encoding is not None:
        overrides["csv_encoding"] = args.csv_encoding
    if args.csv_delimiter is not None:
        overrides["csv_delimiter"] = args.csv_delimiter
    config = replace(Settings(), **overrides)
    try:
        result = build(args.csv, args.output, config)
    except (ValueError, FileNotFoundError, UnicodeError) as exc:
        parser.error(str(exc))
    print(f"Workbook: {result['output']}")
    print(f"CSV: {result['rows']} rows, {result['columns']} columns")
    print(f"Visualization: {result['draw_rows']} rows, {result['components']} components")
    print(f"Native PY cells: {result['python_cells']}")
    print("Note: supported Microsoft 365 Excel calculates the PY plots; "
          "the local builder does not execute them.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
