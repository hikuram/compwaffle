# Changelog

## v0.1.3 — Python in Excel CSV workbook builder

- Integrated the template-free, English-first CSV-to-XLSX generator as
  `compwaffle.excel` with `ExcelSettings`, `build_excel_workbook`, and the
  `compwaffle-excel` command-line entry point.
- Added optional `lxml` dependency via `pip install 'compwaffle[excel]'`.
  The core Matplotlib library and its public drawing API remain compatible.
- Embedded a self-contained PY plotting engine with an Excel-authored Python
  environment compatibility identifier and standard initialization code.
  No source XLSX template or local import of compwaffle into Excel is required.
- Supports 1–16 selected component columns and 1–256 selected data rows, with
  user-selected sample IDs, evaluation columns, component styles, and hatch
  tone shift. All CSV data are copied to a `table` worksheet.
- Included generic CSV examples, a Python configuration script, regression
  tests, and updated documentation of Python in Excel limitations/privacy.
- Improved generated workbook readability: non-wrapping setting hints in
  column D and right-aligned component settings/legend in columns B onward.
- Documented the recommended static-chart transfer workflow to avoid
  unneeded Python in Excel recalculation during routine spreadsheet edits.
- The PY workbook generator is based on a compatibility profile validated in
  Microsoft 365 Excel for a small diagnostic workbook. Other Excel builds or
  tenants have not been independently verified.

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
