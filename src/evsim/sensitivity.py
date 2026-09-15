"""Sensitivity study over the assumed parameters.

Most of the parameters that drive the range prediction are *assumptions* rather
than published data (see the assumption register).  This module quantifies how
much each one matters, which is the honest way to present a result that rests
on estimated inputs: a parameter the answer is insensitive to needs no defence,
one it is sensitive to does.

Two views are produced:

``sweep``
    Range versus a parameter over a plausible interval.

``tornado``
    The change in range when each parameter is moved to the low and high end of
    its plausible interval, ranked by influence.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .cycles import DrivingCycle
from .parameters import ParameterSet
from .rangecalc import range_on_cycle


@dataclasses.dataclass(frozen=True)
class SensitivityCase:
    """One parameter to be varied, with the interval considered plausible."""

    path: str            # dotted parameter path
    label: str           # name for plots and tables
    low: float           # low end of the plausible interval
    high: float          # high end
    unit: str = ""

    @property
    def key(self) -> str:
        return self.path.replace(".", "__")


# Parameters common to both road-load formulations.
_COMMON_CASES = (
    SensitivityCase("mass.test_payload", "Payload", 0.0, 400.0, "kg"),
    SensitivityCase("auxiliaries.hvac_load", "HVAC load", 0.0, 3000.0, "W"),
    SensitivityCase(
        "regeneration.max_regen_power", "Regen power limit", 0.0, 90000.0, "W"
    ),
    SensitivityCase("battery.gross_capacity", "Battery capacity", 57.5, 66.0, "kWh"),
    SensitivityCase("transmission.efficiency", "Gearbox efficiency", 0.960, 0.992, "-"),
    SensitivityCase(
        "motor.loss_k_windage", "Motor windage loss", 1.0e-6, 3.0e-6, "W/(rad/s)^3"
    ),
)

# Road-load parameters. Only the set belonging to the ACTIVE formulation has any
# effect, so the case list is built from the model in use rather than fixed. A
# tornado chart showing zero span for an inert parameter would be misleading.
_COASTDOWN_CASES = (
    SensitivityCase(
        "road_load.coastdown_f0", "Coastdown F0 (rolling)", 95.0, 140.0, "N"
    ),
    SensitivityCase(
        "road_load.coastdown_f1", "Coastdown F1 (driveline)", 1.30, 2.45, "N/(m/s)"
    ),
    SensitivityCase(
        "road_load.coastdown_f2", "Coastdown F2 (aero)", 0.340, 0.440, "N/(m/s)^2"
    ),
)
_PHYSICAL_CASES = (
    SensitivityCase(
        "aerodynamics.drag_coefficient", "Drag coefficient", 0.200, 0.245, "-"
    ),
    SensitivityCase("aerodynamics.frontal_area", "Frontal area", 2.10, 2.35, "m^2"),
    SensitivityCase(
        "tyres.rolling_resistance_coefficient", "Rolling resistance", 0.0065, 0.0110, "-"
    ),
    SensitivityCase(
        "aerodynamics.air_density", "Air density", 1.150, 1.290, "kg/m^3"
    ),
)


def cases_for(ps: ParameterSet) -> tuple[SensitivityCase, ...]:
    """Sensitivity cases that actually influence the result for this vehicle.

    Varying the wind-tunnel drag coefficient does nothing when the coastdown
    road-load model is active, and varying the coastdown coefficients does
    nothing when the physical model is active.  Picking the wrong set would
    produce a tornado chart full of silent zeros.
    """
    from .roadload import COASTDOWN

    model = str(ps.raw.get("road_load", {}).get("model", COASTDOWN))
    road_cases = _COASTDOWN_CASES if model == COASTDOWN else _PHYSICAL_CASES
    return _COMMON_CASES + road_cases


def sweep(
    ps: ParameterSet,
    cycle: DrivingCycle,
    case: SensitivityCase,
    n: int = 9,
) -> tuple[np.ndarray, np.ndarray]:
    """Range versus one parameter across its plausible interval."""
    values = np.linspace(case.low, case.high, n)
    ranges = np.zeros(n)
    for index, value in enumerate(values):
        variant = ps.override(**{case.key: float(value)})
        ranges[index] = range_on_cycle(variant, cycle).range_integrated_km
    return values, ranges


def tornado(
    ps: ParameterSet,
    cycle: DrivingCycle,
    cases: tuple[SensitivityCase, ...] | None = None,
) -> list[dict[str, object]]:
    """Effect on range of moving each parameter to its interval ends.

    Returned rows are sorted by influence, largest first, which is what a
    tornado chart plots.
    """
    if cases is None:
        cases = cases_for(ps)
    baseline = range_on_cycle(ps, cycle).range_integrated_km

    rows: list[dict[str, object]] = []
    for case in cases:
        nominal = ps[case.path]
        low_range = range_on_cycle(
            ps.override(**{case.key: case.low}), cycle
        ).range_integrated_km
        high_range = range_on_cycle(
            ps.override(**{case.key: case.high}), cycle
        ).range_integrated_km
        rows.append(
            {
                "parameter": case.label,
                "path": case.path,
                "unit": case.unit,
                "nominal": nominal,
                "low": case.low,
                "high": case.high,
                "range_low_km": low_range,
                "range_high_km": high_range,
                "delta_low_km": low_range - baseline,
                "delta_high_km": high_range - baseline,
                "span_km": abs(high_range - low_range),
                "span_pct": abs(high_range - low_range) / baseline * 100.0,
            }
        )

    rows.sort(key=lambda row: row["span_km"], reverse=True)
    for row in rows:
        row["baseline_km"] = baseline
    return rows



def _is_coastdown(ps: ParameterSet) -> bool:
    from .roadload import COASTDOWN

    return str(ps.raw.get("road_load", {}).get("model", COASTDOWN)) == COASTDOWN


def _aero_key(ps: ParameterSet) -> str:
    """Override key for the aerodynamic term of the active road-load model."""
    return "road_load__coastdown_f2" if _is_coastdown(ps) else "aerodynamics__air_density"


def _aero_value(ps: ParameterSet, factor: float) -> float:
    path = "road_load.coastdown_f2" if _is_coastdown(ps) else "aerodynamics.air_density"
    return ps[path] * factor


def _roll_key(ps: ParameterSet) -> str:
    """Override key for the rolling term of the active road-load model."""
    return (
        "road_load__coastdown_f0"
        if _is_coastdown(ps)
        else "tyres__rolling_resistance_coefficient"
    )


def _roll_value(ps: ParameterSet, factor: float) -> float:
    path = (
        "road_load.coastdown_f0"
        if _is_coastdown(ps)
        else "tyres.rolling_resistance_coefficient"
    )
    return ps[path] * factor


def scenarios(ps: ParameterSet, cycle: DrivingCycle) -> list[dict[str, object]]:
    """Range under a few named real-world conditions.

    The certification figure is measured with the auxiliaries off, a defined
    test mass and standard air.  Real driving is not like that, and the gap
    between the two is what an owner actually experiences.
    """
    definitions = [
        (
            "WLTP certification",
            {"auxiliaries__hvac_load": 0.0, "mass__test_payload": 100.0},
            "Auxiliaries off, driver only, standard air",
        ),
        (
            "Mild weather, 2 occupants",
            {"auxiliaries__hvac_load": 500.0, "mass__test_payload": 250.0},
            "Ventilation only, 20 degC",
        ),
        (
            "Summer, air conditioning",
            {
                "auxiliaries__hvac_load": 1800.0,
                "mass__test_payload": 250.0,
                _aero_key(ps): _aero_value(ps, 0.963),
            },
            "A/C at 30 degC ambient, thinner air",
        ),
        (
            "Winter, cabin + battery heating",
            {
                "auxiliaries__hvac_load": 3200.0,
                "mass__test_payload": 250.0,
                _aero_key(ps): _aero_value(ps, 1.071),
                _roll_key(ps): _roll_value(ps, 1.30),
            },
            "Heating at 0 degC, cold and stiff tyres, dense air",
        ),
        (
            "Fully loaded, roof box",
            {
                "auxiliaries__hvac_load": 500.0,
                "mass__test_payload": 450.0,
                _aero_key(ps): _aero_value(ps, 1.30),
            },
            "Five occupants plus luggage on the roof",
        ),
    ]

    # The baseline must be the certification scenario itself, not the nominal
    # parameter set. They coincide only while the file happens to carry zero
    # HVAC load and the certification payload; anchoring to the row keeps the
    # "against certification" column honest if either default changes.
    certification = definitions[0]
    baseline = range_on_cycle(
        ps.override(**certification[1]), cycle
    ).range_integrated_km

    rows = []
    for name, overrides, note in definitions:
        variant = ps.override(**overrides)
        result = range_on_cycle(variant, cycle)
        rows.append(
            {
                "scenario": name,
                "note": note,
                "range_km": result.range_integrated_km,
                "consumption_kwh_per_100km": result.consumption_kwh_per_100km,
                "delta_vs_certification_pct": (result.range_integrated_km - baseline)
                / baseline
                * 100.0,
            }
        )
    return rows
