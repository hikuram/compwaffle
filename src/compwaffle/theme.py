"""Small bridge from ordinary Matplotlib rcParams to UI ink/backgrounds."""
from __future__ import annotations
from dataclasses import replace
import matplotlib as mpl
from .geometry import WaffleStyle


def is_dark() -> bool:
    r, g, b = mpl.colors.to_rgb(mpl.rcParams['figure.facecolor'])
    # Perceptual sRGB lightness is sufficient for theme selection here.
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) < 0.46


def ui_ink() -> dict[str, str]:
    if is_dark():
        return {
            'primary': '#EAF0F8', 'secondary': '#BDCADB',
            'muted': '#A4B2C6', 'rule': '#526075',
            'subtle_rule': '#364457', 'stripe': '#202A3A',
        }
    return {
        'primary': '#20344E', 'secondary': '#526174',
        'muted': '#596779', 'rule': '#CAD4E0',
        'subtle_rule': '#E2E8F0', 'stripe': '#F6F8FB',
    }


def adapt_cell_style(style: WaffleStyle) -> WaffleStyle:
    """Respect custom colors, but make the default empty-cell theme legible."""
    if not is_dark():
        return style
    default = WaffleStyle()
    replacements = {}
    if style.empty_color == default.empty_color:
        replacements['empty_color'] = '#2B3649'
    if style.edgecolor == default.edgecolor:
        replacements['edgecolor'] = '#17202E'
    # Hatch ink derives from each cell's fill color, regardless of the theme.
    return replace(style, **replacements) if replacements else style
