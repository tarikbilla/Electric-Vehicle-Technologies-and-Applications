"""Cycle simulation: tracking, energy conservation and limit handling."""

from __future__ import annotations

import numpy as np
import pytest

from evsim.cycles import DrivingCycle
from evsim.parameters import ParameterSet
from evsim.simulation import CycleSimulator, SimulationResult


@pytest.fixture(scope="module")
def run(vehicle: ParameterSet, wltc: DrivingCycle) -> SimulationResult:
    return CycleSimulator(vehicle).run(wltc)


# ------------------------------------------------------------- tracking
def test_the_vehicle_follows_the_whole_cycle(run: SimulationResult) -> None:
    """Acceptance criterion: no unmet speed points on WLTC Class 3b."""
    assert run.unmet_count == 0
    assert run.max_tracking_error_kph < 0.1


def test_distance_matches_the_cycle(run: SimulationResult, wltc: DrivingCycle) -> None:
    assert run.total_distance_km == pytest.approx(wltc.distance_km, rel=1e-3)


def test_traces_all_have_the_same_length(run: SimulationResult) -> None:
    n = run.time.size
    for name in ("speed", "acceleration", "distance", "power_battery", "soc", "unmet"):
        assert getattr(run, name).size == n, name


# --------------------------------------------------------- energy balance
def test_battery_discharges_over_the_cycle(run: SimulationResult) -> None:
    assert run.soc[-1] < run.soc[0]
    assert run.energy_net > 0


def test_net_energy_is_traction_plus_auxiliary_minus_regen(
    run: SimulationResult,
) -> None:
    expected = run.energy_traction + run.energy_auxiliary - run.energy_regen
    assert run.energy_net == pytest.approx(expected, rel=0.02)


def test_traction_energy_exceeds_the_road_load(run: SimulationResult) -> None:
    """Drivetrain losses must make the electrical demand larger than the road load."""
    assert run.energy_traction > run.energy_resistance


def test_regeneration_recovers_a_plausible_share(run: SimulationResult) -> None:
    assert 0.10 < run.regen_fraction < 0.45


def test_consumption_is_in_a_plausible_band(run: SimulationResult) -> None:
    """A mid-size BEV on WLTP sits around 11-20 kWh/100 km at the battery."""
    assert 10.0 < run.consumption_kwh_per_100km < 20.0


def test_state_of_charge_only_rises_while_regenerating(run: SimulationResult) -> None:
    rising = np.diff(run.soc) > 1e-12
    assert np.all(run.power_battery[1:][rising] <= 1e-6)


# ---------------------------------------------------------------- limits
def test_battery_power_respects_its_limits(
    run: SimulationResult, vehicle: ParameterSet
) -> None:
    assert run.power_battery.max() <= vehicle["battery.max_discharge_power"] * 1.001
    assert run.power_battery.min() >= -vehicle["battery.max_charge_power"] * 1.001


def test_motor_stays_inside_its_envelope(
    run: SimulationResult, vehicle: ParameterSet
) -> None:
    assert np.max(np.abs(run.motor_torque)) <= vehicle["motor.peak_torque"] * 1.001


# --------------------------------------------------------- physical trends
def test_disabling_regeneration_costs_energy(
    vehicle: ParameterSet, wltc: DrivingCycle
) -> None:
    with_regen = CycleSimulator(vehicle).run(wltc)
    without = CycleSimulator(vehicle.override(regeneration__max_regen_power=0.0)).run(wltc)
    assert without.consumption_kwh_per_100km > with_regen.consumption_kwh_per_100km
    assert without.energy_friction_brake > with_regen.energy_friction_brake


def test_auxiliary_load_raises_consumption(
    vehicle: ParameterSet, wltc: DrivingCycle
) -> None:
    quiet = CycleSimulator(vehicle, auxiliary_power=0.0).run(wltc)
    loud = CycleSimulator(vehicle, auxiliary_power=3000.0).run(wltc)
    assert loud.consumption_kwh_per_100km > quiet.consumption_kwh_per_100km


def test_extra_mass_raises_consumption(
    vehicle: ParameterSet, wltc: DrivingCycle
) -> None:
    light = CycleSimulator(vehicle.override(mass__test_payload=0.0)).run(wltc)
    heavy = CycleSimulator(vehicle.override(mass__test_payload=500.0)).run(wltc)
    assert heavy.consumption_kwh_per_100km > light.consumption_kwh_per_100km


def test_an_underpowered_car_cannot_follow_the_cycle(
    vehicle: ParameterSet, wltc: DrivingCycle
) -> None:
    """The simulation must flag steps it cannot meet rather than fake them."""
    feeble = vehicle.override(motor__peak_power=4000.0, motor__peak_torque=40.0)
    result = CycleSimulator(feeble).run(wltc)
    assert result.unmet_count > 0
    assert result.max_tracking_error_kph > 1.0


def test_nedc_is_gentler_than_wltp(
    vehicle: ParameterSet, wltc: DrivingCycle, nedc_cycle: DrivingCycle
) -> None:
    simulator = CycleSimulator(vehicle)
    assert (
        simulator.run(nedc_cycle).consumption_kwh_per_100km
        < simulator.run(wltc).consumption_kwh_per_100km
    )
