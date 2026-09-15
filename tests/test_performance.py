"""Speed and acceleration characteristics against the manufacturer's figures."""

from __future__ import annotations

import numpy as np
import pytest

from evsim.parameters import ParameterSet
from evsim.performance import PerformanceModel, PerformanceResult
from evsim.units import MPS_TO_KPH, mps


@pytest.fixture(scope="module")
def model(vehicle: ParameterSet) -> PerformanceModel:
    return PerformanceModel(vehicle)


@pytest.fixture(scope="module")
def result(model: PerformanceModel) -> PerformanceResult:
    return model.run()


# ------------------------------------------------------------- acceptance
def test_zero_to_hundred_matches_the_published_figure(
    result: PerformanceResult, vehicle: ParameterSet
) -> None:
    """Acceptance criterion: within 10 % of the manufacturer's figure."""
    published = vehicle["reference.acceleration_0_100_kph"]
    simulated = result.accel_times["0-100 km/h"]
    assert abs(simulated - published) / published <= 0.10


def test_top_speed_matches_the_published_figure(
    result: PerformanceResult, vehicle: ParameterSet
) -> None:
    """Acceptance criterion: within 5 %, or equal to the electronic limiter."""
    published = vehicle["reference.top_speed"]
    simulated = result.top_speed * MPS_TO_KPH
    assert abs(simulated - published) / published <= 0.05


def test_validation_rows_all_pass(model: PerformanceModel) -> None:
    for row in model.validation():
        assert row["pass"], f"{row['quantity']} deviates by {row['deviation_pct']:.1f} %"


# ------------------------------------------------------------- behaviour
def test_acceleration_falls_away_with_speed(result: PerformanceResult) -> None:
    moving = result.speed > mps(20.0)
    assert np.all(np.diff(result.acceleration[moving]) < 1e-6)


def test_benchmark_times_increase_with_the_target_speed(
    result: PerformanceResult,
) -> None:
    times = [t for t in result.accel_times.values() if np.isfinite(t)]
    assert times == sorted(times)


def test_launch_is_traction_limited(result: PerformanceResult) -> None:
    """A rear-drive car must run out of grip before it runs out of torque."""
    assert result.adhesion_force[0] < result.tractive_force[0]
    assert result.available_force[0] == pytest.approx(result.adhesion_force[0])


def test_available_force_never_exceeds_either_limit(result: PerformanceResult) -> None:
    assert np.all(result.available_force <= result.tractive_force + 1e-6)
    assert np.all(result.available_force <= result.adhesion_force + 1e-6)


def test_resistance_is_the_sum_of_its_components_on_the_flat(
    result: PerformanceResult,
) -> None:
    assert np.allclose(
        result.resistance, result.mechanical + result.aerodynamic, atol=1e-6
    )


def test_the_textbook_form_under_predicts_the_road_load(
    result: PerformanceResult,
) -> None:
    """Reported so the report can show the gap rather than hide it."""
    fast = result.speed > mps(100.0)
    assert np.all(result.resistance_physical[fast] < result.resistance[fast])


def test_top_speed_is_set_by_the_limiter_on_this_vehicle(
    model: PerformanceModel,
) -> None:
    assert model.top_speed()[1] == "electronic limiter"


def test_limiter_binds_when_it_is_below_the_unlimited_top_speed(
    vehicle: ParameterSet,
) -> None:
    limited_model = PerformanceModel(vehicle.override(reference__speed_limiter=150.0))
    v_top, reason = limited_model.top_speed()
    assert reason == "electronic limiter"
    assert v_top * MPS_TO_KPH == pytest.approx(150.0)


def test_without_a_limiter_the_motor_speed_binds(vehicle: ParameterSet) -> None:
    """A single-speed drivetrain usually runs out of revs before it runs out of pull."""
    unlimited = PerformanceModel(vehicle.override(reference__speed_limiter=0.0))
    v_top, reason = unlimited.top_speed()
    assert reason == "maximum motor speed"
    assert v_top == pytest.approx(unlimited.powertrain.max_vehicle_speed)


def test_surplus_force_vanishes_when_the_force_balance_binds(
    vehicle: ParameterSet,
) -> None:
    """With enough drag the top speed is where available force meets resistance."""
    draggy = PerformanceModel(
        vehicle.override(
            reference__speed_limiter=0.0, road_load__coastdown_f2=1.20
        )
    )
    v_top, reason = draggy.top_speed()
    assert reason == "tractive force balance"
    surplus = (
        min(
            float(draggy.powertrain.max_tractive_force(v_top)),
            float(draggy.adhesion_limit(v_top)),
        )
        - float(draggy.road.resistance(v_top))
    )
    assert surplus == pytest.approx(0.0, abs=5.0)


def test_a_low_rev_limit_caps_the_top_speed(vehicle: ParameterSet) -> None:
    slow = PerformanceModel(
        vehicle.override(reference__speed_limiter=0.0, motor__max_speed=11000.0)
    )
    v_top, reason = slow.top_speed()
    assert reason == "maximum motor speed"
    assert v_top * MPS_TO_KPH < 180.0


def test_gradeability_falls_with_speed(model: PerformanceModel) -> None:
    speeds = np.linspace(mps(10.0), mps(120.0), 40)
    grades = model.gradeability(speeds)
    assert np.all(np.diff(grades) < 0)
    assert grades[0] > 20.0          # a modern BEV pulls away on a steep hill


def test_extra_mass_slows_the_car_down(vehicle: ParameterSet) -> None:
    heavy = PerformanceModel(vehicle.override(mass__test_payload=500.0)).run()
    light = PerformanceModel(vehicle.override(mass__test_payload=0.0)).run()
    assert heavy.accel_times["0-100 km/h"] > light.accel_times["0-100 km/h"]


def test_more_drag_lowers_the_top_speed(vehicle: ParameterSet) -> None:
    draggy = PerformanceModel(
        vehicle.override(road_load__coastdown_f2=0.90, reference__speed_limiter=0.0)
    )
    slippery = PerformanceModel(
        vehicle.override(road_load__coastdown_f2=0.30, reference__speed_limiter=0.0)
    )
    assert draggy.top_speed()[0] < slippery.top_speed()[0]
