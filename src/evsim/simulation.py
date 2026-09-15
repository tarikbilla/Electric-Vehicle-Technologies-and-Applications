"""Time-stepped driving-cycle simulation (FR-6, FR-7).

For every step of the cycle the model resolves the chain

    speed demand -> wheel force -> motor torque -> electrical power -> battery

A *backward-facing* (quasi-static) formulation is used, the standard approach
for energy and range studies: the speed trace is the input and the model asks
what the powertrain must do to follow it.  Where the powertrain cannot follow,
the achievable acceleration is substituted and the step is flagged, so the
simulation degrades gracefully instead of silently reporting an impossible
result.

Within each step the forces are evaluated at the mid-point speed, which makes
the integration second-order accurate rather than first-order.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .battery import Battery
from .cycles import DrivingCycle
from .parameters import ParameterSet
from .powertrain import Powertrain
from .roadload import RoadLoad
from .units import J_PER_KWH, MPS_TO_KPH


@dataclasses.dataclass
class SimulationResult:
    """Per-step traces and aggregate energy results of one cycle run."""

    cycle_name: str
    time: np.ndarray                  # s
    speed_target: np.ndarray          # m/s, demanded
    speed: np.ndarray                 # m/s, achieved
    acceleration: np.ndarray          # m/s^2, achieved
    distance: np.ndarray              # m, cumulative
    force_wheel: np.ndarray           # N, at the wheels (+drive, -brake)
    force_friction_brake: np.ndarray  # N, taken by the friction brakes
    power_wheel: np.ndarray           # W
    power_motor_shaft: np.ndarray     # W
    power_battery: np.ndarray         # W, terminal (+discharge, -charge)
    power_auxiliary: np.ndarray       # W
    motor_torque: np.ndarray          # N*m
    motor_speed: np.ndarray           # rad/s
    soc: np.ndarray                   # -
    unmet: np.ndarray                 # bool, powertrain could not follow
    limited: np.ndarray               # bool, a battery limit was active
    # Aggregate energies [J]
    energy_traction: float = 0.0
    energy_regen: float = 0.0
    energy_auxiliary: float = 0.0
    energy_net: float = 0.0
    energy_friction_brake: float = 0.0
    energy_resistance: float = 0.0
    depleted: bool = False

    # ------------------------------------------------------------- summary
    @property
    def total_distance(self) -> float:
        return float(self.distance[-1])

    @property
    def total_distance_km(self) -> float:
        return self.total_distance / 1000.0

    @property
    def consumption_wh_per_km(self) -> float:
        """Net energy at the battery terminals per kilometre [Wh/km]."""
        if self.total_distance <= 0:
            return float("nan")
        return self.energy_net / 3600.0 / self.total_distance_km

    @property
    def consumption_kwh_per_100km(self) -> float:
        return self.consumption_wh_per_km / 10.0

    @property
    def regen_fraction(self) -> float:
        """Share of traction energy recovered by regenerative braking."""
        if self.energy_traction <= 0:
            return 0.0
        return self.energy_regen / self.energy_traction

    @property
    def unmet_count(self) -> int:
        return int(np.sum(self.unmet))

    @property
    def max_tracking_error_kph(self) -> float:
        return float(np.max(np.abs(self.speed - self.speed_target))) * MPS_TO_KPH

    def summary(self) -> dict[str, float]:
        return {
            "distance_km": self.total_distance_km,
            "energy_traction_kwh": self.energy_traction / J_PER_KWH,
            "energy_regen_kwh": self.energy_regen / J_PER_KWH,
            "energy_auxiliary_kwh": self.energy_auxiliary / J_PER_KWH,
            "energy_friction_brake_kwh": self.energy_friction_brake / J_PER_KWH,
            "energy_net_kwh": self.energy_net / J_PER_KWH,
            "consumption_wh_per_km": self.consumption_wh_per_km,
            "consumption_kwh_per_100km": self.consumption_kwh_per_100km,
            "regen_fraction": self.regen_fraction,
            "soc_start": float(self.soc[0]),
            "soc_end": float(self.soc[-1]),
            "unmet_steps": float(self.unmet_count),
            "max_tracking_error_kph": self.max_tracking_error_kph,
        }


class CycleSimulator:
    """Quasi-static backward-facing simulator for a single vehicle."""

    def __init__(self, ps: ParameterSet, auxiliary_power: float | None = None) -> None:
        self.ps = ps
        self.road = RoadLoad.from_parameters(ps)
        self.powertrain = Powertrain.from_parameters(ps)
        self.battery = Battery.from_parameters(ps)
        if auxiliary_power is None:
            auxiliary_power = (
                ps["auxiliaries.base_load"] + ps["auxiliaries.hvac_load"]
            )
        self.auxiliary_power = auxiliary_power

        # Adhesion limit, reused from the performance model.
        from .performance import PerformanceModel

        self._performance = PerformanceModel(ps)

    # ------------------------------------------------------------------ run
    def run(
        self,
        cycle: DrivingCycle,
        soc_start: float = 1.0,
        stop_when_empty: bool = False,
    ) -> SimulationResult:
        """Simulate one pass of ``cycle`` starting from ``soc_start``."""
        time = cycle.time
        target = cycle.speed
        n = time.size
        dt_all = np.diff(time)

        speed = np.zeros(n)
        accel = np.zeros(n)
        distance = np.zeros(n)
        f_wheel = np.zeros(n)
        f_brake = np.zeros(n)
        p_wheel = np.zeros(n)
        p_shaft = np.zeros(n)
        p_batt = np.zeros(n)
        p_aux = np.zeros(n)
        torque = np.zeros(n)
        omega = np.zeros(n)
        soc = np.zeros(n)
        unmet = np.zeros(n, dtype=bool)
        limited = np.zeros(n, dtype=bool)

        speed[0] = target[0]
        soc[0] = soc_start

        e_traction = e_regen = e_aux = e_brake = e_resist = 0.0
        depleted = False

        for i in range(n - 1):
            dt = float(dt_all[i])
            v0 = speed[i]
            v_demand = target[i + 1]
            a_demand = (v_demand - v0) / dt

            v_mid = 0.5 * (v0 + v_demand)
            f_required = float(self.road.tractive_force(v_mid, a_demand))

            aux = self.auxiliary_power if not depleted else 0.0

            if f_required >= 0.0:
                # ---------------------------------------------- driving
                f_limit = float(
                    min(
                        self.powertrain.max_tractive_force(v_mid),
                        self._adhesion(v_mid),
                    )
                )
                if depleted:
                    f_limit = 0.0
                f_applied = min(f_required, f_limit)
                if f_applied < f_required - 1e-6:
                    unmet[i + 1] = True
                    a_actual = (
                        f_applied - float(self.road.resistance(v_mid))
                    ) / self.road.effective_mass()
                    v1 = max(v0 + a_actual * dt, 0.0)
                    v_mid = 0.5 * (v0 + v1)
                else:
                    v1 = v_demand

                p_elec, t_motor, w_motor = self.powertrain.electrical_power_motoring(
                    f_applied, v_mid
                )
                p_elec = float(p_elec)
                f_friction = 0.0
            else:
                # ---------------------------------------------- braking
                f_brake_total = -f_required
                f_regen = min(
                    f_brake_total, float(self.powertrain.max_regen_wheel_force(v_mid))
                )
                f_friction = f_brake_total - f_regen
                v1 = v_demand
                f_applied = -f_regen

                p_elec, t_motor, w_motor = self.powertrain.electrical_power_regen(
                    f_regen, v_mid
                )
                p_elec = float(p_elec)
                t_motor = -float(t_motor)

            # ------------------------------------------------- battery step
            p_demand = p_elec + aux
            soc_next, p_applied, _, was_limited = self.battery.step(
                p_demand, soc[i], dt
            )

            if was_limited and p_applied < p_demand - 1e-6 and p_demand > 0:
                unmet[i + 1] = True
            limited[i + 1] = was_limited

            if self.battery.is_depleted(soc_next) and not depleted:
                depleted = True

            if depleted and stop_when_empty:
                speed[i + 1] = v1
                soc[i + 1] = soc_next
                distance[i + 1] = distance[i] + 0.5 * (v0 + v1) * dt
                n = i + 2
                break

            # ---------------------------------------------------- book-keeping
            speed[i + 1] = v1
            accel[i + 1] = (v1 - v0) / dt
            distance[i + 1] = distance[i] + 0.5 * (v0 + v1) * dt
            f_wheel[i + 1] = f_applied
            f_brake[i + 1] = f_friction
            p_wheel[i + 1] = f_applied * v_mid
            p_shaft[i + 1] = float(t_motor) * float(w_motor)
            p_batt[i + 1] = p_applied
            p_aux[i + 1] = aux
            torque[i + 1] = float(t_motor)
            omega[i + 1] = float(w_motor)
            soc[i + 1] = soc_next

            if p_elec >= 0:
                e_traction += p_elec * dt
            else:
                e_regen += -p_elec * dt
            e_aux += aux * dt
            e_brake += f_friction * v_mid * dt
            e_resist += float(self.road.resistance(v_mid)) * v_mid * dt

        sl = slice(0, n)
        result = SimulationResult(
            cycle_name=cycle.name,
            time=time[sl],
            speed_target=target[sl],
            speed=speed[sl],
            acceleration=accel[sl],
            distance=distance[sl],
            force_wheel=f_wheel[sl],
            force_friction_brake=f_brake[sl],
            power_wheel=p_wheel[sl],
            power_motor_shaft=p_shaft[sl],
            power_battery=p_batt[sl],
            power_auxiliary=p_aux[sl],
            motor_torque=torque[sl],
            motor_speed=omega[sl],
            soc=soc[sl],
            unmet=unmet[sl],
            limited=limited[sl],
            energy_traction=e_traction,
            energy_regen=e_regen,
            energy_auxiliary=e_aux,
            energy_friction_brake=e_brake,
            energy_resistance=e_resist,
            depleted=depleted,
        )
        # Net energy actually taken from the battery over the run.
        result.energy_net = float(
            np.sum(result.power_battery[1:] * np.diff(result.time))
        )
        return result

    # -------------------------------------------------------------- helpers
    def _adhesion(self, v: float) -> float:
        return float(self._performance.adhesion_limit(v))
