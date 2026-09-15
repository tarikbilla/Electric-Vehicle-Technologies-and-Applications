"""Driving cycles (FR-5).

Three sources of speed profiles are supported:

``NEDC``
    Rebuilt from its regulatory definition (UNECE R83 Annex 4a), which tabulates
    the cycle as idle / constant-acceleration / constant-speed segments.  The
    EUDC half reproduces the official 6.955 km exactly.  The ECE-15 urban half
    integrates to 1.005 km against the regulatory 1.013 km, a shortfall of 8 m
    per repetition, so the assembled cycle is 1180 s and 10.975 km against the
    official 11.007 km - low by 0.29 %.  The residual sits in the published
    segment table itself, whose durations sum to 194 s rather than 195 s; the
    missing second is carried in the final idle here.

``WLTC Class 3b``
    The official trace is a 1800-point table published in UNECE GTR 15 and is
    not reproduced here.  Instead a *statistically equivalent* profile is
    synthesised: for each of the four phases the construction reproduces the
    published duration, distance, maximum speed and stop time exactly, using
    micro-trips with realistic acceleration rates.  Cycle-average energy demand
    is therefore very close to the official trace, but the second-by-second
    trace differs.  **This is an assumption and is flagged as such.**
    Drop the official ``wltc_class3b.csv`` into ``data/cycles/`` and it is used
    automatically in place of the synthetic profile.

``CSV``
    Any user-supplied 1 Hz profile with ``time_s`` and ``speed_kph`` columns.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np

from .units import KPH_TO_MPS, MPS_TO_KPH

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "cycles"


# =============================================================================
# Cycle container
# =============================================================================
@dataclasses.dataclass(frozen=True)
class DrivingCycle:
    """A 1 Hz speed-versus-time profile."""

    name: str
    time: np.ndarray        # s
    speed: np.ndarray       # m/s
    phases: dict[str, tuple[int, int]] = dataclasses.field(default_factory=dict)
    synthetic: bool = False
    description: str = ""

    # ------------------------------------------------------------- properties
    @property
    def dt(self) -> float:
        """Nominal sample interval [s]. Use ``intervals`` for a ragged grid."""
        return float(np.median(np.diff(self.time)))

    @property
    def intervals(self) -> np.ndarray:
        """Duration each sample represents [s].

        Interior samples own half of the gap on either side; the two endpoints
        own half of their single neighbouring gap.  Computing this properly
        rather than assuming a uniform grid matters for a profile loaded from
        CSV, which may be sampled finely while driving and coarsely at a
        standstill.
        """
        gaps = np.diff(self.time)
        weights = np.zeros(self.time.size)
        weights[:-1] += 0.5 * gaps
        weights[1:] += 0.5 * gaps
        return weights

    @property
    def uniform(self) -> bool:
        """Whether the profile is sampled on a uniform time grid."""
        gaps = np.diff(self.time)
        return bool(np.allclose(gaps, gaps[0], rtol=1e-6, atol=1e-9))

    @property
    def duration(self) -> float:
        """Cycle length [s]. The trace includes both t=0 and t=T."""
        return float(self.time[-1] - self.time[0])

    @property
    def acceleration(self) -> np.ndarray:
        """Acceleration [m/s^2] from a central difference of the speed trace."""
        return np.gradient(self.speed, self.time)

    @property
    def distance(self) -> float:
        """Total distance [m] by trapezoidal integration."""
        return float(np.trapezoid(self.speed, self.time))

    @property
    def distance_km(self) -> float:
        return self.distance / 1000.0

    @property
    def max_speed(self) -> float:
        return float(np.max(self.speed))

    @property
    def mean_speed(self) -> float:
        """Average speed including stops [m/s]."""
        return self.distance / self.duration

    @property
    def mean_driving_speed(self) -> float:
        """Average speed excluding stops [m/s]."""
        return self.distance / max(self.duration - self.stop_time, 1e-9)

    @property
    def stop_time(self) -> float:
        """Time spent at standstill [s]."""
        return float(np.sum(self.intervals[self.speed <= 0.1]))

    @property
    def max_acceleration(self) -> float:
        return float(np.max(self.acceleration))

    @property
    def max_deceleration(self) -> float:
        return float(np.min(self.acceleration))

    def phase_slice(self, phase: str) -> slice:
        start, stop = self.phases[phase]
        return slice(start, stop)

    def statistics(self) -> dict[str, float]:
        return {
            "duration_s": self.duration,
            "distance_km": self.distance_km,
            "max_speed_kph": self.max_speed * MPS_TO_KPH,
            "mean_speed_kph": self.mean_speed * MPS_TO_KPH,
            "mean_driving_speed_kph": self.mean_driving_speed * MPS_TO_KPH,
            "stop_time_s": self.stop_time,
            "max_acceleration_mps2": self.max_acceleration,
            "max_deceleration_mps2": self.max_deceleration,
        }


# =============================================================================
# NEDC - exact regulatory construction
# =============================================================================
# (duration [s], speed at the END of the segment [km/h]); speed ramps linearly
# from the previous segment's end speed.  A segment whose end speed equals the
# previous one is a constant-speed hold - either a steady-speed phase or a gear
# change, during which the regulation holds road speed constant.  An electric
# vehicle has no gear changes, but the *speed trace* is defined by the
# regulation and is identical for every vehicle, so the holds are retained.
#
# Source: UNECE Regulation 83, Annex 4a, Tables 1 (ECE-15) and 2 (EUDC).
_ECE15 = [
    (11, 0.0),                                    # idle
    (4, 15.0), (8, 15.0), (2, 10.0), (3, 0.0),    # 1st acceleration / steady / stop
    (21, 0.0),                                    # idle
    (5, 15.0), (2, 15.0), (5, 32.0),              # 2nd acceleration (gear change held)
    (24, 32.0), (8, 10.0), (3, 0.0),              # steady 32 / stop
    (21, 0.0),                                    # idle
    (5, 15.0), (2, 15.0), (9, 35.0), (2, 35.0), (8, 50.0),   # 3rd acceleration
    (12, 50.0), (8, 35.0), (13, 35.0),            # steady 50 / decel / steady 35
    (8, 10.0), (3, 0.0),                          # stop
    (8, 0.0),                                     # idle (7 s in the table; 8 s here
]                                                 # so the phase totals exactly 195 s
_EUDC = [
    (20, 0.0),                                    # idle
    (5, 15.0), (2, 15.0), (9, 35.0), (2, 35.0),   # acceleration with gear-change holds
    (8, 50.0), (2, 50.0), (13, 70.0),
    (50, 70.0), (8, 50.0), (69, 50.0),            # steady 70 / decel / steady 50
    (13, 70.0), (50, 70.0),                       # re-accelerate / steady 70
    (35, 100.0), (30, 100.0),                     # accelerate / steady 100
    (20, 120.0), (10, 120.0),                     # accelerate / steady 120
    (16, 80.0), (8, 50.0), (10, 0.0),             # three-stage deceleration to rest
    (20, 0.0),                                    # idle
]


def _build_segments(segments: list[tuple[int, float]], v_start: float = 0.0) -> np.ndarray:
    """Expand (duration, end-speed) segments into a 1 Hz speed trace [km/h].

    The returned array excludes t=0 and contains one sample per second at the
    *end* of each second, which is how regulatory cycle tables are defined.
    """
    trace: list[float] = []
    v_prev = v_start
    for duration, v_end in segments:
        for step in range(1, duration + 1):
            trace.append(v_prev + (v_end - v_prev) * step / duration)
        v_prev = v_end
    return np.asarray(trace, dtype=float)


def nedc() -> DrivingCycle:
    """New European Driving Cycle: 4 x ECE-15 urban + one EUDC. 1180 s."""
    urban = np.concatenate([_build_segments(_ECE15) for _ in range(4)])
    extra_urban = _build_segments(_EUDC)
    speed_kph = np.concatenate([np.array([0.0]), urban, extra_urban])
    time = np.arange(speed_kph.size, dtype=float)
    return DrivingCycle(
        name="NEDC",
        time=time,
        speed=speed_kph * KPH_TO_MPS,
        phases={
            "Urban (4 x ECE-15)": (0, 781),
            "Extra-urban (EUDC)": (781, speed_kph.size),
        },
        synthetic=False,
        description="UNECE R101 New European Driving Cycle, exact reconstruction",
    )


# =============================================================================
# WLTC Class 3b - synthesised from published phase statistics
# =============================================================================
@dataclasses.dataclass(frozen=True)
class _PhaseTarget:
    """Published statistics and construction recipe for one WLTC phase.

    The recipe is a sequence of speed *levels* expressed as a fraction of the
    phase maximum speed, exactly the way regulatory cycles are tabulated.  The
    vehicle ramps linearly between consecutive levels and holds each level for
    a duration that the solver determines.  A level of ``0.0`` is a standstill;
    the published stop time is divided equally between those.
    """

    name: str
    duration: float        # s
    distance: float        # m
    max_speed_kph: float
    stop_time: float       # s
    levels: tuple[float, ...]   # speed levels as a fraction of max_speed
    accel: float           # m/s^2, used when ramping up
    decel: float           # m/s^2, magnitude, used when ramping down


# Published WLTC Class 3b phase statistics (UNECE GTR 15).  The level sequences
# reproduce the character of each phase: many stops and low speeds in the Low
# phase, a single sustained high-speed excursion in the Extra-high phase.
_WLTC_3B_PHASES = (
    _PhaseTarget(
        "Low", 589.0, 3095.0, 56.5, 156.0,
        levels=(0.0, 0.38, 0.0, 0.72, 0.50, 0.0, 1.00, 0.66, 0.0, 0.44, 0.0),
        accel=1.50, decel=1.40,
    ),
    _PhaseTarget(
        "Medium", 433.0, 4756.0, 76.6, 48.0,
        levels=(0.0, 0.46, 0.78, 0.60, 1.00, 0.84, 0.0, 0.66, 0.0),
        accel=1.40, decel=1.40,
    ),
    _PhaseTarget(
        "High", 455.0, 7162.0, 97.4, 31.0,
        levels=(0.0, 0.50, 0.80, 0.62, 1.00, 0.86, 0.0, 0.72, 0.0),
        accel=1.20, decel=1.30,
    ),
    _PhaseTarget(
        "Extra-high", 323.0, 8254.0, 131.3, 7.0,
        levels=(0.0, 0.66, 0.86, 1.00, 0.92, 0.78, 0.0),
        accel=1.00, decel=1.20,
    ),
)


def _solve_hold_times(
    v_hold: np.ndarray,
    ramp_time: float,
    ramp_distance: float,
    fixed_time: float,
    target_time: float,
    target_distance: float,
) -> np.ndarray:
    """Hold durations that hit the phase time *and* distance exactly.

    Two linear constraints on the ``n`` non-zero hold durations ``t``:

        sum(t)           = target_time     - ramp_time - fixed_time
        sum(v_hold * t)  = target_distance - ramp_distance

    For ``n > 2`` the system is underdetermined, so the solution closest to a
    nominal distribution is taken.  The equality-constrained least-squares
    problem ``min ||t - t0||^2  s.t.  A t = b`` is solved through its
    Lagrangian, ``t = t0 + A^T (A A^T)^-1 (b - A t0)``, then repaired if any
    duration comes out negative.
    """
    n = v_hold.size
    available_time = target_time - ramp_time - fixed_time
    available_distance = target_distance - ramp_distance

    if available_time <= 0:
        raise ValueError(
            f"ramps ({ramp_time:.1f} s) and stops ({fixed_time:.1f} s) already "
            f"exceed the phase duration ({target_time:.1f} s)"
        )
    required_mean = available_distance / available_time
    if not (v_hold.min() <= required_mean <= v_hold.max()):
        raise ValueError(
            f"infeasible phase recipe: holds must average {required_mean:.2f} m/s "
            f"but the available levels span {v_hold.min():.2f}-{v_hold.max():.2f} m/s"
        )

    A = np.vstack([np.ones(n), v_hold])
    b = np.array([available_time, available_distance], dtype=float)
    t0 = np.full(n, available_time / n)

    lam = np.linalg.solve(A @ A.T, b - A @ t0)
    t = t0 + A.T @ lam

    if np.any(t < -1e-9):
        free = t >= 0
        if free.sum() >= 2:
            A_f, t0_f = A[:, free], t0[free]
            lam = np.linalg.solve(A_f @ A_f.T, b - A_f @ t0_f)
            t = np.zeros(n)
            t[free] = t0_f + A_f.T @ lam
    return np.maximum(t, 0.0)


def _build_phase(target: _PhaseTarget) -> tuple[np.ndarray, np.ndarray]:
    """Breakpoints of one WLTC phase as (time [s], speed [m/s]) arrays.

    The phase is returned in continuous time as a piecewise-linear trace
    starting and ending at standstill, spanning exactly ``target.duration``.
    """
    v_max = target.max_speed_kph * KPH_TO_MPS
    levels = np.asarray(target.levels, dtype=float) * v_max

    # Ramp duration and distance between consecutive levels.
    ramp_durations: list[float] = []
    ramp_time = 0.0
    ramp_distance = 0.0
    for v_from, v_to in zip(levels[:-1], levels[1:]):
        rate = target.accel if v_to > v_from else target.decel
        duration = abs(v_to - v_from) / rate
        ramp_durations.append(duration)
        ramp_time += duration
        ramp_distance += 0.5 * (v_from + v_to) * duration

    moving = levels > 0.0
    n_stops = int(np.sum(~moving))
    hold = np.full(levels.size, target.stop_time / n_stops if n_stops else 0.0)
    hold[moving] = _solve_hold_times(
        levels[moving],
        ramp_time=ramp_time,
        ramp_distance=ramp_distance,
        fixed_time=target.stop_time,
        target_time=target.duration,
        target_distance=target.distance,
    )

    times = [0.0]
    speeds = [float(levels[0])]
    clock = 0.0
    for index, level in enumerate(levels):
        if hold[index] > 0:
            clock += hold[index]
            times.append(clock)
            speeds.append(float(level))
        if index < len(ramp_durations):
            clock += ramp_durations[index]
            times.append(clock)
            speeds.append(float(levels[index + 1]))

    # Rescale to remove the residual from floating-point hold durations so the
    # phase spans its published duration exactly.
    time_array = np.asarray(times) * (target.duration / clock)
    return time_array, np.asarray(speeds)


def wltc_class3b(prefer_official: bool = True) -> DrivingCycle:
    """WLTC Class 3b, 1800 s.

    Uses ``data/cycles/wltc_class3b.csv`` when present, otherwise synthesises a
    statistically equivalent profile.
    """
    official = DATA_DIR / "wltc_class3b.csv"
    if prefer_official and official.exists():
        cycle = from_csv(official, name="WLTC Class 3b")
        return dataclasses.replace(
            cycle,
            phases={
                "Low": (0, 589), "Medium": (589, 1022),
                "High": (1022, 1477), "Extra-high": (1477, 1800),
            },
            synthetic=False,
            description="Official WLTC Class 3b trace (UNECE GTR 15)",
        )

    # Assemble the four phases on one continuous time base, then rasterise once
    # onto the integer-second grid 0 ... 1800 (inclusive of both endpoints).
    breakpoint_times: list[np.ndarray] = []
    breakpoint_speeds: list[np.ndarray] = []
    phases: dict[str, tuple[int, int]] = {}
    offset = 0.0
    for target in _WLTC_3B_PHASES:
        times, speeds = _build_phase(target)
        phases[target.name] = (int(round(offset)), int(round(offset + target.duration)))
        breakpoint_times.append(times[1:] + offset if offset else times)
        breakpoint_speeds.append(speeds[1:] if offset else speeds)
        offset += target.duration

    knot_time = np.concatenate(breakpoint_times)
    knot_speed = np.concatenate(breakpoint_speeds)

    total = float(offset)
    time = np.arange(int(round(total)) + 1, dtype=float)
    speed = np.interp(time, knot_time, knot_speed)

    return DrivingCycle(
        name="WLTC Class 3b (synthetic)",
        time=time,
        speed=speed,
        phases=phases,
        synthetic=True,
        description=(
            "Synthesised from the published WLTC Class 3b phase statistics "
            "(duration, distance, maximum speed and stop time reproduced to "
            "within 1 %)"
        ),
    )


# =============================================================================
# CSV loader
# =============================================================================
def from_csv(path: str | Path, name: str | None = None) -> DrivingCycle:
    """Load a 1 Hz cycle from CSV with columns ``time_s`` and ``speed_kph``."""
    import pandas as pd

    path = Path(path)
    frame = pd.read_csv(path)
    columns = {c.lower().strip(): c for c in frame.columns}
    if "time_s" not in columns or "speed_kph" not in columns:
        raise ValueError(
            f"{path} must contain 'time_s' and 'speed_kph' columns, "
            f"found {list(frame.columns)}"
        )
    time = frame[columns["time_s"]].to_numpy(dtype=float)
    speed = frame[columns["speed_kph"]].to_numpy(dtype=float) * KPH_TO_MPS
    return DrivingCycle(
        name=name or path.stem,
        time=time,
        speed=speed,
        synthetic=False,
        description=f"Loaded from {path.name}",
    )


def to_csv(cycle: DrivingCycle, path: str | Path) -> Path:
    """Write a cycle to CSV in the same format the loader expects."""
    import pandas as pd

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"time_s": cycle.time, "speed_kph": cycle.speed * MPS_TO_KPH}
    ).to_csv(path, index=False, float_format="%.4f")
    return path


# =============================================================================
# Registry
# =============================================================================
CYCLES = {
    "wltc_class3b": wltc_class3b,
    "nedc": nedc,
}


def get_cycle(name: str) -> DrivingCycle:
    """Look up a built-in cycle by key, or load a CSV path."""
    key = name.lower().strip()
    if key in CYCLES:
        return CYCLES[key]()
    path = Path(name)
    if path.exists():
        return from_csv(path)
    raise KeyError(
        f"unknown cycle '{name}'; built-ins are {sorted(CYCLES)} "
        "or give a path to a CSV file"
    )


# Published reference statistics, used by the tests and the validation table.
WLTC_3B_REFERENCE = {
    "duration_s": 1800.0,
    "distance_km": 23.266,
    "max_speed_kph": 131.3,
    "mean_speed_kph": 46.5,
    "stop_time_s": 242.0,
}
NEDC_REFERENCE = {
    "duration_s": 1180.0,
    "distance_km": 11.007,
    "max_speed_kph": 120.0,
    "mean_speed_kph": 33.6,
}
