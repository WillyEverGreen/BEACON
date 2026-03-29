"""
Confidence scoring and false-positive control.
Multi-signal formula: source reliability + signal strength + cross-engine agreement + evidence quality.
"""
import logging

from app.config import (
    CONFIDENCE_WEIGHTS,
    SOURCE_RELIABILITY_SCORES,
    RULE_TYPE_MAP,
)

logger = logging.getLogger(__name__)


def _calc_source_reliability(sources: list[str]) -> float:
    """Average reliability of all contributing engines."""
    if not sources:
        return 0.5
    scores = [SOURCE_RELIABILITY_SCORES.get(s, 0.5) for s in sources]
    return sum(scores) / len(scores)


def _calc_signal_strength(issue: dict) -> float:
    """
    How clear-cut is the violation? (0.0–1.0)
    Based on issue_type and severity certainty.
    """
    issue_type = issue.get("issue_type", "violation")
    severity = issue.get("severity", "moderate")

    base = {
        "violation": 0.9,
        "needs-review": 0.4,
        "best-practice": 0.6,
    }.get(issue_type, 0.5)

    severity_boost = {
        "critical": 0.1,
        "serious": 0.05,
        "moderate": 0.0,
        "minor": -0.05,
    }.get(severity, 0.0)

    return min(1.0, max(0.0, base + severity_boost))


def _calc_cross_engine_agreement(sources: list[str]) -> float:
    """Score based on how many engines found this issue."""
    unique_sources = set(sources)
    count = len(unique_sources)
    if count >= 3:
        return 1.0
    elif count == 2:
        return 0.7
    else:
        return 0.3


def _calc_evidence_quality(issue: dict) -> float:
    """Score based on evidence attached to the issue."""
    evidence = issue.get("evidence", {})
    html_snippet = issue.get("html_snippet", "")
    reproducibility = issue.get("reproducibility", "")

    score = 0.0

    if html_snippet:
        score += 0.3
    if evidence:
        score += 0.3
    if reproducibility:
        score += 0.2
    if issue.get("code_fix"):
        score += 0.2

    return min(1.0, score)


def calculate_confidence(issue: dict) -> float:
    """
    Calculate calibrated confidence score using multi-signal formula:
    
    confidence = (
        0.30 × source_reliability     +
        0.25 × signal_strength         +
        0.25 × cross_engine_agreement  +
        0.20 × evidence_quality
    )
    """
    sources = issue.get("confidence_sources", [])

    source_reliability = _calc_source_reliability(sources)
    signal_strength = _calc_signal_strength(issue)
    cross_agreement = _calc_cross_engine_agreement(sources)
    evidence_quality = _calc_evidence_quality(issue)

    confidence = (
        CONFIDENCE_WEIGHTS["source_reliability"] * source_reliability +
        CONFIDENCE_WEIGHTS["signal_strength"] * signal_strength +
        CONFIDENCE_WEIGHTS["cross_engine_agreement"] * cross_agreement +
        CONFIDENCE_WEIGHTS["evidence_quality"] * evidence_quality
    )

    # Calibrate by rule type: hard checks are more objective, contextual less so.
    rule_type = RULE_TYPE_MAP.get(issue.get("rule_id", ""), "hard")
    if rule_type == "hard":
        confidence += 0.03
    elif rule_type == "visual":
        confidence -= 0.02
    elif rule_type == "contextual":
        confidence -= 0.07

    return round(min(1.0, max(0.0, confidence)), 3)


def _confidence_tier(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.60:
        return "medium"
    return "low"


def apply_confidence_rules(issues: list[dict]) -> list[dict]:
    """
    Apply confidence scoring and rules engine to all issues.
    
    Rules:
    - Heuristic-only → auto-set issue_type = "needs-review"
    - confidence < 0.4 → auto-downgrade severity by 1 level
    - confidence < 0.2 → auto-set needs_manual_review, exclude from score
    - ≥2 engines agree → auto-set confidence = max(confidence, 0.8)
    - ≥3 engines agree → auto-confirm: confidence = 0.95
    """
    severity_order = ["minor", "moderate", "serious", "critical"]

    for issue in issues:
        sources = issue.get("confidence_sources", [])
        unique_sources = set(sources)

        # Calculate confidence
        confidence = calculate_confidence(issue)

        # Rule: ≥3 engines → auto-confirm
        if len(unique_sources) >= 3:
            confidence = 0.95

        # Rule: ≥2 engines → floor at 0.8
        elif len(unique_sources) >= 2:
            confidence = max(confidence, 0.8)

        # Rule: heuristic-only → needs-review
        if unique_sources == {"heuristic"}:
            issue["issue_type"] = "needs-review"
            issue["needs_manual_review"] = True

        issue["confidence"] = confidence
        issue["confidence_tier"] = _confidence_tier(confidence)
        issue["rule_type"] = RULE_TYPE_MAP.get(issue.get("rule_id", ""), "hard")

        # Rule: confidence < 0.4 → downgrade severity
        if confidence < 0.4:
            current_severity = issue.get("severity", "moderate")
            if current_severity in severity_order:
                idx = severity_order.index(current_severity)
                if idx > 0:
                    issue["severity"] = severity_order[idx - 1]
                    logger.debug(
                        f"Downgraded {issue.get('rule_id')} severity "
                        f"{current_severity} → {issue['severity']} (confidence={confidence})"
                    )

        # Rule: confidence < 0.2 → exclude from scoring, flag for review
        if confidence < 0.2:
            issue["needs_manual_review"] = True
            issue["issue_type"] = "needs-review"

        # General: confidence < 0.6 → needs manual review
        if confidence < 0.6:
            issue["needs_manual_review"] = True

    # Log summary
    avg_confidence = sum(i.get("confidence", 0) for i in issues) / len(issues) if issues else 0
    needs_review = sum(1 for i in issues if i.get("needs_manual_review"))
    logger.info(
        f"Confidence scoring: {len(issues)} issues, "
        f"avg confidence={avg_confidence:.2f}, "
        f"{needs_review} flagged for manual review"
    )

    return issues
