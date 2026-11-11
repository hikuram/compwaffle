"""Editable CSV to Python in Excel example (compwaffle v0.1.3).

Run from the repository root:
    python examples/python_in_excel/build_from_csv.py

Change INPUT_CSV, OUTPUT_XLSX and settings below for your own CSV.
"""
from dataclasses import replace
from pathlib import Path

from compwaffle.excel import ExcelSettings, build_excel_workbook

DATA_DIR = Path(__file__).resolve().parent
INPUT_CSV = DATA_DIR / 'example_generic_7.csv'
OUTPUT_XLSX = DATA_DIR / 'output_waffle.xlsx'

# Ranges refer to the CSV copied into the 'table' sheet.
BASE = ExcelSettings()
SETTINGS = replace(
    BASE,
    composition_range='B2:H',
    sample_id_column='A',
    evaluation_columns=('I', 'J', 'K'),
    # Configure one style per component, in composition-column order.
    fill_colors=BASE.fill_colors,
    hatches=BASE.hatches,
    corner_spans=None,
    corner_bends=None,
    reference_weights=None,
    options={**BASE.options, 'hatch_tone_shift': -30},
)

if __name__ == '__main__':
    print(build_excel_workbook(INPUT_CSV, OUTPUT_XLSX, SETTINGS))
