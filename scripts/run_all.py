#!/usr/bin/env python3
"""Regenerate every figure, table and document of the study.

    python scripts/run_all.py                    # WLTP, full sensitivity study
    python scripts/run_all.py --cycle nedc       # NEDC instead
    python scripts/run_all.py --skip-sensitivity # quick run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from evsim.cycles import get_cycle            # noqa: E402
from evsim.parameters import ParameterSet     # noqa: E402
from evsim.study import run_study             # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vehicle", default=str(ROOT / "data/vehicles/tesla_model_3_rwd_2024.yaml")
    )
    parser.add_argument("--cycle", default="wltc_class3b")
    parser.add_argument("--outdir", default=str(ROOT / "results"))
    parser.add_argument("--skip-sensitivity", action="store_true")
    args = parser.parse_args()

    ps = ParameterSet.from_yaml(args.vehicle)
    print(f"Vehicle: {ps.meta('name')} ({ps.meta('model_year')})")
    print(f"Parameters: {len(ps.published())} published, {len(ps.assumptions())} assumed")

    run_study(
        ps,
        get_cycle(args.cycle),
        Path(args.outdir),
        run_sensitivity=not args.skip_sensitivity,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
