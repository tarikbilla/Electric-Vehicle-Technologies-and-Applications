"""Command-line interface.

    evsim run          full study: figures, tables, report
    evsim performance  characteristic curves and benchmark times
    evsim cycle        driving-cycle statistics
    evsim range        range on a full battery
    evsim assumptions  the assumption register
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DEFAULT_VEHICLE = "data/vehicles/tesla_model_3_rwd_2024.yaml"


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--vehicle", default=DEFAULT_VEHICLE, help="vehicle parameter YAML file"
    )
    parser.add_argument(
        "--cycle", default="wltc_class3b",
        help="built-in cycle key (wltc_class3b, nedc) or a path to a CSV",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evsim", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run the full study and write all outputs")
    _add_common(run)
    run.add_argument("--outdir", default="results", help="output directory")
    run.add_argument(
        "--skip-sensitivity", action="store_true",
        help="skip the sensitivity study (much faster)",
    )

    performance = sub.add_parser("performance", help="characteristic curves")
    _add_common(performance)

    cycle = sub.add_parser("cycle", help="driving-cycle statistics")
    _add_common(cycle)
    cycle.add_argument("--export", help="write the cycle to this CSV path")

    range_cmd = sub.add_parser("range", help="range on a full battery")
    _add_common(range_cmd)
    range_cmd.add_argument(
        "--aux", type=float, default=None, help="auxiliary load in W (overrides the file)"
    )

    assumptions = sub.add_parser("assumptions", help="print the assumption register")
    _add_common(assumptions)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    from .cycles import get_cycle, to_csv
    from .parameters import ParameterSet

    ps = ParameterSet.from_yaml(args.vehicle)

    if args.command == "run":
        from .study import run_study

        run_study(
            ps,
            get_cycle(args.cycle),
            Path(args.outdir),
            run_sensitivity=not args.skip_sensitivity,
        )
        return 0

    if args.command == "performance":
        from .performance import PerformanceModel
        from .units import MPS_TO_KPH

        model = PerformanceModel(ps)
        result = model.run()
        print(f"{ps.meta('name')}")
        print(f"  top speed        {result.top_speed * MPS_TO_KPH:7.1f} km/h"
              f"  ({result.top_speed_limit})")
        for label, seconds in result.accel_times.items():
            print(f"  {label:16s} {seconds:7.2f} s")
        print()
        for row in model.validation():
            mark = "PASS" if row["pass"] else "FAIL"
            print(f"  [{mark}] {row['quantity']:12s} simulated {row['simulated']:8.1f} "
                  f"{row['unit']:6s} published {row['published']:8.1f}  "
                  f"deviation {row['deviation_pct']:+6.2f} %")
        return 0

    if args.command == "cycle":
        cycle = get_cycle(args.cycle)
        print(f"{cycle.name}  ({'synthesised' if cycle.synthetic else 'exact'})")
        for key, value in cycle.statistics().items():
            print(f"  {key:26s} {value:10.3f}")
        if args.export:
            print(f"  written to {to_csv(cycle, args.export)}")
        return 0

    if args.command == "range":
        from .rangecalc import range_on_cycle, range_validation

        cycle = get_cycle(args.cycle)
        result = range_on_cycle(ps, cycle, auxiliary_power=args.aux)
        print(f"{ps.meta('name')} on {cycle.name}")
        for key, value in result.summary().items():
            print(f"  {key:28s} {value:10.3f}")
        print()
        for row in range_validation(ps, result):
            mark = "PASS" if row["pass"] else "FAIL"
            print(f"  [{mark}] {row['quantity']:34s} simulated {row['simulated']:8.2f} "
                  f"published {row['published']:8.2f}  "
                  f"deviation {row['deviation_pct']:+6.2f} %")
        return 0

    if args.command == "assumptions":
        assumed = ps.assumptions()
        print(f"{ps.meta('name')}: {len(assumed)} assumed of "
              f"{len(assumed) + len(ps.published())} parameters\n")
        for parameter in assumed:
            print(f"  {parameter.path:48s} {parameter.value:>12g} {parameter.unit}")
            print(f"  {'':48s} {parameter.source}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
