"""Publication-quality figures (FR-9).

Every figure is written to ``results/figures`` as both PNG (for the report) and
SVG (for the slides).  Axes carry SI or clearly stated engineering units and a
caption-ready title.  Curves that depend on an assumed parameter are drawn in
the assumption colour so the reader can see at a glance which results rest on
an estimate.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from .cycles import DrivingCycle
from .parameters import ParameterSet
from .performance import PerformanceResult
from .rangecalc import RangeResult
from .simulation import SimulationResult
from .units import MPS_TO_KPH, rpm

# Assumption red, matching the colour the report uses for assumed values.
ASSUMED = "#c0271c"
PRIMARY = "#1f4e79"
SECONDARY = "#2e8b57"
ACCENT = "#d98c00"
NEUTRAL = "#555f6b"

STYLE = {
    "figure.figsize": (8.6, 5.0),
    "figure.dpi": 130,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "font.size": 10,
    "axes.titlesize": 11.5,
    "axes.labelsize": 10.5,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "legend.frameon": False,
    "legend.fontsize": 9,
    "lines.linewidth": 1.8,
}


def _save(fig: plt.Figure, outdir: Path, name: str) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    png = outdir / f"{name}.png"
    fig.savefig(png)
    fig.savefig(outdir / f"{name}.svg")
    plt.close(fig)
    return png


# =============================================================================
# Performance figures
# =============================================================================
def plot_tractive_force(result: PerformanceResult, outdir: Path) -> Path:
    """Tractive force and resistance versus speed - the classic traction diagram."""
    v = result.speed * MPS_TO_KPH
    fig, ax = plt.subplots()

    ax.plot(v, result.tractive_force / 1e3, color=PRIMARY, label="Motor envelope")
    ax.plot(
        v, result.adhesion_force / 1e3, color=ASSUMED, ls="--",
        label="Tyre adhesion limit (assumed $\\mu$)",
    )
    ax.fill_between(
        v, 0, result.available_force / 1e3, color=PRIMARY, alpha=0.10,
        label="Force available",
    )
    ax.plot(v, result.resistance / 1e3, color=NEUTRAL, label="Total running resistance")
    ax.plot(v, result.rolling / 1e3, color=SECONDARY, ls=":", label="Rolling resistance")
    ax.plot(v, result.aerodynamic / 1e3, color=ACCENT, ls=":", label="Aerodynamic drag")

    top = result.top_speed * MPS_TO_KPH
    ax.axvline(top, color="k", ls="-.", lw=1.0)
    ax.annotate(
        f"top speed {top:.0f} km/h"
        + f"\n({result.top_speed_limit})",
        xy=(top, ax.get_ylim()[1] * 0.50),
        xytext=(-8, 0), textcoords="offset points",
        ha="right", fontsize=8.5, color="k",
    )

    ax.set_xlabel("Vehicle speed [km/h]")
    ax.set_ylabel("Force at the wheels [kN]")
    ax.set_title("Traction diagram: available force against running resistance")
    ax.set_xlim(0, v.max())
    ax.set_ylim(0, float(np.max(result.tractive_force) / 1e3) * 1.32)
    ax.legend(loc="upper right", ncols=2, framealpha=0.0)
    return _save(fig, outdir, "01_traction_diagram")


def plot_acceleration_curve(result: PerformanceResult, outdir: Path) -> Path:
    """Maximum acceleration versus speed, and the full-throttle launch."""
    fig, (left, right) = plt.subplots(1, 2, figsize=(11.2, 4.4))

    v = result.speed * MPS_TO_KPH
    left.plot(v, result.acceleration, color=PRIMARY)
    left.fill_between(v, 0, result.acceleration, color=PRIMARY, alpha=0.12)

    # Mark the two regimes.
    traction_limited = result.adhesion_force < result.tractive_force
    if traction_limited.any():
        v_switch = v[np.max(np.flatnonzero(traction_limited))]
        left.axvspan(0, v_switch, color=ASSUMED, alpha=0.08)
        left.annotate(
            "tyre-limited", xy=(v_switch * 0.5, result.acceleration.max() * 0.93),
            ha="center", fontsize=8.5, color=ASSUMED,
        )
    left.set_xlabel("Vehicle speed [km/h]")
    left.set_ylabel("Maximum acceleration [m/s$^2$]")
    left.set_title("Acceleration characteristic")
    left.set_xlim(0, v.max())
    left.set_ylim(0, None)

    right.plot(result.launch_time, result.launch_speed * MPS_TO_KPH, color=PRIMARY)
    for label, seconds in result.accel_times.items():
        if not np.isfinite(seconds):
            continue
        target = float(label.split("-")[1].split()[0])
        right.plot([seconds], [target], "o", color=ASSUMED, ms=5)
        right.annotate(
            f"{label}: {seconds:.1f} s", xy=(seconds, target),
            xytext=(6, -10), textcoords="offset points", fontsize=8.5,
        )
    right.set_xlabel("Time [s]")
    right.set_ylabel("Vehicle speed [km/h]")
    right.set_title("Full-throttle launch from rest")
    right.set_xlim(0, None)
    right.set_ylim(0, None)

    fig.suptitle("Speed and acceleration characteristic curves", fontsize=12)
    return _save(fig, outdir, "02_acceleration_characteristic")


def plot_power_and_gradeability(
    result: PerformanceResult, gradeability: np.ndarray, outdir: Path
) -> Path:
    """Wheel power envelope and maximum climbable gradient."""
    fig, (left, right) = plt.subplots(1, 2, figsize=(11.2, 4.4))
    v = result.speed * MPS_TO_KPH

    left.plot(v, result.wheel_power / 1e3, color=PRIMARY, label="At the wheels")
    left.plot(
        v, result.resistance * result.speed / 1e3, color=NEUTRAL,
        label="Needed to hold speed",
    )
    left.set_xlabel("Vehicle speed [km/h]")
    left.set_ylabel("Power [kW]")
    left.set_title("Power envelope")
    left.set_xlim(0, v.max())
    left.set_ylim(0, None)
    left.legend(loc="lower right")

    right.plot(v, gradeability, color=SECONDARY)
    right.axhline(0, color="k", lw=0.8)
    for grade in (10.0, 20.0, 30.0):
        right.axhline(grade, color=NEUTRAL, ls=":", lw=0.8)
        right.annotate(f"{grade:.0f} %", xy=(v.max() * 0.98, grade), fontsize=8,
                       ha="right", va="bottom", color=NEUTRAL)
    right.set_xlabel("Vehicle speed [km/h]")
    right.set_ylabel("Maximum gradient [%]")
    right.set_title("Gradeability at steady speed")
    right.set_xlim(0, v.max())
    right.set_ylim(0, None)
    return _save(fig, outdir, "03_power_and_gradeability")


def plot_efficiency_map(powertrain, result: PerformanceResult, outdir: Path) -> Path:
    """Drive-unit efficiency map with the cycle envelope drawn on it."""
    grid_w, grid_t, eff = powertrain.efficiency_map()
    fig, ax = plt.subplots()

    levels = np.arange(0.70, 0.985, 0.01)
    contour = ax.contourf(rpm(grid_w), grid_t, eff, levels=levels, cmap="viridis", extend="min")
    lines = ax.contour(rpm(grid_w), grid_t, eff, levels=[0.85, 0.90, 0.93, 0.95, 0.96],
                       colors="white", linewidths=0.7)
    ax.clabel(lines, fmt="%.2f", fontsize=7.5)

    omega = np.linspace(1.0, powertrain.max_speed, 500)
    ax.plot(rpm(omega), powertrain.max_motor_torque(omega), color=ASSUMED, lw=2.0,
            label="Peak torque envelope")
    ax.axvline(rpm(powertrain.base_speed), color="white", ls="--", lw=1.0)
    ax.annotate(
        f"base speed {rpm(powertrain.base_speed):.0f} rpm",
        xy=(rpm(powertrain.base_speed), powertrain.peak_torque * 0.5),
        xytext=(8, 0), textcoords="offset points", color="white", fontsize=8.5,
    )

    fig.colorbar(contour, ax=ax, label="Motor + inverter efficiency [-]")
    ax.set_xlabel("Motor speed [rpm]")
    ax.set_ylabel("Shaft torque [N m]")
    ax.set_title("Drive-unit efficiency map (loss model - assumed coefficients)")
    ax.legend(loc="upper right")
    return _save(fig, outdir, "04_efficiency_map")


# =============================================================================
# Cycle figures
# =============================================================================
def plot_cycle(cycle: DrivingCycle, outdir: Path, name: str = "05_driving_cycle") -> Path:
    """The driving profile with its phases marked."""
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(10.5, 6.0), sharex=True, height_ratios=[2, 1]
    )

    top.plot(cycle.time, cycle.speed * MPS_TO_KPH, color=PRIMARY, lw=1.1)
    top.fill_between(cycle.time, 0, cycle.speed * MPS_TO_KPH, color=PRIMARY, alpha=0.10)

    colours = [SECONDARY, ACCENT, NEUTRAL, ASSUMED]
    for index, (label, (start, stop)) in enumerate(cycle.phases.items()):
        top.axvspan(cycle.time[start], cycle.time[min(stop, cycle.time.size - 1)],
                    color=colours[index % len(colours)], alpha=0.07)
        top.annotate(
            label,
            xy=(0.5 * (cycle.time[start] + cycle.time[min(stop, cycle.time.size - 1)]),
                cycle.max_speed * MPS_TO_KPH * 1.04),
            ha="center", fontsize=8.5, color=colours[index % len(colours)],
        )
    top.set_ylabel("Speed [km/h]")
    top.set_ylim(0, cycle.max_speed * MPS_TO_KPH * 1.15)
    title = f"{cycle.name}: {cycle.distance_km:.2f} km in {cycle.duration:.0f} s"
    if cycle.synthetic:
        title += "  (synthesised profile - assumption)"
    top.set_title(title, color=ASSUMED if cycle.synthetic else "black")

    bottom.plot(cycle.time, cycle.acceleration, color=NEUTRAL, lw=0.9)
    bottom.axhline(0, color="k", lw=0.7)
    bottom.set_xlabel("Time [s]")
    bottom.set_ylabel("Acceleration\n[m/s$^2$]")
    bottom.set_xlim(0, cycle.duration)
    return _save(fig, outdir, name)


def plot_cycle_simulation(result: SimulationResult, outdir: Path) -> Path:
    """Speed, power and state of charge over one pass of the cycle."""
    fig, axes = plt.subplots(3, 1, figsize=(10.5, 8.0), sharex=True)
    speed_ax, power_ax, soc_ax = axes

    speed_ax.plot(result.time, result.speed_target * MPS_TO_KPH, color=NEUTRAL,
                  lw=2.4, alpha=0.35, label="Demanded")
    speed_ax.plot(result.time, result.speed * MPS_TO_KPH, color=PRIMARY, lw=1.0,
                  label="Achieved")
    if result.unmet_count:
        speed_ax.plot(result.time[result.unmet], result.speed[result.unmet] * MPS_TO_KPH,
                      "x", color=ASSUMED, ms=4, label="Powertrain limit reached")
    speed_ax.set_ylabel("Speed [km/h]")
    speed_ax.legend(loc="upper left", ncols=3)
    speed_ax.set_title(f"Cycle simulation: {result.cycle_name}")

    battery_kw = result.power_battery / 1e3
    power_ax.fill_between(result.time, 0, np.maximum(battery_kw, 0),
                          color=PRIMARY, alpha=0.5, lw=0, label="Traction")
    power_ax.fill_between(result.time, 0, np.minimum(battery_kw, 0),
                          color=SECONDARY, alpha=0.6, lw=0, label="Regeneration")
    power_ax.axhline(0, color="k", lw=0.7)
    power_ax.set_ylabel("Battery power [kW]")
    power_ax.legend(loc="upper left", ncols=2)

    soc_ax.plot(result.time, result.soc * 100.0, color=ACCENT)
    soc_ax.set_ylabel("State of charge [%]")
    soc_ax.set_xlabel("Time [s]")
    soc_ax.set_xlim(0, result.time[-1])
    soc_ax.annotate(
        f"{result.consumption_kwh_per_100km:.2f} kWh/100 km over "
        f"{result.total_distance_km:.2f} km",
        xy=(0.99, 0.12), xycoords="axes fraction", ha="right", fontsize=9,
    )
    return _save(fig, outdir, "06_cycle_simulation")


def plot_energy_balance(result: SimulationResult, outdir: Path) -> Path:
    """Where the energy goes over one cycle."""
    road_kwh = result.energy_resistance / 3.6e6
    regen_kwh = result.energy_regen / 3.6e6
    aux_kwh = result.energy_auxiliary / 3.6e6
    brake_kwh = result.energy_friction_brake / 3.6e6
    traction_kwh = result.energy_traction / 3.6e6
    losses_kwh = traction_kwh - road_kwh - brake_kwh

    fig, (left, right) = plt.subplots(1, 2, figsize=(11.2, 4.4))

    labels = ["Road load\n(rolling + drag)", "Drivetrain\nlosses", "Friction\nbrakes",
              "Auxiliaries"]
    values = [road_kwh, max(losses_kwh, 0.0), brake_kwh, aux_kwh]
    colours = [PRIMARY, ACCENT, NEUTRAL, SECONDARY]
    bars = left.bar(labels, values, color=colours)
    left.bar_label(bars, fmt="%.3f", fontsize=8.5, padding=2)
    left.set_ylabel("Energy over one cycle [kWh]")
    left.set_title("Energy expenditure")
    left.tick_params(axis="x", labelsize=8.5)

    flow_labels = ["Drawn from\nbattery", "Recovered by\nregeneration", "Net from\nbattery"]
    flow_values = [traction_kwh + aux_kwh, -regen_kwh,
                   traction_kwh + aux_kwh - regen_kwh]
    flow_colours = [PRIMARY, SECONDARY, ASSUMED]
    bars = right.bar(flow_labels, flow_values, color=flow_colours)
    right.bar_label(bars, fmt="%.3f", fontsize=8.5, padding=2)
    right.axhline(0, color="k", lw=0.8)
    right.set_ylabel("Energy [kWh]")
    right.set_title(
        f"Battery energy balance - {result.regen_fraction * 100:.1f} % recovered"
    )
    right.tick_params(axis="x", labelsize=8.5)
    return _save(fig, outdir, "07_energy_balance")


# =============================================================================
# Range figures
# =============================================================================
def plot_range(result: RangeResult, published_km: float, outdir: Path) -> Path:
    """State of charge against distance, down to an empty battery."""
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(11.2, 4.4), width_ratios=[2, 1]
    )

    left.plot(result.distance_trace, result.soc_trace * 100.0, color=PRIMARY, lw=1.2)
    left.axhline(0, color="k", lw=0.8)
    left.axvline(result.range_integrated_km, color=ASSUMED, ls="--", lw=1.2)
    left.annotate(
        f"{result.range_integrated_km:.0f} km",
        xy=(result.range_integrated_km, 50), xytext=(-8, 0),
        textcoords="offset points", ha="right", color=ASSUMED, fontsize=10,
    )
    left.set_xlabel("Distance [km]")
    left.set_ylabel("State of charge [%]")
    left.set_title(f"Discharge over repeated {result.cycle_name}")
    left.set_xlim(0, result.range_integrated_km * 1.05)
    left.set_ylim(0, 102)

    labels = ["Simulated\n(integrated)", "Simulated\n(analytic)", "Published\nWLTP"]
    values = [result.range_integrated_km, result.range_analytic_km, published_km]
    bars = right.bar(labels, values, color=[PRIMARY, NEUTRAL, SECONDARY])
    right.bar_label(bars, fmt="%.0f km", fontsize=9, padding=2)
    right.set_ylabel("Range [km]")
    right.set_title("Validation")
    right.set_ylim(0, max(values) * 1.18)
    right.tick_params(axis="x", labelsize=8.5)
    return _save(fig, outdir, "08_range")


def plot_constant_speed_range(
    speeds: np.ndarray, ranges: np.ndarray, consumption: np.ndarray, outdir: Path
) -> Path:
    """Range and consumption at steady cruising speed."""
    fig, ax = plt.subplots()
    ax.plot(speeds, ranges, color=PRIMARY, label="Range")
    ax.set_xlabel("Constant cruising speed [km/h]")
    ax.set_ylabel("Range [km]", color=PRIMARY)
    ax.tick_params(axis="y", labelcolor=PRIMARY)
    ax.set_xlim(speeds.min(), speeds.max())
    ax.set_ylim(0, None)

    twin = ax.twinx()
    twin.plot(speeds, consumption, color=ACCENT, ls="--", label="Consumption")
    twin.set_ylabel("Consumption [Wh/km]", color=ACCENT)
    twin.tick_params(axis="y", labelcolor=ACCENT)
    twin.grid(False)
    twin.set_ylim(0, None)

    best = int(np.nanargmax(ranges))
    ax.plot([speeds[best]], [ranges[best]], "o", color=PRIMARY, ms=6)
    ax.annotate(
        f"best {ranges[best]:.0f} km at {speeds[best]:.0f} km/h",
        xy=(speeds[best], ranges[best]), xytext=(10, -14),
        textcoords="offset points", fontsize=9,
    )
    ax.set_title("Range and consumption at steady speed")
    return _save(fig, outdir, "09_constant_speed_range")


# =============================================================================
# Sensitivity figures
# =============================================================================
def plot_tornado(rows: list[dict], outdir: Path) -> Path:
    """Tornado chart: influence of each assumed parameter on the range."""
    fig, ax = plt.subplots(figsize=(10.0, 5.6))
    baseline = rows[0]["baseline_km"]

    ordered = rows[::-1]                      # largest influence at the top
    labels = [row["parameter"] for row in ordered]
    lows = [row["delta_low_km"] for row in ordered]
    highs = [row["delta_high_km"] for row in ordered]
    y = np.arange(len(labels))

    ax.barh(y, lows, color=ASSUMED, alpha=0.8, label="Parameter at the low end")
    ax.barh(y, highs, color=PRIMARY, alpha=0.8, label="Parameter at the high end")
    ax.axvline(0, color="k", lw=1.0)
    ax.set_yticks(y, labels)

    # Place the interval labels clear of the widest bar on the positive side,
    # and widen the axis so they never clip.
    extent = max(max(abs(v) for v in lows), max(abs(v) for v in highs))
    label_x = max(max(lows + highs), 0.0) + extent * 0.06
    ax.set_xlim(-extent * 1.08, label_x + extent * 0.62)

    for index, row in enumerate(ordered):
        unit = "" if row["unit"] in ("-", "") else f" {row['unit']}"
        ax.annotate(
            f"{row['low']:g} to {row['high']:g}{unit}",
            xy=(label_x, index), va="center", fontsize=8.2, color=NEUTRAL,
        )

    ax.set_xlabel(f"Change in range from the baseline of {baseline:.0f} km [km]")
    ax.set_title("Sensitivity of the range prediction to the assumed parameters")
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, -0.13), ncols=2)
    return _save(fig, outdir, "10_sensitivity_tornado")


def plot_scenarios(rows: list[dict], outdir: Path) -> Path:
    """Range under named real-world conditions."""
    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    labels = [row["scenario"].replace(", ", ",\n") for row in rows]
    values = [row["range_km"] for row in rows]
    colours = [PRIMARY] + [NEUTRAL] * (len(rows) - 1)
    bars = ax.bar(labels, values, color=colours)
    ax.bar_label(bars, fmt="%.0f km", fontsize=9, padding=2)
    for index, row in enumerate(rows[1:], start=1):
        ax.annotate(
            f"{row['delta_vs_certification_pct']:+.0f} %",
            xy=(index, values[index] * 0.5), ha="center", color="white", fontsize=9,
        )
    ax.set_ylabel("Range [km]")
    ax.set_title("Range under real-world conditions against the certification case")
    ax.set_ylim(0, max(values) * 1.18)
    ax.tick_params(axis="x", labelsize=8.5)
    return _save(fig, outdir, "11_scenarios")


def plot_parameter_provenance(ps: ParameterSet, outdir: Path) -> Path:
    """How much of the parameter set is published and how much is assumed."""
    assumed = len(ps.assumptions())
    published = len(ps.published())
    fig, ax = plt.subplots(figsize=(6.0, 4.0))
    bars = ax.bar(
        ["Published /\nmeasured", "Assumed"], [published, assumed],
        color=[SECONDARY, ASSUMED],
    )
    ax.bar_label(bars, fmt="%d", fontsize=11, padding=2)
    ax.set_ylabel("Number of parameters")
    ax.set_title(
        f"Parameter provenance: {assumed} of {assumed + published} values are assumed"
    )
    ax.set_ylim(0, max(published, assumed) * 1.25)
    return _save(fig, outdir, "12_parameter_provenance")
