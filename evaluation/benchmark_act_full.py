"""Run expanded ACT benchmark fixtures using benchmark_runner."""

from __future__ import annotations

import argparse
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from datetime import datetime
from pathlib import Path

from evaluation.act_loader import load_act_cases
from evaluation.benchmark_runner import run_benchmark, save_benchmark_results


def _default_output() -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return Path("evaluation/results") / f"act_full_{stamp}.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ACT full fixture benchmark")
    parser.add_argument(
        "--fixtures",
        default="evaluation/fixtures/act",
        help="ACT fixture directory or repo snapshot root",
    )
    parser.add_argument(
        "--out",
        default=str(_default_output()),
        help="Output JSON path",
    )
    parser.add_argument(
        "--scan-mode",
        default="deep",
        choices=["fast", "deep", "max"],
        help="Scan mode label stored in results",
    )
    args = parser.parse_args()

    cases = load_act_cases(args.fixtures)
    if not cases:
        raise SystemExit(f"No ACT fixtures found in {args.fixtures}")

    results = run_benchmark(
        cases,
        dataset_name="act_full",
        scan_mode=args.scan_mode,
        run_heuristics=True,
    )
    output_path = save_benchmark_results(results, Path(args.out))

    aggregate = results.get("aggregate", {})
    print("=== ACT Full Benchmark ===")
    print(f"Fixtures: {aggregate.get('fixtures', 0)}")
    print(f"Precision: {aggregate.get('precision', 0.0):.2%}")
    print(f"Recall:    {aggregate.get('recall', 0.0):.2%}")
    print(f"F1:        {aggregate.get('f1', 0.0):.2%}")
    print(f"Saved: {output_path.as_posix()}")


if __name__ == "__main__":
    main()
