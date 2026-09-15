"""Driving cycles against their published statistics."""

from __future__ import annotations

import numpy as np
import pytest

from evsim.cycles import (
    NEDC_REFERENCE,
    WLTC_3B_REFERENCE,
    _WLTC_3B_PHASES,
    DrivingCycle,
    from_csv,
    get_cycle,
    to_csv,
)
from evsim.units import MPS_TO_KPH


# --------------------------------------------------------------------- NEDC
def test_nedc_duration_is_exact(nedc_cycle: DrivingCycle) -> None:
    assert nedc_cycle.duration == pytest.approx(NEDC_REFERENCE["duration_s"])


def test_nedc_distance_matches_the_regulation(nedc_cycle: DrivingCycle) -> None:
    """The reconstruction should land within half a per cent of 11.007 km."""
    assert nedc_cycle.distance_km == pytest.approx(
        NEDC_REFERENCE["distance_km"], rel=0.005
    )


def test_nedc_maximum_speed_is_exact(nedc_cycle: DrivingCycle) -> None:
    assert nedc_cycle.max_speed * MPS_TO_KPH == pytest.approx(120.0, abs=0.01)


def test_nedc_starts_and_ends_at_rest(nedc_cycle: DrivingCycle) -> None:
    assert nedc_cycle.speed[0] == 0.0
    assert nedc_cycle.speed[-1] == 0.0


# --------------------------------------------------------------------- WLTC
def test_wltc_duration_is_exact(wltc: DrivingCycle) -> None:
    assert wltc.duration == pytest.approx(WLTC_3B_REFERENCE["duration_s"])


@pytest.mark.parametrize(
    "key,tolerance",
    [
        ("distance_km", 0.01),
        ("max_speed_kph", 0.01),
        ("mean_speed_kph", 0.01),
        ("stop_time_s", 0.03),
    ],
)
def test_wltc_statistics_match_the_published_values(
    wltc: DrivingCycle, key: str, tolerance: float
) -> None:
    assert wltc.statistics()[key] == pytest.approx(
        WLTC_3B_REFERENCE[key], rel=tolerance
    )


def test_wltc_phase_distances_match(wltc: DrivingCycle) -> None:
    for target in _WLTC_3B_PHASES:
        section = wltc.phase_slice(target.name)
        distance = float(np.trapezoid(wltc.speed[section], wltc.time[section]))
        assert distance == pytest.approx(target.distance, rel=0.01), target.name


def test_wltc_phase_peak_speeds_match(wltc: DrivingCycle) -> None:
    for target in _WLTC_3B_PHASES:
        section = wltc.phase_slice(target.name)
        peak = float(np.max(wltc.speed[section])) * MPS_TO_KPH
        assert peak == pytest.approx(target.max_speed_kph, rel=0.015), target.name


def test_wltc_accelerations_are_realistic(wltc: DrivingCycle) -> None:
    """A passenger car cycle must not demand implausible accelerations."""
    assert 0.8 < wltc.max_acceleration < 2.0
    assert -2.0 < wltc.max_deceleration < -0.8


def test_wltc_is_flagged_as_synthetic(wltc: DrivingCycle) -> None:
    assert wltc.synthetic, "the synthesised profile must declare itself an assumption"


def test_wltc_speed_is_never_negative(wltc: DrivingCycle) -> None:
    assert np.all(wltc.speed >= -1e-12)


# ------------------------------------------------------------------ plumbing
def test_registry_lookup() -> None:
    assert get_cycle("nedc").name == "NEDC"
    assert "WLTC" in get_cycle("wltc_class3b").name


def test_unknown_cycle_raises() -> None:
    with pytest.raises(KeyError):
        get_cycle("not_a_cycle")


def test_csv_round_trip(tmp_path, nedc_cycle: DrivingCycle) -> None:
    path = to_csv(nedc_cycle, tmp_path / "nedc.csv")
    reloaded = from_csv(path)
    assert reloaded.distance_km == pytest.approx(nedc_cycle.distance_km, rel=1e-6)
    assert reloaded.duration == pytest.approx(nedc_cycle.duration)
