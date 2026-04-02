"""
Confidence scoring and false-positive control.
Multi-signal formula: source reliability + signal strength + cross-engine agreement + evidence quality.
"""
import logging

from app.config import (
    CONFIDENCE_WEIGHTS,
    SOURCE_RELIABILITY_SCORES,
    RULE_TYPE_MAP,
    USER_IMPACT_SCORES,
    IMPACT_SUMMARIES,
    PAGE_LEVEL_RULES,
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


def _calc_user_impact(issue: dict) -> float:
    """
    How blocking is this issue for affected disability groups? (0.0–1.0)
    Missing alt for blind users = 1.0. Minor contrast = 0.5 (default).
    This ensures life-critical violations surface above noise.
    """
    rule_id = issue.get("rule_id", "")
    return USER_IMPACT_SCORES.get(rule_id, USER_IMPACT_SCORES["_default"])


def document_completeness_score(html: str) -> float:
    """
    Score 0.0–1.0 based on how structurally complete the HTML document is.
    Full pages score ~1.0. Test fixtures / fragments score ~0.2.
    This lets us penalize page-level rules on fragments without bluntly excluding them.
    """
    if not html:
        return 0.0
    html_lower = html.lower()
    signals = 0
    if "<html" in html_lower:
        signals += 1
    if "<head" in html_lower:
        signals += 1
    if "<body" in html_lower:
        signals += 1
    if "<title" in html_lower:
        signals += 1
    if "lang=" in html_lower:
        signals += 1
    # Real pages are substantially larger than test fixtures
    if len(html) > 2000:
        signals += 1
    if len(html) > 10000:
        signals += 1
    return min(1.0, signals / 5.0)


def calculate_confidence(issue: dict, html: str = "") -> float:
    """
    Calculate calibrated confidence score using 5-signal formula:

    confidence = (
        0.35 × source_reliability     +
        0.25 × signal_strength         +
        0.15 × cross_engine_agreement  +
        0.20 × evidence_quality        +
        0.05 × user_impact
    )

    Fragment penalty: page-level rules on incomplete documents get a heavy
    confidence reduction so they are filtered by precision profiles automatically.
    """
    sources = issue.get("confidence_sources", [])

    source_reliability = _calc_source_reliability(sources)
    signal_strength    = _calc_signal_strength(issue)
    cross_agreement    = _calc_cross_engine_agreement(sources)
    evidence_quality   = _calc_evidence_quality(issue)
    user_impact        = _calc_user_impact(issue)

    confidence = (
        CONFIDENCE_WEIGHTS["source_reliability"]     * source_reliability +
        CONFIDENCE_WEIGHTS["signal_strength"]        * signal_strength    +
        CONFIDENCE_WEIGHTS["cross_engine_agreement"] * cross_agreement    +
        CONFIDENCE_WEIGHTS["evidence_quality"]       * evidence_quality   +
        CONFIDENCE_WEIGHTS["user_impact"]            * user_impact
    )

    # Calibrate by rule type: hard checks are more objective, contextual less so.
    rule_type = RULE_TYPE_MAP.get(issue.get("rule_id", ""), "hard")
    if rule_type == "hard":
        confidence += 0.03
    elif rule_type == "visual":
        confidence -= 0.02
    elif rule_type == "contextual":
        confidence -= 0.07

    # ── Fragment Penalty ────────────────────────────────────────────────
    # Page-level rules (no-lang, no-title, etc.) on HTML fragments are almost
    # always false positives. Apply a graduated penalty based on how incomplete
    # the document is. This replaces the old blunt exclude_rules approach.
    rule_id = issue.get("rule_id", "")
    if html and rule_id in PAGE_LEVEL_RULES:
        completeness = document_completeness_score(html)
        if completeness < 0.6:
            # Scale penalty: completeness 0.0 → -0.45; completeness 0.59 → -0.07
            penalty = 0.45 * (1.0 - completeness / 0.6)
            confidence -= penalty
            logger.debug(
                f"Fragment penalty: {rule_id} completeness={completeness:.2f} "
                f"penalty=-{penalty:.2f} → confidence={confidence:.3f}"
            )

    return round(min(1.0, max(0.0, confidence)), 3)


def _confidence_tier(confidence: float) -> str:
    if confidence >= 0.85:
        return "high"
    if confidence >= 0.60:
        return "medium"
    return "low"


def apply_confidence_rules(issues: list[dict], html: str = "") -> list[dict]:
    """
    Apply confidence scoring and rules engine to all issues.
    
    Args:
        issues: List of normalized accessibility issues.
        html: Raw HTML of the audited page (used by the fragment detector).
    
    Rules:
    - Heuristic-only → auto-set issue_type = "needs-review"
    - confidence < 0.4 → auto-downgrade severity by 1 level
    - confidence < 0.2 → auto-set needs_manual_review, exclude from score
    - ≥2 engines agree → auto-set confidence = max(confidence, 0.8)
    - ≥3 engines agree → auto-confirm: confidence = 0.95
    - Fragment penalty: page-level rules on incomplete HTML get reduced confidence
    """
    severity_order = ["minor", "moderate", "serious", "critical"]

    for issue in issues:
        sources = issue.get("confidence_sources", [])
        unique_sources = set(sources)

        # Calculate confidence (with fragment detection)
        confidence = calculate_confidence(issue, html=html)

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

        # Generate Confidence Explanation (Reasoning)
        unique_sources_list = list(unique_sources)
        reason_parts = []
        if len(unique_sources_list) >= 3:
            reason_parts.append(f"Confirmed by 3+ engines ({', '.join(unique_sources_list)})")
        elif len(unique_sources_list) == 2:
            reason_parts.append(f"Cross-verified by 2 engines ({', '.join(unique_sources_list)})")
        else:
            engine = unique_sources_list[0] if unique_sources_list else "unknown"
            if engine == "heuristic":
                reason_parts.append("Heuristic match only (needs manual review)")
            elif engine == "axe-core":
                reason_parts.append("Axe-core deterministic check")
            else:
                reason_parts.append(f"Single engine detection ({engine})")
        
        repro_score = _calc_evidence_quality(issue)
        if repro_score >= 0.6:
            reason_parts.append("with strong code evidence.")
        elif repro_score >= 0.3:
            reason_parts.append("with partial evidence.")
        else:
            reason_parts.append("with minimal evidence.")
            
        issue["confidence_reason"] = " ".join(reason_parts)
        
        # Attach Human Impact Summary
        rule_id = issue.get("rule_id", "")
        issue["impact_summary"] = IMPACT_SUMMARIES.get(rule_id, IMPACT_SUMMARIES["_default"])

    # Log summary
    avg_confidence = sum(i.get("confidence", 0) for i in issues) / len(issues) if issues else 0
    needs_review = sum(1 for i in issues if i.get("needs_manual_review"))
    logger.info(
        f"Confidence scoring: {len(issues)} issues, "
        f"avg confidence={avg_confidence:.2f}, "
        f"{needs_review} flagged for manual review"
    )

    return _boost_cross_engine_agreement(issues)


def _boost_cross_engine_agreement(issues: list[dict]) -> list[dict]:
    """
    Boost confidence when multiple engines independently find the same rule_id.
    E.g. both static and axe-core report 'missing-label' → both get confidence ≥ 0.92.
    This makes cross-corroborated issues surface above single-source noise.
    """
    from collections import defaultdict

    # Build rule_id → set of engines that reported it
    rule_sources: dict[str, set] = defaultdict(set)
    for issue in issues:
        rule_id = issue.get("rule_id", "")
        for src in issue.get("confidence_sources", []):
            rule_sources[rule_id].add(src)

    # Apply boost for rules confirmed by 2+ independent engines
    for issue in issues:
        rule_id = issue.get("rule_id", "")
        confirming = rule_sources.get(rule_id, set())
        if len(confirming) >= 2:
            current = issue.get("confidence", 0.0)
            # Strong boost: 2 engines → floor at 0.92
            issue["confidence"] = max(current, 0.92)
            issue["confidence_tier"] = "high"
            logger.debug(
                f"Cross-engine boost: {rule_id} confirmed by {confirming} → confidence={issue['confidence']}"
            )

    return issues
