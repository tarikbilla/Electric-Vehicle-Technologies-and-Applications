"""Battery energy book-keeping and limits."""

from __future__ import annotations

import numpy as np
import pytest

from evsim.battery import Battery
from evsim.parameters import ParameterSet
from evsim.units import J_PER_KWH


@pytest.fixture(scope="module")
def battery(vehicle: ParameterSet) -> Battery:
    return Battery.from_parameters(vehicle)


def test_usable_energy_follows_the_parameter_file(
    battery: Battery, vehicle: ParameterSet
) -> None:
    expected = vehicle["battery.gross_capacity"] * vehicle["battery.usable_fraction"]
    assert battery.usable_energy_kwh == pytest.approx(expected)


def test_open_circuit_voltage_rises_with_state_of_charge(battery: Battery) -> None:
    soc = np.linspace(0.0, 1.0, 50)
    voltage = battery.open_circuit_voltage(soc)
    assert np.all(np.diff(voltage) > 0)


def test_lfp_voltage_plateau_is_flat(battery: Battery) -> None:
    """LFP chemistry must show only a small voltage change across the mid band."""
    low = float(battery.open_circuit_voltage(0.25))
    high = float(battery.open_circuit_voltage(0.85))
    assert (high - low) / low < 0.06


def test_capacity_is_consistent_with_the_voltage_curve(battery: Battery) -> None:
    energy = battery.capacity_ah * 3600.0 * battery.mean_open_circuit_voltage
    assert energy == pytest.approx(battery.usable_energy, rel=1e-9)


def test_slow_full_discharge_delivers_the_nameplate_energy(battery: Battery) -> None:
    """A gentle discharge should give back the rated energy, less a little ohmic loss."""
    soc, delivered = battery.soc_max, 0.0
    while not battery.is_depleted(soc):
        soc, applied, _, _ = battery.step(2000.0, soc, 1.0)
        delivered += applied
    delivered_kwh = delivered / J_PER_KWH
    assert delivered_kwh == pytest.approx(battery.usable_energy_kwh, rel=0.01)
    assert delivered_kwh < battery.usable_energy_kwh      # ohmic loss is real


def test_discharging_lowers_and_charging_raises_the_state_of_charge(
    battery: Battery,
) -> None:
    discharged, _, _, _ = battery.step(20000.0, 0.8, 10.0)
    charged, _, _, _ = battery.step(-20000.0, 0.8, 10.0)
    assert discharged < 0.8 < charged


def test_power_is_clipped_to_the_discharge_limit(battery: Battery) -> None:
    _, applied, _, limited = battery.step(battery.max_discharge_power * 3, 0.9, 1.0)
    assert limited
    assert applied <= battery.max_discharge_power * 1.001


def test_power_is_clipped_to_the_charge_limit(battery: Battery) -> None:
    _, applied, _, limited = battery.step(-battery.max_charge_power * 3, 0.5, 1.0)
    assert limited
    assert applied >= -battery.max_charge_power * 1.001


def test_current_solution_satisfies_the_circuit_equation(battery: Battery) -> None:
    """The returned current must reproduce the demanded terminal power."""
    for power in (5_000.0, 50_000.0, 150_000.0):
        current, limited = battery.current(power, 0.6)
        assert not limited
        v_oc = float(battery.open_circuit_voltage(0.6))
        recovered = v_oc * current - current**2 * battery.internal_resistance
        assert recovered == pytest.approx(power, rel=1e-9)


def test_ohmic_ceiling_is_respected(battery: Battery) -> None:
    ceiling = battery.power_limit(0.5)
    _, limited = battery.current(ceiling * 2.0, 0.5)
    assert limited


def test_state_of_charge_never_leaves_its_bounds(battery: Battery) -> None:
    soc = 0.02
    for _ in range(500):
        soc, _, _, _ = battery.step(100_000.0, soc, 1.0)
        assert 0.0 <= soc <= 1.0
