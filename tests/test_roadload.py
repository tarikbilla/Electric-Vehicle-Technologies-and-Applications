"""Road-load model: each resistance term against a hand calculation."""

from __future__ import annotations

import numpy as np
import pytest

from evsim.parameters import ParameterSet
from evsim.roadload import COASTDOWN, PHYSICAL, RoadLoad
from evsim.units import mps


@pytest.fixture(scope="module")
def road(vehicle: ParameterSet) -> RoadLoad:
    """The vehicle's active road-load model (coastdown by default)."""
    return RoadLoad.from_parameters(vehicle)


@pytest.fixture(scope="module")
def physical(vehicle: ParameterSet) -> RoadLoad:
    """The textbook decomposition, used to check the closed-form terms."""
    return RoadLoad.from_parameters(vehicle, model=PHYSICAL)


def test_test_mass_is_kerb_plus_payload(road: RoadLoad, vehicle: ParameterSet) -> None:
    assert road.mass == pytest.approx(
        vehicle["mass.curb_mass"] + vehicle["mass.test_payload"]
    )


def test_aerodynamic_drag_matches_hand_calculation(physical: RoadLoad) -> None:
    v = mps(100.0)
    expected = 0.5 * physical.air_density * physical.drag_coefficient * physical.frontal_area * v**2
    assert float(physical.aerodynamic_drag(v)) == pytest.approx(expected, rel=1e-12)


def test_drag_scales_with_the_square_of_speed(physical: RoadLoad) -> None:
    single = float(physical.aerodynamic_drag(mps(50.0)))
    double = float(physical.aerodynamic_drag(mps(100.0)))
    assert double / single == pytest.approx(4.0, rel=1e-9)


def test_rolling_resistance_vanishes_at_standstill(road: RoadLoad) -> None:
    assert float(road.rolling_resistance(0.0)) == 0.0
    assert float(road.rolling_resistance(mps(30.0))) > 0.0


def test_rolling_resistance_matches_hand_calculation(physical: RoadLoad) -> None:
    v = mps(80.0)
    f_r = physical.f_r0 + physical.f_r_k * v**2
    expected = f_r * physical.mass * physical.gravity
    assert float(physical.rolling_resistance(v)) == pytest.approx(expected, rel=1e-12)


def test_grade_resistance_is_zero_on_the_flat(road: RoadLoad) -> None:
    assert float(np.asarray(road.grade_resistance(mps(50.0)))) == pytest.approx(0.0)


def test_grade_resistance_on_a_ten_percent_slope(vehicle: ParameterSet) -> None:
    graded = RoadLoad.from_parameters(vehicle.override(environment__road_grade=np.arctan(0.10)))
    expected = graded.mass * graded.gravity * np.sin(np.arctan(0.10))
    assert float(np.asarray(graded.grade_resistance(0.0))) == pytest.approx(expected)


def test_inertia_uses_the_rotational_mass_factor(road: RoadLoad) -> None:
    force = float(road.inertia_force(1.0))
    assert force == pytest.approx(road.rotational_factor * road.mass)
    assert force > road.mass          # rotating parts must add to the effective mass


def test_tractive_force_is_the_sum_of_its_parts(road: RoadLoad) -> None:
    """Whichever formulation is active, the total must be its parts plus inertia."""
    v, a = mps(60.0), 0.8
    total = float(road.tractive_force(v, a))
    parts = sum(float(part) for part in road.components(v).values())
    parts += float(road.inertia_force(a))
    assert total == pytest.approx(parts, rel=1e-12)


def test_physical_decomposition_sums_correctly(vehicle: ParameterSet) -> None:
    physical = RoadLoad.from_parameters(vehicle, model=PHYSICAL)
    v = mps(60.0)
    total = float(physical.running_resistance(v))
    parts = float(physical.rolling_resistance(v)) + float(physical.aerodynamic_drag(v))
    assert total == pytest.approx(parts, rel=1e-12)


def test_coastdown_matches_its_polynomial(vehicle: ParameterSet) -> None:
    road = RoadLoad.from_parameters(vehicle, model=COASTDOWN)
    for v in (mps(30.0), mps(80.0), mps(130.0)):
        expected = road.f0 * road.mass_ratio + road.f1 * v + road.f2 * v**2
        assert float(road.running_resistance(v)) == pytest.approx(expected, rel=1e-12)


def test_coastdown_rolling_term_scales_with_mass(vehicle: ParameterSet) -> None:
    """Rolling resistance is proportional to normal load, so payload must cost."""
    light = RoadLoad.from_parameters(vehicle.override(mass__test_payload=0.0))
    heavy = RoadLoad.from_parameters(vehicle.override(mass__test_payload=400.0))
    v = mps(50.0)
    assert float(heavy.running_resistance(v)) > float(light.running_resistance(v))
    ratio = heavy.mass_ratio / light.mass_ratio
    assert ratio == pytest.approx(heavy.mass / light.mass, rel=1e-12)


def test_coastdown_exceeds_the_textbook_form_at_speed(vehicle: ParameterSet) -> None:
    """The textbook decomposition has no linear term and a wind-tunnel drag
    coefficient, so it under-predicts the real road load at motorway speed."""
    coastdown = RoadLoad.from_parameters(vehicle, model=COASTDOWN)
    physical = coastdown.with_model(PHYSICAL)
    v = mps(120.0)
    shortfall = 1.0 - float(physical.resistance(v)) / float(coastdown.resistance(v))
    assert 0.08 < shortfall < 0.30


def test_effective_drag_area_exceeds_the_wind_tunnel_value(vehicle: ParameterSet) -> None:
    road = RoadLoad.from_parameters(vehicle, model=COASTDOWN)
    assert 1.1 < road.drag_discrepancy() < 1.5


def test_unknown_road_load_model_raises(vehicle: ParameterSet) -> None:
    with pytest.raises(ValueError, match="unknown road-load model"):
        RoadLoad.from_parameters(vehicle, model="magic")


def test_coasting_decelerates_the_vehicle(road: RoadLoad) -> None:
    assert float(road.coastdown_deceleration(mps(100.0))) < 0.0


def test_forces_broadcast_over_arrays(road: RoadLoad) -> None:
    speeds = np.linspace(0.0, mps(150.0), 25)
    resistance = np.asarray(road.resistance(speeds))
    assert resistance.shape == speeds.shape
    assert np.all(np.diff(resistance) >= -1e-9)      # monotonically increasing
