# Publishing a GitHub source release (v0.1.3)

This repository is ready for review as **compwaffle v0.1.3**. Creating archives
or testing builds does **not** itself publish them to GitHub or PyPI.

1. Review `README.md`, `docs/EXCEL.md`, `LICENSE`, and
   `examples/data/README.md` (MIT library versus CC BY 4.0 dataset).
2. Run `python -m pip install -e '.[dev,excel]'`, `python -m pytest -q`,
   and `python examples/python_in_excel/build_from_csv.py`.
3. Confirm a generated sample recalculates in supported Microsoft 365 Excel.
4. Publish through the existing repository (do not recreate it):

```bash
git add .
git commit -m "Release compwaffle v0.1.3"
git tag v0.1.3
git push origin main
git push origin v0.1.3
gh release create v0.1.3 --title "compwaffle v0.1.3 — Python in Excel CSV Builder" \
  --notes "Adds a template-free CSV-to-XLSX builder (1–16 components, up to 256 plotted compositions), with an English workbook interface and a tested Excel Python environment profile. The core Matplotlib API remains compatible with v0.1.2."
```

If your release branch is not `main`, change the push command accordingly.
PyPI publication is optional and separate. Excel's Python execution is
Microsoft 365 cloud-hosted; generation and structural tests do not replace
an Excel runtime compatibility check.
