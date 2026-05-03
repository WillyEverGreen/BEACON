from pathlib import Path

from evaluation.benchmark_runner import run_benchmark, save_benchmark_results
from evaluation.gena11y_loader import load_gena11y_cases


def _write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _missing_alt_html() -> str:
    return """<!DOCTYPE html>
<html lang=\"en\"><head><title>Fail</title></head><body><img src=\"a.jpg\"></body></html>
"""


def _valid_alt_html() -> str:
    return """<!DOCTYPE html>
<html lang=\"en\"><head><title>Pass</title></head><body><img src=\"a.jpg\" alt=\"Example\"></body></html>
"""


def test_gena11y_recall_threshold(tmp_path: Path) -> None:
    fixtures = tmp_path / "gena11y"

    for idx in range(6):
        _write(fixtures / f"img-sc-1.1.1-fail-{idx}.html", _missing_alt_html())
    for idx in range(4):
        _write(fixtures / f"img-sc-1.1.1-pass-{idx}.html", _valid_alt_html())

    cases = load_gena11y_cases(fixtures)
    assert len(cases) == 10

    results = run_benchmark(cases, dataset_name="gena11y-test", scan_mode="deep")
    metrics = results["per_sc"]["1.1.1"]

    assert metrics["fixtures"] >= 5
    assert metrics["recall"] >= 0.50


def test_gena11y_results_written(tmp_path: Path) -> None:
    fixtures = tmp_path / "gena11y"
    _write(fixtures / "img-sc-1.1.1-fail-0.html", _missing_alt_html())

    cases = load_gena11y_cases(fixtures)
    results = run_benchmark(cases, dataset_name="gena11y-test", scan_mode="deep")

    output = tmp_path / "results" / "gena11y_baseline_20990101.json"
    saved = save_benchmark_results(results, output)

    assert saved.exists()
    assert saved.read_text(encoding="utf-8").strip().startswith("{")
