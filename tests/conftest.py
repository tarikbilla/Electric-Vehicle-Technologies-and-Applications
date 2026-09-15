"""Shared fixtures.

The cycle and vehicle are session-scoped because building the WLTC profile and
parsing the parameter file are the slowest parts of the suite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evsim.cycles import DrivingCycle, nedc, wltc_class3b
from evsim.parameters import ParameterSet

ROOT = Path(__file__).resolve().parents[1]
VEHICLE_FILE = ROOT / "data" / "vehicles" / "tesla_model_3_rwd_2024.yaml"


@pytest.fixture(scope="session")
def vehicle() -> ParameterSet:
    return ParameterSet.from_yaml(VEHICLE_FILE)


@pytest.fixture(scope="session")
def wltc() -> DrivingCycle:
    return wltc_class3b()


@pytest.fixture(scope="session")
def nedc_cycle() -> DrivingCycle:
    return nedc()
