"""Site-level issue aggregation for Phase 6 multi-page crawl outputs."""

from __future__ import annotations

import logging
import re
from typing import Any

from app.audit.fingerprint import stable_selector_fingerprint
from app.config import IMPACT_SUMMARIES
from app.services.prioritizer import build_scoring_summary

logger = logging.getLogger(__name__)


_SEVERITY_ORDER = {
    "critical": 4,
    "serious": 3,
    "major": 3,
    "moderate": 2,
    "minor": 1,
}

_GENERATED_CLASS_PATTERN = re.compile(r"\.(?:sc|css|jss|jsx|emotion)?-?[a-z0-9]{5,}\b", re.IGNORECASE)
_DYNAMIC_CLASS_PATTERN = re.compile(r"\.[a-z0-9_-]*\d+[a-z0-9_-]*\b", re.IGNORECASE)
_DYNAMIC_ID_PATTERN = re.compile(r"#[a-z0-9_-]*\d+[a-z0-9_-]*\b", re.IGNORECASE)
_HTML_TAG_PATTERN = re.compile(r"<\s*([a-zA-Z][a-zA-Z0-9:-]*)")


def aggregate_site_issues(page_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate issues across pages, recompute site priority, and derive recommendations."""
    total_issues_before_dedup = sum(len(list(page.get("issues") or [])) for page in page_results)
    total_pages_audited = max(1, len(page_results))

    buckets: dict[str, dict[str, Any]] = {}

    for page in page_results:
        page_url = str(page.get("url") or page.get("fetch_url") or "")
        for issue in list(page.get("issues") or []):
            issue_type = str(issue.get("issue_type") or issue.get("rule_id") or "unknown")
            wcag_criterion = str(issue.get("wcag_criterion") or "")
            element_role = _infer_element_role(issue)
            selector_fp = _selector_fingerprint(issue, element_role)
            dedup_key = f"{issue_type}:{wcag_criterion}:{element_role}:{selector_fp}"

            frequency = _issue_frequency(issue)
            severity = _normalize_severity(str(issue.get("severity") or "minor"))

            existing = buckets.get(dedup_key)
            if existing is None:
                buckets[dedup_key] = {
                    "issue_dedup_key": dedup_key,
                    "issue_type": issue_type,
                    "rule_id": str(issue.get("rule_id") or issue_type),
                    "wcag_criterion": wcag_criterion,
                    "element_role": element_role,
                    "selector_fingerprint": selector_fp,
                    "severity": severity,
                    "total_frequency": frequency,
                    "affected_pages": {page_url},
                    "representative_issue": dict(issue),
                    "fix": _extract_issue_fix(issue),
                }
                continue

            existing["total_frequency"] = int(existing.get("total_frequency", 0) or 0) + frequency
            existing["affected_pages"].add(page_url)

            if _SEVERITY_ORDER.get(severity, 1) > _SEVERITY_ORDER.get(str(existing.get("severity") or "minor"), 1):
                existing["severity"] = severity

            current_fix = str(existing.get("fix") or "").strip()
            candidate_fix = _extract_issue_fix(issue)
            if candidate_fix and (not current_fix or len(candidate_fix) > len(current_fix)):
                existing["fix"] = candidate_fix

            if _issue_confidence(issue) > _issue_confidence(existing.get("representative_issue") or {}):
                existing["representative_issue"] = dict(issue)

    aggregated = list(buckets.values())

    base_priority_by_key = _compute_base_priority_scores(aggregated)

    for item in aggregated:
        affected_pages = sorted({url for url in item.get("affected_pages", set()) if url})
        affected_page_count = len(affected_pages)
        frequency_weight = affected_page_count / float(total_pages_audited)

        severity = _normalize_severity(str(item.get("severity") or "minor"))
        severity_multiplier = _severity_multiplier(severity)

        base_priority_score = float(base_priority_by_key.get(item.get("issue_dedup_key"), 0.0) or 0.0)
        aggregated_priority_score = base_priority_score * (1.0 + frequency_weight) * severity_multiplier

        item["affected_pages"] = affected_pages
        item["affected_page_count"] = affected_page_count
        item["frequency_weight"] = round(frequency_weight, 6)
        item["base_priority_score"] = round(base_priority_score, 6)
        item["aggregated_priority_score"] = round(aggregated_priority_score, 6)

    aggregated.sort(
        key=lambda issue: (
            -float(issue.get("aggregated_priority_score", 0.0) or 0.0),
            -int(issue.get("affected_page_count", 0) or 0),
            -int(issue.get("total_frequency", 0) or 0),
            str(issue.get("issue_type") or ""),
            str(issue.get("wcag_criterion") or ""),
        )
    )

    aggregated_issues = [
        {
            "issue_type": str(item.get("issue_type") or "unknown"),
            "wcag_criterion": str(item.get("wcag_criterion") or ""),
            "severity": _normalize_severity(str(item.get("severity") or "minor")),
            "total_frequency": int(item.get("total_frequency", 0) or 0),
            "affected_page_count": int(item.get("affected_page_count", 0) or 0),
            "affected_pages": list(item.get("affected_pages") or []),
            "aggregated_priority_score": round(float(item.get("aggregated_priority_score", 0.0) or 0.0), 6),
            "fix": str(item.get("fix") or "").strip() or None,
            "issue_dedup_key": str(item.get("issue_dedup_key") or ""),
        }
        for item in aggregated
    ]

    top_priorities = list(aggregated_issues[:10])

    recommendations: list[str] = []
    for priority in top_priorities[:5]:
        issue_type = str(priority.get("issue_type") or "unknown")
        affected_page_count = int(priority.get("affected_page_count", 0) or 0)
        total_frequency = int(priority.get("total_frequency", 0) or 0)
        impact = IMPACT_SUMMARIES.get(issue_type, IMPACT_SUMMARIES.get("_default", "Accessibility barrier affecting users."))
        recommendations.append(
            f"Fix {issue_type} affecting {affected_page_count} pages ({total_frequency} occurrences) — {impact}"
        )

    if len(recommendations) < 3 and recommendations:
        recommendations = recommendations + recommendations[: 3 - len(recommendations)]
        recommendations = recommendations[:3]

    return {
        "aggregated_issues": aggregated_issues,
        "top_priorities": top_priorities,
        "recommendations": recommendations,
        "total_issues_before_dedup": int(total_issues_before_dedup),
        "total_issues_after_dedup": len(aggregated_issues),
    }


def _compute_base_priority_scores(aggregated: list[dict[str, Any]]) -> dict[str, float]:
    if not aggregated:
        return {}

    synthetic_issues: list[dict[str, Any]] = []
    for item in aggregated:
        representative = dict(item.get("representative_issue") or {})
        aggregation_key = str(item.get("issue_dedup_key") or "")
        if not aggregation_key:
            continue

        synthetic_issues.append(
            {
                "_aggregation_key": aggregation_key,
                "rule_id": str(item.get("rule_id") or representative.get("rule_id") or item.get("issue_type") or "unknown"),
                "issue_type": str(item.get("issue_type") or representative.get("issue_type") or "unknown"),
                "wcag_level": str(representative.get("wcag_level") or "AA"),
                "element_type": str(item.get("element_role") or representative.get("element_type") or "content"),
                "frequency": int(item.get("total_frequency", 1) or 1),
                "user_impact": representative.get("user_impact") or representative.get("impact_summary") or IMPACT_SUMMARIES.get(str(item.get("issue_type") or ""), "confusing"),
                "severity": _normalize_severity(str(item.get("severity") or representative.get("severity") or "minor")),
                "confidence": float(representative.get("confidence", 0.8) or 0.8),
                "message": str(representative.get("message") or representative.get("description") or ""),
                "domain": str(representative.get("domain") or "general"),
                "fix": representative.get("fix") or {"description": str(item.get("fix") or "")},
            }
        )

    if not synthetic_issues:
        return {}

    summary = build_scoring_summary(synthetic_issues, degraded_mode=False)
    priority_scores: dict[str, float] = {}

    for row in list(summary.get("prioritized_issues") or []):
        key = str(row.get("_aggregation_key") or "")
        if not key:
            continue
        priority_scores[key] = float(row.get("priority_score", 0.0) or 0.0)

    for issue in synthetic_issues:
        key = str(issue.get("_aggregation_key") or "")
        if key and key not in priority_scores:
            priority_scores[key] = float(issue.get("priority_score", 0.0) or 0.0)

    return priority_scores


def _issue_frequency(issue: dict[str, Any]) -> int:
    for field in ("frequency", "affected_count", "count", "occurrences"):
        value = issue.get(field)
        if isinstance(value, (int, float)):
            return max(1, int(value))
        if isinstance(value, str) and value.isdigit():
            return max(1, int(value))
    return 1


def _issue_confidence(issue: dict[str, Any]) -> float:
    try:
        return float(issue.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _extract_issue_fix(issue: dict[str, Any]) -> str:
    for field in ("suggested_fix", "code_fix"):
        value = str(issue.get(field) or "").strip()
        if value:
            return value

    fix = issue.get("fix")
    if isinstance(fix, dict):
        for key in ("description", "vanilla", "text"):
            value = str(fix.get(key) or "").strip()
            if value:
                return value
    elif isinstance(fix, str) and fix.strip():
        return fix.strip()

    structured_fix = issue.get("structured_fix")
    if isinstance(structured_fix, dict):
        value = str(structured_fix.get("explanation") or "").strip()
        if value:
            return value

    return ""


def _infer_element_role(issue: dict[str, Any]) -> str:
    for key in ("element_role", "role", "element_type"):
        value = str(issue.get(key) or "").strip().lower()
        if value:
            return value

    for key in ("element", "selector", "html_snippet"):
        text = str(issue.get(key) or "")
        match = _HTML_TAG_PATTERN.search(text)
        if match:
            return match.group(1).lower()

    return "content"


def _selector_fingerprint(issue: dict[str, Any], element_role: str) -> str:
    selector = (
        str(issue.get("selector") or "").strip()
        or str(issue.get("element") or "").strip()
        or str(issue.get("target") or "").strip()
        or str(issue.get("html_snippet") or "").strip()
    )

    if not selector:
        return element_role or "content"

    stable = stable_selector_fingerprint(selector)
    stable = _DYNAMIC_ID_PATTERN.sub(element_role or "node", stable)
    stable = _GENERATED_CLASS_PATTERN.sub(".generated", stable)
    stable = _DYNAMIC_CLASS_PATTERN.sub(".generated", stable)
    stable = re.sub(r"\s+", " ", stable).strip()

    return stable or (element_role or "content")


def _normalize_severity(severity: str) -> str:
    lowered = str(severity or "minor").strip().lower()
    if lowered == "major":
        return "serious"
    if lowered not in {"critical", "serious", "moderate", "minor"}:
        return "minor"
    return lowered


def _severity_multiplier(severity: str) -> float:
    normalized = _normalize_severity(severity)
    if normalized == "critical":
        return 1.5
    if normalized == "serious":
        return 1.2
    if normalized == "moderate":
        return 1.0
    return 0.8
