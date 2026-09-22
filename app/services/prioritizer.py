"""
Issue prioritization and deterministic scoring.

This module turns detected issues into an explainable decision surface:
- severity classification
- per-issue priority scoring
- overall accessibility scoring
- grouped summaries for reporting and telemetry
"""
from __future__ import annotations

import logging
import math
from collections import defaultdict
from statistics import mean
from typing import Any

from app.config import DEGRADED_MODE_MULTIPLIER, TRUST_CALIBRATION

logger = logging.getLogger(__name__)

WCAG_LEVEL_WEIGHT: dict[str, float] = {
    "A": 1.0,
    "AA": 0.7,
    "AAA": 0.4,
}

INTERACTION_CRITICALITY_WEIGHT: dict[str, float] = {
    "form": 1.0,
    "input": 1.0,
    "button": 1.0,
    "navigation": 0.9,
    "media": 0.6,
    "content": 0.6,
}

ELEMENT_WEIGHT: dict[str, float] = {
    "input/form": 1.0,
    "button": 0.9,
    "link": 0.8,
    "image": 0.6,
    "text": 0.4,
}

USER_IMPACT_WEIGHT: dict[str, float] = {
    "blocks action": 1.0,
    "blocking": 1.0,
    "confusing": 0.7,
    "minor": 0.4,
}

_SEVERITY_BUCKETS = ("critical", "major", "minor")
_DEFAULT_USER_IMPACT = 0.7
_FREQUENCY_NORMALIZER = math.log1p(10.0)
_MAX_PRIORITY_RULES = 5
_MIN_CONFIDENCE_FOR_SCORING = float(TRUST_CALIBRATION.get("min_confidence_for_scoring", 0.6) or 0.6)
_MIN_CONFIDENCE_FOR_SUMMARY = float(TRUST_CALIBRATION.get("min_confidence_for_summary", 0.6) or 0.6)
_PENALTY_EXPONENT = float(TRUST_CALIBRATION.get("penalty_exponent", 0.7) or 0.7)
_REPEAT_INSTANCE_WEIGHT = float(TRUST_CALIBRATION.get("repeat_instance_weight", 0.2) or 0.2)
_HIDDEN_PENALTY_MULTIPLIER = float(TRUST_CALIBRATION.get("hidden_element_penalty_multiplier", 0.3) or 0.3)
_ABOVE_FOLD_PENALTY_MULTIPLIER = float(TRUST_CALIBRATION.get("above_fold_penalty_multiplier", 1.5) or 1.5)
_CATEGORY_BASE_WEIGHTS = dict(TRUST_CALIBRATION.get("category_base_weights", {}) or {"critical": 5.0, "major": 3.0, "minor": 1.1})
_CATEGORY_PENALTY_CAPS = dict(TRUST_CALIBRATION.get("category_penalty_caps", {}) or {"critical": 24.0, "major": 18.0, "minor": 10.0})
_HIGH_QUALITY_FLOOR = dict(TRUST_CALIBRATION.get("high_quality_floor", {}) or {})


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _lower_text(value: Any) -> str:
    return str(value or "").strip().lower()


def _resolve_frequency(issue: dict[str, Any]) -> float:
    raw_value = issue.get("frequency", issue.get("affected_count", issue.get("count", 1)))
    try:
        frequency = float(raw_value)
    except (TypeError, ValueError):
        frequency = 1.0
    return max(1.0, frequency)


def _normalize_wcag_level(issue: dict[str, Any]) -> str:
    level_text = _lower_text(issue.get("wcag_level") or issue.get("wcag_criterion") or "AA")
    if level_text.startswith("aaa"):
        return "AAA"
    if level_text.startswith("aa"):
        return "AA"
    if level_text.startswith("a"):
        return "A"
    return "AA"


def _infer_component(issue: dict[str, Any]) -> str:
    text = " ".join(
        _lower_text(value)
        for value in (
            issue.get("component"),
            issue.get("domain"),
            issue.get("category"),
            issue.get("element_type"),
            issue.get("rule_id"),
        )
    )

    if any(token in text for token in ("form", "input", "label", "button", "field", "autocomplete")):
        return "forms"
    if any(token in text for token in ("nav", "menu", "breadcrumb", "link", "skip")):
        return "navigation"
    if any(token in text for token in ("video", "audio", "media", "image", "img", "svg", "alt", "caption", "transcript")):
        return "media"
    return "structure"


def _infer_element_weight(issue: dict[str, Any]) -> float:
    text = " ".join(
        _lower_text(value)
        for value in (
            issue.get("element_type"),
            issue.get("component"),
            issue.get("category"),
            issue.get("domain"),
            issue.get("rule_id"),
        )
    )

    if any(token in text for token in ("input", "form", "field", "label", "textarea", "select")):
        return ELEMENT_WEIGHT["input/form"]
    if any(token in text for token in ("button", "cta", "toggle", "switch")):
        return ELEMENT_WEIGHT["button"]
    if any(token in text for token in ("link", "anchor", "nav", "breadcrumb", "menu", "skip")):
        return ELEMENT_WEIGHT["link"]
    if any(token in text for token in ("image", "img", "svg", "picture", "figure")):
        return ELEMENT_WEIGHT["image"]
    return ELEMENT_WEIGHT["text"]


def _infer_interaction_criticality(issue: dict[str, Any]) -> float:
    component = _infer_component(issue)
    element_weight = _infer_element_weight(issue)

    if component == "forms":
        return INTERACTION_CRITICALITY_WEIGHT["form"]
    if component == "navigation":
        return INTERACTION_CRITICALITY_WEIGHT["navigation"]
    if component == "media":
        return INTERACTION_CRITICALITY_WEIGHT["media"]
    return _clamp(0.5 + (element_weight * 0.2))


def _infer_user_impact(issue: dict[str, Any]) -> float:
    explicit = issue.get("user_impact")
    if isinstance(explicit, (int, float)):
        return _clamp(float(explicit))

    text = " ".join(
        _lower_text(value)
        for value in (
            explicit,
            issue.get("human_impact"),
            issue.get("impact_summary"),
            issue.get("description"),
            issue.get("message"),
        )
    )
    if any(token in text for token in ("block", "blocks", "prevent", "cannot", "can't", "unable")):
        return USER_IMPACT_WEIGHT["blocks action"]
    if any(token in text for token in ("confus", "unclear", "ambiguous", "frustrat", "hard")):
        return USER_IMPACT_WEIGHT["confusing"]
    if any(token in text for token in ("minor", "small", "low")):
        return USER_IMPACT_WEIGHT["minor"]

    severity = _lower_text(issue.get("severity"))
    if severity == "critical":
        return USER_IMPACT_WEIGHT["blocks action"]
    if severity in {"serious", "major"}:
        return USER_IMPACT_WEIGHT["confusing"]
    return _DEFAULT_USER_IMPACT


def _severity_score_from_signals(issue: dict[str, Any]) -> float:
    wcag_score = WCAG_LEVEL_WEIGHT.get(_normalize_wcag_level(issue), WCAG_LEVEL_WEIGHT["AA"])
    interaction_score = _infer_interaction_criticality(issue)
    user_impact = _infer_user_impact(issue)
    frequency = _resolve_frequency(issue)
    frequency_score = _clamp(math.log1p(frequency) / _FREQUENCY_NORMALIZER)
    score = (
        (wcag_score * 0.35)
        + (interaction_score * 0.25)
        + (user_impact * 0.25)
        + (frequency_score * 0.15)
    )
    return round(_clamp(score), 3)


def _severity_bucket(severity_score: float) -> str:
    if severity_score >= 0.8:
        return "critical"
    if severity_score >= 0.5:
        return "major"
    return "minor"


def _priority_score_from_issue(issue: dict[str, Any], severity_score: float) -> float:
    frequency = _resolve_frequency(issue)
    frequency_score = _clamp(math.log1p(frequency) / _FREQUENCY_NORMALIZER)
    element_weight = _infer_element_weight(issue)
    user_impact = _infer_user_impact(issue)
    score = (
        (severity_score * 0.4)
        + (frequency_score * 0.2)
        + (element_weight * 0.2)
        + (user_impact * 0.2)
    )
    return round(_clamp(score), 3)


def _representative_fix(issue: dict[str, Any]) -> Any:
    if issue.get("fix"):
        return issue.get("fix")
    if issue.get("suggested_fix"):
        return issue.get("suggested_fix")
    if issue.get("code_fix"):
        return issue.get("code_fix")
    if issue.get("structured_fix"):
        return issue.get("structured_fix")
    return ""


def _stable_issue_sort_key(issue: dict[str, Any]) -> tuple:
    return (
        -float(issue.get("priority_score", 0.0) or 0.0),
        -float(issue.get("severity_score", 0.0) or 0.0),
        -_resolve_frequency(issue),
        -float(issue.get("confidence", 0.0) or 0.0),
        _lower_text(issue.get("issue_type") or issue.get("rule_id")),
        _lower_text(issue.get("rule_id")),
        _lower_text(issue.get("element")),
    )


def _issue_signature(issue: dict[str, Any]) -> str:
    return "|".join(
        [
            _lower_text(issue.get("issue_type") or "unknown"),
            _lower_text(issue.get("rule_id") or "unknown"),
            _infer_component(issue),
            _lower_text(issue.get("wcag_level") or issue.get("wcag_criterion") or ""),
        ]
    )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _confidence_tier_from_value(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.60:
        return "medium"
    return "low"


def _is_hidden_issue(issue: dict[str, Any]) -> bool:
    snippet = _lower_text(issue.get("html_snippet"))
    element = _lower_text(issue.get("element"))
    return any(
        token in snippet or token in element
        for token in (
            "aria-hidden=\"true\"",
            "aria-hidden='true'",
            " role=\"presentation\"",
            " role='presentation'",
            "display:none",
            "visibility:hidden",
            " hidden",
        )
    )


def _is_above_fold_issue(issue: dict[str, Any]) -> bool:
    evidence = issue.get("evidence")
    if isinstance(evidence, dict):
        above_fold = evidence.get("above_fold")
        in_viewport = evidence.get("in_viewport")
        viewport_position = _lower_text(evidence.get("viewport_position"))
        if bool(above_fold) or bool(in_viewport):
            return True
        if viewport_position in {"top", "above-fold", "above_fold"}:
            return True

    marker_blob = " ".join(
        _lower_text(v)
        for v in (
            issue.get("selector"),
            issue.get("element"),
            issue.get("description"),
            issue.get("message"),
        )
    )
    return "above-fold" in marker_blob or "above_fold" in marker_blob


def _effective_occurrence_count(issue: dict[str, Any]) -> float:
    raw_count = max(1.0, _resolve_frequency(issue))
    if raw_count <= 1.0:
        return 1.0
    return 1.0 + ((raw_count - 1.0) * _clamp(_REPEAT_INSTANCE_WEIGHT, 0.05, 1.0))


def _penalty_multiplier_for_issue(issue: dict[str, Any]) -> float:
    multiplier = 1.0
    if _is_hidden_issue(issue):
        multiplier *= _clamp(_HIDDEN_PENALTY_MULTIPLIER, 0.05, 1.0)
    if _is_above_fold_issue(issue):
        multiplier *= max(1.0, _ABOVE_FOLD_PENALTY_MULTIPLIER)
    return multiplier


def _confidence_summary(issues: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"high": 0, "medium": 0, "low": 0}
    for issue in issues:
        confidence = _safe_float(issue.get("confidence", 0.0), 0.0)
        tier = str(issue.get("confidence_tier") or _confidence_tier_from_value(confidence)).lower()
        if tier not in summary:
            tier = _confidence_tier_from_value(confidence)
        summary[tier] += 1
    return summary


def _high_quality_signal(
    *,
    scorable_issues: list[dict[str, Any]],
    severity_counts: dict[str, int],
    confidence_summary: dict[str, int],
) -> float:
    total = len(scorable_issues)
    if total == 0:
        return 1.0

    high_plus_medium = int(confidence_summary.get("high", 0)) + int(confidence_summary.get("medium", 0))
    high_conf_ratio = high_plus_medium / float(max(1, total))
    critical = int(severity_counts.get("critical", 0))
    major = int(severity_counts.get("major", 0))

    max_critical = int(_HIGH_QUALITY_FLOOR.get("max_critical_issues", 0) or 0)
    max_scorable = int(_HIGH_QUALITY_FLOOR.get("max_scorable_issues", 8) or 8)
    min_ratio = float(_HIGH_QUALITY_FLOOR.get("min_high_confidence_ratio", 0.7) or 0.7)

    if critical <= max_critical and total <= max_scorable and high_conf_ratio >= min_ratio and major <= 2:
        return 0.90

    load_component = _clamp(1.0 - (total / float(max(1, max_scorable * 2))), 0.0, 1.0)
    severity_component = _clamp(1.0 - ((critical * 0.45) + (major * 0.12)), 0.0, 1.0)
    signal = (0.45 * load_component) + (0.35 * severity_component) + (0.20 * _clamp(high_conf_ratio, 0.0, 1.0))
    return round(_clamp(signal, 0.0, 1.0), 3)


def _group_items(items: list[dict[str, Any]], key_name: str, label_key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in items:
        groups[str(issue.get(key_name) or "unknown")].append(issue)

    grouped: list[dict[str, Any]] = []
    for group_key, group_items in groups.items():
        frequency = sum(_resolve_frequency(issue) for issue in group_items)
        weighted_severity = sum(float(issue.get("severity_score", 0.0) or 0.0) * _resolve_frequency(issue) for issue in group_items)
        combined_severity = round(weighted_severity / max(1.0, frequency), 3)
        grouped.append({
            label_key: group_key,
            "frequency": round(frequency, 3),
            "issue_count": len(group_items),
            "combined_severity": combined_severity,
            "representative_fix": _representative_fix(max(group_items, key=lambda item: float(item.get("priority_score", 0.0) or 0.0))),
            "priority_score": round(max(float(item.get("priority_score", 0.0) or 0.0) for item in group_items), 3),
            "rule_ids": sorted({str(item.get("rule_id") or "unknown") for item in group_items}),
        })

    grouped.sort(key=lambda item: (-float(item.get("frequency", 0.0) or 0.0), -float(item.get("combined_severity", 0.0) or 0.0), _lower_text(item.get(label_key))))
    return grouped


def build_issue_groupings(issues: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if not issues:
        return {"by_issue_type": [], "by_component": [], "by_pattern": []}

    for issue in issues:
        issue.setdefault("component", _infer_component(issue))

    by_issue_type = _group_items(issues, "issue_type", "issue_type")
    by_component = _group_items(issues, "component", "component")

    pattern_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issues:
        pattern_groups[_issue_signature(issue)].append(issue)

    by_pattern: list[dict[str, Any]] = []
    for pattern_key, group_items in pattern_groups.items():
        frequency = sum(_resolve_frequency(issue) for issue in group_items)
        weighted_severity = sum(float(issue.get("severity_score", 0.0) or 0.0) * _resolve_frequency(issue) for issue in group_items)
        combined_severity = round(weighted_severity / max(1.0, frequency), 3)
        by_pattern.append({
            "pattern": pattern_key,
            "frequency": round(frequency, 3),
            "issue_count": len(group_items),
            "combined_severity": combined_severity,
            "representative_fix": _representative_fix(max(group_items, key=lambda item: float(item.get("priority_score", 0.0) or 0.0))),
            "priority_score": round(max(float(item.get("priority_score", 0.0) or 0.0) for item in group_items), 3),
            "rule_ids": sorted({str(item.get("rule_id") or "unknown") for item in group_items}),
        })

    by_pattern.sort(key=lambda item: (-float(item.get("frequency", 0.0) or 0.0), -float(item.get("combined_severity", 0.0) or 0.0), _lower_text(item.get("pattern"))))
    return {
        "by_issue_type": by_issue_type,
        "by_component": by_component,
        "by_pattern": by_pattern,
    }


def _priority_distribution(issues: list[dict[str, Any]]) -> dict[str, float]:
    scores = [float(issue.get("priority_score", 0.0) or 0.0) for issue in issues]
    if not scores:
        return {"min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0, "avg": 0.0}

    ordered = sorted(scores)

    def _percentile(values: list[float], p: float) -> float:
        if not values:
            return 0.0
        if len(values) == 1:
            return float(values[0])
        rank = (len(values) - 1) * p
        lower = math.floor(rank)
        upper = math.ceil(rank)
        if lower == upper:
            return float(values[int(rank)])
        weight = rank - lower
        return float(values[lower] + (values[upper] - values[lower]) * weight)

    return {
        "min": round(float(ordered[0]), 3),
        "p50": round(_percentile(ordered, 0.5), 3),
        "p95": round(_percentile(ordered, 0.95), 3),
        "max": round(float(ordered[-1]), 3),
        "avg": round(float(mean(scores)), 3),
    }


def _top_issue_types(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    for issue in issues:
        counts[str(issue.get("issue_type") or "unknown")] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [{"issue_type": issue_type, "count": count} for issue_type, count in ranked[:5]]


def _build_recommendations(groupings: dict[str, list[dict[str, Any]]], severity_breakdown: dict[str, int]) -> list[str]:
    recommendations: list[str] = []
    component_labels = {
        "forms": "Fix critical form issues first",
        "navigation": "Resolve navigation issues next",
        "media": "Address media issues after blocking flows",
        "structure": "Stabilize structure and heading issues after blockers",
    }

    for component_group in groupings.get("by_component", [])[:4]:
        component = str(component_group.get("component") or "structure")
        label = component_labels.get(component, f"Review {component} issues next")
        if label not in recommendations:
            recommendations.append(label)

    if severity_breakdown.get("critical", 0) > 0 and not any("critical" in item.lower() for item in recommendations):
        recommendations.insert(0, "Fix critical issues first")
    if not recommendations:
        recommendations.append("Review the highest priority issues first")

    return recommendations[:4]


def _build_priority_ranking(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rule_totals: dict[str, float] = defaultdict(float)
    rule_counts: dict[str, int] = defaultdict(int)
    rule_meta: dict[str, dict[str, Any]] = {}

    for issue in issues:
        rule_id = str(issue.get("rule_id") or "unknown")
        rule_totals[rule_id] += float(issue.get("priority_score", 0.0) or 0.0)
        rule_counts[rule_id] += 1
        if rule_id not in rule_meta:
            rule_meta[rule_id] = {
                "rule_id": rule_id,
                "severity": issue.get("severity", "minor"),
                "domain": issue.get("domain", "general"),
                "message": issue.get("message", rule_id),
            }

    ranked = sorted(rule_totals.items(), key=lambda item: (-item[1], -rule_counts[item[0]], item[0]))[:_MAX_PRIORITY_RULES]

    priority_ranking: list[dict[str, Any]] = []
    for rank, (rule_id, total_score) in enumerate(ranked, start=1):
        meta = rule_meta[rule_id]
        priority_ranking.append({
            "rank": rank,
            "rule_id": rule_id,
            "total_score": round(total_score, 3),
            "affected_count": rule_counts[rule_id],
            "severity": meta["severity"],
            "domain": meta["domain"],
            "message": meta["message"],
            "fix_first_reason": _explain_priority(rank, meta, rule_counts[rule_id]),
        })

    return priority_ranking


def build_scoring_summary(issues: list[dict[str, Any]], *, degraded_mode: bool = False) -> dict[str, Any]:
    if not issues:
        empty_breakdown = {"critical": 0, "major": 0, "minor": 0}
        return {
            "overall_score": 100.0 if not degraded_mode else 85.0,
            "severity_breakdown": empty_breakdown,
            "prioritized_issues": [],
            "recommendations": ["Review the highest priority issues first"],
            "score_distribution": {"overall_score": 100.0 if not degraded_mode else 85.0, "critical_penalty": 0.0, "major_penalty": 0.0, "minor_penalty": 0.0, "issue_count": 0},
            "priority_score_distribution": {"min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0, "avg": 0.0},
            "top_issue_types": [],
            "issue_groupings": {"by_issue_type": [], "by_component": [], "by_pattern": []},
            "priority_ranking": [],
            "score_explanation": {
                "base_score": 100.0,
                "critical_penalty": 0.0,
                "major_penalty": 0.0,
                "minor_penalty": 0.0,
                "total_penalty_applied": 0.0,
                "degraded_mode_penalty": 15.0 if degraded_mode else 0.0,
                "critical_issue_cap_applied": False,
                "multiple_critical_cap_applied": False,
                "quality_floor_applied": False,
                "quality_bonus": 0.0,
                "high_quality_signal": 1.0,
                "scorable_issue_count": 0,
                "summary_issue_count": 0,
                "low_confidence_excluded_count": 0,
                "confidence_summary": {"high": 0, "medium": 0, "low": 0},
                "severity_breakdown": empty_breakdown,
                "priority_score_distribution": {"min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0, "avg": 0.0},
                "penalty_breakdown": {},
            },
        }

    for issue in issues:
        frequency = _resolve_frequency(issue)
        confidence = _clamp(_safe_float(issue.get("confidence", 0.0), 0.0), 0.0, 1.0)
        confidence_tier = str(issue.get("confidence_tier") or _confidence_tier_from_value(confidence)).lower()
        if confidence_tier not in {"high", "medium", "low"}:
            confidence_tier = _confidence_tier_from_value(confidence)

        severity_score = _severity_score_from_signals(issue)
        severity_bucket = _severity_bucket(severity_score)
        priority_score = _priority_score_from_issue(issue, severity_score)

        issue["confidence"] = round(confidence, 3)
        issue["confidence_tier"] = confidence_tier
        issue["severity_score"] = severity_score
        issue["priority_score"] = priority_score
        issue["component"] = _infer_component(issue)
        issue["priority_severity"] = severity_bucket
        issue.setdefault("frequency", frequency)
        issue["occurrence_count"] = max(1, int(round(frequency)))
        issue["report_in_summary"] = bool(confidence >= _MIN_CONFIDENCE_FOR_SUMMARY and confidence_tier in {"high", "medium"})

    scorable_issues = [
        issue
        for issue in issues
        if _safe_float(issue.get("confidence", 0.0), 0.0) >= _MIN_CONFIDENCE_FOR_SCORING
        and str(issue.get("confidence_tier") or "").lower() != "low"
    ]
    summary_issues = [issue for issue in issues if bool(issue.get("report_in_summary", False))]

    severity_counts = {"critical": 0, "major": 0, "minor": 0}
    penalties_uncapped = {"critical": 0.0, "major": 0.0, "minor": 0.0}

    for issue in scorable_issues:
        bucket = str(issue.get("priority_severity") or "minor")
        if bucket not in severity_counts:
            bucket = "minor"

        severity_counts[bucket] += 1
        severity_score = _safe_float(issue.get("severity_score", 0.0), 0.0)
        effective_occurrence = _effective_occurrence_count(issue)
        context_multiplier = _penalty_multiplier_for_issue(issue)
        base_weight = float(_CATEGORY_BASE_WEIGHTS.get(bucket, _CATEGORY_BASE_WEIGHTS.get("minor", 1.1)) or 1.1)

        severity_strength = 0.55 + (_clamp(severity_score, 0.0, 1.0) * 0.45)
        issue_penalty = base_weight * (effective_occurrence ** max(0.4, _PENALTY_EXPONENT)) * context_multiplier * severity_strength
        penalties_uncapped[bucket] += issue_penalty

    critical_penalty = min(float(_CATEGORY_PENALTY_CAPS.get("critical", 24.0) or 24.0), penalties_uncapped["critical"])
    major_penalty = min(float(_CATEGORY_PENALTY_CAPS.get("major", 18.0) or 18.0), penalties_uncapped["major"])
    minor_penalty = min(float(_CATEGORY_PENALTY_CAPS.get("minor", 10.0) or 10.0), penalties_uncapped["minor"])

    total_penalty = critical_penalty + major_penalty + minor_penalty
    pre_adjusted_score = 100.0 - total_penalty
    score = pre_adjusted_score

    # Apply hard caps only when declared critical findings are present with solid confidence.
    # This avoids forcing a 70 plateau from inferred critical buckets alone.
    declared_critical_count = sum(
        1
        for issue in scorable_issues
        if _lower_text(issue.get("severity")) == "critical"
        and _safe_float(issue.get("confidence", 0.0), 0.0) >= 0.75
    )
    multiple_critical_cap_applied = False
    critical_issue_cap_applied = False
    if declared_critical_count >= 2:
        score = min(score, 70.0)
        multiple_critical_cap_applied = True
        critical_issue_cap_applied = True
    elif declared_critical_count >= 1:
        score = min(score, 85.0)
        critical_issue_cap_applied = True

    if degraded_mode:
        pre_degraded_score = score  # capture before multiplier for exact penalty
        score = max(0.0, score * DEGRADED_MODE_MULTIPLIER)
    else:
        pre_degraded_score = score

    confidence_summary = _confidence_summary(scorable_issues)
    quality_signal = _high_quality_signal(
        scorable_issues=scorable_issues,
        severity_counts=severity_counts,
        confidence_summary=confidence_summary,
    )

    quality_floor_applied = False
    quality_bonus = 0.0
    if bool(_HIGH_QUALITY_FLOOR.get("enabled", True)):
        signal_threshold = float(_HIGH_QUALITY_FLOOR.get("signal_threshold", 0.85) or 0.85)
        score_floor = float(_HIGH_QUALITY_FLOOR.get("score_floor", 75.0) or 75.0)
        if quality_signal >= signal_threshold and score < score_floor:
            quality_bonus = score_floor - score
            score = score_floor
            quality_floor_applied = True

    score = round(_clamp(score, 0.0, 100.0), 1)

    prioritized_issues = sorted(summary_issues, key=_stable_issue_sort_key)
    issue_groupings = build_issue_groupings(prioritized_issues)
    recommendations = _build_recommendations(issue_groupings, severity_counts)
    priority_ranking = _build_priority_ranking(prioritized_issues)
    score_distribution = {
        "overall_score": score,
        "critical_penalty": round(critical_penalty, 3),
        "major_penalty": round(major_penalty, 3),
        "minor_penalty": round(minor_penalty, 3),
        "issue_count": len(scorable_issues),
    }
    priority_score_distribution = _priority_distribution(prioritized_issues)
    top_issue_types = _top_issue_types(prioritized_issues)
    severity_breakdown = dict(severity_counts)

    score_explanation = {
        "base_score": 100.0,
        "critical_penalty": round(critical_penalty, 3),
        "major_penalty": round(major_penalty, 3),
        "minor_penalty": round(minor_penalty, 3),
        "total_penalty_applied": round(total_penalty, 3),
        "degraded_mode_penalty": round(pre_degraded_score - score, 3) if degraded_mode else 0.0,
        "critical_issue_cap_applied": critical_issue_cap_applied,
        "multiple_critical_cap_applied": multiple_critical_cap_applied,
        "declared_critical_count": declared_critical_count,
        "inferred_critical_bucket_count": severity_counts["critical"],
        "quality_floor_applied": quality_floor_applied,
        "quality_bonus": round(quality_bonus, 3),
        "high_quality_signal": quality_signal,
        "scorable_issue_count": len(scorable_issues),
        "summary_issue_count": len(prioritized_issues),
        "low_confidence_excluded_count": max(0, len(issues) - len(scorable_issues)),
        "confidence_summary": _confidence_summary(issues),
        "severity_breakdown": severity_breakdown,
        "priority_score_distribution": priority_score_distribution,
        "penalty_breakdown": {
            "critical": round(critical_penalty, 3),
            "major": round(major_penalty, 3),
            "minor": round(minor_penalty, 3),
        },
        "penalty_uncapped": {
            "critical": round(penalties_uncapped["critical"], 3),
            "major": round(penalties_uncapped["major"], 3),
            "minor": round(penalties_uncapped["minor"], 3),
        },
        "top_issue_types": top_issue_types,
        "priority_ranking": priority_ranking,
        "overall_score": score,
        "base_score_before_adjustments": round(pre_adjusted_score, 3),
    }

    logger.info(
        "Prioritization: %s issues -> score=%s, top_fix=%s",
        len(prioritized_issues),
        score,
        priority_ranking[0]["rule_id"] if priority_ranking else "none",
    )

    return {
        "overall_score": score,
        "severity_breakdown": severity_breakdown,
        "prioritized_issues": prioritized_issues,
        "recommendations": recommendations,
        "score_distribution": score_distribution,
        "priority_score_distribution": priority_score_distribution,
        "top_issue_types": top_issue_types,
        "issue_groupings": issue_groupings,
        "priority_ranking": priority_ranking,
        "score_explanation": score_explanation,
    }


def prioritize_issues(issues: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Backwards-compatible wrapper that adds priority scores and returns a top-fix ranking."""
    summary = build_scoring_summary(issues)
    return summary["prioritized_issues"], summary["priority_ranking"]


def _explain_priority(rank: int, meta: dict[str, Any], count: int) -> str:
    severity = meta.get("severity", "moderate")
    rule_id = meta.get("rule_id", "")
    domain = meta.get("domain", "general")

    if rank == 1:
        return f"Highest combined impact: {count} {severity} '{rule_id}' issues in the {domain} domain block the most users."
    return f"#{rank} priority: {count} {severity} violations in '{rule_id}' ({domain}) — fixing these unlocks significant accessibility gains."
