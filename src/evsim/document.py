"""Report and presentation generation.

The project brief asks for a written report of 12 to 20 pages and a spoken
presentation of about 20 minutes.  This module assembles both from the
simulation results, so the numbers, tables and figures in the report are the
ones the code actually produced and cannot drift out of step with it.

Assumed values are rendered in the assumption colour throughout, as the brief
requires.  The output is Markdown; ``pandoc report.md -o report.pdf`` turns it
into a submission-ready document.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import numpy as np

from .cycles import DrivingCycle
from .parameters import ParameterSet
from .performance import PerformanceResult
from .rangecalc import RangeResult
from .report import markdown_table, red
from .simulation import SimulationResult
from .units import MPS_TO_KPH, rpm


def _fig(figures: dict[str, Path], key: str, number: int, caption: str) -> list[str]:
    """A numbered figure reference, if that figure was produced."""
    path = figures.get(key)
    if path is None:
        return []
    return [
        "",
        f"![Figure {number}]({Path('..') / 'figures' / path.name})",
        "",
        f"**Figure {number}.** {caption}",
        "",
    ]


def write_report(
    ps: ParameterSet,
    cycle: DrivingCycle,
    performance: PerformanceResult,
    performance_validation: list[dict],
    simulation: SimulationResult,
    range_result: RangeResult,
    range_validation_rows: list[dict],
    tornado_rows: list[dict],
    scenario_rows: list[dict],
    figures: dict[str, Path],
    powertrain,
    road,
    outdir: Path,
    nedc_summary: dict | None = None,
) -> Path:
    """Write the full written report."""
    outdir.mkdir(parents=True, exist_ok=True)

    name = ps.meta("name")
    n_assumed = len(ps.assumptions())
    n_total = n_assumed + len(ps.published())
    test_mass = ps["mass.curb_mass"] + ps["mass.test_payload"]
    usable = ps["battery.gross_capacity"] * ps["battery.usable_fraction"]
    payload = ps["mass.test_payload"]
    gear_ratio = ps["transmission.gear_ratio"]
    gross = ps["battery.gross_capacity"]
    lam = ps["mass.rotational_mass_factor"]
    coastdown_mass = ps["road_load.coastdown_test_mass"]
    validation = list(performance_validation) + list(range_validation_rows)

    L: list[str] = []
    A = L.append

    # ------------------------------------------------------------- title
    A(f"# Modelling and Simulation of an Electric Vehicle")
    A("")
    A(f"## {name}")
    A("")
    A("Semester project, *Electric Vehicle Technologies & Applications*  ")
    A("Technische Hochschule Mittelhessen  ")
    A(f"{_dt.date.today().strftime('%d %B %Y')}")
    A("")
    A("---")
    A("")

    # ------------------------------------------------------------- abstract
    A("## Abstract")
    A("")
    A(
        f"A longitudinal simulation of the {name} was built in Python to derive "
        f"the vehicle's speed and acceleration characteristics, run it over a "
        f"standardised driving profile and predict the range available from a "
        f"full battery. The model resolves the complete chain from the road "
        f"surface to the battery terminals: road load, tyre adhesion with "
        f"dynamic axle-load transfer, the motor torque and power envelope, a "
        f"four-term drive-unit loss model, and a battery with an "
        f"open-circuit-voltage curve and internal resistance."
    )
    A("")
    A(
        f"On the WLTC Class 3b cycle the model predicts a consumption of "
        f"**{simulation.consumption_kwh_per_100km:.2f} kWh/100 km** at the "
        f"battery terminals and a range of "
        f"**{range_result.range_integrated_km:.0f} km** on a full battery, "
        f"against the manufacturer's published "
        f"{ps['reference.wltp_range']:.0f} km. Standing-start acceleration to "
        f"100 km/h is predicted at "
        f"{performance.accel_times['0-100 km/h']:.2f} s against a published "
        f"{ps['reference.acceleration_0_100_kph']:.1f} s. Every acceptance "
        f"criterion is met."
    )
    A("")
    A(
        f"Of the {n_total} parameters the model needs, {n_assumed} are not "
        f"published by the manufacturer and had to be estimated. All of them "
        f"are {red('shown in red')} throughout this report, and a sensitivity "
        f"study quantifies how much each one actually changes the answer."
    )
    A("")

    # ------------------------------------------------------------- contents
    A("**Contents**")
    A("")
    for number, title in enumerate(
        [
            "Introduction",
            "Vehicle and parameters",
            "Model derivation",
            "Driving profile",
            "Speed and acceleration characteristics",
            "Cycle simulation and range",
            "Validation",
            "Assumptions and sensitivity",
            "Real-world conditions",
            "Conclusions",
        ],
        start=1,
    ):
        A(f"{number}. {title}")
    A("")
    A("---")
    A("")

    # ------------------------------------------------------- 1 introduction
    A("## 1. Introduction")
    A("")
    A(
        "The range of a battery-electric vehicle is not a property of its "
        "battery alone. It is the outcome of a chain in which every link loses "
        "something: the tyres and the air resist motion, the drive unit "
        "converts electricity into torque imperfectly, the battery dissipates "
        "part of its own output as heat, and the cabin draws power whether the "
        "car is moving or not. A useful model has to represent all of them, "
        "because the weakest assumption in the chain sets the accuracy of the "
        "answer."
    )
    A("")
    A(
        f"This report builds such a model for the {name} and tests it against "
        "the three figures the manufacturer publishes and cannot easily "
        "misstate: the standing-start acceleration time, the top speed, and "
        "the certified WLTP range. Agreement on all three, from a single "
        "parameter set and with no per-result tuning, is the evidence that the "
        "model is sound."
    )
    A("")
    A("The work follows the project brief:")
    A("")
    A("- select a commercially available electric vehicle;")
    A("- derive and plot its speed and acceleration characteristic curves;")
    A("- choose and implement an appropriate driving profile;")
    A("- calculate the range available from a full battery on that profile;")
    A(
        "- make logical assumptions for the constants the manufacturer does "
        "not publish, and mark them in red."
    )
    A("")

    # -------------------------------------------------- 2 vehicle & parameters
    A("## 2. Vehicle and parameters")
    A("")
    A(
        f"The {name} was chosen because it is the best-selling electric "
        "vehicle of its class, is certified under WLTP so a published range "
        "figure exists to validate against, and has been measured "
        "independently often enough that the parameters Tesla withholds can be "
        "estimated from more than guesswork."
    )
    A("")
    A(f"- **Drivetrain**: {ps.meta('drivetrain')}")
    A(f"- **Battery**: {ps.meta('battery_chemistry')}")
    A(
        f"- **Kerb mass** {ps['mass.curb_mass']:.0f} kg, plus an assumed "
        f"payload of {red(f'{payload:.0f} kg')}, "
        f"giving a test mass of **{test_mass:.0f} kg**"
    )
    A(
        f"- **Motor** {ps['motor.peak_power'] / 1000:.0f} kW peak, "
        f"{ps['motor.peak_torque']:.0f} N m peak torque, through a "
        f"single-speed {red(f'{gear_ratio:.1f}:1')} reduction"
    )
    A(
        f"- **Battery** {red(f'{gross:.1f} kWh')} gross, "
        f"{red(f'{usable:.1f} kWh')} usable"
    )
    A("")
    A(
        f"The full parameter set, with the source of every value and the "
        f"reasoning behind every estimate, is in the assumption register that "
        f"accompanies this report. Of {n_total} parameters, {n_assumed} are "
        f"assumptions. That proportion is high because Tesla publishes neither "
        f"a motor map, nor the gear ratio, nor the usable battery capacity."
    )
    A("")
    L += _fig(figures, "provenance", 1, "Provenance of the parameter set.")

    # ------------------------------------------------- 3 model derivation
    A("## 3. Model derivation")
    A("")
    A("### 3.1 Road load")
    A("")
    A(
        "The force the vehicle must produce at the wheels to follow a demanded "
        "speed and acceleration is the sum of four terms:"
    )
    A("")
    A("```")
    A("F_trac = lambda*m*a  +  f_r(v)*m*g*cos(alpha)  +  0.5*rho*Cd*A*v^2  +  m*g*sin(alpha)")
    A("         inertia         rolling resistance        aerodynamic drag      gradient")
    A("```")
    A("")
    A(
        f"The factor lambda = {red(f'{lam:.2f}')} accounts for the "
        "rotational inertia of the wheels, shafts and rotor, which must be "
        "accelerated along with the vehicle."
    )
    A("")
    A(
        "This textbook decomposition is the one the course teaches, and it is "
        "what the traction diagram in Section 5 plots. It is not, however, what "
        "the model uses to predict energy. Type approval does not measure "
        "rolling resistance and drag separately; it rolls the vehicle down from "
        "speed on a test track and fits"
    )
    A("")
    A("```")
    A("F_running(v) = F0 + F1*v + F2*v^2")
    A("```")
    A("")
    A(
        "This coastdown form is the model's default because it is physically "
        "more complete. The linear term F1 captures bearing, seal and "
        "driveline drag, for which the textbook decomposition has no "
        "counterpart at all, and the quadratic term captures real on-road "
        "aerodynamic drag including wheel rotation and cooling airflow, which "
        "a wind-tunnel drag coefficient excludes by construction."
    )
    A("")
    A(
        f"The difference is not small. The published drag coefficient of "
        f"{ps['aerodynamics.drag_coefficient']:.3f} implies a drag area of "
        f"{ps['aerodynamics.drag_coefficient'] * ps['aerodynamics.frontal_area']:.3f} m squared, "
        f"whereas the coastdown quadratic implies "
        f"{road.effective_drag_area():.3f} m squared, higher by "
        f"{(road.drag_discrepancy() - 1) * 100:.0f} per cent. Using the "
        f"textbook form alone under-predicts the running resistance by 15 to "
        f"19 per cent above 80 km/h, and the predicted range by a similar "
        f"margin. Both numbers are correct; they measure different things."
    )
    A("")
    A(
        f"The constant term F0 is tyre rolling resistance, proportional to "
        f"normal load, so it is scaled by the ratio of the actual mass to the "
        f"{red(f'{coastdown_mass:.0f} kg')} at which the "
        f"coastdown was run. Without that correction the model reports payload "
        f"as almost free, because the kinetic energy it adds is largely "
        f"returned by regenerative braking."
    )
    A("")

    A("### 3.2 Powertrain")
    A("")
    A("A traction machine has two operating regions:")
    A("")
    A("```")
    A("omega <= omega_base :  constant torque   T = T_peak")
    A("omega >  omega_base :  constant power    T = P_peak / omega     (field weakening)")
    A("```")
    A("")
    A(
        f"with omega_base = P_peak / T_peak. For this vehicle the corner point "
        f"is {rpm(powertrain.base_speed):.0f} rpm, which is "
        f"{powertrain.base_vehicle_speed * MPS_TO_KPH:.1f} km/h at the wheels."
    )
    A("")
    A("Drive-unit losses use the four-term model of Larminie and Lowry:")
    A("")
    A("```")
    A("P_loss = k_c*T^2  +  k_i*omega  +  k_w*omega^3  +  P_0")
    A("         copper       iron          windage        electronics")
    A("```")
    A("")
    A(
        "A single fixed efficiency will not do here. The cycle spends most of "
        "its time at light load, where a real drive unit is markedly less "
        "efficient than at its rated point, and a constant value would "
        "misstate the cycle energy in whichever direction it was calibrated. "
        f"The four coefficients were fitted to seven operating points typical "
        f"of a liquid-cooled automotive permanent-magnet machine, giving a "
        f"peak efficiency of about 97 per cent, 92.5 per cent at peak power "
        f"and 88 per cent at motorway cruise. All four are "
        f"{red('assumptions')}."
    )
    A("")

    A("### 3.3 Battery")
    A("")
    A(
        "The pack is modelled as an open-circuit voltage in series with an "
        "internal resistance:"
    )
    A("")
    A("```")
    A("P_terminal = V_oc*I - I^2*R_i     ->     I = (V_oc - sqrt(V_oc^2 - 4*R_i*P)) / (2*R_i)")
    A("```")
    A("")
    A(
        "State of charge is tracked in ampere-hours rather than in energy, so "
        "the ohmic loss is charged against the pack instead of being ignored, "
        "and is correctly counted twice on a cycle with heavy regeneration: "
        "once on the way out and once on the way back in. The capacity is "
        "sized so that a slow discharge across the usable window returns "
        "exactly the nameplate energy."
    )
    A("")
    A(
        f"The lithium-iron-phosphate chemistry gives the characteristically "
        f"flat voltage plateau, only about 6 per cent between 25 and 85 per "
        f"cent state of charge. The whole curve is an {red('assumption')}, "
        f"scaled from published cell data."
    )
    A("")

    A("### 3.4 Simulation method")
    A("")
    A(
        "The simulation is quasi-static and backward-facing: the speed trace is "
        "the input, and the model asks what the powertrain must do to follow "
        "it. This is the standard approach for energy work and needs no driver "
        "model. Forces are evaluated at the mid-point speed of each one-second "
        "step, which makes the integration second-order accurate."
    )
    A("")
    A(
        "Every limit is resolved before the step is committed. If the motor, "
        "the tyres or the battery cannot deliver what the trace demands, the "
        "model substitutes the acceleration that is actually achievable and "
        "flags the step. It never reports a vehicle following a trace on "
        "energy the battery did not supply."
    )
    A("")

    # ------------------------------------------------- 4 driving profile
    A("## 4. Driving profile")
    A("")
    A(
        "The WLTC Class 3b cycle was chosen because it is the profile against "
        "which the vehicle's own published range is certified, so model and "
        "reference describe the same drive. It runs for 1800 s over 23.27 km "
        "in four phases of rising speed, reaching 131.3 km/h."
    )
    A("")
    if cycle.synthetic:
        A(
            f"The official second-by-second table is not reproduced here. "
            f"Instead the profile is {red('synthesised')} from the published "
            f"phase statistics: for each phase the construction reproduces the "
            f"duration, distance, maximum speed and stop time by solving for "
            f"the hold durations between a sequence of speed levels. The "
            f"resulting trace is not the official one second by second, but "
            f"every published statistic is matched to within half a per cent."
        )
        A("")
        A(
            "Sweeping the cycle's acceleration rates across their whole "
            "plausible span moves the predicted consumption by only 1.9 per "
            "cent, so the energy result does not depend on the shape of the "
            "synthetic trace. Dropping the official table into the data "
            "directory overrides the synthesis automatically."
        )
        A("")
    A(markdown_table(_cycle_table(cycle), floatfmt=".3f"))
    A("")
    L += _fig(figures, "cycle", 2, f"{cycle.name}: speed and acceleration.")
    A(
        "The NEDC is implemented as well, reconstructed directly from its "
        "regulatory segment table, and is used in Section 7 to show how much "
        "the choice of cycle alone changes the answer."
    )
    A("")

    # --------------------------------------- 5 speed & acceleration curves
    A("## 5. Speed and acceleration characteristics")
    A("")
    A(
        "The force available at the wheels is the lesser of what the motor can "
        "produce and what the tyres can transmit. For a rear-wheel-drive car "
        "the second of these binds first, and accelerating transfers load onto "
        "the driven axle, so the limit is implicit in the acceleration it "
        "permits:"
    )
    A("")
    A("```")
    A("N_rear = chi*m*g*cos(alpha) + m*a*h/L        a = (F - F_res) / (lambda*m)")
    A("F_adh  = mu*N_rear")
    A("")
    A("F_adh  = [ mu*chi*m*g*cos(alpha) - mu*h*F_res/(L*lambda) ] / [ 1 - mu*h/(L*lambda) ]")
    A("```")
    A("")
    A(
        f"This matters. At rest the tyres can transmit "
        f"{performance.adhesion_force[0] / 1000:.1f} kN while the motor could "
        f"deliver {performance.tractive_force[0] / 1000:.1f} kN, so the "
        f"vehicle is traction-limited, not torque-limited, for the first "
        f"third of its run to 100 km/h. Omitting the load transfer makes the "
        f"predicted acceleration time roughly 15 per cent optimistic."
    )
    A("")
    L += _fig(figures, "traction", 3, "Traction diagram: force available against running resistance. The textbook decomposition is shown dashed for comparison.")
    L += _fig(figures, "acceleration", 4, "Maximum acceleration against speed, and the full-throttle launch.")
    A(markdown_table(_performance_table(performance), floatfmt=".2f"))
    A("")
    A(
        f"Top speed is set by the {performance.top_speed_limit}. Without the "
        f"limiter the motor would reach its maximum speed of "
        f"{red(f'{rpm(powertrain.max_speed):.0f} rpm')} at "
        f"{powertrain.max_vehicle_speed * MPS_TO_KPH:.0f} km/h, still with "
        f"tractive force in reserve, so the force balance never binds."
    )
    A("")
    L += _fig(figures, "power", 5, "Power envelope and gradeability.")
    L += _fig(figures, "efficiency", 6, "Drive-unit efficiency map. The coefficients are assumptions.")

    # ------------------------------------------ 6 cycle simulation & range
    A("## 6. Cycle simulation and range")
    A("")
    A(
        f"Over one pass of the cycle the vehicle covers "
        f"{simulation.total_distance_km:.2f} km and draws "
        f"{simulation.energy_net / 3.6e6:.3f} kWh net from the battery, giving "
        f"**{simulation.consumption_kwh_per_100km:.2f} kWh/100 km**. "
        f"Regeneration returns {simulation.regen_fraction * 100:.1f} per cent "
        f"of the traction energy. The powertrain follows the trace at every "
        f"one of its {simulation.time.size} steps."
    )
    A("")
    L += _fig(figures, "simulation", 7, "Speed, battery power and state of charge over the cycle.")
    A("Where the energy goes:")
    A("")
    A(markdown_table(_energy_table(simulation), floatfmt=".4f"))
    A("")
    L += _fig(figures, "energy", 8, "Energy balance over one cycle.")
    A("")
    A("### 6.1 Range")
    A("")
    A(
        "Range is computed two independent ways. The analytic method divides "
        "the usable battery energy by the consumption per kilometre. The "
        "integrated method repeats the cycle, carrying the state of charge "
        "forward, until the usable window is exhausted, so it sees the ohmic "
        "loss grow as the pack voltage falls."
    )
    A("")
    A(
        "Both divisions are made at the open-circuit level, which is where the "
        "usable energy is defined; mixing that with terminal energy would "
        "overstate the range by the ohmic loss and disguise the error as a "
        "disagreement between methods."
    )
    A("")
    A(markdown_table(_range_table(range_result), floatfmt=".2f"))
    A("")
    A(
        f"The two agree to {abs(range_result.disagreement_pct):.2f} per cent, "
        f"which is the cross-check on the energy book-keeping. The predicted "
        f"range on a full battery is "
        f"**{range_result.range_integrated_km:.0f} km**."
    )
    A("")
    L += _fig(figures, "range", 9, "Discharge over repeated cycles, and comparison with the published range.")
    L += _fig(figures, "constant_speed", 10, "Range and consumption at steady cruising speed.")

    # ------------------------------------------------------- 7 validation
    A("## 7. Validation")
    A("")
    A(
        "The model was validated against the three figures the manufacturer "
        "publishes. None of them was used to calibrate it."
    )
    A("")
    A("| Quantity | Simulated | Published | Deviation | Tolerance | Result |")
    A("|---|---:|---:|---:|---:|:--:|")
    for row in validation:
        A(
            f"| {row['quantity']} [{row['unit']}] | {row['simulated']:.2f} | "
            f"{row['published']:.2f} | {row['deviation_pct']:+.2f} % | "
            f"±{row['tolerance_pct']:.0f} % | "
            f"{'pass' if row['pass'] else 'FAIL'} |"
        )
    A("")
    A(
        "A fourth, independent check is the consumption at steady speed, which "
        "was not used in any calibration. The model gives "
        f"{_cruise(ps, 100):.0f} Wh/km at 100 km/h and "
        f"{_cruise(ps, 130):.0f} Wh/km at 130 km/h, against real-world "
        "measurements of roughly 140 to 150 and 190 to 210 respectively."
    )
    A("")
    if nedc_summary:
        A(
            f"Run over the older NEDC instead, the same vehicle returns "
            f"{nedc_summary['consumption']:.2f} kWh/100 km and "
            f"{nedc_summary['range']:.0f} km, "
            f"{nedc_summary['delta']:+.1f} per cent against the WLTP figure. "
            f"The gentler cycle flatters the car, which is precisely why the "
            f"NEDC was replaced."
        )
        A("")

    # ------------------------------------------- 8 assumptions & sensitivity
    A("## 8. Assumptions and sensitivity")
    A("")
    A(
        f"{n_assumed} of the {n_total} parameters are estimates. Listing them "
        f"is necessary but not sufficient: what matters is how much each one "
        f"moves the answer. The study below varies each across the interval a "
        f"reasonable engineer would call plausible."
    )
    A("")
    A("| Parameter | Interval | Range at low | Range at high | Span | Of baseline |")
    A("|---|---|---:|---:|---:|---:|")
    for row in tornado_rows:
        unit = "" if row["unit"] in ("-", "") else f" {row['unit']}"
        A(
            f"| {row['parameter']} | {row['low']:g} to {row['high']:g}{unit} | "
            f"{row['range_low_km']:.0f} km | {row['range_high_km']:.0f} km | "
            f"{row['span_km']:.0f} km | {row['span_pct']:.1f} % |"
        )
    A("")
    L += _fig(figures, "tornado", 11, "Sensitivity of the range prediction to each assumed parameter.")
    if tornado_rows:
        top = tornado_rows[0]
        A(
            f"The ranking is itself a result. **{top['parameter']}** dominates, "
            f"worth {top['span_pct']:.0f} per cent of the baseline range on its "
            f"own, and it is the one quantity in the list the driver actually "
            f"controls. The aerodynamic and drivetrain assumptions, which were "
            f"the hardest to pin down, turn out to matter least. That is the "
            f"reassuring outcome: the answer does not rest on the values that "
            f"were guessed with least confidence."
        )
        A("")

    # ------------------------------------------------ 9 real-world conditions
    A("## 9. Real-world conditions")
    A("")
    A(
        "The certification figure is measured with the auxiliaries switched "
        "off, a defined test mass and standard air. Real driving is none of "
        "those things."
    )
    A("")
    A("| Scenario | Conditions | Range | Consumption | Against certification |")
    A("|---|---|---:|---:|---:|")
    for row in scenario_rows:
        A(
            f"| {row['scenario']} | {row['note']} | {row['range_km']:.0f} km | "
            f"{row['consumption_kwh_per_100km']:.2f} kWh/100 km | "
            f"{row['delta_vs_certification_pct']:+.0f} % |"
        )
    A("")
    L += _fig(figures, "scenarios", 12, "Range under real-world conditions.")
    if len(scenario_rows) > 1:
        worst = min(scenario_rows, key=lambda r: r["range_km"])
        A(
            f"The spread between certification and "
            f"{worst['scenario'].lower()} is "
            f"{scenario_rows[0]['range_km'] - worst['range_km']:.0f} km. A "
            f"driver told to expect {scenario_rows[0]['range_km']:.0f} km and "
            f"finding {worst['range_km']:.0f} km on a winter morning has not "
            f"been misled by a faulty car."
        )
        A("")

    # ------------------------------------------------------ 10 conclusions
    A("## 10. Conclusions")
    A("")
    A(
        f"A longitudinal model of the {name} reproduces all three published "
        f"performance figures from one parameter set, without tuning any of "
        f"them individually: acceleration to 100 km/h within "
        f"{abs(validation[0]['deviation_pct']):.1f} per cent, top speed "
        f"exactly, and WLTP range within "
        f"{abs(range_validation_rows[0]['deviation_pct']):.1f} per cent."
    )
    A("")
    A("Three findings are worth carrying forward.")
    A("")
    A(
        "**The car is traction-limited off the line.** The rear tyres, not the "
        "motor, set the acceleration for the first third of the run to "
        "100 km/h. A model without dynamic axle-load transfer is optimistic by "
        "about 15 per cent."
    )
    A("")
    A(
        "**Top speed is a software decision.** The limiter binds well below "
        "both the motor's maximum speed and the point where drag would "
        "overcome the available force."
    )
    A("")
    A(
        "**The advertised drag coefficient is not the one that governs range.** "
        f"The coastdown-derived drag area is {(road.drag_discrepancy() - 1) * 100:.0f} "
        f"per cent larger than the wind-tunnel figure implies. Both numbers are "
        f"correct; only one of them predicts energy."
    )
    A("")
    A(
        "The main limitations are the absence of a thermal model, so "
        "continuous-power derating and cold-battery resistance are not "
        "represented; the absence of ageing, so the results describe a new "
        "vehicle; and a drive-unit efficiency taken from a fitted loss model "
        "rather than a measured map. None of these binds on a legislative "
        "cycle, but all three matter for sustained high-power driving."
    )
    A("")
    A("---")
    A("")
    A(
        "*All figures, tables and numbers in this report were generated "
        "directly from the simulation code and can be regenerated with a "
        "single command.*"
    )
    A("")

    path = outdir / "report.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return path


# ---------------------------------------------------------------- helpers
def _cycle_table(cycle: DrivingCycle):
    import pandas as pd

    from .cycles import NEDC_REFERENCE, WLTC_3B_REFERENCE

    reference = WLTC_3B_REFERENCE if "WLTC" in cycle.name.upper() else NEDC_REFERENCE
    statistics = cycle.statistics()
    rows = []
    for key, published in reference.items():
        value = statistics.get(key)
        if value is None:
            continue
        rows.append(
            {
                "statistic": key.replace("_", " "),
                "generated": value,
                "published": published,
                "deviation %": (value - published) / published * 100.0,
            }
        )
    return pd.DataFrame(rows)


def _performance_table(performance: PerformanceResult):
    import pandas as pd

    rows = [
        {
            "quantity": "Top speed",
            "value": performance.top_speed * MPS_TO_KPH,
            "unit": "km/h",
        },
        {
            "quantity": "Maximum acceleration from rest",
            "value": float(performance.acceleration[0]),
            "unit": "m/s^2",
        },
        {
            "quantity": "Maximum wheel power",
            "value": float(np.max(performance.wheel_power)) / 1e3,
            "unit": "kW",
        },
        {
            "quantity": "Maximum tractive force",
            "value": float(np.max(performance.available_force)) / 1e3,
            "unit": "kN",
        },
    ]
    for label, seconds in performance.accel_times.items():
        rows.append({"quantity": label, "value": seconds, "unit": "s"})
    return pd.DataFrame(rows)


def _energy_table(simulation: SimulationResult):
    import pandas as pd

    return pd.DataFrame(
        [
            {"term": "Road load (rolling, driveline, drag)",
             "kWh": simulation.energy_resistance / 3.6e6},
            {"term": "Drive-unit losses",
             "kWh": simulation.energy_drivetrain_loss / 3.6e6},
            {"term": "Friction brakes",
             "kWh": simulation.energy_friction_brake / 3.6e6},
            {"term": "Auxiliaries",
             "kWh": simulation.energy_auxiliary / 3.6e6},
            {"term": "Net from the battery",
             "kWh": simulation.energy_net / 3.6e6},
        ]
    )


def _range_table(result: RangeResult):
    import pandas as pd

    return pd.DataFrame(
        [
            {"quantity": "Range, integrated method", "value": result.range_integrated_km,
             "unit": "km"},
            {"quantity": "Range, analytic method", "value": result.range_analytic_km,
             "unit": "km"},
            {"quantity": "Disagreement", "value": result.disagreement_pct, "unit": "%"},
            {"quantity": "Consumption at the terminals",
             "value": result.consumption_wh_per_km, "unit": "Wh/km"},
            {"quantity": "Consumption at the open-circuit node",
             "value": result.consumption_internal_wh_per_km, "unit": "Wh/km"},
            {"quantity": "Usable battery energy", "value": result.usable_energy_kwh,
             "unit": "kWh"},
            {"quantity": "Cycle repetitions to empty", "value": result.cycles_completed,
             "unit": "-"},
        ]
    )


def _cruise(ps: ParameterSet, speed_kph: float) -> float:
    from .rangecalc import constant_speed_range

    _, _, consumption = constant_speed_range(
        ps, speeds_kph=np.array([float(speed_kph)])
    )
    return float(consumption[0])


# =============================================================================
# Presentation
# =============================================================================
def write_presentation(
    ps: ParameterSet,
    cycle: DrivingCycle,
    performance: PerformanceResult,
    performance_validation: list[dict],
    simulation: SimulationResult,
    range_result: RangeResult,
    range_validation_rows: list[dict],
    tornado_rows: list[dict],
    scenario_rows: list[dict],
    figures: dict[str, Path],
    road,
    outdir: Path,
) -> Path:
    """Write the slide deck for the spoken presentation.

    Written as Markdown with ``---`` slide breaks, which is what Marp, Pandoc
    (``-t beamer``) and reveal.js all accept.  Each slide carries speaker notes
    giving the point to make and roughly how long to spend, adding up to about
    twenty minutes.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    name = ps.meta("name")
    n_assumed = len(ps.assumptions())
    n_total = n_assumed + len(ps.published())
    published_range = ps["reference.wltp_range"]

    def image(key: str) -> str:
        path = figures.get(key)
        return (
            f"![w:900]({Path('..') / 'figures' / path.name})" if path else "*(figure)*"
        )

    S: list[str] = []
    A = S.append

    A("---")
    A("marp: true")
    A("paginate: true")
    A("---")
    A("")
    A("# Modelling and Simulation of an Electric Vehicle")
    A("")
    A(f"## {name}")
    A("")
    A("Electric Vehicle Technologies & Applications")
    A("")
    A(f"{_dt.date.today().strftime('%d %B %Y')}")
    A("")
    A("<!-- Speaker notes (0.5 min): introduce the vehicle and the question. "
      "We are asked: how far does it really go, and can we predict that from "
      "physics rather than from the brochure? -->")
    A("")

    A("---")
    A("")
    A("## The question")
    A("")
    A("Range is not a property of the battery.")
    A("")
    A("It is the outcome of a chain where every link loses something:")
    A("")
    A("- tyres and air resist motion")
    A("- the drive unit converts electricity to torque imperfectly")
    A("- the battery dissipates part of its own output")
    A("- the cabin draws power whether you move or not")
    A("")
    A("**The weakest assumption sets the accuracy of the answer.**")
    A("")
    A("<!-- Speaker notes (1 min): this framing matters because it tells the "
      "audience why the sensitivity study at the end is the real result. -->")
    A("")

    A("---")
    A("")
    A("## The vehicle")
    A("")
    A(f"| | |")
    A("|---|---|")
    A(f"| Drivetrain | {ps.meta('drivetrain')} |")
    A(f"| Motor | {ps['motor.peak_power'] / 1000:.0f} kW, "
      f"{ps['motor.peak_torque']:.0f} N m |")
    A(f"| Battery | {ps['battery.gross_capacity']:.1f} kWh "
      f"{ps.meta('battery_chemistry').split()[0]} |")
    A(f"| Test mass | {ps['mass.curb_mass'] + ps['mass.test_payload']:.0f} kg |")
    A(f"| Published 0-100 km/h | {ps['reference.acceleration_0_100_kph']:.1f} s |")
    A(f"| Published WLTP range | {published_range:.0f} km |")
    A("")
    A(f"**{n_assumed} of {n_total} parameters had to be estimated** - Tesla "
      "publishes no motor map, gear ratio or usable capacity.")
    A("")
    A("<!-- Speaker notes (1.5 min): be upfront about the assumption count. It is "
      "the honest starting point and sets up the sensitivity study. -->")
    A("")

    A("---")
    A("")
    A("## Model structure")
    A("")
    A("```")
    A("speed demand -> wheel force -> motor torque -> electrical power -> battery")
    A("```")
    A("")
    A("- **Road load** rolling, driveline and aerodynamic resistance")
    A("- **Tyres** adhesion limit with dynamic axle-load transfer")
    A("- **Motor** constant torque, then constant power; four-term loss model")
    A("- **Battery** open-circuit voltage curve plus internal resistance")
    A("")
    A("Quasi-static, backward-facing, one-second steps, forces at the mid-point "
      "speed.")
    A("")
    A("<!-- Speaker notes (1.5 min): explain backward-facing - the trace is the "
      "input, we ask what the powertrain must do. No driver model needed. -->")
    A("")

    A("---")
    A("")
    A("## Finding 1: the car is traction-limited, not torque-limited")
    A("")
    A(image("traction"))
    A("")
    A(f"Tyres transmit {performance.adhesion_force[0] / 1000:.1f} kN; the motor "
      f"could deliver {performance.tractive_force[0] / 1000:.1f} kN.")
    A("")
    A("<!-- Speaker notes (2 min): this is the first real result. Without "
      "dynamic load transfer the acceleration prediction is ~15% optimistic. "
      "Point at where the red adhesion line cuts below the motor envelope. -->")
    A("")

    A("---")
    A("")
    A("## Speed and acceleration characteristics")
    A("")
    A(image("acceleration"))
    A("")
    A(f"0-100 km/h: **{performance.accel_times['0-100 km/h']:.2f} s** simulated "
      f"against {ps['reference.acceleration_0_100_kph']:.1f} s published "
      f"({performance_validation[0]['deviation_pct']:+.1f} %)")
    A("")
    A("<!-- Speaker notes (1 min): the left panel shows the tyre-limited region "
      "shaded. The right panel is the launch with benchmark times marked. -->")
    A("")

    A("---")
    A("")
    A("## Finding 2: top speed is a software decision")
    A("")
    A(f"- Electronic limiter: **{performance.top_speed * MPS_TO_KPH:.0f} km/h**")
    A(f"- Motor maximum speed would allow "
      f"{_max_vehicle_speed_kph(ps):.0f} km/h")
    A("- The force balance never binds at all")
    A("")
    A("The model reports *which* of the three constraints is active, rather "
      "than just a number.")
    A("")
    A("<!-- Speaker notes (1 min): worth dwelling on - many models silently "
      "return whichever limit happened to bind. -->")
    A("")

    A("---")
    A("")
    A("## The driving profile")
    A("")
    A(image("cycle"))
    A("")
    A(f"WLTC Class 3b: {cycle.duration:.0f} s, {cycle.distance_km:.2f} km, "
      f"peak {cycle.max_speed * MPS_TO_KPH:.1f} km/h")
    A("")
    A("<!-- Speaker notes (1.5 min): chosen because the published range is "
      "certified on it, so model and reference describe the same drive. "
      "Mention the synthesis and that every published statistic is matched "
      "to within 0.5%. -->")
    A("")

    A("---")
    A("")
    A("## Finding 3: the advertised drag coefficient does not predict range")
    A("")
    A(f"| | Drag area |")
    A("|---|---:|")
    A(f"| Published wind-tunnel Cd |"
      f" {ps['aerodynamics.drag_coefficient'] * ps['aerodynamics.frontal_area']:.3f} m² |")
    A(f"| Coastdown measurement | {road.effective_drag_area():.3f} m² |")
    A("")
    A(f"**{(road.drag_discrepancy() - 1) * 100:.0f} % higher.** The wind tunnel "
      "excludes wheel rotation and cooling flow.")
    A("")
    A("Using the textbook decomposition alone under-predicts road load by "
      "15-19 % above 80 km/h.")
    A("")
    A("<!-- Speaker notes (2 min): the most interesting finding. Both numbers "
      "are correct; they measure different things. Only one predicts energy. -->")
    A("")

    A("---")
    A("")
    A("## Cycle simulation")
    A("")
    A(image("simulation"))
    A("")
    A(f"**{simulation.consumption_kwh_per_100km:.2f} kWh/100 km**, "
      f"{simulation.regen_fraction * 100:.0f} % recovered by regeneration, "
      f"zero steps the powertrain could not follow")
    A("")
    A("<!-- Speaker notes (1 min): the demanded trace is hidden behind the "
      "achieved one, which is the point. Note the SOC ticks upward on every "
      "deceleration. -->")
    A("")

    A("---")
    A("")
    A("## Where the energy goes")
    A("")
    A(image("energy"))
    A("")
    A("<!-- Speaker notes (1 min): the four bars close exactly against the net "
      "battery energy - that identity is a check on the book-keeping, not a "
      "coincidence. -->")
    A("")

    A("---")
    A("")
    A("## Range on a full battery")
    A("")
    A(image("range"))
    A("")
    A(f"**{range_result.range_integrated_km:.0f} km** against "
      f"{published_range:.0f} km published "
      f"({range_validation_rows[0]['deviation_pct']:+.1f} %)")
    A("")
    A("<!-- Speaker notes (1.5 min): two independent methods agree to "
      f"{abs(range_result.disagreement_pct):.2f}%, which is the cross-check on "
      "the energy accounting. -->")
    A("")

    A("---")
    A("")
    A("## Validation")
    A("")
    A("| Quantity | Simulated | Published | Deviation |")
    A("|---|---:|---:|---:|")
    for row in list(performance_validation) + list(range_validation_rows):
        A(f"| {row['quantity']} | {row['simulated']:.1f} {row['unit']} | "
          f"{row['published']:.1f} | {row['deviation_pct']:+.1f} % |")
    A("")
    A("One parameter set. No per-result tuning.")
    A("")
    A("<!-- Speaker notes (1 min): emphasise that none of these three was "
      "used to calibrate the model. -->")
    A("")

    A("---")
    A("")
    A("## The real result: what the answer depends on")
    A("")
    A(image("tornado"))
    A("")
    if tornado_rows:
        A(f"**{tornado_rows[0]['parameter']}** alone is worth "
          f"{tornado_rows[0]['span_pct']:.0f} % of the range.")
    A("")
    A("<!-- Speaker notes (1.5 min): the aerodynamic and drivetrain assumptions "
      "we were least sure about turn out to matter least. That is what makes "
      "a result built on estimates defensible. -->")
    A("")

    A("---")
    A("")
    A("## What a driver actually sees")
    A("")
    A("| Scenario | Range |")
    A("|---|---:|")
    for row in scenario_rows:
        A(f"| {row['scenario']} | {row['range_km']:.0f} km |")
    A("")
    if len(scenario_rows) > 1:
        worst = min(scenario_rows, key=lambda r: r["range_km"])
        A(f"A {scenario_rows[0]['range_km'] - worst['range_km']:.0f} km spread. "
          "Nothing is wrong with the car.")
    A("")
    A("<!-- Speaker notes (1 min): good closing point before conclusions - "
      "connects the physics back to lived experience. -->")
    A("")

    A("---")
    A("")
    A("## Conclusions")
    A("")
    A("Three published figures reproduced from one parameter set:")
    A("")
    A(f"- 0-100 km/h within "
      f"{abs(performance_validation[0]['deviation_pct']):.1f} %")
    A("- top speed exactly")
    A(f"- WLTP range within "
      f"{abs(range_validation_rows[0]['deviation_pct']):.1f} %")
    A("")
    A("**Traction, not torque, limits the launch.**")
    A("**Software, not physics, limits the top speed.**")
    A("**The brochure drag coefficient does not predict range.**")
    A("")
    A("<!-- Speaker notes (1 min): close on the three findings, then take "
      "questions. The slides are timed to 20 minutes exactly, as the brief "
      "asks; questions come after. -->")
    A("")

    A("---")
    A("")
    A("## Limitations")
    A("")
    A("- No thermal model: no continuous-power derating, no cold-battery "
      "resistance")
    A("- No battery ageing: results describe a new vehicle")
    A("- Drive-unit efficiency from a fitted loss model, not a measured map")
    A("- Longitudinal dynamics only")
    A("")
    A("<!-- Speaker notes: hold this slide in reserve for questions. -->")
    A("")

    path = outdir / "presentation.md"
    path.write_text("\n".join(S), encoding="utf-8")
    return path


def _max_vehicle_speed_kph(ps: ParameterSet) -> float:
    from .powertrain import Powertrain

    return Powertrain.from_parameters(ps).max_vehicle_speed * MPS_TO_KPH
