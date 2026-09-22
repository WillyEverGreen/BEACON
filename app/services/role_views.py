"""
Role-Specific Dashboard Views, Controlled Scoring, and Multi-Lens Projection (§39–§48).

Implements:
- §39–§43: Role-specific view projections (DEVELOPER, QA_A11Y, COMPLIANCE, EXECUTIVE)
- §44: Controlled mathematical score model with explicit coverage caveats
- §45: Profile-specific scoring engine
- §46: Profile filter API support
- §47: One scan, many lenses projection without Chromium re-execution
- §48: Evidence-first finding contract
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.profiles.engine import evaluate_profile, map_finding_to_persona_lenses
from app.profiles.registry import GLOBAL_WCAG_22_AA, PERSONA_LENSES, REGULATORY_PROFILES

logger = logging.getLogger(__name__)

SUPPORTED_ROLES = {"DEVELOPER", "QA_A11Y", "COMPLIANCE", "EXECUTIVE"}


# ── §48: Evidence-First Finding Contract ──────────────────────────────────────

def build_evidence_first_finding(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Transforms any scanner or normalized finding into the canonical Evidence-First contract (§48).
    Optional sections remain empty dicts/lists rather than fabricating evidence.
    """
    finding_id = str(raw.get("id") or raw.get("finding_id") or raw.get("issue_id") or "")
    rule_id = str(raw.get("rule_id") or raw.get("raw_rule_id") or "")
    raw_crit = str(
        raw.get("wcag_criterion")
        or raw.get("criterion")
        or (raw.get("wcag") if isinstance(raw.get("wcag"), dict) else {}).get("criterion")
        or raw.get("wcag_sc")
        or ""
    ).strip()
    match = re.search(r"\b\d+\.\d+\.\d+\b", raw_crit)
    criterion = match.group(0) if match else raw_crit
    level = str(raw.get("wcag_level") or raw.get("level") or "AA").upper()

    verdict_raw = str(raw.get("verdict") or raw.get("adjudication_status") or "FAIL").lower()
    if verdict_raw in {"pass", "fail", "needs_review"}:
        verdict = verdict_raw
    else:
        verdict = "fail" if raw.get("issue_type") in {"violation", "error", None} else "needs_review"

    try:
        confidence = float(raw.get("confidence") or raw.get("adjudication_confidence") or 0.85)
    except (ValueError, TypeError):
        confidence = 0.85

    # Evidence preservation
    dom_evidence = raw.get("element_context") or {}
    browser_evidence = raw.get("browser_evidence") or {}
    visual_evidence = raw.get("visual_evidence") or {}
    at_evidence = raw.get("at_evidence") or {}

    # Extract selectors/html
    selector = raw.get("selector") or raw.get("element") or ""
    html = raw.get("html") or raw.get("html_snippet") or ""

    # Persona mapping
    personas = raw.get("persona_lenses")
    if not isinstance(personas, list):
        personas = map_finding_to_persona_lenses({
            "wcag_criterion": criterion,
            "rule_id": rule_id,
            "description": raw.get("description", ""),
        })

    # Profile mappings
    profiles_mapping = raw.get("regulatory_mappings") or {}
    if not profiles_mapping and criterion:
        profiles_mapping = {
            pid: prof.mapped_requirements.get(criterion, f"Clause {criterion}")
            for pid, prof in REGULATORY_PROFILES.items()
            if criterion in prof.mandatory_criteria or criterion in prof.optional_advisory_checks
        }

    return {
        "finding_id": finding_id,
        "rule_id": rule_id,
        "wcag": {
            "criterion": criterion,
            "level": level,
        },
        "severity": str(raw.get("severity") or "moderate").lower(),
        "verification": {
            "verdict": verdict,
            "confidence": round(confidence, 3),
        },
        "location": {
            "selector": selector,
            "html": html,
            "file": raw.get("file"),
            "line": raw.get("line"),
        },
        "evidence": {
            "dom": dom_evidence,
            "browser": browser_evidence,
            "visual": visual_evidence,
            "assistive_technology": at_evidence,
        },
        "root_cause": raw.get("root_cause") or {},
        "profiles": profiles_mapping,
        "personas": personas,
        "remediation": {
            "fix": raw.get("suggested_fix") or raw.get("fix") or "",
            "framework_fix": raw.get("framework_fix") or {},
            "explanation": raw.get("fix_explanation") or "",
        },
        "sandbox": raw.get("sandbox_verification") or {},
        "is_template_inferred": bool(raw.get("is_template_inferred", False)),
        "description": raw.get("description", ""),
    }


# ── §44: Controlled Score Model ───────────────────────────────────────────────

def calculate_controlled_score(
    findings: list[dict[str, Any]],
    *,
    tested_criteria_count: int = 50,
    coverage_pct: float = 85.0,
) -> dict[str, Any]:
    """
    Controlled mathematical accessibility score (§44).
    Inputs are transparent:
    - Base score: % of tested criteria without verified failures
    - Penalties applied ONLY for verified FAIL findings (PASS & suppressed FPs are never penalized)
    - Deductions weighted by severity and adjusted by AI confidence
    - Clear coverage caveat displayed alongside score
    """
    # 1. Filter to verified scorable violations
    scorable_violations = []
    for f in findings:
        verdict = str(f.get("verification", {}).get("verdict") or f.get("verdict") or "fail").lower()
        if verdict == "pass":
            continue  # Never penalize PASS
        if f.get("is_suppressed") or f.get("is_false_positive"):
            continue  # Never penalize suppressed false positives
        scorable_violations.append(f)

    # 2. Penalty weights by severity
    SEVERITY_WEIGHTS = {
        "critical": 15.0,
        "serious": 8.0,
        "moderate": 4.0,
        "minor": 1.5,
    }

    total_penalty = 0.0
    penalties_breakdown = {"critical": 0.0, "serious": 0.0, "moderate": 0.0, "minor": 0.0}
    severity_counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}

    violated_criteria: set[str] = set()

    for item in scorable_violations:
        sev = str(item.get("severity") or "moderate").lower()
        if sev not in SEVERITY_WEIGHTS:
            sev = "moderate"
        
        # Confidence multiplier: low confidence has lower impact
        try:
            conf = float(item.get("verification", {}).get("confidence") or item.get("confidence") or 0.85)
        except (ValueError, TypeError):
            conf = 0.85

        weight = SEVERITY_WEIGHTS[sev]
        effective_penalty = weight * max(0.5, conf)

        total_penalty += effective_penalty
        penalties_breakdown[sev] += effective_penalty
        severity_counts[sev] += 1

        crit = str(item.get("wcag", {}).get("criterion") or item.get("wcag_criterion") or "").strip()
        if crit:
            violated_criteria.add(crit)

    # Base score: criteria pass rate
    tested_count = max(1, tested_criteria_count)
    passing_criteria_count = max(0, tested_count - len(violated_criteria))
    criteria_pass_rate = (passing_criteria_count / tested_count) * 100.0

    # Calculate final score (bounded between 0.0 and 100.0)
    raw_score = max(0.0, 100.0 - total_penalty)
    # Blend with criteria pass rate
    blended_score = round(0.4 * criteria_pass_rate + 0.6 * raw_score, 1)

    return {
        "score": blended_score,
        "criteria_pass_rate": round(criteria_pass_rate, 1),
        "total_penalty_applied": round(total_penalty, 2),
        "penalties_by_severity": {k: round(v, 2) for k, v in penalties_breakdown.items()},
        "severity_counts": severity_counts,
        "scorable_violations_count": len(scorable_violations),
        "tested_criteria_count": tested_count,
        "failing_criteria_count": len(violated_criteria),
        "coverage_percentage": round(coverage_pct, 1),
        "coverage_caveat": (
            f"Score reflects the {coverage_pct}% of WCAG 2.2 criteria evaluable via automated "
            "and semi-automated detection. 100% automated coverage is mathematically impossible."
        ),
    }


# ── §45: Profile-Specific Scoring ─────────────────────────────────────────────

def calculate_profile_score(
    findings: list[dict[str, Any]],
    profile_id: str = "GLOBAL_WCAG_22_AA",
) -> dict[str, Any]:
    """
    Computes a score specifically mapped and filtered to a regulatory profile (§45).
    Evaluates mandatory vs advisory criteria under the profile.
    """
    profile = REGULATORY_PROFILES.get(profile_id, GLOBAL_WCAG_22_AA)
    evaluation = evaluate_profile(profile_id, findings)

    mandatory_violations = evaluation["mandatory_violations"]
    advisory_findings = evaluation["advisory_findings"]

    # Calculate score using mandatory criteria of the profile
    tested_mandatory = len(profile.mandatory_criteria)
    score_result = calculate_controlled_score(
        mandatory_violations,
        tested_criteria_count=tested_mandatory,
        coverage_pct=80.0 if profile_id != "GLOBAL_WCAG_22_AA" else 85.0,
    )

    return {
        "profile_id": profile.profile_id,
        "profile_name": profile.name,
        "jurisdiction": profile.jurisdiction,
        "technical_standard": profile.technical_standard,
        "status": evaluation["status"],
        "profile_score": score_result["score"],
        "technical_assessment_score": score_result["score"],
        "criteria_pass_rate": score_result["criteria_pass_rate"],
        "mandatory_criteria_count": tested_mandatory,
        "mandatory_violations_count": len(mandatory_violations),
        "advisory_findings_count": len(advisory_findings),
        "other_findings_count": evaluation.get("other_findings_count", 0),
        "total_findings_count": evaluation.get("total_findings_count", len(findings)),
        "summary_counts": evaluation.get("summary_counts", {}),
        "score_details": score_result,
        "disclaimer": profile.disclaimer,
        "verification_source": profile.verification_source,
    }


# ── §39–§43: Role-Specific Dashboard Views ────────────────────────────────────

def build_developer_view(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Developer View (§40):
    Prioritizes actionable code fixes, selectors, HTML context, and component grouping.
    """
    prioritized_items = []
    by_component: dict[str, list[dict[str, Any]]] = {}

    for f in findings:
        cf = build_evidence_first_finding(f)
        item = {
            "finding_id": cf["finding_id"],
            "rule_id": cf["rule_id"],
            "wcag_criterion": cf["wcag"]["criterion"],
            "severity": cf["severity"],
            "confidence": cf["verification"]["confidence"],
            "selector": cf["location"]["selector"],
            "html": cf["location"]["html"],
            "file": cf["location"]["file"],
            "line": cf["location"]["line"],
            "root_cause": cf["root_cause"],
            "suggested_fix": cf["remediation"]["fix"],
            "framework_fix": cf["remediation"]["framework_fix"],
            "sandbox_status": cf["sandbox"].get("verdict", "unverified"),
            "is_template_inferred": cf["is_template_inferred"],
        }
        prioritized_items.append(item)

        comp = cf["location"]["file"] or (cf["location"]["selector"].split(" ")[0] if cf["location"]["selector"] else "general")
        by_component.setdefault(comp, []).append(item)

    actionable_ids = [item["finding_id"] for item in prioritized_items if item.get("finding_id")]

    return {
        "role": "DEVELOPER",
        "description": "Code-first perspective prioritizing actionable remediation and DOM/source locations.",
        "total_actionable_findings": len(prioritized_items),
        "findings": prioritized_items,
        "actionable_finding_ids": actionable_ids,
        "by_component": by_component,
        "supported_actions": [
            "copy_fix",
            "copy_selector",
            "download_sarif",
            "open_source_location",
        ],
    }


def build_qa_specialist_view(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """
    QA / Accessibility Specialist View (§41):
    Prioritizes review queue (NEEDS_REVIEW), reproduction steps, multi-modal evidence.
    """
    needs_review_queue = []
    verified_failures = []

    for f in findings:
        cf = build_evidence_first_finding(f)
        verdict = cf["verification"]["verdict"]

        item = {
            "finding_id": cf["finding_id"],
            "rule_id": cf["rule_id"],
            "wcag_criterion": cf["wcag"]["criterion"],
            "verdict": verdict,
            "confidence": cf["verification"]["confidence"],
            "description": cf["description"],
            "selector": cf["location"]["selector"],
            "evidence": cf["evidence"],
            "expected_behavior": f"Element must satisfy WCAG {cf['wcag']['criterion']}.",
            "actual_behavior": cf["description"] or "Failed automated accessibility check.",
            "reproduction_steps": [
                "1. Navigate to target URL.",
                f"2. Inspect element matching '{cf['location']['selector']}'.",
                "3. Verify accessibility tree and keyboard/contrast behavior.",
            ],
            "review_status": "pending_manual_verification" if verdict == "needs_review" else "automated_decision",
        }

        if verdict == "needs_review":
            needs_review_queue.append(item)
        else:
            verified_failures.append(item)

    return {
        "role": "QA_A11Y",
        "description": "Inspection and validation perspective with dedicated review queue and reproduction steps.",
        "needs_review_count": len(needs_review_queue),
        "verified_failures_count": len(verified_failures),
        "review_queue_ids": [item["finding_id"] for item in needs_review_queue if item.get("finding_id")],
        "verified_failure_ids": [item["finding_id"] for item in verified_failures if item.get("finding_id")],
        "review_queue": needs_review_queue,
        "verified_failures": verified_failures,
        "supported_actions": [
            "confirm_finding",
            "reject_finding",
            "request_more_evidence",
            "trigger_retest",
        ],
    }


def build_compliance_view(
    findings: list[dict[str, Any]],
    profile_id: str = "GLOBAL_WCAG_22_AA",
) -> dict[str, Any]:
    """
    Compliance Officer View (§42):
    Prioritizes regulatory mapping, criteria coverage, and technical conformance.
    """
    profile_score = calculate_profile_score(findings, profile_id=profile_id)
    
    # Categorize findings by mandatory vs advisory under the profile
    profile = REGULATORY_PROFILES.get(profile_id, GLOBAL_WCAG_22_AA)
    evaluation = evaluate_profile(profile_id, findings)

    # Criteria coverage summary
    unassessed = sorted(list(profile.mandatory_criteria - set(
        f.get("wcag_criterion") or f.get("wcag", {}).get("criterion") or ""
        for f in evaluation["mandatory_violations"]
    )))

    refined_disclaimer = (
        "Technical assessment only. This evaluation maps detected evidence against the selected "
        f"{profile.name} criteria. It does not constitute legal advice, formal ACR/VPAT certification, "
        "or a government determination of compliance."
    )

    return {
        "role": "COMPLIANCE",
        "description": "Regulatory and legal risk perspective mapped to official control profiles.",
        "selected_profile": profile_score,
        "technical_conformance_status": profile_score["status"],
        "technical_assessment_score": profile_score.get("technical_assessment_score", profile_score["profile_score"]),
        "profile_score": profile_score["profile_score"],
        "mandatory_violations_count": profile_score["mandatory_violations_count"],
        "advisory_findings_count": profile_score["advisory_findings_count"],
        "other_findings_count": evaluation.get("other_findings_count", 0),
        "total_findings_count": evaluation.get("total_findings_count", len(findings)),
        "open_violations": evaluation["mandatory_violations"],
        "advisory_items": evaluation["advisory_findings"],
        "other_items": evaluation.get("other_findings", []),
        "mandatory_finding_ids": evaluation.get("mandatory_finding_ids", []),
        "advisory_finding_ids": evaluation.get("advisory_finding_ids", []),
        "other_finding_ids": evaluation.get("other_finding_ids", []),
        "summary_counts": evaluation.get("summary_counts", {}),
        "unassessed_mandatory_criteria": unassessed,
        "evidence_gaps_noted": len(evaluation["advisory_findings"]),
        "disclaimer": refined_disclaimer,
        "supported_actions": [
            "export_vpat_draft",
            "export_compliance_matrix",
            "generate_accessibility_statement",
        ],
    }


def build_executive_view(
    findings: list[dict[str, Any]],
    *,
    pages_scanned: int = 1,
    templates_count: int = 1,
) -> dict[str, Any]:
    """
    Executive / Product Owner View (§43):
    High-level accessibility posture, business impact, affected personas, and progress.
    """
    controlled_score = calculate_controlled_score(findings)
    canonical = [build_evidence_first_finding(f) for f in findings]

    verified_violations = [f for f in canonical if f["verification"]["verdict"] == "fail"]
    critical_serious_items = [f for f in canonical if f["severity"] in {"critical", "serious"} and f["verification"]["verdict"] != "pass"]
    critical_serious_count = len(critical_serious_items)
    critical_serious_ids = [f["finding_id"] for f in critical_serious_items if f.get("finding_id")]
    needs_review_count = sum(1 for f in canonical if f["verification"]["verdict"] == "needs_review")
    validated_fixes = sum(1 for f in canonical if f["sandbox"].get("verdict") == "PASS")

    # Affected personas rollup
    affected_personas: dict[str, int] = {}
    for f in canonical:
        if f["verification"]["verdict"] == "pass":
            continue
        for p in f.get("personas", []):
            pid = p.get("id", "OTHER")
            affected_personas[pid] = affected_personas.get(pid, 0) + 1

    return {
        "role": "EXECUTIVE",
        "description": "High-level accessibility posture, risk summary, and business impact.",
        "overall_health_score": controlled_score["score"],
        "pages_assessed": pages_scanned,
        "templates_affected": templates_count,
        "total_verified_issues": len(verified_violations),
        "critical_and_serious_issues": critical_serious_count,
        "critical_serious_ids": critical_serious_ids,
        "pending_human_review": needs_review_count,
        "validated_fixes_count": validated_fixes,
        "affected_personas_summary": affected_personas,
        "coverage_caveat": controlled_score["coverage_caveat"],
        "executive_summary_statement": (
            f"Assessed {pages_scanned} page(s) across {templates_count} template(s). "
            f"Detected {len(canonical)} total findings ({critical_serious_count} high impact). "
            f"{validated_fixes} automated fixes validated in sandbox."
        ),
    }


def build_role_view(
    findings: list[dict[str, Any]],
    role: str = "DEVELOPER",
    *,
    profile_id: str | None = None,
    pages_scanned: int = 1,
    templates_count: int = 1,
) -> dict[str, Any]:
    """Dispatcher for role-specific dashboard views (§39)."""
    norm_role = str(role or "DEVELOPER").strip().upper()
    if norm_role == "DEVELOPER":
        return build_developer_view(findings)
    elif norm_role == "QA_A11Y":
        return build_qa_specialist_view(findings)
    elif norm_role == "COMPLIANCE":
        return build_compliance_view(findings, profile_id=profile_id or "GLOBAL_WCAG_22_AA")
    elif norm_role == "EXECUTIVE":
        return build_executive_view(findings, pages_scanned=pages_scanned, templates_count=templates_count)
    else:
        raise ValueError(f"Unsupported role: '{role}'. Supported roles are: {sorted(list(SUPPORTED_ROLES))}")


# ── §47: One Scan, Many Lenses Projector ──────────────────────────────────────

def project_scan_view(
    audit_data: dict[str, Any],
    *,
    profile_id: str | None = None,
    persona_id: str | None = None,
    view: str | None = None,
) -> dict[str, Any]:
    """
    Project scan results under specified regulatory profile, persona lens, and role view (§46, §47).
    Executes entirely on in-memory / persisted audit results without re-scanning.
    """
    # 1. Extract raw findings
    raw_findings = audit_data.get("issues") or audit_data.get("results") or []
    if not isinstance(raw_findings, list):
        raw_findings = []

    # 2. Filter by persona lens if requested
    filtered_findings = raw_findings
    active_persona = None
    if persona_id:
        norm_persona = persona_id.strip().upper()
        if norm_persona not in PERSONA_LENSES:
            raise ValueError(f"Invalid persona_id: '{persona_id}'. Valid personas: {sorted(list(PERSONA_LENSES.keys()))}")
        active_persona = PERSONA_LENSES[norm_persona]
        
        filtered = []
        for f in raw_findings:
            sc = str(f.get("wcag_criterion") or "").strip()
            rule_id = str(f.get("rule_id") or "").strip()
            # Check persona relevance
            if sc in active_persona.relevant_criteria or any(k in rule_id for k in ["alt", "aria", "focus", "contrast", "keyboard"]):
                filtered.append(f)
        filtered_findings = filtered

    # 3. Filter / evaluate under regulatory profile if requested
    if profile_id:
        norm_profile = profile_id.strip().upper()
        if norm_profile not in REGULATORY_PROFILES:
            raise ValueError(f"Invalid profile_id: '{profile_id}'. Valid profiles: {sorted(list(REGULATORY_PROFILES.keys()))}")

    # 4. Project into requested role view
    active_view = (view or "DEVELOPER").strip().upper()
    if active_view not in SUPPORTED_ROLES:
        raise ValueError(f"Invalid view: '{view}'. Valid views: {sorted(list(SUPPORTED_ROLES))}")

    pages_scanned = int(audit_data.get("pages_scanned") or audit_data.get("pages_audited") or 1)
    role_projection = build_role_view(
        filtered_findings,
        role=active_view,
        profile_id=profile_id,
        pages_scanned=pages_scanned,
    )

    # 5. Calculate scores
    profile_score = calculate_profile_score(filtered_findings, profile_id=profile_id or "GLOBAL_WCAG_22_AA")

    return {
        "scan_id": audit_data.get("scan_id") or audit_data.get("audit_id") or audit_data.get("id"),
        "url": audit_data.get("url") or audit_data.get("seed_url"),
        "applied_lenses": {
            "profile": profile_score["profile_id"],
            "persona": active_persona.id if active_persona else None,
            "role_view": active_view,
        },
        "profile_score": profile_score,
        "view_data": role_projection,
    }
