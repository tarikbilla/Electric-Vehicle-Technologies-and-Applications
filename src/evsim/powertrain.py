"""Electric powertrain model: motor envelope, gearbox, losses, regeneration (FR-3).

Motor envelope
--------------
A traction machine is operated in two regions:

    omega <= omega_base : constant torque   T = T_peak
    omega >  omega_base : constant power    T = P_peak / omega   (field weakening)

with ``omega_base = P_peak / T_peak``.  Above ``omega_max`` no torque is
available.

Losses
------
Combined motor + inverter losses follow the four-term model of Larminie &
Lowry (*Electric Vehicle Technology Explained*, 2nd ed., ch. 7):

    P_loss = k_c * T^2 + k_i * omega + k_w * omega^3 + P_0

which captures copper (current), iron (flux), windage and constant electronics
losses.  This reproduces the characteristic efficiency island of a real drive
unit far better than a single constant efficiency.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .parameters import ParameterSet
from .units import rad_s

ArrayLike = float | np.ndarray


@dataclasses.dataclass(frozen=True)
class Powertrain:
    """Single-speed electric drive unit (motor + inverter + reduction gear)."""

    peak_power: float          # W, shaft
    peak_torque: float         # N*m, shaft
    max_speed: float           # rad/s, motor
    continuous_power_fraction: float
    gear_ratio: float          # -
    gear_efficiency: float     # -
    wheel_radius: float        # m
    k_copper: float
    k_iron: float
    k_windage: float
    p_constant: float
    # regeneration
    regen_enabled: bool
    max_regen_power: float     # W, at the battery terminals
    max_regen_torque: float    # N*m, shaft
    regen_cutoff_speed: float  # m/s
    regen_blend_speed: float   # m/s

    # ------------------------------------------------------------ construction
    @classmethod
    def from_parameters(cls, ps: ParameterSet) -> "Powertrain":
        peak_torque = ps["motor.peak_torque"]
        return cls(
            peak_power=ps["motor.peak_power"],
            peak_torque=peak_torque,
            max_speed=rad_s(ps["motor.max_speed"]),
            continuous_power_fraction=ps["motor.continuous_power_fraction"],
            gear_ratio=ps["transmission.gear_ratio"],
            gear_efficiency=ps["transmission.efficiency"],
            wheel_radius=ps["tyres.dynamic_radius"],
            k_copper=ps["motor.loss_k_copper"],
            k_iron=ps["motor.loss_k_iron"],
            k_windage=ps["motor.loss_k_windage"],
            p_constant=ps["motor.loss_p_constant"],
            regen_enabled=bool(ps.raw.get("regeneration", {}).get("enabled", True)),
            max_regen_power=ps["regeneration.max_regen_power"],
            max_regen_torque=peak_torque * ps["regeneration.max_regen_torque_fraction"],
            regen_cutoff_speed=ps["regeneration.cutoff_speed"],
            regen_blend_speed=ps["regeneration.blend_speed"],
        )

    # ----------------------------------------------------------- kinematics
    @property
    def base_speed(self) -> float:
        """Motor speed at the corner point of the envelope [rad/s]."""
        return self.peak_power / self.peak_torque

    @property
    def base_vehicle_speed(self) -> float:
        """Vehicle speed at the motor corner point [m/s]."""
        return self.motor_to_vehicle_speed(self.base_speed)

    @property
    def max_vehicle_speed(self) -> float:
        """Vehicle speed at maximum motor speed [m/s]."""
        return self.motor_to_vehicle_speed(self.max_speed)

    def motor_speed(self, v: ArrayLike) -> ArrayLike:
        """Vehicle speed [m/s] -> motor angular speed [rad/s]."""
        return np.asarray(v) * self.gear_ratio / self.wheel_radius

    def motor_to_vehicle_speed(self, omega: ArrayLike) -> ArrayLike:
        """Motor angular speed [rad/s] -> vehicle speed [m/s]."""
        return np.asarray(omega) * self.wheel_radius / self.gear_ratio

    # ------------------------------------------------------------- envelope
    def max_motor_torque(self, omega: ArrayLike) -> np.ndarray:
        """Peak shaft torque available at motor speed ``omega`` [N*m]."""
        omega = np.abs(np.asarray(omega, dtype=float))
        torque = np.where(
            omega <= self.base_speed,
            self.peak_torque,
            self.peak_power / np.maximum(omega, 1e-6),
        )
        return np.where(omega > self.max_speed, 0.0, torque)

    def max_tractive_force(self, v: ArrayLike) -> np.ndarray:
        """Maximum force the drive unit can put on the road at speed ``v`` [N]."""
        torque = self.max_motor_torque(self.motor_speed(v))
        return torque * self.gear_ratio * self.gear_efficiency / self.wheel_radius

    def max_motor_power(self, omega: ArrayLike) -> np.ndarray:
        """Shaft power envelope [W]."""
        return self.max_motor_torque(omega) * np.abs(np.asarray(omega, dtype=float))

    def continuous_tractive_force(self, v: ArrayLike) -> np.ndarray:
        """Thermally sustainable tractive force [N]."""
        omega = np.abs(self.motor_speed(v))
        p_cont = self.peak_power * self.continuous_power_fraction
        t_cont = np.minimum(
            self.peak_torque * self.continuous_power_fraction,
            p_cont / np.maximum(omega, 1e-6),
        )
        t_cont = np.where(omega > self.max_speed, 0.0, t_cont)
        return t_cont * self.gear_ratio * self.gear_efficiency / self.wheel_radius

    # --------------------------------------------------------------- losses
    def loss(self, torque: ArrayLike, omega: ArrayLike) -> np.ndarray:
        """Combined motor + inverter loss [W] for a shaft operating point."""
        torque = np.abs(np.asarray(torque, dtype=float))
        omega = np.abs(np.asarray(omega, dtype=float))
        return (
            self.k_copper * torque**2
            + self.k_iron * omega
            + self.k_windage * omega**3
            + self.p_constant
        )

    def efficiency(self, torque: ArrayLike, omega: ArrayLike) -> np.ndarray:
        """Motoring efficiency P_shaft / P_electrical at an operating point."""
        p_shaft = np.abs(np.asarray(torque, dtype=float)) * np.abs(
            np.asarray(omega, dtype=float)
        )
        p_elec = p_shaft + self.loss(torque, omega)
        return np.divide(p_shaft, p_elec, out=np.zeros_like(p_elec), where=p_elec > 0)

    def efficiency_map(
        self, n_speed: int = 160, n_torque: int = 160
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Grid of (motor speed, torque, efficiency) inside the envelope.

        Points outside the torque envelope are returned as ``NaN`` so they are
        left blank when the map is contoured.
        """
        omega = np.linspace(1.0, self.max_speed, n_speed)
        torque = np.linspace(1.0, self.peak_torque, n_torque)
        grid_w, grid_t = np.meshgrid(omega, torque)
        eff = self.efficiency(grid_t, grid_w)
        envelope = self.max_motor_torque(grid_w)
        return grid_w, grid_t, np.where(grid_t <= envelope, eff, np.nan)

    # --------------------------------------------------- wheel <-> electrical
    def electrical_power_motoring(
        self, wheel_force: ArrayLike, v: ArrayLike
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Electrical power drawn to deliver ``wheel_force`` at speed ``v``.

        Returns ``(p_electrical, motor_torque, motor_omega)``; power in W.
        """
        wheel_force = np.asarray(wheel_force, dtype=float)
        omega = self.motor_speed(v)
        motor_torque = (
            wheel_force * self.wheel_radius / (self.gear_ratio * self.gear_efficiency)
        )
        p_shaft = motor_torque * omega
        p_elec = p_shaft + self.loss(motor_torque, omega)
        return p_elec, motor_torque, omega

    def electrical_power_regen(
        self, wheel_force: ArrayLike, v: ArrayLike
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Electrical power recovered from a braking force at the wheels.

        ``wheel_force`` is the magnitude of the braking force taken by the motor.
        Returns ``(p_electrical_negative, motor_torque, motor_omega)``.
        """
        wheel_force = np.abs(np.asarray(wheel_force, dtype=float))
        omega = self.motor_speed(v)
        motor_torque = wheel_force * self.wheel_radius * self.gear_efficiency / self.gear_ratio
        p_shaft = motor_torque * omega
        p_elec = p_shaft - self.loss(motor_torque, omega)
        # Below break-even the machine consumes more than it recovers.
        p_elec = np.maximum(p_elec, 0.0)
        return -p_elec, motor_torque, omega

    # --------------------------------------------------------- regen limits
    def regen_blend_factor(self, v: ArrayLike) -> np.ndarray:
        """Fraction of regen authority available at speed ``v`` (0 ... 1).

        Regeneration is blended out at low speed because the machine can no
        longer produce useful torque and the friction brakes must take over.
        """
        v = np.abs(np.asarray(v, dtype=float))
        span = max(self.regen_blend_speed - self.regen_cutoff_speed, 1e-6)
        return np.clip((v - self.regen_cutoff_speed) / span, 0.0, 1.0)

    def max_regen_wheel_force(self, v: ArrayLike) -> np.ndarray:
        """Largest braking force [N] the motor may take at the wheels.

        Limited simultaneously by (a) the motor torque envelope, (b) the regen
        torque ceiling, (c) the battery charge-power ceiling and (d) the
        low-speed blend-out.
        """
        if not self.regen_enabled:
            return np.zeros_like(np.asarray(v, dtype=float))

        v = np.abs(np.asarray(v, dtype=float))
        omega = self.motor_speed(v)

        torque_limit = np.minimum(self.max_motor_torque(omega), self.max_regen_torque)
        force_torque = torque_limit * self.gear_ratio / (
            self.wheel_radius * max(self.gear_efficiency, 1e-6)
        )

        # Power ceiling: P_batt = F * v * eta  ->  F = P / (v * eta)
        with np.errstate(divide="ignore", invalid="ignore"):
            force_power = np.where(
                v > 1e-3, self.max_regen_power / np.maximum(v, 1e-3), np.inf
            )

        return np.minimum(force_torque, force_power) * self.regen_blend_factor(v)
