"""Parameter loading and the assumption register."""

from __future__ import annotations

import pytest

from evsim.parameters import ParameterError, ParameterSet


def test_loads_every_parameter(vehicle: ParameterSet) -> None:
    assert len(list(vehicle)) > 30
    assert vehicle.meta("name").startswith("Tesla Model 3")


def test_parameters_carry_provenance(vehicle: ParameterSet) -> None:
    for parameter in vehicle:
        assert parameter.unit, f"{parameter.path} has no unit"
        assert parameter.source != "unspecified", f"{parameter.path} has no source"


def test_assumptions_are_flagged(vehicle: ParameterSet) -> None:
    assumed = {p.path for p in vehicle.assumptions()}
    published = {p.path for p in vehicle.published()}

    # Values Tesla does not publish must be flagged as assumptions.
    assert "transmission.gear_ratio" in assumed
    assert "aerodynamics.frontal_area" in assumed
    assert "tyres.rolling_resistance_coefficient" in assumed

    # Values Tesla does publish must not be.
    assert "motor.peak_power" in published
    assert "aerodynamics.drag_coefficient" in published
    assert "mass.curb_mass" in published

    assert not assumed & published


def test_missing_parameter_raises(vehicle: ParameterSet) -> None:
    with pytest.raises(ParameterError):
        vehicle.parameter("motor.does_not_exist")


def test_override_is_a_copy(vehicle: ParameterSet) -> None:
    original = vehicle["mass.curb_mass"]
    variant = vehicle.override(mass__curb_mass=2000.0)
    assert variant["mass.curb_mass"] == 2000.0
    assert vehicle["mass.curb_mass"] == original


def test_override_rejects_unknown_parameter(vehicle: ParameterSet) -> None:
    with pytest.raises(ParameterError):
        vehicle.override(mass__not_a_parameter=1.0)
