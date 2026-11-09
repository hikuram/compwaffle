from pathlib import Path
import csv
import pytest
from compwaffle import parts_per_reference, build_layout

PATH = Path(__file__).resolve().parents[1] / "examples/data/slump_test.csv"
INGREDIENTS = ("Cement", "Slag", "Fly ash", "Water", "SP", "Coarse Aggr.", "Fine Aggr.")


def test_uci_concrete_dataset_all_103_samples():
    with PATH.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 103
    for raw in rows:
        values = {name: float(raw[name]) for name in INGREDIENTS}
        pct = build_layout(values, rows=1, columns=20)
        assert pct.capacity == 100
        assert pct.displayed_total == 100
        cement = parts_per_reference(values, "Cement")
        layout = build_layout(cement, mode="absolute", columns="auto",
                              value_per_cell=50, unit="parts")
        assert layout.capacity >= layout.displayed_total - 1e-8
        assert cement["Cement"] == pytest.approx(100)
        binder = parts_per_reference(values, INGREDIENTS[:3])
        assert sum(binder[k] for k in INGREDIENTS[:3]) == pytest.approx(100)
