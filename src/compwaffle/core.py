"""Pure geometry/data model for continuous, fractional-cell waffle charts.

This module intentionally has no matplotlib or pandas dependency.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping


@dataclass(frozen=True)
class CellFill:
    """Portion of a cell, measured left-to-right as fractions of cell width."""

    key: str
    index: int
    row: int
    column: int
    start: float
    end: float

    @property
    def fraction(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class WaffleLayout:
    """Numerical waffle layout independent of any rendering backend."""

    values: tuple[tuple[str, float], ...]
    fills: tuple[CellFill, ...]
    mode: str
    unit: str
    rows: int
    columns: int
    order: str
    value_per_cell: float
    source_total: float
    displayed_total: float

    @property
    def capacity(self) -> float:
        return self.rows * self.columns * self.value_per_cell

    @property
    def count(self) -> int:
        return self.rows * self.columns

    def fills_in_cell(self, index: int) -> tuple[CellFill, ...]:
        return tuple(f for f in self.fills if f.index == index)


def _positive_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _values(data: Mapping[str, float]) -> tuple[tuple[str, float], ...]:
    if not isinstance(data, Mapping) or not data:
        raise ValueError("data must be a non-empty mapping of names to values")
    result: list[tuple[str, float]] = []
    for key, number in data.items():
        if not isinstance(key, str) or not key:
            raise ValueError("all component names must be nonempty strings")
        try:
            num = float(number)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid value for {key!r}") from exc
        if not math.isfinite(num) or num < 0:
            raise ValueError(f"{key!r} must be finite and nonnegative")
        result.append((key, num))
    if not any(value > 0 for _, value in result):
        raise ValueError("composition total must be positive")
    return tuple(result)


def build_layout(
    data: Mapping[str, float],
    *,
    mode: str = "percent",
    rows: int = 1,
    columns: int | str = 20,
    value_per_cell: float | None = None,
    unit: str | None = None,
    order: str = "row",
    max_cells: int = 5000,
) -> WaffleLayout:
    """Compute exact partial-cell occupancies for a composition.

    Parameters
    ----------
    mode : {'percent', 'absolute'}
        ``percent`` normalizes raw values to 100 and fills all cells.
        ``absolute`` preserves raw quantities, requiring ``value_per_cell``.
    rows, columns : int
        Dimensions of the display grid. ``columns='auto'`` is supported only
        for absolute mode and extends the grid to fit the total.
    value_per_cell : float, optional
        Quantity per complete cell in absolute mode (e.g., 5 phr, 100 kg/m3).
    order : {'row', 'column'}
        Row-major or column-major filling sequence for multirow grids.
    """
    if mode not in ("percent", "absolute"):
        raise ValueError("mode must be 'percent' or 'absolute'")
    if order not in ("row", "column"):
        raise ValueError("order must be 'row' or 'column'")
    _positive_int(rows, "rows")
    _positive_int(max_cells, "max_cells")
    if columns != "auto":
        _positive_int(columns, "columns")
    elif mode != "absolute":
        raise ValueError("columns='auto' is only available with mode='absolute'")

    original = _values(data)
    total = math.fsum(value for _, value in original)
    if mode == "percent":
        if value_per_cell is not None:
            raise ValueError("value_per_cell is inferred in percent mode")
        normalized = tuple((name, 100.0 * val / total) for name, val in original)
        # Force the final nonzero boundary to exactly 100 despite floating error.
        cell_value = 100.0 / (rows * int(columns))
        displayed_total = 100.0
        dimension_cols = int(columns)
        display_unit = "%" if unit is None else str(unit)
    else:
        if value_per_cell is None:
            raise ValueError("absolute mode requires value_per_cell")
        cell_value = float(value_per_cell)
        if not math.isfinite(cell_value) or cell_value <= 0:
            raise ValueError("value_per_cell must be finite and positive")
        dimension_cols = (
            max(1, math.ceil(math.nextafter(total / (rows * cell_value), -math.inf)))
            if columns == "auto" else int(columns)
        )
        normalized = original
        displayed_total = total
        display_unit = "" if unit is None else str(unit)
    cell_count = rows * dimension_cols
    if cell_count > max_cells:
        raise ValueError(f"grid exceeds max_cells={max_cells}")
    capacity = cell_count * cell_value
    if displayed_total > capacity and not math.isclose(displayed_total, capacity, rel_tol=1e-12):
        raise ValueError(
            f"composition total {displayed_total:g} exceeds grid capacity {capacity:g}"
        )

    fills: list[CellFill] = []
    start = 0.0
    nonzero = [n for n, (_, v) in enumerate(normalized) if v > 0]
    last_nonzero = nonzero[-1]
    # Separate cumulative edges avoid rounding individual components to cells.
    for comp_index, (name, value) in enumerate(normalized):
        if value == 0:
            continue
        end = (displayed_total if comp_index == last_nonzero
               else min(displayed_total, math.fsum((start, value))))
        # Numerical tolerance for slivers introduced only by floating-point sums.
        first_index = max(0, int(math.floor(start / cell_value)))
        final_index = min(cell_count, int(math.ceil(end / cell_value)))
        for index in range(first_index, final_index):
            left = max(start, index * cell_value)
            right = min(end, (index + 1) * cell_value)
            if right - left <= cell_value * 1e-12:
                continue
            a = max(0.0, min(1.0, (left - index * cell_value) / cell_value))
            b = max(0.0, min(1.0, (right - index * cell_value) / cell_value))
            if order == "row":
                r, c = divmod(index, dimension_cols)
            else:
                r, c = index % rows, index // rows
            fills.append(CellFill(name, index, r, c, a, b))
        start = end

    return WaffleLayout(normalized, tuple(fills), mode, display_unit,
                        rows, dimension_cols, order, cell_value, total,
                        displayed_total)
