# Changelog

## v0.1.2 — Hatch tone adjustment

- Hatch ink now defaults to a per-category RGB shade derived from the resolved fill color.
- Added `WaffleStyle.hatch_tone_shift` (-100 to +100, default -30) with `hatch_color` as an explicit shared-color override.
- Applied the same logic to chart segments, legends, tables and the Python in Excel inline engine (`K13`).
- Older 11-value Python in Excel options still use the new -30 default.

## v0.1.1 — Initial public release

- Rounded waffle charts using clipped fractional fills and cubic-Bézier `PathPatch` outlines.
- Normalized percentages, absolute quantities, variable-length grids, and arbitrary reference-part conversions.
- Signed corner bends, independent color/shape/hatch maps, grayscale-friendly rendering and legend swatches.
- Configurable dimensions, gaps, styles, titles, comments, labels, and one-row scales.
- Experimental `waffle_table()` with aligned notes, metrics, and optional row stripes.
- Matplotlib style sheets; SVG, PDF, and PNG output.
- Unit tests, a CC BY 4.0 public-data example, and Python in Excel setup notes.
