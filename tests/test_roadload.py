"""Road-load model: each resistance term against a hand calculation."""

from __future__ import annotations

import numpy as np
import pytest

from evsim.parameters import ParameterSet
from evsim.roadload import RoadLoad
from evsim.units import mps


@pytest.fixture(scope="module")
def road(vehicle: ParameterSet) -> RoadLoad:
    return RoadLoad.from_parameters(vehicle)


def test_test_mass_is_kerb_plus_payload(road: RoadLoad, vehicle: ParameterSet) -> None:
    assert road.mass == pytest.approx(
        vehicle["mass.curb_mass"] + vehicle["mass.test_payload"]
    )


def test_aerodynamic_drag_matches_hand_calculation(road: RoadLoad) -> None:
    v = mps(100.0)
    expected = 0.5 * road.air_density * road.drag_coefficient * road.frontal_area * v**2
    assert float(road.aerodynamic_drag(v)) == pytest.approx(expected, rel=1e-12)


def test_drag_scales_with_the_square_of_speed(road: RoadLoad) -> None:
    single = float(road.aerodynamic_drag(mps(50.0)))
    double = float(road.aerodynamic_drag(mps(100.0)))
    assert double / single == pytest.approx(4.0, rel=1e-9)


def test_rolling_resistance_vanishes_at_standstill(road: RoadLoad) -> None:
    assert float(road.rolling_resistance(0.0)) == 0.0
    assert float(road.rolling_resistance(mps(30.0))) > 0.0


def test_rolling_resistance_matches_hand_calculation(road: RoadLoad) -> None:
    v = mps(80.0)
    f_r = road.f_r0 + road.f_r_k * v**2
    expected = f_r * road.mass * road.gravity
    assert float(road.rolling_resistance(v)) == pytest.approx(expected, rel=1e-12)


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
    v, a = mps(60.0), 0.8
    total = float(road.tractive_force(v, a))
    parts = (
        float(road.rolling_resistance(v))
        + float(road.aerodynamic_drag(v))
        + float(np.asarray(road.grade_resistance(v)))
        + float(road.inertia_force(a))
    )
    assert total == pytest.approx(parts, rel=1e-12)


def test_coasting_decelerates_the_vehicle(road: RoadLoad) -> None:
    assert float(road.coastdown_deceleration(mps(100.0))) < 0.0


def test_forces_broadcast_over_arrays(road: RoadLoad) -> None:
    speeds = np.linspace(0.0, mps(150.0), 25)
    resistance = np.asarray(road.resistance(speeds))
    assert resistance.shape == speeds.shape
    assert np.all(np.diff(resistance) >= -1e-9)      # monotonically increasing
