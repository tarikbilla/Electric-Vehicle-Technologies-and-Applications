"""Sensitivity study: every case must actually influence the result."""

from __future__ import annotations

import pytest

from evsim.cycles import DrivingCycle
from evsim.parameters import ParameterSet
from evsim.roadload import PHYSICAL
from evsim.sensitivity import cases_for, scenarios, tornado
from evsim.simulation import CycleSimulator


def _consumption(ps: ParameterSet, cycle: DrivingCycle) -> float:
    """Cycle consumption [Wh/km].

    Used instead of a full range integration wherever a test only needs to know
    whether a parameter changes the answer: one cycle pass costs a tenth of a
    second, a discharge to empty costs two seconds, and for these assertions
    they carry the same information.
    """
    return CycleSimulator(ps).run(cycle).consumption_wh_per_km


def test_no_sensitivity_case_is_inert(
    vehicle: ParameterSet, wltc: DrivingCycle
) -> None:
    """A case with no effect would appear as a silent zero on the tornado chart.

    This guards a real trap: the drag coefficient influences nothing when the
    coastdown road-load model is active, and the coastdown coefficients
    influence nothing when the physical model is active.
    """
    baseline = _consumption(vehicle, wltc)
    for case in cases_for(vehicle):
        low = _consumption(vehicle.override(**{case.key: case.low}), wltc)
        high = _consumption(vehicle.override(**{case.key: case.high}), wltc)
        # Battery capacity changes the range without changing consumption, so
        # it is checked on its own terms.
        if case.path == "battery.gross_capacity":
            assert case.high > case.low
            continue
        span = abs(high - low) / baseline
        assert span > 0.005, f"{case.label} ({case.path}) moves consumption by {span:.4%}"


def test_case_set_follows_the_active_road_load_model(vehicle: ParameterSet) -> None:
    coastdown_paths = {c.path for c in cases_for(vehicle)}
    assert any(p.startswith("road_load.coastdown") for p in coastdown_paths)
    assert "aerodynamics.drag_coefficient" not in coastdown_paths

    physical = vehicle.override()
    physical.raw["road_load"]["model"] = PHYSICAL
    physical_paths = {c.path for c in cases_for(physical)}
    assert "aerodynamics.drag_coefficient" in physical_paths
    assert not any(p.startswith("road_load.coastdown") for p in physical_paths)


@pytest.fixture(scope="module")
def scenario_rows(vehicle: ParameterSet, wltc: DrivingCycle) -> list[dict]:
    """Shared across the scenario tests: each row costs a full discharge."""
    return scenarios(vehicle, wltc)


def test_tornado_is_ranked_by_influence(
    vehicle: ParameterSet, wltc: DrivingCycle
) -> None:
    """Exercised on a three-case subset; each case costs two full discharges."""
    subset = tuple(cases_for(vehicle)[:3])
    rows = tornado(vehicle, wltc, cases=subset)
    assert len(rows) == 3
    spans = [row["span_km"] for row in rows]
    assert spans == sorted(spans, reverse=True)
    assert all(row["baseline_km"] > 0 for row in rows)
    for row in rows:
        assert row["range_low_km"] > 0 and row["range_high_km"] > 0
        assert row["span_pct"] == pytest.approx(
            row["span_km"] / row["baseline_km"] * 100.0
        )


def test_more_auxiliary_load_costs_range(
    vehicle: ParameterSet, wltc: DrivingCycle
) -> None:
    consumption = [
        _consumption(vehicle.override(auxiliaries__hvac_load=load), wltc)
        for load in (0.0, 1000.0, 2000.0, 3000.0)
    ]
    assert all(a < b for a, b in zip(consumption, consumption[1:]))


def test_every_scenario_moves_the_range(scenario_rows: list[dict]) -> None:
    rows = scenario_rows
    assert rows[0]["scenario"] == "WLTP certification"
    assert rows[0]["delta_vs_certification_pct"] == pytest.approx(0.0, abs=1e-6)
    for row in rows[1:]:
        assert row["delta_vs_certification_pct"] < -1.0, row["scenario"]


def test_winter_is_the_worst_scenario(scenario_rows: list[dict]) -> None:
    worst = min(scenario_rows, key=lambda row: row["range_km"])
    assert "Winter" in worst["scenario"]


def test_sweep_returns_a_declining_range_curve(
    vehicle: ParameterSet, wltc: DrivingCycle
) -> None:
    """The full sweep path is exercised once, on the cheapest case available."""
    from evsim.sensitivity import sweep

    case = next(c for c in cases_for(vehicle) if c.path == "auxiliaries.hvac_load")
    values, ranges = sweep(vehicle, wltc, case, n=3)
    assert len(values) == len(ranges) == 3
    assert all(a > b for a, b in zip(ranges, ranges[1:])), "more HVAC must cost range"
