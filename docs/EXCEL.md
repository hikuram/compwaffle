# Python in Excel: CSV workbook builder

`compwaffle` v0.1.3 can produce a **ready-to-recalculate Python in Excel workbook** from any CSV whose component columns and drawing range you specify. No XLSX template, Office automation, or local Excel installation is required to **generate** the workbook. The output is English-first and has two worksheets:

- **`table`**: every CSV row and column, in original order. Excel-compatible numeric values become numbers; identifiers with leading zeros stay text. CSV headers and user data are not translated.
- **`waffle`**: editable global settings, up to 16 per-component colors/shapes/hatches, legend, and one Python plot per selected data row (up to 256). Selected evaluation columns are linked as ordinary worksheet cells.

The workbook embeds a Matplotlib drawing engine adapted from compwaffle; **Excel does not need to import the compwaffle package**. The local generator requires `lxml`, while the Python plots run in Microsoft 365's Python in Excel service (NumPy and Matplotlib are available in that environment).

## Installation

```bash
python -m pip install 'compwaffle[excel]'
```

This adds `lxml` for the workbook generator. The ordinary Matplotlib charting functions of compwaffle are unchanged.

## CLI

For the included generic 7-component example:

```bash
compwaffle-excel examples/python_in_excel/example_generic_7.csv -o waffle.xlsx
```

For a CSV with 16 component columns and 256 compositions:

```bash
compwaffle-excel examples/python_in_excel/example_capacity_16x256.csv \
  -o waffle_16.xlsx \
  --composition-range B2:Q257 \
  --evaluation-columns R,S,T
```

To disable metric columns, pass `--evaluation-columns -`; to number plots sequentially instead of copying sample IDs, pass `--sample-id-column -`. The default component range is `B2:H` and the default metric columns are `I,J,K`. Use `compwaffle-excel --help` for CSV encoding, delimiter and header options.

## Python API / editable settings

For full control of colors, hatches, corner geometry, reference weights, and global options, set up a short Python script. Do **not** edit code installed inside `site-packages`.

```python
from dataclasses import replace
from compwaffle.excel import ExcelSettings, build_excel_workbook

settings = replace(
    ExcelSettings(),
    composition_range='B2:Q257',
    sample_id_column='A',
    evaluation_columns=('R', 'S', 'T'),
    fill_colors=('#4477AA', '#66A6A0', '#DDAA55', '#88B4D8') * 4,
    hatches=('//', '..', '', '/') * 4,
    options={**ExcelSettings().options, 'hatch_tone_shift': -30},
)
result = build_excel_workbook('data.csv', 'waffle.xlsx', settings)
print(result)
```

An editable version is included at [`examples/python_in_excel/build_from_csv.py`](../examples/python_in_excel/build_from_csv.py). These columns and settings refer to the copied `table` worksheet. `composition_range` may omit the final row (`B2:H`) to include all subsequent data rows; `B2:H257` includes exactly 256 rows.

## Worksheet layout

| Range | Contents |
| --- | --- |
| `waffle!B3` and `B17` | Embedded Python engine / draw-function definitions |
| `waffle!B4:B15` | 12 global drawing options, including `hatch_tone_shift` |
| `waffle!B20:Q28` | Up to 16 component names, colors, corner shapes, hatches, and reference weights |
| `waffle!B33:Q33` | Python-generated legend swatches |
| `waffle!A36` onward | Sample IDs, row plots, selected metric columns |
| `table!A1` onward | Imported CSV data |

`hatch_tone_shift=-30` shades hatch ink 30% toward black relative to its fill color. Allowed values are -100 (black) through +100 (white); this is an RGB interpolation, not perceptual lightness. Changing the value in the worksheet requires Python in Excel recalculation.

For readability, the setting hints in column D do not wrap, and component
settings and legend cells (columns B onward within their sections) are
right-aligned in generated workbooks.

The builder currently supports **1–16 contiguous composition columns** and **1–256 selected data rows**. Source CSV sheets can contain other columns and additional rows. Each selected component must contain a finite, nonnegative number and each composition must have a positive total.

## Recalculation and transferring finished charts

The generated `waffle` sheet is a **rendering workspace**, not the recommended
location for day-to-day formulation management. Python in Excel recalculates
its PY cells sequentially when inputs they depend on change. A workbook with
many charts can therefore feel slow during further editing.

A practical workflow is:

1. Keep the original formulation workbook as the working source of truth.
2. Generate a compwaffle workbook from an exported CSV, then finish the
   component/plot settings and allow the PY figures to calculate.
3. Copy **only the finished visualizations** back to the original workbook as
   static output. In Excel, choose **Python Output → Excel Value** for an
   in-cell plot before trying **Paste Special → Values** at the destination.
   Confirm that the pasted cell is an image and not a formula containing `PY`.
   If a given Excel version does not retain the picture when pasting values,
   use **Copy as Picture / Paste as Picture** instead, which creates a static
   picture over cells; arrange it to suit the destination layout.
4. Continue editing the original workbook; regenerate the static figures when
   the underlying compositions actually change.

If the user has a **Python in Excel add-on license**, Excel's
**Formulas → Calculation Options** may offer **Partial** or **Manual** mode
(`F9` to recalculate when ready). Standard Python in Excel availability supports
**Automatic** mode, so the builder intentionally leaves `calcMode=auto`
instead of forcing a setting that some users cannot use. Excel desktop
calculation settings can affect other open workbooks, so check the setting
before changing it.

References: [Microsoft — Recalculation](https://support.microsoft.com/en-us/excel/python/get-started-with-python-in-excel),
[Python in Excel availability](https://support.microsoft.com/en-us/excel/python/python-in-excel-availability), and
[Create plots and charts](https://support.microsoft.com/en-us/excel/python/create-plots-and-charts-with-python-in-excel).

## Excel compatibility and privacy

The generated workbook contains native PY cells, `xl/python.xml`, and the rich-value structures used for Python figure outputs. It pins the Python environment definition observed in **multiple Excel-created workbooks**:

`{882DD1B0-6546-4DFA-8A08-902A380B44EA}`

This is an **environment compatibility identifier, not a secret or user credential**. On the tested Microsoft 365 installation, arbitrary UUID v4 substitutions produced `#BLOCKED!`; restoring this Excel-authored environment definition was necessary to execute the charts. The resulting structure was tested in a small workbook. **Microsoft has not promised that this environment ID will remain usable across every tenant, release channel, or future version.** Using this identifier does not bypass licensing, access permissions, connected-service settings, or security policies. The optional initialization code is the standard Excel Python startup configuration, not account-specific data.

Generated workbooks should be opened in a **supported Microsoft 365 Excel version with Python in Excel enabled** and recalculated there. The generator itself cannot execute those cloud formulas, and a syntactically valid XLSX is not proof that Python will run on every installation. Files downloaded from the internet may open in Protected View and be unable to recalculate until trusted through normal Excel controls.

**Data handling:** Microsoft 365 sends Python source code and referenced numeric inputs to its cloud Python execution service when recalculated. For confidential data that cannot be processed by that service, use the ordinary local Matplotlib API instead. The generator copies the entire CSV into the workbook but Python `xl()` references are restricted to numerical component and style settings. This does not mean the workbook is free of potentially sensitive data; evaluate the complete CSV before sharing it.

Avoid opening and **resaving** these PY-enabled workbooks with `openpyxl`, LibreOffice, or other generic XLSX writers: they may remove or rewrite Python-specific parts. `openpyxl` read-only inspection is useful, but this generator builds the OOXML package directly with `lxml` to preserve the required structure.

## Troubleshooting

- **`#BLOCKED!` / unsupported Python environment:** verify Excel can run a newly created Python cell, then compare the generated workbook. Check organization security settings, Protected View, and Python availability. Do not replace the fixed environment GUID with a random UUID.
- **Wrong components/metrics:** inspect `composition_range`, `sample_id_column`, `evaluation_columns`, and the original CSV headers.
- **Nothing drawn:** ensure all selected data are nonnegative numbers and selected rows have a positive total.
- **Visual changes do not appear:** recalculate the Python cells in a Python-enabled Excel session; local generation only prepares the workbook.

See [Microsoft's Python in Excel troubleshooting](https://support.microsoft.com/en-us/excel/python/troubleshoot-python-in-excel-errors) and the [OOXML Python environment specification](https://learn.microsoft.com/en-us/openspecs/office_standards/ms-xlsx/1c0b3d12-5f97-46c2-a8e2-5a2e4171df63).
