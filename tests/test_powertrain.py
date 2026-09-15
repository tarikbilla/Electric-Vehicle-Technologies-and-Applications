"""Motor envelope, loss model and regeneration limits."""

from __future__ import annotations

import numpy as np
import pytest

from evsim.parameters import ParameterSet
from evsim.powertrain import Powertrain
from evsim.units import mps, rad_s


@pytest.fixture(scope="module")
def powertrain(vehicle: ParameterSet) -> Powertrain:
    return Powertrain.from_parameters(vehicle)


def test_base_speed_is_the_corner_of_the_envelope(powertrain: Powertrain) -> None:
    assert powertrain.base_speed == pytest.approx(
        powertrain.peak_power / powertrain.peak_torque
    )


def test_constant_torque_below_base_speed(powertrain: Powertrain) -> None:
    for omega in (1.0, powertrain.base_speed * 0.5, powertrain.base_speed * 0.99):
        assert float(powertrain.max_motor_torque(omega)) == pytest.approx(
            powertrain.peak_torque
        )


def test_constant_power_above_base_speed(powertrain: Powertrain) -> None:
    for factor in (1.2, 1.8, 2.5):
        omega = powertrain.base_speed * factor
        power = float(powertrain.max_motor_torque(omega)) * omega
        assert power == pytest.approx(powertrain.peak_power, rel=1e-9)


def test_no_torque_beyond_maximum_motor_speed(powertrain: Powertrain) -> None:
    assert float(powertrain.max_motor_torque(powertrain.max_speed * 1.01)) == 0.0


def test_speed_conversions_are_inverse(powertrain: Powertrain) -> None:
    v = mps(72.0)
    assert float(powertrain.motor_to_vehicle_speed(powertrain.motor_speed(v))) == pytest.approx(v)


def test_peak_wheel_force_matches_hand_calculation(powertrain: Powertrain) -> None:
    expected = (
        powertrain.peak_torque
        * powertrain.gear_ratio
        * powertrain.gear_efficiency
        / powertrain.wheel_radius
    )
    assert float(powertrain.max_tractive_force(1.0)) == pytest.approx(expected)


def test_efficiency_is_physical(powertrain: Powertrain) -> None:
    """Efficiency must stay strictly below one and peak in a plausible band."""
    omega = np.linspace(20.0, powertrain.max_speed, 200)
    torque = np.linspace(5.0, powertrain.peak_torque, 200)
    grid_w, grid_t = np.meshgrid(omega, torque)
    envelope = powertrain.max_motor_torque(grid_w)
    efficiency = np.where(grid_t <= envelope, powertrain.efficiency(grid_t, grid_w), np.nan)

    assert np.nanmax(efficiency) < 1.0
    assert 0.93 < np.nanmax(efficiency) < 0.985      # realistic for motor + inverter
    assert np.nanmin(efficiency) >= 0.0


def test_efficiency_falls_away_at_light_load(powertrain: Powertrain) -> None:
    omega = powertrain.base_speed
    assert float(powertrain.efficiency(5.0, omega)) < float(
        powertrain.efficiency(150.0, omega)
    )


def test_losses_grow_with_torque_and_speed(powertrain: Powertrain) -> None:
    assert powertrain.loss(200.0, 300.0) > powertrain.loss(100.0, 300.0)
    assert powertrain.loss(100.0, 600.0) > powertrain.loss(100.0, 300.0)


def test_motoring_draws_more_than_it_delivers(powertrain: Powertrain) -> None:
    v = mps(80.0)
    force = 1500.0
    p_elec, _, _ = powertrain.electrical_power_motoring(force, v)
    assert float(p_elec) > force * v


def test_regeneration_recovers_less_than_it_absorbs(powertrain: Powertrain) -> None:
    v = mps(80.0)
    force = 1500.0
    p_elec, _, _ = powertrain.electrical_power_regen(force, v)
    assert float(p_elec) < 0.0                       # negative = charging
    assert abs(float(p_elec)) < force * v            # losses must not be recovered


def test_regeneration_blends_out_at_low_speed(powertrain: Powertrain) -> None:
    assert float(powertrain.max_regen_wheel_force(0.5)) == 0.0
    assert float(powertrain.max_regen_wheel_force(mps(30.0))) > 0.0


def test_regeneration_respects_the_battery_charge_limit(powertrain: Powertrain) -> None:
    v = mps(120.0)
    force = float(powertrain.max_regen_wheel_force(v))
    assert force * v <= powertrain.max_regen_power * 1.001


def test_continuous_rating_is_below_the_peak(powertrain: Powertrain) -> None:
    v = mps(60.0)
    assert float(powertrain.continuous_tractive_force(v)) < float(
        powertrain.max_tractive_force(v)
    )
