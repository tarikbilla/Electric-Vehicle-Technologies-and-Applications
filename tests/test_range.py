"""Range on a full battery, and the acceptance criterion against WLTP."""

from __future__ import annotations

import numpy as np
import pytest

from evsim.cycles import DrivingCycle
from evsim.parameters import ParameterSet
from evsim.rangecalc import (
    RangeResult,
    constant_speed_range,
    range_on_cycle,
    range_validation,
)


@pytest.fixture(scope="module")
def result(vehicle: ParameterSet, wltc: DrivingCycle) -> RangeResult:
    return range_on_cycle(vehicle, wltc)


# ------------------------------------------------------------- acceptance
def test_range_matches_the_published_wltp_figure(
    result: RangeResult, vehicle: ParameterSet
) -> None:
    """Acceptance criterion: within 10 % of the published WLTP range."""
    published = vehicle["reference.wltp_range"]
    deviation = abs(result.range_integrated_km - published) / published
    assert deviation <= 0.10, f"deviation {deviation * 100:.1f} %"


def test_validation_rows_all_pass(vehicle: ParameterSet, result: RangeResult) -> None:
    for row in range_validation(vehicle, result):
        assert row["pass"], f"{row['quantity']} deviates by {row['deviation_pct']:.1f} %"


# ------------------------------------------------------ the two methods agree
def test_the_two_methods_agree_closely(result: RangeResult) -> None:
    assert abs(result.disagreement_pct) < 5.0


def test_integrating_gives_the_shorter_range(result: RangeResult) -> None:
    """Ohmic loss grows as the pack voltage falls, which the analytic method misses."""
    assert result.range_integrated_km < result.range_analytic_km


def test_energy_delivered_is_close_to_the_usable_energy(result: RangeResult) -> None:
    assert result.energy_delivered_kwh == pytest.approx(
        result.usable_energy_kwh, rel=0.05
    )


# ------------------------------------------------------------- discharge trace
def test_state_of_charge_falls_to_empty(result: RangeResult) -> None:
    assert result.soc_trace[0] == pytest.approx(1.0)
    assert result.soc_trace[-1] < 0.02


def test_distance_trace_is_monotonic(result: RangeResult) -> None:
    assert np.all(np.diff(result.distance_trace) >= -1e-9)


def test_cycles_completed_is_consistent(
    result: RangeResult, wltc: DrivingCycle
) -> None:
    assert result.cycles_completed == pytest.approx(
        result.range_integrated_km * 1000.0 / wltc.distance, rel=1e-6
    )


# ------------------------------------------------------------ physical trends
def test_a_bigger_battery_goes_further(
    vehicle: ParameterSet, wltc: DrivingCycle, result: RangeResult
) -> None:
    bigger = range_on_cycle(vehicle.override(battery__gross_capacity=80.0), wltc)
    assert bigger.range_integrated_km > result.range_integrated_km


def test_heating_the_cabin_costs_range(
    vehicle: ParameterSet, wltc: DrivingCycle, result: RangeResult
) -> None:
    cold = range_on_cycle(vehicle.override(auxiliaries__hvac_load=3000.0), wltc)
    assert cold.range_integrated_km < result.range_integrated_km * 0.85


# ----------------------------------------------------------- constant speed
def test_constant_speed_range_has_an_interior_maximum(vehicle: ParameterSet) -> None:
    """Auxiliaries dominate at low speed, drag at high speed, so there is a peak."""
    speeds, ranges, _ = constant_speed_range(vehicle)
    best = int(np.nanargmax(ranges))
    assert 0 < best < len(speeds) - 1


def test_consumption_rises_with_cruising_speed(vehicle: ParameterSet) -> None:
    speeds, _, consumption = constant_speed_range(
        vehicle, speeds_kph=np.array([60.0, 90.0, 120.0, 150.0])
    )
    assert np.all(np.diff(consumption) > 0)


def test_motorway_cruising_range_is_plausible(vehicle: ParameterSet) -> None:
    speeds, ranges, consumption = constant_speed_range(
        vehicle, speeds_kph=np.array([130.0])
    )
    assert 220.0 < ranges[0] < 360.0
    assert 160.0 < consumption[0] < 250.0
