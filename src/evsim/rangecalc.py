"""Range on a full battery (FR-8).

Two independent methods are evaluated and cross-checked:

*Analytic*
    A single cycle is simulated, its net consumption per kilometre is taken and
    the usable battery energy is divided by it.  Fast, and the standard way a
    certification range figure is derived, but it assumes the consumption is
    independent of the state of charge.

*Integrated*
    The cycle is repeated, carrying the state of charge from one repetition to
    the next, until the usable window is exhausted.  This captures the rise in
    ohmic loss as the open-circuit voltage falls towards the end of the
    discharge, so it is the primary result.

The two agreeing to within a per cent is a useful self-check on the energy
book-keeping.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .cycles import DrivingCycle
from .parameters import ParameterSet
from .simulation import CycleSimulator, SimulationResult
from .units import J_PER_KWH, MPS_TO_KPH, mps


@dataclasses.dataclass
class RangeResult:
    """Range prediction for one vehicle on one cycle."""

    cycle_name: str
    range_analytic_km: float
    range_integrated_km: float
    consumption_kwh_per_100km: float
    consumption_wh_per_km: float
    usable_energy_kwh: float
    energy_delivered_kwh: float
    cycles_completed: float
    soc_trace: np.ndarray
    distance_trace: np.ndarray      # km
    first_cycle: SimulationResult

    @property
    def disagreement_pct(self) -> float:
        """Relative difference between the two methods."""
        return (
            (self.range_integrated_km - self.range_analytic_km)
            / self.range_analytic_km
            * 100.0
        )

    def summary(self) -> dict[str, float]:
        return {
            "range_integrated_km": self.range_integrated_km,
            "range_analytic_km": self.range_analytic_km,
            "method_disagreement_pct": self.disagreement_pct,
            "consumption_kwh_per_100km": self.consumption_kwh_per_100km,
            "consumption_wh_per_km": self.consumption_wh_per_km,
            "usable_energy_kwh": self.usable_energy_kwh,
            "energy_delivered_kwh": self.energy_delivered_kwh,
            "cycles_completed": self.cycles_completed,
        }


def range_on_cycle(
    ps: ParameterSet,
    cycle: DrivingCycle,
    auxiliary_power: float | None = None,
    max_repeats: int = 100,
) -> RangeResult:
    """Range on a full battery for the given cycle."""
    simulator = CycleSimulator(ps, auxiliary_power=auxiliary_power)
    battery = simulator.battery

    first = simulator.run(cycle, soc_start=battery.soc_max)
    consumption_per_km = first.energy_net / first.total_distance_km   # J/km
    if consumption_per_km <= 0:
        raise ValueError(
            "cycle consumes no net energy; check the regeneration parameters"
        )
    range_analytic = battery.usable_energy / consumption_per_km

    # ---------------------------------------------------- integrated method
    soc = battery.soc_max
    distance = 0.0
    energy = 0.0
    repeats = 0
    soc_points = [soc]
    distance_points = [0.0]

    while not battery.is_depleted(soc) and repeats < max_repeats:
        result = simulator.run(cycle, soc_start=soc, stop_when_empty=True)
        # Sub-sample the intra-cycle trace so the SOC curve stays smooth.
        step = max(1, result.time.size // 200)
        soc_points.extend(result.soc[1::step].tolist())
        distance_points.extend(
            ((distance + result.distance[1::step]) / 1000.0).tolist()
        )

        distance += result.total_distance
        energy += result.energy_net
        soc = float(result.soc[-1])
        repeats += 1
        if result.total_distance < 1.0:       # no progress, avoid a dead loop
            break

    range_integrated = distance / 1000.0
    cycles_completed = distance / cycle.distance

    return RangeResult(
        cycle_name=cycle.name,
        range_analytic_km=range_analytic,
        range_integrated_km=range_integrated,
        consumption_kwh_per_100km=first.consumption_kwh_per_100km,
        consumption_wh_per_km=first.consumption_wh_per_km,
        usable_energy_kwh=battery.usable_energy_kwh,
        energy_delivered_kwh=energy / J_PER_KWH,
        cycles_completed=cycles_completed,
        soc_trace=np.asarray(soc_points),
        distance_trace=np.asarray(distance_points),
        first_cycle=first,
    )


def constant_speed_range(
    ps: ParameterSet,
    speeds_kph: np.ndarray | None = None,
    auxiliary_power: float | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Range and consumption at steady cruising speed.

    A classic electric-vehicle characteristic: at low speed the constant
    auxiliary load dominates and range is poor, at high speed aerodynamic drag
    dominates, so the range curve has an interior maximum.

    Returns ``(speeds_kph, range_km, consumption_wh_per_km)``.
    """
    if speeds_kph is None:
        speeds_kph = np.arange(20.0, 185.0, 2.5)

    simulator = CycleSimulator(ps, auxiliary_power=auxiliary_power)
    road, powertrain, battery = simulator.road, simulator.powertrain, simulator.battery
    aux = simulator.auxiliary_power

    ranges = np.zeros(speeds_kph.size)
    consumption = np.zeros(speeds_kph.size)

    for index, v_kph in enumerate(speeds_kph):
        v = mps(float(v_kph))
        force = float(road.resistance(v))
        if force > float(powertrain.max_tractive_force(v)):
            ranges[index] = np.nan
            consumption[index] = np.nan
            continue
        p_terminal = float(powertrain.electrical_power_motoring(force, v)[0]) + aux

        # The pack must also cover its own ohmic loss, so the power drawn from
        # the open-circuit source is V_oc * I, not the terminal power.  The
        # usable energy is defined at that same level, so the two are
        # consistent.  Evaluated at mid-SOC, representative of the discharge.
        current, _ = battery.current(p_terminal, 0.5)
        p_internal = float(battery.open_circuit_voltage(0.5)) * current

        consumption[index] = p_terminal / v * 1000.0 / 3600.0       # Wh/km, terminals
        ranges[index] = battery.usable_energy / (p_internal / v * 1000.0)   # km

    return speeds_kph, ranges, consumption


def range_validation(ps: ParameterSet, result: RangeResult) -> list[dict[str, object]]:
    """Compare the predicted range against the manufacturer's WLTP figure."""
    published = ps["reference.wltp_range"]
    simulated = result.range_integrated_km
    rows = [
        {
            "quantity": "WLTP range (full battery)",
            "unit": "km",
            "simulated": simulated,
            "published": published,
            "deviation_pct": (simulated - published) / published * 100.0,
            "tolerance_pct": 10.0,
        }
    ]
    # The published consumption figure is measured at the wall and therefore
    # includes charging losses; the model reports energy at the battery
    # terminals.  Compare on a like-for-like basis.
    published_consumption = ps["reference.wltp_consumption"]
    battery_side = published / 100.0
    implied = ps["battery.gross_capacity"] * ps["battery.usable_fraction"] / battery_side
    rows.append(
        {
            "quantity": "Cycle consumption (battery side)",
            "unit": "kWh/100km",
            "simulated": result.consumption_kwh_per_100km,
            "published": implied,
            "deviation_pct": (result.consumption_kwh_per_100km - implied) / implied * 100.0,
            "tolerance_pct": 10.0,
            "note": (
                f"derived from the published range; the {published_consumption} "
                "kWh/100km type-approval figure is measured at the wall socket "
                "and includes charging losses"
            ),
        }
    )
    for row in rows:
        row["pass"] = abs(row["deviation_pct"]) <= row["tolerance_pct"]
    return rows
