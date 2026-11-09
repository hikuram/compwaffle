"""Explicit, unit-agnostic conversions between common composition bases."""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from .core import _values


def parts_per_reference(
    data: Mapping[str, float],
    reference: str | Sequence[str],
    *,
    basis: float = 100.0,
) -> dict[str, float]:
    """Express components as parts per ``basis`` parts of a reference.

    ``reference`` accepts one component name or a sequence of distinct names.
    The denominator is the sum of their input values. Input amounts must use
    consistent units; no material-specific conversion is implicit.
    """
    valid = dict(_values(data))
    if isinstance(reference, str):
        names = (reference,)
    else:
        names = tuple(reference)
    if not names or len(set(names)) != len(names):
        raise ValueError("reference must list one or more distinct components")
    missing = [name for name in names if name not in valid]
    if missing:
        raise KeyError(f"reference component(s) not in data: {missing}")
    denominator = math.fsum(valid[name] for name in names)
    if denominator <= 0:
        raise ValueError("reference amount must be positive")
    factor = float(basis)
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError("basis must be finite and positive")
    return {key: value * factor / denominator for key, value in valid.items()}


def mass_to_volume_parts(
    data: Mapping[str, float],
    densities: Mapping[str, float],
) -> dict[str, float]:
    """Convert mass amounts to unnormalized volume amounts (mass/density).

    Densities must use consistent units. Use ``build_layout(mode='percent')``
    afterwards for volume fractions; no densities are guessed.
    """
    values = dict(_values(data))
    output: dict[str, float] = {}
    for key, value in values.items():
        if key not in densities:
            raise KeyError(f"missing density for component: {key}")
        density = float(densities[key])
        if not math.isfinite(density) or density <= 0:
            raise ValueError(f"density for {key!r} must be finite and positive")
        output[key] = value / density
    return output
