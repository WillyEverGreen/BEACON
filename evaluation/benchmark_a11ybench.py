"""Run the A11YBench regression suite."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from evaluation.benchmark_runner import run_benchmark, save_benchmark_results
from evaluation.gena11y_loader import load_gena11y_cases


def _default_output() -> Path:
    stamp = datetime.now().strftime("%Y%m%d")
    return Path("evaluation/results") / f"a11ybench_regression_{stamp}.json"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run A11YBench Regression Suite")
    parser.add_argument(
        "--fixtures",
        default="evaluation/fixtures/a11ybench",
        help="Directory containing A11YBench HTML fixtures",
    )
    parser.add_argument(
        "--out",
        default=str(_default_output()),
        help="Output JSON path",
    )
    args = parser.parse_args()

    # Create directory if missing
    fixtures_path = Path(args.fixtures)
    fixtures_path.mkdir(parents=True, exist_ok=True)

    # For now, we reuse the gena11y loader as it handles standard HTML+JSON pairs
    cases = load_gena11y_cases(args.fixtures)
    
    # If no cases found, we'll create a dummy one just to ensure the runner works
    if not cases:
        print(f"No fixtures found in {args.fixtures}. Please add regression cases.")
        return

    results = run_benchmark(
        cases,
        dataset_name="a11ybench",
        scan_mode="deep",
        run_heuristics=True,
    )
    output_path = save_benchmark_results(results, Path(args.out))

    aggregate = results.get("aggregate", {})
    print("=== A11YBench Regression Suite ===")
    print(f"Fixtures:  {aggregate.get('fixtures', 0)}")
    print(f"Pass Rate: {aggregate.get('f1', 0.0):.2%}")
    print(f"Saved:     {output_path.as_posix()}")
    
    if aggregate.get('f1', 0.0) < 1.0:
        print("\n[!] WARNING: Regression detected! Some cases failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
