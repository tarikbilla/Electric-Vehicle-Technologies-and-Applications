"""End-to-end study: one call regenerates every figure, table and document.

This is the reproducibility requirement of the PRD: ``python scripts/run_all.py``
(or ``evsim run``) rebuilds the complete set of results from the parameter file
alone, with nothing carried over from a previous run.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import document, plotting, report
from .cycles import NEDC_REFERENCE, WLTC_3B_REFERENCE, DrivingCycle, nedc, to_csv
from .parameters import ParameterSet
from .performance import PerformanceModel
from .rangecalc import constant_speed_range, range_on_cycle, range_validation
from .sensitivity import scenarios, tornado
from .simulation import CycleSimulator
from .units import MPS_TO_KPH


def _banner(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


def _cycle_slug(cycle: DrivingCycle) -> str:
    """Filename stem matching the key the cycle loader looks for."""
    return cycle.name.split(" (")[0].lower().replace(" ", "").replace("-", "_")


def _reference_for(cycle: DrivingCycle) -> dict[str, float]:
    """Published statistics to validate this cycle against.

    Only the two built-in cycles have published statistics.  A user-supplied
    profile is validated against itself - an empty reference - rather than
    silently against the NEDC, which would fill the report with meaningless
    deviations.
    """
    name = cycle.name.upper()
    if "WLTC" in name or "WLTP" in name:
        return WLTC_3B_REFERENCE
    if "NEDC" in name:
        return NEDC_REFERENCE
    return {}


def run_study(
    ps: ParameterSet,
    cycle: DrivingCycle,
    outdir: Path = Path("results"),
    run_sensitivity: bool = True,
) -> dict[str, object]:
    """Run the complete study and write every output under ``outdir``."""
    started = time.perf_counter()

    figures_dir = outdir / "figures"
    tables_dir = outdir / "tables"
    report_dir = outdir / "report"
    for directory in (figures_dir, tables_dir, report_dir):
        directory.mkdir(parents=True, exist_ok=True)

    with plotting.plt.rc_context(plotting.STYLE):
        figures: dict[str, Path] = {}

        # ------------------------------------------------- 1. performance
        _banner("1. Speed and acceleration characteristics")
        performance_model = PerformanceModel(ps)
        performance = performance_model.run()
        gradeability = performance_model.gradeability(performance.speed)

        print(f"  top speed          {performance.top_speed * MPS_TO_KPH:7.1f} km/h"
              f"  ({performance.top_speed_limit})")
        for label, seconds in performance.accel_times.items():
            print(f"  {label:18s} {seconds:7.2f} s")

        figures["traction"] = plotting.plot_tractive_force(performance, figures_dir)
        figures["acceleration"] = plotting.plot_acceleration_curve(performance, figures_dir)
        figures["power"] = plotting.plot_power_and_gradeability(
            performance, gradeability, figures_dir
        )
        figures["efficiency"] = plotting.plot_efficiency_map(
            performance_model.powertrain, performance, figures_dir
        )

        performance_validation = performance_model.validation()
        for row in performance_validation:
            print(f"  [{'PASS' if row['pass'] else 'FAIL'}] {row['quantity']:12s} "
                  f"{row['deviation_pct']:+6.2f} % against the published figure")

        # ------------------------------------------------- 2. driving cycle
        _banner(f"2. Driving profile: {cycle.name}")
        reference = _reference_for(cycle)
        cycle_table = report.cycle_validation_table(cycle, reference)
        print(cycle_table.to_string(index=False, float_format=lambda v: f"{v:9.3f}"))
        figures["cycle"] = plotting.plot_cycle(cycle, figures_dir)
        to_csv(cycle, outdir / "cycles" / f"{_cycle_slug(cycle)}.csv")

        # ------------------------------------------------- 3. cycle simulation
        _banner("3. Cycle simulation")
        simulation = CycleSimulator(ps).run(cycle)
        print(f"  distance           {simulation.total_distance_km:8.3f} km")
        print(f"  consumption        {simulation.consumption_kwh_per_100km:8.3f} kWh/100 km")
        print(f"  recovered by regen {simulation.regen_fraction * 100:8.1f} %")
        print(f"  steps not followed {simulation.unmet_count:8d}")
        print(f"  max tracking error {simulation.max_tracking_error_kph:8.3f} km/h")
        figures["simulation"] = plotting.plot_cycle_simulation(simulation, figures_dir)
        figures["energy"] = plotting.plot_energy_balance(simulation, figures_dir)

        # ------------------------------------------------- 4. range
        _banner("4. Range on a full battery")
        range_result = range_on_cycle(ps, cycle)
        print(f"  range (integrated) {range_result.range_integrated_km:8.1f} km")
        print(f"  range (analytic)   {range_result.range_analytic_km:8.1f} km")
        print(f"  published WLTP     {ps['reference.wltp_range']:8.1f} km")
        range_validation_rows = range_validation(ps, range_result)
        for row in range_validation_rows:
            print(f"  [{'PASS' if row['pass'] else 'FAIL'}] {row['quantity']:34s} "
                  f"{row['deviation_pct']:+6.2f} %")
        figures["range"] = plotting.plot_range(
            range_result, ps["reference.wltp_range"], figures_dir
        )

        speeds, ranges, consumption = constant_speed_range(ps)
        figures["constant_speed"] = plotting.plot_constant_speed_range(
            speeds, ranges, consumption, figures_dir
        )
        pd.DataFrame(
            {"speed_kph": speeds, "range_km": ranges, "consumption_wh_per_km": consumption}
        ).to_csv(tables_dir / "constant_speed_range.csv", index=False)

        # ------------------------------------------------- 5. sensitivity
        tornado_rows: list[dict] = []
        scenario_rows: list[dict] = []
        if run_sensitivity:
            _banner("5. Sensitivity and scenarios")
            tornado_rows = tornado(ps, cycle)
            for row in tornado_rows:
                print(f"  {row['parameter']:24s} span {row['span_km']:6.1f} km "
                      f"({row['span_pct']:5.1f} % of the baseline)")
            figures["tornado"] = plotting.plot_tornado(tornado_rows, figures_dir)
            pd.DataFrame(tornado_rows).to_csv(
                tables_dir / "sensitivity_tornado.csv", index=False
            )

            scenario_rows = scenarios(ps, cycle)
            print()
            for row in scenario_rows:
                print(f"  {row['scenario']:32s} {row['range_km']:6.0f} km "
                      f"({row['delta_vs_certification_pct']:+5.0f} %)")
            figures["scenarios"] = plotting.plot_scenarios(scenario_rows, figures_dir)
            pd.DataFrame(scenario_rows).to_csv(
                tables_dir / "scenarios.csv", index=False
            )

        figures["provenance"] = plotting.plot_parameter_provenance(ps, figures_dir)

        # ------------------------------------------------- 6. secondary cycle
        _banner("6. Comparison cycle (NEDC)")
        nedc_cycle = nedc()
        nedc_range = range_on_cycle(ps, nedc_cycle)
        print(f"  NEDC consumption   {nedc_range.consumption_kwh_per_100km:8.3f} kWh/100 km")
        nedc_delta = (
            nedc_range.range_integrated_km / range_result.range_integrated_km - 1
        ) * 100
        print(f"  NEDC range         {nedc_range.range_integrated_km:8.1f} km  "
              f"({nedc_delta:+.1f} % against WLTP)")
        nedc_summary = {
            "consumption": nedc_range.consumption_kwh_per_100km,
            "range": nedc_range.range_integrated_km,
            "delta": nedc_delta,
        }
        plotting.plot_cycle(nedc_cycle, figures_dir, name="13_nedc_cycle")

    # ----------------------------------------------------- 7. tables & report
    _banner("7. Tables and report")
    report.performance_table(performance, ps).to_csv(
        tables_dir / "performance.csv", index=False
    )
    cycle_table.to_csv(tables_dir / "cycle_validation.csv", index=False)
    pd.DataFrame(
        [{"quantity": k, "value": v} for k, v in simulation.summary().items()]
    ).to_csv(tables_dir / "cycle_simulation.csv", index=False)
    pd.DataFrame(
        [{"quantity": k, "value": v} for k, v in range_result.summary().items()]
    ).to_csv(tables_dir / "range.csv", index=False)
    report.validation_table(
        performance_validation + range_validation_rows
    ).to_csv(tables_dir / "validation.csv", index=False)

    register_md, register_csv = report.write_assumption_register(ps, report_dir)
    results_md = report.write_results_document(
        ps=ps,
        cycle=cycle,
        cycle_reference=reference,
        performance=performance,
        performance_validation=performance_validation,
        simulation=simulation,
        range_result=range_result,
        range_validation_rows=range_validation_rows,
        tornado_rows=tornado_rows,
        scenario_rows=scenario_rows,
        figures=figures,
        outdir=report_dir,
    )
    report_md = document.write_report(
        ps=ps,
        cycle=cycle,
        performance=performance,
        performance_validation=performance_validation,
        simulation=simulation,
        range_result=range_result,
        range_validation_rows=range_validation_rows,
        tornado_rows=tornado_rows,
        scenario_rows=scenario_rows,
        figures=figures,
        powertrain=performance_model.powertrain,
        road=performance_model.road,
        outdir=report_dir,
        nedc_summary=nedc_summary,
    )
    presentation_md = document.write_presentation(
        ps=ps,
        cycle=cycle,
        performance=performance,
        performance_validation=performance_validation,
        simulation=simulation,
        range_result=range_result,
        range_validation_rows=range_validation_rows,
        tornado_rows=tornado_rows,
        scenario_rows=scenario_rows,
        figures=figures,
        road=performance_model.road,
        outdir=report_dir,
    )

    for path in (register_md, register_csv, results_md, report_md, presentation_md):
        print(f"  {path}")
    print(f"  {len(figures) + 1} figures in {figures_dir}")

    elapsed = time.perf_counter() - started
    _banner(f"Done in {elapsed:.1f} s")

    return {
        "report": report_md,
        "presentation": presentation_md,
        "performance": performance,
        "simulation": simulation,
        "range": range_result,
        "figures": figures,
        "tornado": tornado_rows,
        "scenarios": scenario_rows,
    }
