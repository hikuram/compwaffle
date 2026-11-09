import math
import pytest
from compwaffle import build_layout


def test_percent_20_cells_and_fractional_boundary():
    layout = build_layout({"A": 72.5, "B": 27.5}, columns=20)
    assert layout.count == 20
    assert layout.value_per_cell == 5
    parts = layout.fills_in_cell(14)
    assert [(p.key, p.start, p.end) for p in parts] == [
        ("A", 0, pytest.approx(0.5)), ("B", pytest.approx(0.5), 1.0)]
    assert sum(p.fraction for p in parts) == pytest.approx(1.0)


def test_multiple_categories_in_a_single_cell():
    layout = build_layout({"A": .2, "B": .3, "C": 99.5})
    assert {p.key for p in layout.fills_in_cell(0)} == {"A", "B", "C"}
    assert sum(p.fraction for p in layout.fills_in_cell(0)) == pytest.approx(1)


def test_raw_counts_get_normalized_without_rounding():
    layout = build_layout({"A": 1, "B": 3}, rows=1, columns=20)
    assert layout.values[0][1] == 25
    assert layout.source_total == 4
    assert layout.capacity == 100


def test_absolute_auto_extends_grid_and_keeps_ends_partial():
    layout = build_layout({"A": 100, "B": 20, "C": 2.5},
                          mode="absolute", columns="auto", value_per_cell=5)
    assert layout.columns == 25
    last = layout.fills_in_cell(24)
    assert len(last) == 1
    assert last[0].key == "C"
    assert last[0].fraction == pytest.approx(0.5)
    assert layout.capacity == 125


def test_absolute_undersized_grid_is_rejected():
    with pytest.raises(ValueError, match="exceeds grid capacity"):
        build_layout({"A": 101}, mode="absolute", columns=20, value_per_cell=5)


def test_order_changes_cell_mapping_for_multirow():
    a = build_layout({"A": 55, "B": 45}, rows=2, columns=10, order="row")
    b = build_layout({"A": 55, "B": 45}, rows=2, columns=10, order="column")
    assert a.fills_in_cell(1)[0].row == 0
    assert a.fills_in_cell(1)[0].column == 1
    assert b.fills_in_cell(1)[0].row == 1
    assert b.fills_in_cell(1)[0].column == 0


@pytest.mark.parametrize("values", [
    {}, {"A": -1}, {"A": 0}, {"A": math.nan}, {"A": math.inf},
    {"A": "nan"}, {"A": None},
])
def test_invalid_data(values):
    with pytest.raises(ValueError):
        build_layout(values)


def test_fixed_absolute_can_show_unfilled_cells():
    layout = build_layout({"A": 9}, mode="absolute", value_per_cell=5, columns=4)
    assert layout.count == 4
    assert layout.fills_in_cell(2) == ()


def test_unknown_mode_and_mixed_scale_rules():
    with pytest.raises(ValueError):
        build_layout({"A": 1}, mode="wrong")
    with pytest.raises(ValueError):
        build_layout({"A": 1}, value_per_cell=5)
    with pytest.raises(ValueError):
        build_layout({"A": 1}, mode="absolute")
    with pytest.raises(ValueError):
        build_layout({"A": 1}, columns="auto")


def test_very_small_but_meaningful_part():
    layout = build_layout({"A": .001, "B": 99.999})
    first = layout.fills_in_cell(0)
    assert first[0].fraction == pytest.approx(.001 / 5)
    assert sum(p.fraction for p in first) == pytest.approx(1)


def test_explicit_cell_pitch_and_multiple_rows():
    layout = build_layout({'A': 73.5, 'B': 26.5}, rows=2, columns=10)
    assert layout.value_per_cell == 5
    assert layout.count == 20
    assert sum(p.fraction for p in layout.fills_in_cell(14)) == pytest.approx(1.0)


def test_finite_and_positive_cell_capacity():
    with pytest.raises(ValueError):
        build_layout({'A': 1}, mode='absolute', columns='auto', value_per_cell=0)
    with pytest.raises(ValueError):
        build_layout({'A': 1}, mode='absolute', columns='auto', value_per_cell=float('nan'))
    with pytest.raises(ValueError, match='max_cells'):
        build_layout({'A': 10000}, mode='absolute', columns='auto', value_per_cell=1)
