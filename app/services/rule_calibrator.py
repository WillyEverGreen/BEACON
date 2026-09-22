"""
Rule Calibrator: self-improving feedback loop for the Rule Trust Registry.

After every ACT benchmark run, this module auto-updates
rule_trust_registry.json with precision/recall/trust scores derived from
benchmark ground truth.
"""
import json
import logging
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "data" / "rule_trust_registry.json"
_REGISTRY_CACHE: dict[str, dict] | None = None
_REGISTRY_CACHE_MTIME: float = 0.0

# ── Default trust score for unknown rules ───────────────────────────
# Unknown rules get a moderate default so they are reported but
# subject to the multi-signal confidence formula.
_DEFAULT_TRUST_SCORE = 0.50
_MIN_CASES_FOR_VERDICT_FLIP = 5


def _ema(previous: float, current: float, alpha: float) -> float:
    """Exponential moving average for trust stability across benchmark passes."""
    a = min(0.95, max(0.05, float(alpha)))
    return (a * float(current)) + ((1.0 - a) * float(previous))


def _alpha_for_support(case_count: int) -> float:
    """Use lower alpha for sparse evidence and higher alpha for stable evidence."""
    if case_count >= 20:
        return 0.65
    if case_count >= 10:
        return 0.50
    if case_count >= 5:
        return 0.35
    return 0.20


def load_trust_registry() -> dict[str, dict]:
    """Load the rule trust registry from disk with caching."""
    global _REGISTRY_CACHE, _REGISTRY_CACHE_MTIME

    if not _REGISTRY_PATH.exists():
        logger.warning("Trust registry not found at %s — using empty registry", _REGISTRY_PATH)
        return {}

    try:
        mtime = _REGISTRY_PATH.stat().st_mtime
        if _REGISTRY_CACHE is not None and mtime == _REGISTRY_CACHE_MTIME:
            return _REGISTRY_CACHE

        with _REGISTRY_PATH.open("r", encoding="utf-8") as f:
            registry = json.load(f)
        _REGISTRY_CACHE = registry
        _REGISTRY_CACHE_MTIME = mtime
        return registry
    except Exception as exc:
        logger.error("Failed to load trust registry: %s", exc)
        return {}


def save_trust_registry(registry: dict[str, dict]) -> None:
    """Write the trust registry to disk and invalidate cache."""
    global _REGISTRY_CACHE, _REGISTRY_CACHE_MTIME

    try:
        _REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _REGISTRY_PATH.open("w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)
        _REGISTRY_CACHE = dict(registry)
        _REGISTRY_CACHE_MTIME = _REGISTRY_PATH.stat().st_mtime
        logger.info("Trust registry saved (%d rules)", len(registry))
    except Exception as exc:
        logger.error("Failed to save trust registry: %s", exc)


def get_rule_trust_score(rule_id: str) -> float:
    """
    Get the trust score for a specific rule.

    Returns the trust_score from the registry, or _DEFAULT_TRUST_SCORE
    for rules not yet calibrated.
    """
    registry = load_trust_registry()
    entry = registry.get(rule_id)
    if entry is not None:
        return float(entry.get("trust_score", _DEFAULT_TRUST_SCORE))
    return _DEFAULT_TRUST_SCORE


def get_rule_trust_entry(rule_id: str) -> dict:
    """Get the full trust entry for a rule, or a default entry."""
    registry = load_trust_registry()
    entry = registry.get(rule_id)
    if entry is not None:
        return dict(entry)
    return {
        "precision_score": _DEFAULT_TRUST_SCORE,
        "recall_score": _DEFAULT_TRUST_SCORE,
        "trust_score": _DEFAULT_TRUST_SCORE,
        "last_calibrated": "unknown",
        "calibration_source": "default",
        "verdict": "uncalibrated",
        "required_engines": 1,
    }


def _compute_trust_score(precision: float, recall: float) -> float:
    """
    Compute harmonic trust score, weighting precision 2x.

    Rationale: False positives destroy user trust faster than
    false negatives. A user who sees garbage results stops using
    the tool. A user who misses an issue may never know.
    """
    if precision + recall < 1e-9:
        return 0.0
    return round((3 * precision * recall) / (2 * precision + recall + 1e-9), 4)


def _determine_verdict(trust_score: float) -> str:
    """Map trust score to behavioral verdict tier."""
    if trust_score < 0.20:
        return "suppress"
    elif trust_score < 0.40:
        return "noisy"
    elif trust_score < 0.60:
        return "moderate"
    else:
        return "trusted"


def _derive_rule_metrics_from_cases(cases: list[dict]) -> dict[str, dict[str, int]]:
    """Build per-rule TP/FP/FN counters from benchmark case rows."""
    rule_tp: Counter = Counter()
    rule_fp: Counter = Counter()
    rule_fn: Counter = Counter()

    for case in cases:
        if case.get("skipped", False):
            continue
        predicted = set(case.get("predicted_rule_ids", []))
        expected = set(case.get("expected_rule_ids", []))

        for rule_id in predicted:
            if rule_id in expected:
                rule_tp[rule_id] += 1
            else:
                rule_fp[rule_id] += 1

        for rule_id in expected:
            if rule_id not in predicted:
                rule_fn[rule_id] += 1

    all_rules = set(rule_tp) | set(rule_fp) | set(rule_fn)
    return {
        rule_id: {
            "tp": int(rule_tp[rule_id]),
            "fp": int(rule_fp[rule_id]),
            "fn": int(rule_fn[rule_id]),
        }
        for rule_id in all_rules
    }


def recalibrate_from_act_results(act_results: dict) -> dict[str, dict]:
    """
    Ingest ACT benchmark output and update rule trust scores.

    This is the core self-improvement loop. After each ACT benchmark
    run, this function:
    1. Computes per-rule TP/FP/FN (from `per_rule_metrics` or case rows)
    2. Calculates precision, recall, and harmonic trust scores
    3. Updates the registry entries for ACT-observed rules

    Args:
        act_results: Parsed JSON from benchmark_precision_recall.py output.
                     Must contain a "cases" list with per-case predicted/expected rules.

    Returns:
        Updated registry dict.
    """
    raw_per_rule = act_results.get("per_rule_metrics")
    if isinstance(raw_per_rule, dict) and raw_per_rule:
        per_rule_metrics: dict[str, dict[str, int]] = {}
        for rule_id, metrics in raw_per_rule.items():
            if not isinstance(metrics, dict):
                continue
            per_rule_metrics[str(rule_id)] = {
                "tp": int(metrics.get("tp", 0) or 0),
                "fp": int(metrics.get("fp", 0) or 0),
                "fn": int(metrics.get("fn", 0) or 0),
            }
    else:
        cases = act_results.get("cases", [])
        if not cases:
            logger.warning("No per_rule_metrics or cases found in ACT results — skipping recalibration")
            return load_trust_registry()
        per_rule_metrics = _derive_rule_metrics_from_cases(cases)

    if not per_rule_metrics:
        logger.warning("Derived empty per-rule metrics from ACT results — skipping recalibration")
        return load_trust_registry()

    # Load existing registry to merge
    registry = load_trust_registry()
    today = date.today().isoformat()

    updated_count = 0

    for rule_id, metrics in per_rule_metrics.items():
        previous = registry.get(rule_id, {}) if isinstance(registry, dict) else {}
        tp = int(metrics.get("tp", 0) or 0)
        fp = int(metrics.get("fp", 0) or 0)
        fn = int(metrics.get("fn", 0) or 0)
        evidence_cases = tp + fp + fn
        alpha = _alpha_for_support(evidence_cases)

        prev_precision = float(previous.get("precision_score", _DEFAULT_TRUST_SCORE))
        prev_recall = float(previous.get("recall_score", _DEFAULT_TRUST_SCORE))
        prev_trust = float(previous.get("trust_score", _DEFAULT_TRUST_SCORE))
        prev_verdict = str(previous.get("verdict", "uncalibrated")).lower()
        prev_required_engines = int(previous.get("required_engines", 1) or 1)

        candidate_verdict: str

        if tp == 0 and fp == 0 and fn > 0:
            # Under-detected rule: we observed misses but no positive predictions.
            # Precision is unknown in this slice, so avoid collapsing trust to zero.
            # Also avoid trust oscillation: previously noisy/suppressed rules should
            # not bounce back to moderate trust after a single missed run.
            precision_raw = max(0.0, prev_precision)
            recall_raw = 0.0

            if prev_precision < 0.40 or prev_verdict in {"suppress", "noisy"}:
                # Keep low-trust behavior for historically noisy rules.
                trust_raw = max(0.05, prev_trust * 0.85)
                candidate_verdict = _determine_verdict(trust_raw)
            else:
                # Preserve underdetected signal for rules with historically decent precision.
                precision_raw = max(0.45, prev_precision)
                trust_raw = max(0.30, prev_trust * 0.90)
                candidate_verdict = "underdetected"
        else:
            precision_raw = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall_raw = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            trust_raw = _compute_trust_score(precision_raw, recall_raw)
            candidate_verdict = _determine_verdict(trust_raw)

        # EMA smoothing reduces pass-to-pass oscillation on sparse ACT slices.
        precision = _ema(prev_precision, precision_raw, alpha)
        recall = _ema(prev_recall, recall_raw, alpha)
        trust_score = _ema(prev_trust, trust_raw, alpha)

        # Compute post-smoothing candidate behavior.
        if candidate_verdict == "underdetected":
            smoothed_verdict = "underdetected"
            smoothed_required_engines = 1 if trust_score >= 0.40 else 2
        else:
            smoothed_verdict = _determine_verdict(trust_score)
            smoothed_required_engines = 1 if trust_score >= 0.60 else 2

        # Minimum evidence guard: prevent verdict flips on tiny sample sizes.
        if (
            evidence_cases < _MIN_CASES_FOR_VERDICT_FLIP
            and prev_verdict not in {"", "uncalibrated"}
            and smoothed_verdict != prev_verdict
        ):
            verdict = prev_verdict
            required_engines = prev_required_engines
        else:
            verdict = smoothed_verdict
            required_engines = smoothed_required_engines

        registry[rule_id] = {
            "precision_score": round(precision, 4),
            "recall_score": round(recall, 4),
            "trust_score": round(trust_score, 4),
            "last_calibrated": today,
            "calibration_source": "ACT-auto-calibration",
            "verdict": verdict,
            "required_engines": required_engines,
        }
        updated_count += 1

    save_trust_registry(registry)
    logger.info(
        "Recalibration complete: %d rules updated, %d total in registry",
        updated_count, len(registry),
    )

    return registry


def recalibrate_from_benchmark_file(filepath: str) -> dict[str, dict]:
    """Convenience: load a benchmark JSON file and recalibrate."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        act_results = json.load(f)

    return recalibrate_from_act_results(act_results)


def get_trust_summary() -> dict[str, Any]:
    """Return a summary of the trust registry for observability."""
    registry = load_trust_registry()
    if not registry:
        return {"total_rules": 0, "by_verdict": {}}

    by_verdict: dict[str, int] = {}
    for entry in registry.values():
        verdict = entry.get("verdict", "unknown")
        by_verdict[verdict] = by_verdict.get(verdict, 0) + 1

    trust_scores = [e.get("trust_score", 0) for e in registry.values()]
    return {
        "total_rules": len(registry),
        "by_verdict": by_verdict,
        "avg_trust_score": round(sum(trust_scores) / len(trust_scores), 4),
        "min_trust_score": round(min(trust_scores), 4),
        "max_trust_score": round(max(trust_scores), 4),
    }
