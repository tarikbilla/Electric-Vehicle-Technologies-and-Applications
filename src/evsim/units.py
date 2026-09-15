"""Unit conversion helpers.

The simulator works exclusively in SI units internally.  Conversions happen
only at the input/output boundary (parameter files, plots, reports).
"""

from __future__ import annotations

# --------------------------------------------------------------------- speed
KPH_TO_MPS = 1.0 / 3.6
MPS_TO_KPH = 3.6


def kph(v_mps: float) -> float:
    """m/s -> km/h."""
    return v_mps * MPS_TO_KPH


def mps(v_kph: float) -> float:
    """km/h -> m/s."""
    return v_kph * KPH_TO_MPS


# -------------------------------------------------------------------- energy
J_PER_KWH = 3.6e6
J_PER_WH = 3.6e3


def kwh(energy_j: float) -> float:
    """joule -> kWh."""
    return energy_j / J_PER_KWH


def joule_from_kwh(energy_kwh: float) -> float:
    """kWh -> joule."""
    return energy_kwh * J_PER_KWH


def wh(energy_j: float) -> float:
    """joule -> Wh."""
    return energy_j / J_PER_WH


# ------------------------------------------------------------ rotation / misc
RPM_TO_RADS = 2.0 * 3.141592653589793 / 60.0
RADS_TO_RPM = 1.0 / RPM_TO_RADS


def rad_s(speed_rpm: float) -> float:
    """rpm -> rad/s."""
    return speed_rpm * RPM_TO_RADS


def rpm(speed_rad_s: float) -> float:
    """rad/s -> rpm."""
    return speed_rad_s * RADS_TO_RPM


def percent_grade_to_rad(grade_percent: float) -> float:
    """Road grade in % -> slope angle in rad."""
    import math

    return math.atan(grade_percent / 100.0)
