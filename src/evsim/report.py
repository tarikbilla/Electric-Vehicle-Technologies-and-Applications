"""Result tables and the assumption register (FR-9, FR-10).

The project brief requires that assumed constants be *marked in red*.  Markdown
has no colour of its own, so every assumed value is wrapped in an inline HTML
span carrying the assumption colour.  That renders red in GitHub, in VS Code,
in Pandoc HTML/PDF output and in Word when the Markdown is imported, which
covers every route the report is likely to take.

A machine-readable CSV of the register is written alongside it so the values can
be pulled into a spreadsheet or a LaTeX table without retyping.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import numpy as np
import pandas as pd

from .cycles import DrivingCycle
from .parameters import ParameterSet
from .performance import PerformanceResult
from .rangecalc import RangeResult
from .simulation import SimulationResult
from .units import MPS_TO_KPH, rpm

RED = "#c0271c"


def red(text: object) -> str:
    """Wrap a value in the assumption colour."""
    return f'<span style="color:{RED}">{text}</span>'


def _fmt(value: float, digits: int = 4) -> str:
    """Format a number to a fixed number of significant figures."""
    if value == 0:
        return "0"
    return f"{value:.{digits}g}"


def markdown_table(frame: pd.DataFrame, floatfmt: str = ".3f") -> str:
    """Render a data frame as a GitHub-flavoured Markdown table.

    Written out rather than using ``DataFrame.to_markdown`` so the project does
    not depend on ``tabulate`` for a reproducible build, and so numeric columns
    can be right-aligned the way an engineering table should be.
    """
    if frame.empty:
        return "_(no rows)_"

    def cell(value: object) -> str:
        if isinstance(value, bool):
            return "yes" if value else "no"
        if isinstance(value, (int, np.integer)):
            return str(int(value))
        if isinstance(value, (float, np.floating)):
            if not np.isfinite(value):
                return "n/a"
            return format(float(value), floatfmt)
        return str(value)

    numeric = [
        column
        for column in frame.columns
        if pd.api.types.is_numeric_dtype(frame[column])
        and not pd.api.types.is_bool_dtype(frame[column])
    ]
    header = "| " + " | ".join(str(c).replace("_", " ") for c in frame.columns) + " |"
    rule = "|" + "|".join(
        "---:" if column in numeric else "---" for column in frame.columns
    ) + "|"
    rows = [
        "| " + " | ".join(cell(value) for value in record) + " |"
        for record in frame.itertuples(index=False, name=None)
    ]
    return "\n".join([header, rule, *rows])


# =============================================================================
# Assumption register
# =============================================================================
def assumption_table(ps: ParameterSet) -> pd.DataFrame:
    """The assumption register as a data frame."""
    return pd.DataFrame(
        [
            {
                "parameter": parameter.path,
                "value": parameter.value,
                "unit": parameter.unit,
                "rationale": parameter.source,
            }
            for parameter in ps.assumptions()
        ]
    )


def write_assumption_register(ps: ParameterSet, outdir: Path) -> tuple[Path, Path]:
    """Write the assumption register as Markdown (red) and CSV."""
    outdir.mkdir(parents=True, exist_ok=True)
    frame = assumption_table(ps)
    csv_path = outdir / "assumption_register.csv"
    frame.to_csv(csv_path, index=False)

    assumed = ps.assumptions()
    published = ps.published()

    lines = [
        "# Assumption register",
        "",
        f"**Vehicle:** {ps.meta('name')} ({ps.meta('model_year')})  ",
        f"**Parameter file:** `{ps.origin}`  ",
        f"**Generated:** {_dt.date.today().isoformat()}",
        "",
        f"Of the {len(assumed) + len(published)} parameters in the model, "
        f"**{len(assumed)}** are engineering assumptions rather than published "
        f"or measured data. Every assumed value is shown "
        f"{red('in red')} throughout this report, as required by the project brief.",
        "",
        "Each assumption was chosen from the manufacturer's own documentation "
        "where it exists, from independent teardowns and measurements where it "
        "does not, and otherwise from the standard automotive literature. The "
        "sensitivity study quantifies how much each one actually matters to the "
        "final result.",
        "",
        "## Assumed parameters",
        "",
        "| # | Parameter | Value | Unit | Basis for the assumption |",
        "|--:|---|---:|---|---|",
    ]
    for index, parameter in enumerate(assumed, start=1):
        lines.append(
            f"| {index} | `{parameter.path}` | {red(_fmt(parameter.value))} | "
            f"{parameter.unit} | {parameter.source} |"
        )

    lines += [
        "",
        "## Published and measured parameters",
        "",
        "| # | Parameter | Value | Unit | Source |",
        "|--:|---|---:|---|---|",
    ]
    for index, parameter in enumerate(published, start=1):
        lines.append(
            f"| {index} | `{parameter.path}` | {_fmt(parameter.value)} | "
            f"{parameter.unit} | {parameter.source} |"
        )

    lines += [
        "",
        "## Modelling assumptions that are not single numbers",
        "",
        "| Assumption | Why | Effect on the result |",
        "|---|---|---|",
        f"| {red('Quasi-static (backward-facing) simulation')} | The speed trace "
        "is the input; no driver model or closed-loop control is needed for an "
        "energy study | None, provided the powertrain can follow the trace, "
        "which the simulation verifies at every step |",
        f"| {red('Constant battery internal resistance')} | No temperature or "
        "state-of-charge dependence published | Ohmic loss is a small share of "
        "the total; the two range methods bracket the error |",
        f"| {red('No thermal model')} | Out of scope per the brief | Continuous "
        "power derating is not captured; it does not bind on a legislative cycle |",
        f"| {red('No battery ageing')} | Out of scope per the brief | Results "
        "apply to a new vehicle |",
        f"| {red('Synthesised WLTC trace')} | The official 1800-point table is "
        "copyright and not redistributed here | Cycle statistics are reproduced "
        "to within 0.5 %; see the cycle validation table |",
        "",
    ]
    md_path = outdir / "assumption_register.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path, csv_path


# =============================================================================
# Result tables
# =============================================================================
def cycle_validation_table(cycle: DrivingCycle, reference: dict[str, float]) -> pd.DataFrame:
    """Generated cycle statistics against the published ones."""
    statistics = cycle.statistics()
    rows = []
    for key, published in reference.items():
        simulated = statistics.get(key)
        if simulated is None:
            continue
        rows.append(
            {
                "quantity": key.replace("_", " "),
                "generated": simulated,
                "published": published,
                "deviation_pct": (simulated - published) / published * 100.0,
            }
        )
    return pd.DataFrame(rows)


def performance_table(result: PerformanceResult, ps: ParameterSet) -> pd.DataFrame:
    rows = [
        {"quantity": "Top speed", "value": result.top_speed * MPS_TO_KPH, "unit": "km/h"},
        {
            "quantity": "Maximum acceleration (from rest)",
            "value": float(result.acceleration[0]),
            "unit": "m/s^2",
        },
        {
            "quantity": "Maximum wheel power",
            "value": float(np.max(result.wheel_power)) / 1e3,
            "unit": "kW",
        },
        {
            "quantity": "Maximum tractive force",
            "value": float(np.max(result.available_force)) / 1e3,
            "unit": "kN",
        },
    ]
    for label, seconds in result.accel_times.items():
        rows.append({"quantity": label, "value": seconds, "unit": "s"})
    return pd.DataFrame(rows)


def validation_table(rows: list[dict[str, object]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if "note" not in frame.columns:
        frame["note"] = ""
    frame["note"] = frame["note"].fillna("")
    return frame


# =============================================================================
# Results document
# =============================================================================
def write_results_document(
    ps: ParameterSet,
    cycle: DrivingCycle,
    cycle_reference: dict[str, float],
    performance: PerformanceResult,
    performance_validation: list[dict],
    simulation: SimulationResult,
    range_result: RangeResult,
    range_validation_rows: list[dict],
    tornado_rows: list[dict],
    scenario_rows: list[dict],
    figures: dict[str, Path],
    outdir: Path,
) -> Path:
    """Write the full results document that the report draws on."""
    outdir.mkdir(parents=True, exist_ok=True)

    def figure(key: str, caption: str) -> list[str]:
        path = figures.get(key)
        if path is None:
            return []
        relative = Path("..") / "figures" / path.name
        return ["", f"![{caption}]({relative})", "", f"*{caption}*", ""]

    lines: list[str] = [
        f"# Simulation results - {ps.meta('name')}",
        "",
        f"**Generated:** {_dt.date.today().isoformat()}  ",
        f"**Parameter file:** `{ps.origin}`  ",
        f"**Driving cycle:** {cycle.name}  ",
        f"**Assumed parameters:** {len(ps.assumptions())} of "
        f"{len(ps.assumptions()) + len(ps.published())}, all shown {red('in red')}",
        "",
        "---",
        "",
        "## 1. Headline results",
        "",
        "| Quantity | Simulated | Published | Deviation |",
        "|---|---:|---:|---:|",
    ]
    for row in list(performance_validation) + list(range_validation_rows):
        lines.append(
            f"| {row['quantity']} [{row['unit']}] | {row['simulated']:.1f} | "
            f"{row['published']:.1f} | {row['deviation_pct']:+.1f} % |"
        )
    lines += [
        "",
        f"Cycle consumption is **{simulation.consumption_kwh_per_100km:.2f} kWh/100 km** "
        f"at the battery terminals, and the predicted range on a full battery is "
        f"**{range_result.range_integrated_km:.0f} km**.",
        "",
        "## 2. Vehicle and parameters",
        "",
        f"- Drivetrain: {ps.meta('drivetrain')}",
        f"- Battery chemistry: {ps.meta('battery_chemistry')}",
        f"- Kerb mass {ps['mass.curb_mass']:.0f} kg plus an assumed payload "
        f"of {red(_fmt(ps['mass.test_payload']))} kg, giving a test mass of "
        f"{ps['mass.curb_mass'] + ps['mass.test_payload']:.0f} kg",
        f"- Battery: {red(_fmt(ps['battery.gross_capacity']))} kWh gross, "
        f"{red(_fmt(ps['battery.gross_capacity'] * ps['battery.usable_fraction']))} "
        f"kWh usable at {red(_fmt(ps['battery.nominal_voltage']))} V nominal",
        f"- Motor: {ps['motor.peak_power'] / 1000:.0f} kW peak, "
        f"{ps['motor.peak_torque']:.0f} N m peak torque, single-speed "
        f"{red(_fmt(ps['transmission.gear_ratio']))}:1 reduction",
        f"- Aerodynamics: C_d {ps['aerodynamics.drag_coefficient']:.3f}, "
        f"frontal area {red(_fmt(ps['aerodynamics.frontal_area']))} m^2",
        "",
        "The full parameter set, with the provenance of every value, is in "
        "[`assumption_register.md`](assumption_register.md).",
        "",
        "## 3. Speed and acceleration characteristics",
        "",
        markdown_table(performance_table(performance, ps), floatfmt=".2f"),
        "",
    ]
    lines += figure("traction", "Traction diagram: available force against running resistance")
    lines += figure("acceleration", "Speed and acceleration characteristic curves")
    lines += figure("power", "Power envelope and gradeability")
    lines += figure("efficiency", "Drive-unit efficiency map")

    lines += [
        "## 4. Driving profile",
        "",
        f"{cycle.description}.",
        "",
        markdown_table(cycle_validation_table(cycle, cycle_reference), floatfmt=".3f"),
        "",
    ]
    lines += figure("cycle", f"{cycle.name} speed and acceleration trace")

    lines += [
        "## 5. Cycle simulation",
        "",
        markdown_table(
            pd.DataFrame(
                [{"quantity": k, "value": v} for k, v in simulation.summary().items()]
            ),
            floatfmt=".4f",
        ),
        "",
    ]
    lines += figure("simulation", "Speed, battery power and state of charge over the cycle")
    lines += figure("energy", "Energy balance over one cycle")

    lines += [
        "## 6. Range on a full battery",
        "",
        markdown_table(
            pd.DataFrame(
                [{"quantity": k, "value": v} for k, v in range_result.summary().items()]
            ),
            floatfmt=".3f",
        ),
        "",
        "The *integrated* method repeats the cycle carrying the state of charge "
        "forward until the usable window is exhausted, so it sees the ohmic "
        "loss grow as the open-circuit voltage falls. The *analytic* method "
        "divides the usable energy by the cycle consumption and so assumes "
        "consumption is independent of the state of charge. Both divisions are "
        "made at the open-circuit level, which is where the usable energy is "
        "defined; the two agree to "
        f"{abs(range_result.disagreement_pct):.2f} %, which is the cross-check "
        "on the energy book-keeping.",
        "",
    ]
    lines += figure("range", "Discharge over repeated cycles and validation against the published range")
    lines += figure("constant_speed", "Range and consumption at steady cruising speed")

    lines += [
        "## 7. Sensitivity to the assumptions",
        "",
        "Ranked by how much each assumed parameter moves the range prediction "
        "across its plausible interval.",
        "",
        "| Parameter | Interval | Range at low | Range at high | Span | Span of baseline |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in tornado_rows:
        lines.append(
            f"| {row['parameter']} | {row['low']:g} - {row['high']:g} {row['unit']} | "
            f"{row['range_low_km']:.0f} km | {row['range_high_km']:.0f} km | "
            f"{row['span_km']:.0f} km | {row['span_pct']:.1f} % |"
        )
    lines += [""]
    lines += figure("tornado", "Sensitivity of the range prediction to the assumed parameters")

    lines += [
        "## 8. Real-world scenarios",
        "",
        "| Scenario | Conditions | Range | Consumption | Against certification |",
        "|---|---|---:|---:|---:|",
    ]
    for row in scenario_rows:
        lines.append(
            f"| {row['scenario']} | {row['note']} | {row['range_km']:.0f} km | "
            f"{row['consumption_kwh_per_100km']:.2f} kWh/100 km | "
            f"{row['delta_vs_certification_pct']:+.0f} % |"
        )
    lines += [""]
    lines += figure("scenarios", "Range under real-world conditions")
    lines += figure("provenance", "Parameter provenance")

    lines += [
        "## 9. Limitations",
        "",
        "- No thermal model, so continuous-power derating and cold-battery "
        "resistance are not represented.",
        "- No battery ageing; the results describe a new vehicle.",
        "- The drive-unit efficiency comes from a four-term loss model fitted to "
        "plausible peak efficiencies, not from a measured map.",
        "- The WLTC trace is synthesised from published phase statistics rather "
        "than the official second-by-second table.",
        "",
    ]

    path = outdir / "results.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
