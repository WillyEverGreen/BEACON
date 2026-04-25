"""Generic benchmark runner for local HTML fixture datasets.

Phase 1 uses this runner for GenA11y, ACT-full fixture snapshots, and
AccessGuru semantic snippets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

from app.services.heuristics import HeuristicAnalyzer
from app.services.static_checks import StaticChecker


@dataclass(frozen=True)
class FixtureCase:
    fixture_file: Path
    sc_id: str
    expected_violation: bool
    rule_id: str = ""
    source: str = ""


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _score(tp: int, fp: int, fn: int) -> dict[str, float | int]:
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2.0 * precision * recall, precision + recall)
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def _collect_findings(
    html: str,
    url: str,
    *,
    run_heuristics: bool,
) -> list[dict[str, Any]]:
    checker = StaticChecker(html, url)
    static_issues = checker.run_all()

    heuristic_issues: list[dict[str, Any]] = []
    if run_heuristics:
        analyzer = HeuristicAnalyzer(html, url)
        heuristic_issues = analyzer.run_all()

    findings: list[dict[str, Any]] = []
    for issue in [*static_issues, *heuristic_issues]:
        sc_id = str(issue.get("wcag_criterion", "") or "").strip()
        if not sc_id:
            continue
        sources = issue.get("confidence_sources", [])
        source_name = ""
        if isinstance(sources, list) and sources:
            source_name = str(sources[0] or "").strip()
        findings.append(
            {
                "sc_id": sc_id,
                "rule_id": str(issue.get("rule_id", "") or "").strip(),
                "engine": source_name or "static",
                "confidence": float(issue.get("confidence", 0.0) or 0.0),
            }
        )

    return findings


def run_benchmark(
    cases: Iterable[FixtureCase],
    *,
    dataset_name: str,
    scan_mode: str = "deep",
    run_heuristics: bool = False,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    sc_counters: dict[str, dict[str, int]] = {}

    for case in cases:
        html = case.fixture_file.read_text(encoding="utf-8", errors="ignore")
        findings = _collect_findings(
            html,
            f"file://{case.fixture_file.as_posix()}",
            run_heuristics=run_heuristics,
        )
        matched = [f for f in findings if f.get("sc_id") == case.sc_id]

        detected = bool(matched)
        best_conf = max((float(f.get("confidence", 0.0) or 0.0) for f in matched), default=0.0)
        primary_engine = str(matched[0].get("engine", "") if matched else "")

        rows.append(
            {
                "sc_id": case.sc_id,
                "fixture_file": str(case.fixture_file.as_posix()),
                "expected": bool(case.expected_violation),
                "beacon_detected": detected,
                "engine": primary_engine,
                "scan_mode": scan_mode,
                "confidence": round(best_conf, 4),
                "rule_id": case.rule_id,
                "source": case.source,
            }
        )

        sc_key = case.sc_id or "unknown"
        counters = sc_counters.setdefault(sc_key, {"tp": 0, "fp": 0, "fn": 0, "total": 0})
        counters["total"] += 1
        if case.expected_violation and detected:
            counters["tp"] += 1
        elif case.expected_violation and not detected:
            counters["fn"] += 1
        elif (not case.expected_violation) and detected:
            counters["fp"] += 1

    per_sc: dict[str, dict[str, float | int]] = {}
    total_tp = total_fp = total_fn = 0
    for sc_id, counters in sorted(sc_counters.items()):
        tp = int(counters["tp"])
        fp = int(counters["fp"])
        fn = int(counters["fn"])
        total_tp += tp
        total_fp += fp
        total_fn += fn
        metrics = _score(tp, fp, fn)
        metrics["fixtures"] = int(counters["total"])
        per_sc[sc_id] = metrics

    aggregate = _score(total_tp, total_fp, total_fn)
    aggregate["fixtures"] = len(rows)

    return {
        "dataset": dataset_name,
        "scan_mode": scan_mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "aggregate": aggregate,
        "per_sc": per_sc,
        "rows": rows,
    }


def save_benchmark_results(results: dict[str, Any], output_file: Path) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return output_file
