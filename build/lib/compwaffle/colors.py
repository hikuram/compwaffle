"""Category-stable colors for individual waffles and comparison tables."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import matplotlib as mpl


def resolve_colors(
    categories: Sequence[str], *,
    cmap: str = "tab20",
    colors: Mapping[str, str] | None = None,
) -> dict[str, tuple[float, float, float, float]]:
    """Map each category to an RGBA color; preserve category order."""
    cmap_obj = mpl.colormaps.get_cmap(cmap)
    unique = list(dict.fromkeys(categories))
    result = {}
    for i, cat in enumerate(unique):
        if colors is not None and cat in colors:
            result[cat] = mpl.colors.to_rgba(colors[cat])
        elif hasattr(cmap_obj, "colors"):
            color_list = cmap_obj.colors
            result[cat] = mpl.colors.to_rgba(color_list[i % len(color_list)])
        else:
            result[cat] = cmap_obj(i / max(1, len(unique) - 1))
    return result
