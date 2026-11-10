"""Generic color/shape/hatch demonstration with synthetic category values."""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from compwaffle import CornerShape, WaffleStyle, build_layout, draw_waffle, waffle_table

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"
OUT.mkdir(parents=True, exist_ok=True)

CATEGORIES = ("Category A", "Category B", "Category C", "Category D", "Category E")
rows = ((50, 20, 15, 10, 5), (40, 25, 10, 15, 10),
        (36, 27.5, 12.5, 19, 5), (45, 22, 18, 8, 7))
records = [
    {"label": str(i+1).zfill(2), "composition": dict(zip(CATEGORIES, values)),
     "comment": ("Reference", "Variant 1", "Variant 2", "Variant 3")[i],
     "metric_a": (11.2, 13.4, 12.5, 13.0)[i],
     "metric_b": (167, 170, 169, 171)[i]}
    for i, values in enumerate(rows)
]
shapes = dict(zip(CATEGORIES, (CornerShape(.10, +.55), CornerShape(.10, -.80),
                               CornerShape(.10, 0.00), CornerShape(.10, +.9),
                               CornerShape(.10, -.35))))
hatches = dict(zip(CATEGORIES, (None, "//", "..", "xx", "||")))
color_style = WaffleStyle(
    corner_span=.10, corner_bend=.55,
    color_map=dict(zip(CATEGORIES, ("#619BCE", "#78A68C", "#DCAA62", "#9A89B8", "#58697F"))),
    shape_map=shapes, hatch_map=hatches,
)
gray_style = WaffleStyle(
    corner_span=.10, corner_bend=.55,
    color_map=dict(zip(CATEGORIES, ("#F2F2F2", "#D8D8D8", "#BFBFBF", "#A0A0A0", "#818181"))),
    shape_map=shapes, hatch_map=hatches, edgecolor="#606060",
    hatch_color="#303030",  # explicitly shared hatch ink for grayscale
)
for name, style in (("shape_color_preview", color_style), ("shape_grayscale_preview", gray_style)):
    with plt.rc_context({"figure.facecolor": "#FFFFFF", "axes.facecolor": "#FFFFFF",
                         "savefig.facecolor": "#FFFFFF", "font.size": 10}):
        fig, ax = waffle_table(
            records, properties=("metric_a", "metric_b"),
            property_labels={"metric_a": "Metric A", "metric_b": "Metric B"},
            property_formats={"metric_a": ".1f", "metric_b": ".0f"},
            show_scale=True, show_stripes=False,
            title="Composition comparison | color / shape / hatch" if "color" in name
                  else "Composition comparison | grayscale", style=style,
        )
        fig.savefig(OUT / f"{name}.png", dpi=180, bbox_inches="tight", pad_inches=.13)
        fig.savefig(OUT / f"{name}.svg", bbox_inches="tight", pad_inches=.13)
        plt.close(fig)

with plt.rc_context({"figure.facecolor": "white", "axes.facecolor": "white"}):
    fig, ax = plt.subplots(figsize=(9, 3.5))
    for i, bend in enumerate((-1., -.8, -.35, 0, .55, .9, 1.)):
        draw_waffle(ax, build_layout({"Category A": 100}, columns=1),
                    {"Category A": "#78A68C"}, x=i*1.5, y=1.2, scale=1.,
                    style=WaffleStyle(corner_span=.15, corner_bend=bend))
        ax.text(i*1.5+.5, .92, f"{bend:+.2f}", ha="center", va="center", fontsize=10)
    ax.set_xlim(-.3, 10.6)
    ax.set_ylim(.5, 2.4)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(OUT / "corner_bend_gallery.png", dpi=180)
    plt.close(fig)
print("Saved public preview images to", OUT)
