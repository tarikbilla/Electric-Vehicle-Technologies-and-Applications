"""Battery model (FR-7): energy book-keeping with an internal-resistance model.

An *Rint* equivalent circuit is used: an SOC-dependent open-circuit voltage in
series with a constant internal resistance.

    V_terminal = V_oc(SOC) - I * R_i
    P_terminal = V_oc * I - I^2 * R_i

Solving for current at a demanded terminal power gives

    I = ( V_oc - sqrt(V_oc^2 - 4 * R_i * P_terminal) ) / (2 * R_i)

The radicand becomes negative beyond the resistance-limited power ceiling
``V_oc^2 / (4 R_i)``, which the model reports as a power limit rather than
silently returning a complex number.

State of charge is tracked in ampere-hours, so the ohmic loss ``I^2 R_i`` is
charged against the pack rather than being ignored, and is therefore correctly
counted twice on a regen-heavy cycle (once on discharge, once on charge).
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .parameters import ParameterSet
from .units import J_PER_KWH

ArrayLike = float | np.ndarray


@dataclasses.dataclass
class Battery:
    """Traction battery with an Rint equivalent circuit."""

    gross_energy: float        # J, nameplate
    usable_fraction: float     # -
    nominal_voltage: float     # V
    internal_resistance: float # ohm
    max_discharge_power: float # W, terminal
    max_charge_power: float    # W, terminal
    soc_min: float
    soc_max: float
    ocv_soc: np.ndarray        # -, breakpoints
    ocv_pu: np.ndarray         # -, OCV / nominal voltage

    # ------------------------------------------------------------ construction
    @classmethod
    def from_parameters(cls, ps: ParameterSet) -> "Battery":
        return cls(
            gross_energy=ps["battery.gross_capacity"] * J_PER_KWH,
            usable_fraction=ps["battery.usable_fraction"],
            nominal_voltage=ps["battery.nominal_voltage"],
            internal_resistance=ps["battery.internal_resistance"],
            max_discharge_power=ps["battery.max_discharge_power"],
            max_charge_power=ps["battery.max_charge_power"],
            soc_min=ps["battery.soc_min"],
            soc_max=ps["battery.soc_max"],
            ocv_soc=np.asarray(ps.node("battery.ocv_soc_points"), dtype=float),
            ocv_pu=np.asarray(ps.node("battery.ocv_voltage_pu"), dtype=float),
        )

    # --------------------------------------------------------------- capacity
    @property
    def usable_energy(self) -> float:
        """Usable energy measured at the terminals under nominal conditions [J]."""
        return self.gross_energy * self.usable_fraction

    @property
    def usable_energy_kwh(self) -> float:
        return self.usable_energy / J_PER_KWH

    @property
    def mean_open_circuit_voltage(self) -> float:
        """SOC-averaged open-circuit voltage over the usable window [V].

        Integrating the OCV curve rather than using the nominal voltage keeps
        the model self-consistent: a slow full discharge then delivers exactly
        the nameplate usable energy, independent of the shape of the OCV curve.
        """
        soc = np.linspace(self.soc_min, self.soc_max, 501)
        return float(np.trapezoid(self.open_circuit_voltage(soc), soc) /
                     (self.soc_max - self.soc_min))

    @property
    def capacity_ah(self) -> float:
        """Usable charge capacity [A*h].

        Sized so that ``integral(V_oc dQ)`` over the usable SOC window equals
        the nameplate usable energy.
        """
        return self.usable_energy / (self.mean_open_circuit_voltage * 3600.0)

    # -------------------------------------------------------------- behaviour
    def open_circuit_voltage(self, soc: ArrayLike) -> np.ndarray:
        """Open-circuit voltage [V] at a state of charge (0 ... 1)."""
        soc = np.clip(np.asarray(soc, dtype=float), 0.0, 1.0)
        return np.interp(soc, self.ocv_soc, self.ocv_pu) * self.nominal_voltage

    def power_limit(self, soc: ArrayLike) -> float:
        """Resistance-limited maximum terminal power [W] at this SOC."""
        v_oc = float(np.asarray(self.open_circuit_voltage(soc)).reshape(-1)[0])
        return v_oc**2 / (4.0 * self.internal_resistance)

    def current(self, power_terminal: float, soc: float) -> tuple[float, bool]:
        """Pack current [A] for a demanded terminal power (positive = discharge).

        Returns ``(current, limited)`` where ``limited`` says whether the demand
        had to be clipped to the resistance-limited ceiling.
        """
        v_oc = float(self.open_circuit_voltage(soc))
        r_i = self.internal_resistance
        limited = False

        ceiling = v_oc**2 / (4.0 * r_i)
        if power_terminal > ceiling:
            power_terminal = ceiling
            limited = True

        radicand = v_oc**2 - 4.0 * r_i * power_terminal
        radicand = max(radicand, 0.0)
        return (v_oc - np.sqrt(radicand)) / (2.0 * r_i), limited

    def clip_power(self, power_terminal: float, soc: float) -> tuple[float, bool]:
        """Clip a demanded terminal power to the discharge/charge/ohmic limits."""
        limited = False
        if power_terminal > self.max_discharge_power:
            power_terminal, limited = self.max_discharge_power, True
        elif power_terminal < -self.max_charge_power:
            power_terminal, limited = -self.max_charge_power, True

        ceiling = self.power_limit(soc)
        if power_terminal > ceiling:
            power_terminal, limited = ceiling, True
        return power_terminal, limited

    def step(
        self, power_terminal: float, soc: float, dt: float
    ) -> tuple[float, float, float, bool]:
        """Advance the pack by ``dt`` at a demanded terminal power.

        Parameters
        ----------
        power_terminal : positive to discharge, negative to charge [W]
        soc            : state of charge at the start of the step (0 ... 1)
        dt             : step length [s]

        Returns
        -------
        (soc_new, power_applied, ohmic_loss, limited)
        """
        power_applied, limited = self.clip_power(power_terminal, soc)
        current, current_limited = self.current(power_applied, soc)
        limited = limited or current_limited

        ohmic_loss = current**2 * self.internal_resistance
        delta_ah = current * dt / 3600.0
        soc_new = soc - delta_ah / self.capacity_ah
        return float(np.clip(soc_new, 0.0, 1.0)), power_applied, ohmic_loss, limited

    def is_depleted(self, soc: float) -> bool:
        return soc <= self.soc_min + 1e-9
