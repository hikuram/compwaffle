"""UCI Concrete Slump Test: ingredient waffles and measured property columns.

Run:
    python examples/concrete_slump.py
    python examples/concrete_slump.py --output-dir docs/images

This uses 7 input ingredients in kg/m3; SLUMP/FLOW/strength are measured
properties and must never become parts of the composition.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from compwaffle import waffle_table, parts_per_reference, WaffleStyle

INPUTS = ("Cement", "Slag", "Fly ash", "Water", "SP", "Coarse Aggr.", "Fine Aggr.")
PROPS = ("SLUMP(cm)", "FLOW(cm)", "Compressive Strength (28-day)(Mpa)")
COLORS = {
    "Cement": "#457FBC",
    "Slag": "#56A99E",
    "Fly ash": "#9AC7B0",
    "Water": "#83B6E0",
    "SP": "#E3A34A",
    "Coarse Aggr.": "#64748B",
    "Fine Aggr.": "#BBC4CF",
}


def records_from_csv(csv_path: Path, indices: tuple[int, ...]) -> list[dict]:
    df = pd.read_csv(csv_path)
    selected = df[df["No"].isin(indices)].sort_values("No")
    records = []
    for _, row in selected.iterrows():
        composition = {name: float(row[name]) for name in INPUTS}
        record = {
            "label": f"No. {int(row['No']):03d}",
            "composition": composition,
            "comment": f"W/C = {composition['Water']/composition['Cement']:.2f}",
            **{name: float(row[name]) for name in PROPS},
        }
        records.append(record)
    if not records:
        raise ValueError("no data matched the selected indices")
    return records


def plot_variants(records: list[dict], outdir: Path) -> None:
    outdir.mkdir(exist_ok=True, parents=True)
    kwargs = dict(
        properties=PROPS,
        property_labels={PROPS[0]: "Slump (cm)", PROPS[1]: "Flow (cm)",
                         PROPS[2]: "28-day MPa"},
        property_formats={PROPS[0]: ".1f", PROPS[1]: ".1f", PROPS[2]: ".2f"},
        style=WaffleStyle.preset("rounded"), colors=COLORS,
        show_legend=True, show_scale=True,
    )
    fig, _ = waffle_table(
        records, mode="percent", columns=20,
        title="Concrete compositions | 100% normalized (20 cells)", **kwargs,
    )
    fig.savefig(outdir / "concrete_percent.png", dpi=190)
    fig.savefig(outdir / "concrete_percent.svg")
    plt.close(fig)

    as_single_reference = [
        {**record,
         "composition": parts_per_reference(record["composition"], "Cement")}
        for record in records
    ]
    fig, _ = waffle_table(
        as_single_reference, mode="absolute", columns="auto",
        value_per_cell=50, unit="parts",
        title="Concrete compositions | 100 parts of cement as reference (50 / cell)",
        **kwargs,
    )
    fig.savefig(outdir / "concrete_reference_single.png", dpi=190)
    fig.savefig(outdir / "concrete_reference_single.svg")
    plt.close(fig)

    reference_group = ("Cement", "Slag", "Fly ash")
    as_group_reference = [
        {**record,
         "composition": parts_per_reference(record["composition"], reference_group)}
        for record in records
    ]
    fig, _ = waffle_table(
        as_group_reference, mode="absolute", columns="auto",
        value_per_cell=25, unit="parts",
        title="Concrete compositions | 100 parts of selected constituents (25 / cell)",
        **kwargs,
    )
    fig.savefig(outdir / "concrete_reference_group.png", dpi=190)
    fig.savefig(outdir / "concrete_reference_group.svg")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "out")
    args = parser.parse_args()
    plt.rcParams["font.family"] = "DejaVu Sans"
    data = Path(__file__).parent / "data" / "slump_test.csv"
    records = records_from_csv(data, (1, 2, 5, 8, 14, 15, 43, 60))
    plot_variants(records, args.output_dir)
    print("Wrote 3 PNG and 3 SVG graphics to", args.output_dir)

if __name__ == "__main__":
    main()
