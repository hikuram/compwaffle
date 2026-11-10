"""Category-stable colors for individual waffles and comparison tables."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
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


def shift_tone(color: object, shift: float) -> tuple[float, float, float, float]:
    """Move RGB channels toward black (-100) or white (+100).

    This is an RGB shade/tint adjustment, not a perceptual luminance change.
    Alpha is kept unchanged.  At zero, the input color is returned as RGBA.
    """
    if not math.isfinite(shift) or not -100 <= shift <= 100:
        raise ValueError("hatch_tone_shift must be finite and in [-100, 100]")
    r, g, b, alpha = mpl.colors.to_rgba(color)
    fraction = shift / 100.0
    if fraction < 0:
        factor = 1 + fraction
        return (r * factor, g * factor, b * factor, alpha)
    return (r + (1 - r) * fraction,
            g + (1 - g) * fraction,
            b + (1 - b) * fraction, alpha)
