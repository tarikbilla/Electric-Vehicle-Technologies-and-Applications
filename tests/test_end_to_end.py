"""End-to-end: the whole study runs and writes every artefact (FR-9, FR-10)."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from evsim.cli import main as cli_main
from evsim.cycles import DrivingCycle
from evsim.parameters import ParameterSet
from evsim.report import write_assumption_register
from evsim.study import run_study


def test_full_study_writes_every_artefact(
    tmp_path: Path, vehicle: ParameterSet, wltc: DrivingCycle
) -> None:
    """One call must regenerate the complete set of results from scratch."""
    outdir = tmp_path / "results"
    outcome = run_study(vehicle, wltc, outdir, run_sensitivity=False)

    figures = sorted((outdir / "figures").glob("*.png"))
    assert len(figures) >= 10
    assert all(path.stat().st_size > 10_000 for path in figures)
    # Every figure must also exist as a vector file for the slides.
    for path in figures:
        assert path.with_suffix(".svg").exists()

    for name in ("performance", "cycle_validation", "range", "validation"):
        assert (outdir / "tables" / f"{name}.csv").is_file()

    assert (outdir / "report" / "results.md").is_file()
    assert (outdir / "report" / "assumption_register.md").is_file()
    assert outcome["range"].range_integrated_km > 0


def test_assumption_register_marks_every_assumption_in_red(
    tmp_path: Path, vehicle: ParameterSet
) -> None:
    """The brief requires assumed constants to be marked in red."""
    md_path, csv_path = write_assumption_register(vehicle, tmp_path)
    text = md_path.read_text(encoding="utf-8")

    assumed = vehicle.assumptions()
    assert text.count('<span style="color:#c0271c">') >= len(assumed)

    for parameter in assumed:
        assert f"`{parameter.path}`" in text, parameter.path
        assert parameter.source[:40] in text, parameter.path

    # No published value may be dressed up as an assumption.
    for parameter in vehicle.published():
        assert f'<span style="color:#c0271c">{parameter.value:g}</span> | {parameter.unit} |' not in text

    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(assumed)
    assert {"parameter", "value", "unit", "rationale"} <= set(rows[0])


def test_results_document_reports_the_headline_numbers(
    tmp_path: Path, vehicle: ParameterSet, wltc: DrivingCycle
) -> None:
    outdir = tmp_path / "results"
    run_study(vehicle, wltc, outdir, run_sensitivity=False)
    text = (outdir / "report" / "results.md").read_text(encoding="utf-8")

    for heading in (
        "Headline results",
        "Speed and acceleration characteristics",
        "Driving profile",
        "Cycle simulation",
        "Range on a full battery",
        "Limitations",
    ):
        assert heading in text, heading
    assert "0-100 km/h" in text
    assert "WLTP range" in text


@pytest.mark.parametrize(
    "argv",
    [
        ["performance"],
        ["cycle", "--cycle", "nedc"],
        ["range"],
        ["assumptions"],
    ],
)
def test_cli_subcommands_succeed(argv: list[str], capsys: pytest.CaptureFixture) -> None:
    root = Path(__file__).resolve().parents[1]
    vehicle_file = str(root / "data" / "vehicles" / "tesla_model_3_rwd_2024.yaml")
    assert cli_main([*argv, "--vehicle", vehicle_file]) == 0
    assert capsys.readouterr().out.strip()
