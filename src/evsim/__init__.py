"""Modelling and simulation of a battery-electric vehicle.

Semester project for *Electric Vehicle Technologies & Applications* (THM):
derive the speed and acceleration characteristics of a commercially available
electric vehicle, run it over a driving profile and predict the range on a full
battery.  Reference vehicle: Tesla Model 3 RWD (2024).

Typical use::

    from evsim import ParameterSet, CycleSimulator, wltc_class3b, range_on_cycle

    ps = ParameterSet.from_yaml("data/vehicles/tesla_model_3_rwd_2024.yaml")
    cycle = wltc_class3b()
    result = range_on_cycle(ps, cycle)
    print(result.range_integrated_km)
"""

from __future__ import annotations

__version__ = "1.0.0"

from .battery import Battery
from .cycles import (
    NEDC_REFERENCE,
    WLTC_3B_REFERENCE,
    DrivingCycle,
    from_csv,
    get_cycle,
    nedc,
    to_csv,
    wltc_class3b,
)
from .parameters import Parameter, ParameterSet
from .performance import PerformanceModel, PerformanceResult
from .powertrain import Powertrain
from .rangecalc import (
    RangeResult,
    constant_speed_range,
    range_on_cycle,
    range_validation,
)
from .roadload import RoadLoad
from .sensitivity import scenarios, tornado
from .simulation import CycleSimulator, SimulationResult

__all__ = [
    "__version__",
    "Battery",
    "CycleSimulator",
    "DrivingCycle",
    "NEDC_REFERENCE",
    "Parameter",
    "ParameterSet",
    "PerformanceModel",
    "PerformanceResult",
    "Powertrain",
    "RangeResult",
    "RoadLoad",
    "SimulationResult",
    "WLTC_3B_REFERENCE",
    "constant_speed_range",
    "from_csv",
    "get_cycle",
    "nedc",
    "range_on_cycle",
    "range_validation",
    "scenarios",
    "to_csv",
    "tornado",
    "wltc_class3b",
]
