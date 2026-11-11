"""compwaffle: rounded, continuous waffle charts for compositions."""
from .core import CellFill, WaffleLayout, build_layout
from .geometry import CornerShape, WaffleStyle, cell_path, draw_waffle
from .transforms import parts_per_reference, mass_to_volume_parts
from .plotting import waffle
from .table import waffle_table

__version__ = "0.1.3"
__all__ = [
    "CellFill", "WaffleLayout", "WaffleStyle", "CornerShape", "cell_path", "build_layout",
    "draw_waffle", "parts_per_reference", "mass_to_volume_parts",
    "waffle", "waffle_table",
]
