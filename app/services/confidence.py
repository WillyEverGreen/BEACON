"""
Confidence scoring and false-positive control.
Multi-signal formula: source reliability + signal strength + cross-engine agreement
+ evidence quality + rule trust (from adaptive trust registry).
"""
import logging
import re

from app.config import (
    CONFIDENCE_WEIGHTS,
    SOURCE_RELIABILITY_SCORES,
    RULE_TYPE_MAP,
    USER_IMPACT_SCORES,
    IMPACT_SUMMARIES,
    PAGE_LEVEL_RULES,
    STRUCTURAL_FP_RULES,
)
from app.services.rule_calibrator import get_rule_trust_score, get_rule_trust_entry


logger = logging.getLogger(__name__)


# Deterministic/structural rules we can trust more when additional signals agree.
HIGH_CONFIDENCE_RULES = {
    "missing-alt",
    "image-alt",
    "empty-link",
    "link-name",
    "button-name",
    "button-no-name",
    "form-label",
    "table-no-headers",
    "table-no-caption",
    "th-no-scope",
    "missing-lang",
    "invalid-lang",
    "valid-lang",
    "missing-autocomplete",
    "autocomplete-missing",
    "meta-viewport-zoom",
    "focus-management",
    "no-headings",
}


HIGH_FN_RULES = {
    "missing-label",
    "input-label",
    "form-label-missing",
    "label",
    "input-name",
    "letter-spacing",
    "line-height",
    "text-spacing",
    "avoid-inline-spacing",
    "aria-role",
    "media-alternative",
    "svg-no-accessible-name",
    "no-lang",
    "empty-link",
    "link-name",
    "link-purpose",
}


def _apply_production_confidence_boost(issue: dict, confidence: float, rule_occurrences: int) -> float:
    """Boost confidence using multiple corroborating signals for production reliability."""
    rule_id = issue.get("rule_id", "")
    source_count = len(set(issue.get("confidence_sources", [])))
    occurrence_count = max(
        1,
        int(
            issue.get("count")
            or issue.get("affected_count")
            or issue.get("occurrence_count")
            or rule_occurrences
            or 1
        ),
    )
    trust_score = float(issue.get("rule_trust_score", get_rule_trust_score(rule_id)))

    boosted = float(confidence)
    if source_count >= 2:
        boosted += 0.15
    if occurrence_count > 1:
        boosted += 0.10
    if rule_id in HIGH_CONFIDENCE_RULES or rule_id in STRUCTURAL_FP_RULES or trust_score >= 0.70:
        boosted += 0.10

    return round(min(boosted, 0.95), 4)


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


def compute_final_confidence(
    base_confidence: float,
    rule_id: str,
    engine_agreement: float,
    behavioral_signal: float = 0.5,
) -> float:
    """
    Final confidence is a calibrated, evidence-weighted score.

    This prevents both under-reporting and noisy over-reporting:
    - A low-trust rule (landmark-one-main, trust=0.0) found only by static
      gets a confidence of ~0.20 → fails the min_confidence gate.
    - A high-trust rule (missing-alt, trust=0.89) found by both browser
      AND static gets confidence ~0.88 → passes the gate.

    Formula (blended, not fully multiplicative):
        final = (0.55 * base)
              + (0.20 * engine_agreement)
              + (0.15 * effective_trust)
              + (0.10 * behavioral_signal)

    A small suppress-penalty remains for low-agreement noisy rules.
    """
    trust_entry = get_rule_trust_entry(rule_id)
    trust = float(trust_entry.get("trust_score", get_rule_trust_score(rule_id)))
    verdict = str(trust_entry.get("verdict", "uncalibrated")).lower()

    base = min(1.0, max(0.0, float(base_confidence)))
    engine = min(1.0, max(0.0, float(engine_agreement)))
    behavioral = min(1.0, max(0.0, float(behavioral_signal)))
    effective_trust = min(1.0, max(0.0, trust))

    if verdict == "underdetected":
        # Avoid suppressing rules where benchmark evidence says we are missing detections.
        effective_trust = max(effective_trust, 0.50)
    elif verdict == "uncalibrated":
        effective_trust = max(effective_trust, 0.45)
    elif verdict == "suppress":
        effective_trust = min(effective_trust, 0.25)

    final = (
        (0.55 * base)
        + (0.20 * engine)
        + (0.15 * effective_trust)
        + (0.10 * behavioral)
    )

    if verdict == "suppress" and engine < 0.5:
        final *= 0.75

    if engine >= 0.7:
        final = max(final, base * 0.85)

    return round(min(final, 0.99), 4)


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
    rule_id = issue.get("rule_id", "")
    evidence = issue.get("evidence") if isinstance(issue.get("evidence"), dict) else {}
    high_signal_no_headings = bool(
        rule_id == "no-headings" and evidence.get("contentful_page_without_headings", False)
    )

    source_reliability = _calc_source_reliability(sources)
    signal_strength    = _calc_signal_strength(issue)
    cross_agreement    = _calc_cross_engine_agreement(sources)
    evidence_quality   = _calc_evidence_quality(issue)
    user_impact        = _calc_user_impact(issue)

    base_confidence = (
        CONFIDENCE_WEIGHTS["source_reliability"]     * source_reliability +
        CONFIDENCE_WEIGHTS["signal_strength"]        * signal_strength    +
        CONFIDENCE_WEIGHTS["cross_engine_agreement"] * cross_agreement    +
        CONFIDENCE_WEIGHTS["evidence_quality"]       * evidence_quality   +
        CONFIDENCE_WEIGHTS["user_impact"]            * user_impact
    )

    # Calibrate by rule type: hard checks are more objective, contextual less so.
    rule_type = RULE_TYPE_MAP.get(rule_id, "hard")
    if rule_type == "hard":
        base_confidence += 0.03
    elif rule_type == "visual":
        base_confidence -= 0.02
    elif rule_type == "contextual":
        base_confidence -= 0.07

    # ── Fragment Penalty ────────────────────────────────────────────────
    if html and rule_id in PAGE_LEVEL_RULES:
        completeness = document_completeness_score(html)
        if completeness < 0.6:
            penalty = 0.45 * (1.0 - completeness / 0.6)
            base_confidence -= penalty
            logger.debug(
                f"Fragment penalty: {rule_id} completeness={completeness:.2f} "
                f"penalty=-{penalty:.2f} → base_confidence={base_confidence:.3f}"
            )

    base_confidence = round(min(1.0, max(0.0, base_confidence)), 3)

    # ── Trust-Weighted Final Confidence ──────────────────────────────
    # Apply the multi-signal trust formula from Phase 9.3.
    # This modulates confidence by rule trustworthiness (from the registry),
    # engine agreement level, and behavioral signal strength.
    engine_agreement = cross_agreement  # Already 0.0–1.0
    behavioral = evidence_quality       # Use evidence quality as behavioral proxy

    confidence = compute_final_confidence(
        base_confidence=base_confidence,
        rule_id=rule_id,
        engine_agreement=engine_agreement,
        behavioral_signal=behavioral,
    )

    if high_signal_no_headings:
        confidence = max(confidence, 0.74)

    return confidence


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
    rule_occurrence_counts = {}
    for issue in issues:
        rid = issue.get("rule_id", "")
        rule_occurrence_counts[rid] = rule_occurrence_counts.get(rid, 0) + 1

    for issue in issues:
        sources = issue.get("confidence_sources", [])
        unique_sources = set(sources)
        rule_id = issue.get("rule_id", "")

        # Calculate confidence (with fragment detection + trust weighting)
        confidence = calculate_confidence(issue, html=html)

        # ── Attach trust metadata (Phase 9 requirement) ─────────────
        trust_entry = get_rule_trust_entry(rule_id)
        issue["rule_trust_score"] = trust_entry.get("trust_score", 0.50)
        issue["rule_trust_verdict"] = trust_entry.get("verdict", "uncalibrated")

        # Multi-signal production boost (source agreement, recurrence, trust/structural strength).
        confidence = _apply_production_confidence_boost(
            issue,
            confidence,
            rule_occurrences=rule_occurrence_counts.get(rule_id, 1),
        )

        if rule_id in HIGH_FN_RULES:
            confidence = round(min(confidence + 0.10, 0.99), 4)

        # Rule: heuristic-only → needs-review
        if unique_sources == {"heuristic"}:
            issue["issue_type"] = "needs-review"
            issue["needs_manual_review"] = True

        issue["confidence"] = confidence
        issue["confidence_tier"] = _confidence_tier(confidence)
        issue["rule_type"] = RULE_TYPE_MAP.get(rule_id, "hard")

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

        # Keep needs-review findings visible, but with slightly reduced confidence.
        if bool(issue.get("needs_manual_review", False)):
            issue["confidence"] = round(max(0.10, float(issue.get("confidence", 0.0)) * 0.95), 4)
            issue["confidence_tier"] = _confidence_tier(issue["confidence"])

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

    # ── Confidence boost contract ── TWO PASSES BY DESIGN ─────────────────
    # DO NOT consolidate these into a single pass without reading this contract.
    # Pass 1 (_apply_production_confidence_boost, above): per-issue boost based on
    #         source_count, recurrence, and structural trust. Hard-capped at 0.95.
    # Pass 2 (_boost_cross_engine_agreement, below): rule-level floor when 2+
    #         independent engines agree on same rule_id. Uses max(current, 0.85|0.95).
    #         Never lowers a result from Pass 1; only raises it.
    # Example: issue at 0.92 from Pass 1 stays 0.92. Issue at 0.70 from Pass 1
    #          is floored to 0.85 if 2 engines agree, or 0.95 if 3+ agree.
    issues = _boost_cross_engine_agreement(issues)

    # Log summary
    avg_confidence = sum(i.get("confidence", 0) for i in issues) / len(issues) if issues else 0
    needs_review = sum(1 for i in issues if i.get("needs_manual_review"))
    logger.info(
        f"Confidence scoring: {len(issues)} issues, "
        f"avg confidence={avg_confidence:.2f}, "
        f"{needs_review} flagged for manual review"
    )

    return issues


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
            floor = 0.95 if len(confirming) >= 3 else 0.85
            issue["confidence"] = max(current, floor)
            issue["confidence_tier"] = "high"
            logger.debug(
                f"Cross-engine boost: {rule_id} confirmed by {confirming} → confidence={issue['confidence']}"
            )

    return issues


# ── Score computation utilities (Production Readiness) ─────────────
# DESIGN CONSTRAINT: These functions affect SCORE COMPUTATION ONLY.
# They do NOT affect visibility filtering.  Confidence ≠ visibility.
# Visibility decisions happen in audit_runner._apply_precision_profile().




def detect_semantic_html_density(html: str) -> float:
    """Measure the ratio of semantic HTML elements to total elements.

    Returns a 0.0–1.0 density value.  High values (>0.85) signal a
    well-structured page unlikely to have real structural accessibility
    issues — used by apply_quality_bonus() to floor scores.
    """
    if not html:
        return 0.0

    _SEMANTIC_TAGS = {
        "main", "nav", "header", "footer", "article", "section",
        "aside", "figure", "figcaption", "details", "summary",
        "dialog", "mark", "time",
    }

    try:
        # Count all opening tags vs semantic tags (cheap regex, no parser)
        all_tags = re.findall(r"<([a-zA-Z][a-zA-Z0-9]*)", html)
        if not all_tags:
            return 0.0
        semantic_count = sum(1 for tag in all_tags if tag.lower() in _SEMANTIC_TAGS)
        density = semantic_count / len(all_tags)
        return round(min(1.0, density), 3)
    except Exception:
        return 0.0


def apply_quality_bonus(score: float, site_signals: dict) -> float:
    """Apply score floor for high-quality sites.

    Prevents over-penalisation of well-built pages that happen to trigger
    minor structural rules.  Affects final score only, never visibility.

    Args:
        score:        Current score (0-100).
        site_signals: Dict with keys like ``semantic_html_density``,
                      ``has_skip_link``, ``has_lang_attr``,
                      ``has_critical_violations``, etc.

    Returns:
        Adjusted score (may be floored upward, never lowered).
    """
    # GUARD: Never apply quality bonus when critical violations exist.
    # Prevents bad sites from gaming the system with semantic tags.
    if bool(site_signals.get("has_critical_violations", False)):
        return score

    density = float(site_signals.get("semantic_html_density", 0.0))
    has_skip_link = bool(site_signals.get("has_skip_link", False))
    has_lang_attr = bool(site_signals.get("has_lang_attr", False))

    quality_indicators = sum([
        density > 0.85,
        has_skip_link,
        has_lang_attr,
    ])

    # Floor: if 2+ quality indicators present, score cannot drop below 75
    if quality_indicators >= 2 and score < 75.0:
        logger.debug(
            "Quality bonus: flooring score from %.1f to 75.0 (density=%.2f, indicators=%d)",
            score, density, quality_indicators,
        )
        return 75.0

    # Small bonus for very high quality sites (capped at 100)
    if quality_indicators >= 3:
        bonus = min(3.0, 100.0 - score)
        if bonus > 0:
            logger.debug("Quality bonus: adding +%.1f bonus (all indicators met)", bonus)
            return round(score + bonus, 1)

    return score


def calculate_diminishing_penalty(
    count: int,
    base_weight: float,
    *,
    exponent: float = 0.65,
) -> float:
    """Sub-linear penalty: 10 repeated issues ≠ 10× penalty.

    Used by the scoring system to prevent repeated structural rules from
    collapsing the score.  This is a pure math utility.

    Args:
        count:       Number of occurrences.
        base_weight: Per-issue penalty weight.
        exponent:    Diminishing returns exponent (default 0.65 from TRUST_CALIBRATION).

    Returns:
        Total penalty for all occurrences.
    """
    safe_count = max(1, int(count))
    safe_weight = max(0.0, float(base_weight))
    safe_exponent = max(0.3, min(1.0, float(exponent)))
    return round(safe_weight * (safe_count ** safe_exponent), 3)

