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
    energy_drivetrain_loss: float = 0.0
    energy_internal: float = 0.0
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
    def consumption_internal_wh_per_km(self) -> float:
        """Energy drawn from the open-circuit source per kilometre [Wh/km].

        Larger than the terminal figure by the pack's own ohmic loss.  This is
        the basis on which the battery's usable energy is defined, so a range
        estimate must divide by this one, not by the terminal consumption.
        """
        if self.total_distance <= 0:
            return float("nan")
        return self.energy_internal / 3600.0 / self.total_distance_km

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
            "energy_drivetrain_loss_kwh": self.energy_drivetrain_loss / J_PER_KWH,
            "energy_road_load_kwh": self.energy_resistance / J_PER_KWH,
            "energy_net_kwh": self.energy_net / J_PER_KWH,
            "consumption_wh_per_km": self.consumption_wh_per_km,
            "consumption_internal_wh_per_km": self.consumption_internal_wh_per_km,
            "consumption_kwh_per_100km": self.consumption_kwh_per_100km,
            "regen_fraction": self.regen_fraction,
            "soc_start": float(self.soc[0]),
            "soc_end": float(self.soc[-1]),
            "unmet_steps": float(self.unmet_count),
            "limited_steps": float(np.sum(self.limited)),
            "max_tracking_error_kph": self.max_tracking_error_kph,
            "depleted": float(self.depleted),
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
        """Simulate one pass of ``cycle`` starting from ``soc_start``.

        Every per-step channel (force, power, torque, motor speed) is evaluated
        at the *mid-point* speed of the step and stored at the step's end index,
        alongside the instantaneous speed, distance and state of charge.  Index
        0 of those channels is therefore always zero: no step has been taken yet.
        """
        time = cycle.time
        target = cycle.speed
        n_full = time.size
        dt_all = np.diff(time)

        speed = np.zeros(n_full)
        accel = np.zeros(n_full)
        distance = np.zeros(n_full)
        f_wheel = np.zeros(n_full)
        f_brake = np.zeros(n_full)
        p_wheel = np.zeros(n_full)
        p_shaft = np.zeros(n_full)
        p_batt = np.zeros(n_full)
        p_aux = np.zeros(n_full)
        torque = np.zeros(n_full)
        omega = np.zeros(n_full)
        soc = np.zeros(n_full)
        unmet = np.zeros(n_full, dtype=bool)
        limited = np.zeros(n_full, dtype=bool)

        speed[0] = target[0]
        soc[0] = soc_start

        e_traction = e_regen = e_aux = e_brake = e_resist = e_internal = 0.0
        e_drive_loss = 0.0
        depleted = False
        n = n_full

        for i in range(n_full - 1):
            dt = float(dt_all[i])
            v0 = speed[i]
            soc_now = soc[i]
            v_demand = target[i + 1]
            a_demand = (v_demand - v0) / dt

            aux = 0.0 if depleted else self.auxiliary_power

            v_mid = 0.5 * (v0 + v_demand)
            f_required = float(self.road.tractive_force(v_mid, a_demand))
            step_unmet = False
            step_limited = False

            if f_required >= 0.0:
                # ------------------------------------------------- driving
                # Mechanical ceiling: motor envelope and tyre adhesion.
                f_ceiling = (
                    0.0
                    if depleted
                    else float(
                        min(
                            float(self.powertrain.max_tractive_force(v_mid)),
                            self._adhesion(v_mid),
                        )
                    )
                )
                f_applied = min(f_required, f_ceiling)

                # Electrical ceiling: what the pack can actually deliver.  This
                # is resolved BEFORE the speed is committed, so a power-limited
                # vehicle slows down instead of following the trace on energy
                # the battery never supplied.
                p_elec = float(
                    self.powertrain.electrical_power_motoring(f_applied, v_mid)[0]
                )
                p_available = self.battery.max_discharge_terminal_power(soc_now, dt)
                if p_elec + aux > p_available + 1e-9:
                    step_limited = True
                    budget = max(p_available - aux, 0.0)
                    f_applied = self._force_for_electrical_power(
                        budget, v_mid, f_applied
                    )

                if f_applied < f_required - 1e-6:
                    step_unmet = True
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
                p_elec, t_motor, w_motor = float(p_elec), float(t_motor), float(w_motor)
                f_friction = 0.0
            else:
                # ------------------------------------------------- braking
                f_brake_total = -f_required
                f_regen = min(
                    f_brake_total, float(self.powertrain.max_regen_wheel_force(v_mid))
                )

                # Charge ceiling: what the pack can absorb this step.  Anything
                # the battery cannot take must go to the friction brakes, or the
                # energy would simply vanish from the balance.
                p_recovered = -float(
                    self.powertrain.electrical_power_regen(f_regen, v_mid)[0]
                )
                p_room = self.battery.max_charge_terminal_power(soc_now, dt)
                if p_recovered > p_room + 1e-9:
                    step_limited = True
                    f_regen = self._regen_force_for_electrical_power(
                        p_room, v_mid, f_regen
                    )

                f_friction = max(f_brake_total - f_regen, 0.0)
                v1 = v_demand
                f_applied = -f_regen

                p_elec, t_motor, w_motor = self.powertrain.electrical_power_regen(
                    f_regen, v_mid
                )
                p_elec, w_motor = float(p_elec), float(w_motor)
                t_motor = -float(t_motor)

            # ------------------------------------------------- battery step
            p_demand = p_elec + aux
            soc_next, p_applied, ohmic, was_limited = self.battery.step(
                p_demand, soc_now, dt
            )
            step_limited = step_limited or was_limited

            if self.battery.is_depleted(soc_next):
                depleted = True

            # ------------------------------------------------- book-keeping
            # Energies are accumulated from the APPLIED power, the same
            # quantity the battery actually saw, so the loop totals and the
            # integral of the power trace can never drift apart.
            # The auxiliary load is served first, so whatever is left of the
            # applied power belongs to the drive unit.  Splitting it this way
            # keeps traction + auxiliary - regen identical to the integral of
            # the battery power trace, whether or not a limit bound.
            motor_electrical = p_applied - aux
            e_traction += max(motor_electrical, 0.0) * dt
            e_regen += max(-motor_electrical, 0.0) * dt
            e_aux += aux * dt
            e_brake += f_friction * v_mid * dt
            e_resist += float(self.road.resistance(v_mid)) * v_mid * dt
            # Drive-unit loss, measured directly rather than inferred by
            # subtraction: electrical power minus wheel power, which is
            # positive in both directions of energy flow.
            e_drive_loss += (motor_electrical - f_applied * v_mid) * dt
            # Energy leaving the open-circuit source, ohmic loss included.
            e_internal += (p_applied + ohmic) * dt

            speed[i + 1] = v1
            accel[i + 1] = (v1 - v0) / dt
            distance[i + 1] = distance[i] + 0.5 * (v0 + v1) * dt
            f_wheel[i + 1] = f_applied
            f_brake[i + 1] = f_friction
            p_wheel[i + 1] = f_applied * v_mid
            p_shaft[i + 1] = t_motor * w_motor
            p_batt[i + 1] = p_applied
            p_aux[i + 1] = aux
            torque[i + 1] = t_motor
            omega[i + 1] = w_motor
            soc[i + 1] = soc_next
            unmet[i + 1] = step_unmet
            limited[i + 1] = step_limited

            if depleted and stop_when_empty:
                n = i + 2
                break

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
            energy_drivetrain_loss=e_drive_loss,
            energy_internal=e_internal,
            depleted=depleted,
        )
        result.energy_net = e_traction + e_aux - e_regen
        return result

    # ---------------------------------------------------- limit resolution
    def _force_for_electrical_power(
        self, power_budget: float, v: float, f_upper: float
    ) -> float:
        """Wheel force whose electrical demand just fits ``power_budget`` [N].

        Bisection on force: the electrical demand is monotonic in it, so 60
        iterations put the answer well inside floating-point noise.
        """
        if power_budget <= 0.0 or f_upper <= 0.0:
            return 0.0
        if float(self.powertrain.electrical_power_motoring(f_upper, v)[0]) <= power_budget:
            return f_upper
        low, high = 0.0, f_upper
        for _ in range(60):
            mid = 0.5 * (low + high)
            if float(self.powertrain.electrical_power_motoring(mid, v)[0]) > power_budget:
                high = mid
            else:
                low = mid
        return low

    def _regen_force_for_electrical_power(
        self, power_budget: float, v: float, f_upper: float
    ) -> float:
        """Braking force whose recovered power just fits ``power_budget`` [N]."""
        if power_budget <= 0.0 or f_upper <= 0.0:
            return 0.0
        recovered = -float(self.powertrain.electrical_power_regen(f_upper, v)[0])
        if recovered <= power_budget:
            return f_upper
        low, high = 0.0, f_upper
        for _ in range(60):
            mid = 0.5 * (low + high)
            if -float(self.powertrain.electrical_power_regen(mid, v)[0]) > power_budget:
                high = mid
            else:
                low = mid
        return low

    # -------------------------------------------------------------- helpers
    def _adhesion(self, v: float) -> float:
        return float(self._performance.adhesion_limit(v))
