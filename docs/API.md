# API reference (v0.1.1)

## `build_layout(data, *, mode='percent', rows=1, columns=20, value_per_cell=None, unit=None, order='row', max_cells=5000)`

Numerical layout generator. No dependency on Matplotlib or pandas. Values must be a nonempty mapping from nonempty component names to finite, nonnegative values; the total must be positive.

- **`mode='percent'`**: normalize total to 100; `rows*columns` cells fill exactly 100. `value_per_cell` is inferred as `100/(rows*columns)` and must not be explicitly specified. `columns` must be an integer.
- **`mode='absolute'`**: keep the original values. Specify a strictly positive `value_per_cell`. Use `columns='auto'` for a variable-length grid or set a fixed column count that has sufficient capacity. Empty cells remain visible when fixed capacity is greater than the actual total.
- **`order='row'`** fills rows from left to right, top to bottom. **`order='column'`** fills columns from top to bottom, left to right.
- **`max_cells`** limits accidental allocation of extremely large grids.

Returns a `WaffleLayout` with `fills`, `source_total`, `displayed_total`, `capacity`, `count`, `rows`, `columns`, and `value_per_cell`. Each `CellFill` has `key`, `index`, `row`, `column`, `start` and `end` (normalized 0–1 inside one cell). Multiple `CellFill` entries may share the same cell.

## `WaffleStyle`

```python
WaffleStyle(
    cell_width=1.0, cell_height=0.78,
    gap_x=0.12, gap_y=0.18,
    corner_radius=0.14,  # backwards compatible raw cell units
    corner_span=None,    # if set, fraction of short side; overrides corner_radius
    corner_bend=0.55228475,   # -1 to +1; negative = concave
    color_map=None,     # category: color
    shape_map=None,     # category: (span, bend) or CornerShape(...)
    hatch_map=None,     # category: Matplotlib hatch string or None
    hatch_color="#263445",
    edgecolor="white", linewidth=0.55,
    empty_color="#EDF1F5",
)
```

Numeric geometry is **relative cell units**. In `draw_waffle()`, the `scale` multiplier converts them to an axes' data units. `linewidth` is in Matplotlib points. `corner_radius` is capped at half the smaller cell dimension. Presets are `WaffleStyle.preset('rounded'|'square'|'compact'|'pill')`.

## `CornerShape(span=0.15, bend=0.55228475)` and `cell_path(left, bottom, width, height, shape)`

- `span`: 0..0.5 of the **shorter side** of the cell (not absolute units).
- `bend`: -1..+1; negative = inward recess, zero = chamfer, positive = rounded/outward. A cubic Bezier approximation to a quarter circle uses `0.55228475`.
- All four corner curves are enclosed in squares of side `span * min(width, height)`. The straight central portions of each cell edge are unchanged; geometry is continuous. Negative bends deliberately join straight edges at an angle.
- The corner treatment changes area modestly, not exactly area-preservingly. Keep `span` small when area matching matters (e.g. <=0.10).

`cell_path` provides the generated closed `matplotlib.path.Path`, suitable for downstream `PathPatch` clipping. `WaffleStyle.shape_map` may use `CornerShape` objects or `(span, bend)` tuples. For a fully occupied single-category cell the per-category shape applies; mixed or partially filled cells use the common default shape.

`WaffleStyle.color_map`, `.shape_map`, and `.hatch_map` are **independent**. `colors=` at the plotting-function level overrides `color_map` only. `hatch_map` accepts Matplotlib hatch strings such as `/`, `..`, `x`, `||` or `None`. Hatch colors can be set globally with `WaffleStyle.hatch_color`, including in grayscale mode. The legend reflects all three encodings.

## `draw_waffle(ax, layout, palette, *, x=0, y=0, scale=1, style=None)`

Low-level in-axes patch renderer. Adds Matplotlib artists without configuring axes limits or aspect ratio. Coordinates `x, y` are the bottom-left origin of the waffle. Set axes aspect ratio appropriately, for example `ax.set_aspect('equal')`, to preserve physical roundness. Returns a list of patches. If embedding in subplots, users are responsible for layout and axes limits.

## `waffle(data, *, ax=None, mode='percent', rows=1, columns=20, value_per_cell=None, unit=None, order='row', style=None, cell_scale=None, cmap='tab20', colors=None, title=None, show_title=True, comment=None, show_comment=True, show_legend=True, show_scale=False, scale_interval=None, show_labels=False, font_size=10)`

High-level standalone function. Returns `(figure, axes)`; `ax` may be supplied, but it will be cleared and configured. If the plot is being embedded into a complex figure that must retain its existing axes limits, use `draw_waffle` instead.

**Numeric scale requires `rows=1`**; enabling it for multirow charts raises an error. Physical placement is managed in inches for standalone figures so that cell dimensions remain stable. `cell_scale` controls inches per one relative geometry unit (e.g. `cell_scale=.25`, `cell_width=1` gives a 0.25-inch cell). `colors={component: '#rrggbb'}` overrides the named Matplotlib `cmap`; colors are shared across every row in `waffle_table`.

## `parts_per_reference(data, reference, *, basis=100)`

Converts consistent input masses into parts per a named reference. `reference` can be a single component name (`'Cement'`) or a sequence (`('Cement','Slag','Fly ash')`). The denominator is the sum of the specified components, which must be positive. The default basis is 100, but other positive bases are supported. **No automatic normalisation to 100% is performed.**

## `mass_to_volume_parts(data, densities)`

Returns `mass/density` for each component. All density values must be supplied in units consistent with the input mass units. For normalized volume fractions, pass the result to `build_layout(..., mode='percent')` or `waffle(..., mode='percent')`.

## `waffle_table(records, ..., properties=(), mode='percent', columns=20, show_scale=True, show_stripes=True, stripe_color=None)`

Experimental comparison table. `records` can be an iterable (sequence) of mappings or a pandas DataFrame. A record contains a composition mapping under the key `composition`, a display label under `label`, an optional `comment`, and arbitrary property columns. Other field names can be selected by `composition=`, `label=`, and `comment=`.

- `properties`: property column keys.
- `property_labels`: mapping from property keys to column headings.
- `property_formats`: mapping from property keys to Python `format()` specs (e.g. `.2f`).
- `columns='auto'` with `mode='absolute'` produces aligned variable-length rows at one scale; no normalization is introduced.
- Numeric scale and notes are shared globally; numeric scales are limited to one-row charts.
- `show_stripes=False` disables alternating row backgrounds. `stripe_color` customizes their color. These are table-specific options, not Matplotlib rcParams.
- Column widths are fixed; long header/property text may overflow. Keep headings short.

## Matplotlib `mplstyle`

`.mplstyle` can set only standard Matplotlib `rcParams`, e.g. fonts, face colors, figure DPI, vector-font handling. It cannot configure `WaffleStyle`'s `corner_radius` and `gap_x` because those are custom library options. Use a `WaffleStyle` object or a preset for cell geometry.
