"""Minimal normalized and absolute waffle charts with generic values."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from compwaffle import waffle

out = Path(__file__).resolve().parent / "out"
out.mkdir(exist_ok=True)
amounts = {"Category A": 100, "Category B": 20, "Category C": 2.5}
colors = {"Category A": "#4582BA", "Category B": "#D59A40", "Category C": "#536579"}
for name, kwargs in (("percent", dict(mode="percent", columns=20)),
                     ("absolute", dict(mode="absolute", columns="auto",
                                       value_per_cell=5, unit="parts"))):
    fig, ax = waffle(amounts, colors=colors, show_scale=True,
                     title=f"Composition | {name}", **kwargs)
    fig.savefig(out / f"basic_{name}.svg")
    plt.close(fig)
print("Saved examples to", out)
