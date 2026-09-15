"""Vehicle performance characteristics (FR-4).

Derives the speed and acceleration characteristic curves of the vehicle from
the road-load model and the powertrain envelope:

* tractive force available at the wheels versus speed, against the resistance
  curve, including the tyre adhesion limit with dynamic axle-load transfer;
* maximum acceleration versus speed;
* the full-throttle launch (speed versus time) and the 0-100 km/h time;
* top speed, and gradeability versus speed.

Adhesion limit
--------------
A rear-wheel-drive vehicle cannot use more force than the rear tyres can carry.
Accelerating transfers load onto the driven axle, so the limit is implicit:

    N_rear  = chi * m * g * cos(alpha) + m * a * h / L
    F_adh   = mu * N_rear
    a       = (F - F_res) / (lambda * m)

Eliminating ``a`` gives a closed-form adhesion-limited tractive force

    F_adh = [ mu*chi*m*g*cos(alpha) - mu*h*F_res/(L*lambda) ] / [ 1 - mu*h/(L*lambda) ]
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .parameters import ParameterSet
from .powertrain import Powertrain
from .roadload import RoadLoad
from .units import MPS_TO_KPH, mps

ArrayLike = float | np.ndarray


@dataclasses.dataclass
class PerformanceResult:
    """Outcome of the performance analysis."""

    speed: np.ndarray                  # m/s, analysis grid
    tractive_force: np.ndarray         # N, motor envelope at the wheels
    adhesion_force: np.ndarray         # N, tyre limit
    available_force: np.ndarray        # N, min of the two
    resistance: np.ndarray             # N
    mechanical: np.ndarray             # N, rolling + driveline drag
    aerodynamic: np.ndarray            # N
    resistance_physical: np.ndarray    # N, textbook decomposition, for comparison
    acceleration: np.ndarray           # m/s^2, maximum
    wheel_power: np.ndarray            # W, available at the wheels
    top_speed: float                   # m/s
    top_speed_limit: str               # which constraint sets the top speed
    launch_time: np.ndarray            # s, full-throttle launch
    launch_speed: np.ndarray           # m/s
    accel_times: dict[str, float]      # named benchmark times [s]

    def time_to(self, speed_kph: float) -> float:
        """Time to reach a given speed from rest [s] (``inf`` if unreachable)."""
        target = mps(speed_kph)
        if target > self.launch_speed[-1]:
            return float("inf")
        return float(np.interp(target, self.launch_speed, self.launch_time))


class PerformanceModel:
    """Full-throttle performance of the vehicle."""

    def __init__(self, ps: ParameterSet) -> None:
        self.ps = ps
        self.road = RoadLoad.from_parameters(ps)
        self.powertrain = Powertrain.from_parameters(ps)
        self.mu = ps["tyres.peak_friction_coefficient"]
        self.cg_height = ps["mass.cg_height"]
        self.wheelbase = ps["mass.wheelbase"]
        self.rear_fraction = ps["mass.rear_axle_static_load_fraction"]
        self.speed_limiter = mps(ps["reference.speed_limiter"])

    # ------------------------------------------------------------- adhesion
    def adhesion_limit(self, v: ArrayLike) -> np.ndarray:
        """Maximum tractive force the driven axle can transmit [N]."""
        road = self.road
        resistance = np.asarray(road.resistance(v), dtype=float)
        weight = road.mass * road.gravity * np.cos(road.grade)
        transfer = self.mu * self.cg_height / (
            self.wheelbase * road.rotational_factor
        )
        denominator = 1.0 - transfer
        if denominator <= 0:
            return np.full_like(resistance, np.inf)
        numerator = (
            self.mu * self.rear_fraction * weight - transfer * resistance
        )
        return np.maximum(numerator / denominator, 0.0)

    # ------------------------------------------------- characteristic curves
    def acceleration_curve(self, v: ArrayLike) -> np.ndarray:
        """Maximum achievable acceleration at each speed [m/s^2]."""
        force = np.minimum(
            self.powertrain.max_tractive_force(v), self.adhesion_limit(v)
        )
        surplus = force - np.asarray(self.road.resistance(v), dtype=float)
        return surplus / self.road.effective_mass()

    def top_speed(self) -> tuple[float, str]:
        """Top speed [m/s] and the name of the constraint that sets it.

        Three things can cap the top speed of a battery-electric vehicle, and
        which one binds is a design statement worth reporting:

        ``"tractive force balance"``
            The drive can no longer overcome the running resistance.
        ``"maximum motor speed"``
            The machine reaches its mechanical speed limit first, which is
            common on a single-speed drivetrain.
        ``"electronic limiter"``
            The vehicle is held below its mechanical capability by software.
        """
        v_ceiling = self.powertrain.max_vehicle_speed
        v_grid = np.linspace(0.0, v_ceiling, 4000)
        surplus = (
            np.minimum(
                self.powertrain.max_tractive_force(v_grid),
                self.adhesion_limit(v_grid),
            )
            - np.asarray(self.road.resistance(v_grid), dtype=float)
        )
        positive = surplus > 0
        if not positive.any():
            return 0.0, "tractive force balance"

        last = int(np.max(np.flatnonzero(positive)))
        if last >= v_grid.size - 1:
            # Still pulling at the motor's speed limit: the drivetrain caps it.
            v_unlimited, reason = float(v_ceiling), "maximum motor speed"
        else:
            # Linear interpolation of the zero crossing of the surplus force.
            v0, v1 = v_grid[last], v_grid[last + 1]
            s0, s1 = surplus[last], surplus[last + 1]
            v_unlimited = float(v0 + (v1 - v0) * s0 / (s0 - s1))
            reason = "tractive force balance"

        if 0 < self.speed_limiter < v_unlimited:
            return self.speed_limiter, "electronic limiter"
        return v_unlimited, reason

    def launch(self, v_end: float, n: int = 4000) -> tuple[np.ndarray, np.ndarray]:
        """Full-throttle launch from rest.

        Integrates ``t = integral(dv / a(v))`` on a fine speed grid, which is
        numerically far better behaved near standstill than stepping in time.
        """
        v = np.linspace(0.0, v_end, n)
        a = self.acceleration_curve(v)
        if np.any(a <= 0):
            first_zero = int(np.argmax(a <= 0))
            v, a = v[:first_zero], a[:first_zero]
        inverse = 1.0 / a
        time = np.concatenate([[0.0], np.cumsum(np.diff(v) * 0.5 * (inverse[:-1] + inverse[1:]))])
        return time, v

    def gradeability(self, v: ArrayLike) -> np.ndarray:
        """Maximum climbable gradient [%] at steady speed.

        At steady speed the surplus force goes entirely into the grade term,
        ``F_avail = F_roll + F_aero + m*g*sin(alpha)``.
        """
        v = np.asarray(v, dtype=float)
        road = self.road
        force = np.minimum(
            self.powertrain.max_tractive_force(v), self.adhesion_limit(v)
        )
        flat = np.asarray(road.running_resistance(v), dtype=float)
        sin_alpha = np.clip((force - flat) / (road.mass * road.gravity), -1.0, 1.0)
        return np.tan(np.arcsin(sin_alpha)) * 100.0

    # ------------------------------------------------------------- full run
    def run(self, n_points: int = 1200) -> PerformanceResult:
        """Evaluate every characteristic curve and benchmark time."""
        top_speed, top_speed_limit = self.top_speed()
        v_max_plot = max(top_speed * 1.05, mps(10.0))
        v = np.linspace(0.0, v_max_plot, n_points)

        tractive = self.powertrain.max_tractive_force(v)
        adhesion = self.adhesion_limit(v)
        available = np.minimum(tractive, adhesion)
        parts = self.road.components(v)
        mechanical = np.asarray(parts["mechanical"], dtype=float)
        aero = np.asarray(parts["aerodynamic"], dtype=float)
        resistance = np.asarray(self.road.resistance(v), dtype=float)
        from .roadload import PHYSICAL

        resistance_physical = np.asarray(
            self.road.with_model(PHYSICAL).resistance(v), dtype=float
        )
        acceleration = (available - resistance) / self.road.effective_mass()

        launch_time, launch_speed = self.launch(top_speed * 0.999)

        benchmarks = {}
        for label, target in (
            ("0-50 km/h", 50.0),
            ("0-100 km/h", 100.0),
            ("0-130 km/h", 130.0),
            ("0-160 km/h", 160.0),
        ):
            target_mps = mps(target)
            benchmarks[label] = (
                float(np.interp(target_mps, launch_speed, launch_time))
                if target_mps <= launch_speed[-1]
                else float("inf")
            )

        return PerformanceResult(
            speed=v,
            tractive_force=tractive,
            adhesion_force=adhesion,
            available_force=available,
            resistance=resistance,
            mechanical=mechanical,
            aerodynamic=aero,
            resistance_physical=resistance_physical,
            acceleration=acceleration,
            wheel_power=available * v,
            top_speed=top_speed,
            top_speed_limit=top_speed_limit,
            launch_time=launch_time,
            launch_speed=launch_speed,
            accel_times=benchmarks,
        )

    # ------------------------------------------------------------ validation
    def validation(self) -> list[dict[str, object]]:
        """Compare the model against the manufacturer's published figures."""
        result = self.run()
        rows = []

        published_accel = self.ps["reference.acceleration_0_100_kph"]
        simulated_accel = result.accel_times["0-100 km/h"]
        rows.append(
            {
                "quantity": "0-100 km/h",
                "unit": "s",
                "simulated": simulated_accel,
                "published": published_accel,
                "deviation_pct": (simulated_accel - published_accel) / published_accel * 100.0,
                "tolerance_pct": 10.0,
            }
        )

        published_top = self.ps["reference.top_speed"]
        simulated_top = result.top_speed * MPS_TO_KPH
        rows.append(
            {
                "quantity": "Top speed",
                "unit": "km/h",
                "simulated": simulated_top,
                "published": published_top,
                "deviation_pct": (simulated_top - published_top) / published_top * 100.0,
                "tolerance_pct": 5.0,
            }
        )
        for row in rows:
            row["pass"] = abs(row["deviation_pct"]) <= row["tolerance_pct"]
        return rows
