import pytest
from compwaffle import parts_per_reference, mass_to_volume_parts


def test_cement_mass_parts():
    sample = {"Cement": 273, "Slag": 82, "Fly ash": 105, "Water": 210}
    ph = parts_per_reference(sample, "Cement")
    assert ph["Cement"] == pytest.approx(100)
    assert ph["Water"] == pytest.approx(76.923076923)


def test_binder_reference_sum_is_100():
    sample = {"Cement": 273, "Slag": 82, "Fly ash": 105, "Water": 210}
    ph = parts_per_reference(sample, ["Cement", "Slag", "Fly ash"])
    assert ph["Cement"] + ph["Slag"] + ph["Fly ash"] == pytest.approx(100)
    assert ph["Water"] == pytest.approx(100 * 210 / 460)


def test_no_reference_or_zero_reference():
    with pytest.raises(KeyError):
        parts_per_reference({"A": 10}, "B")
    with pytest.raises(ValueError):
        parts_per_reference({"A": 0, "B": 5}, "A")
    with pytest.raises(ValueError):
        parts_per_reference({"A": 1, "B": 2}, ["A", "A"])


def test_volume_parts():
    volume = mass_to_volume_parts({"A": 100, "B": 200},
                                  {"A": 2.0, "B": 4.0})
    assert volume == {"A": 50, "B": 50}
    with pytest.raises(KeyError):
        mass_to_volume_parts({"A": 1}, {})
    with pytest.raises(ValueError):
        mass_to_volume_parts({"A": 1}, {"A": 0})
