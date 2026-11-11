# Python in Excel examples

The recommended v0.1.3 path uses the **template-free CSV workbook generator**
(`compwaffle.excel`); no manual PY-cell copying is necessary.

```bash
pip install 'compwaffle[excel]'
compwaffle-excel examples/python_in_excel/example_generic_7.csv -o output.xlsx
python examples/python_in_excel/build_from_csv.py
```

- `example_generic_7.csv`: 7 generic components, 5 data rows, 3 property columns.
- `example_capacity_16x256.csv`: 16 generic components and 256 data rows.
- `build_from_csv.py`: editable Python example with explicit component range,
  metric columns and appearance options.
- `engine_part1.py`, `engine_part2.py`, `row_example.py.txt`, and
  `swatch_example.py.txt`: **legacy manual Python in Excel setup**. They remain
  available for users who prefer building a workbook themselves, but are not
  needed for v0.1.3's automatic generator.

Generated workbooks require a supported Microsoft 365 Python in Excel session
to recalculate the embedded plots. The generator builds but does not execute
Python cloud formulas. See [`docs/EXCEL.md`](../../docs/EXCEL.md).

For everyday spreadsheet work, treat the generated workbook as a rendering
workspace. Copy completed waffle images back to the original spreadsheet
rather than copying live PY formulas. See the [recalculation and static-image
workflow](../../docs/EXCEL.md#recalculation-and-transferring-finished-charts).
