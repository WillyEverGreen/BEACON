"""
Profile Resolution & Persona Lens Engine (§25–§38)
Executes:
- §31: One-scan, many-profiles evaluation without re-scanning or mutating raw evidence
- §32–§38: Multi-persona lens mapping and user-centered impact explanations
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.profiles.models import PersonaMapping
from app.profiles.registry import GLOBAL_WCAG_22_AA, PERSONA_LENSES, REGULATORY_PROFILES

logger = logging.getLogger(__name__)


# ── §32–§38: Persona Lens Mapper ──────────────────────────────────────────────

def _extract_sc(finding: dict[str, Any]) -> str:
    raw = str(
        finding.get("wcag_criterion")
        or (finding.get("wcag") if isinstance(finding.get("wcag"), dict) else {}).get("criterion")
        or finding.get("wcag_sc")
        or ""
    ).strip()
    match = re.search(r"\b\d+\.\d+\.\d+\b", raw)
    return match.group(0) if match else raw


def map_finding_to_persona_lenses(finding: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Evaluates a finding against all 5 persona lenses (§32) and attaches relevance and user-centered explanations.
    Does not pretend to model actual people; represents perspective relevance (§33).
    """
    sc = _extract_sc(finding)
    rule_id = str(finding.get("rule_id") or "").strip()
    desc = str(finding.get("description") or "").strip()

    persona_mappings: list[PersonaMapping] = []

    for lens_id, lens in PERSONA_LENSES.items():
        is_relevant = sc in lens.relevant_criteria

        # Rule-specific relevance heuristics
        if not is_relevant:
            if lens_id == "SCREEN_READER" and any(k in rule_id for k in ["alt", "aria", "name", "label", "heading"]) or lens_id == "KEYBOARD_MOTOR" and any(k in rule_id for k in ["focus", "keyboard", "target", "drag"]) or lens_id == "LOW_VISION" and any(k in rule_id for k in ["contrast", "color", "zoom", "spacing"]) or lens_id == "COGNITIVE" and any(k in rule_id for k in ["coga", "reading", "auth", "help", "redundant"]) or lens_id == "DEAF_HARD_OF_HEARING" and any(k in rule_id for k in ["caption", "audio", "video", "media"]):
                is_relevant = True

        if is_relevant:
            relevance = 0.95 if sc in lens.relevant_criteria else 0.75
            # Generate human-centered explanation
            user_impact = f"{lens.user_impact_template} Issue: {desc}" if desc else lens.user_impact_template
            reason = f"Criterion {sc} directly affects the {lens.name.lower()}."

            mapping = PersonaMapping(
                id=lens_id,
                name=lens.name,
                relevance=relevance,
                reason=reason,
                user_impact_explanation=user_impact,
            )
            persona_mappings.append(mapping)

    return [m.to_dict() for m in persona_mappings]


def attach_persona_lenses_to_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enriches all findings with persona lens perspectives."""
    enriched = []
    for f in findings:
        item = dict(f)
        item["persona_lenses"] = map_finding_to_persona_lenses(item)
        enriched.append(item)
    return enriched


# ── §31: Profile Resolution Engine ────────────────────────────────────────────

def evaluate_profile(
    profile_id: str,
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Evaluates a set of findings under a single regulatory profile (§31).
    Filters, prioritizes, and maps clauses without mutating raw evidence.
    """
    profile = REGULATORY_PROFILES.get(profile_id, GLOBAL_WCAG_22_AA)
    
    mandatory_violations: list[dict[str, Any]] = []
    needs_review_findings: list[dict[str, Any]] = []
    advisory_findings: list[dict[str, Any]] = []
    passing_findings: list[dict[str, Any]] = []
    other_findings: list[dict[str, Any]] = []

    for f in findings:
        sc = _extract_sc(f)
        clause = profile.mapped_requirements.get(sc)
        
        entry = dict(f)
        entry["regulatory_clause"] = clause or f"Standard SC {sc}"

        raw_verdict = str(f.get("verdict") or f.get("verification", {}).get("verdict") or "fail").lower()
        
        if raw_verdict == "pass":
            passing_findings.append(entry)
            continue
        if f.get("is_suppressed") or f.get("is_false_positive"):
            continue

        if raw_verdict == "needs_review":
            needs_review_findings.append(entry)
        elif sc in profile.mandatory_criteria:
            mandatory_violations.append(entry)
        elif sc in profile.optional_advisory_checks:
            advisory_findings.append(entry)
        else:
            other_findings.append(entry)

    total_applicable = len(mandatory_violations) + len(advisory_findings) + len(needs_review_findings)
    status = (
        "NON_CONFORMANT" if len(mandatory_violations) > 0
        else "NEEDS_REVIEW" if len(needs_review_findings) > 0
        else "CONFORMANT_WITH_ADVISORY" if len(advisory_findings) > 0
        else "CONFORMANT"
    )

    def _get_fid(item: dict[str, Any]) -> str:
        return str(item.get("finding_id") or item.get("id") or item.get("issue_id") or "")

    return {
        "profile_id": profile.profile_id,
        "profile_name": profile.name,
        "jurisdiction": profile.jurisdiction,
        "technical_standard": profile.technical_standard,
        "status": status,
        "mandatory_violations_count": len(mandatory_violations),
        "needs_review_count": len(needs_review_findings),
        "advisory_findings_count": len(advisory_findings),
        "other_findings_count": len(other_findings),
        "passing_findings_count": len(passing_findings),
        "total_findings_count": len(findings),
        "total_applicable_findings": total_applicable,
        "mandatory_violations": mandatory_violations,
        "needs_review_findings": needs_review_findings,
        "advisory_findings": advisory_findings,
        "other_findings": other_findings,
        "passing_findings": passing_findings,
        "mandatory_finding_ids": [_get_fid(f) for f in mandatory_violations if _get_fid(f)],
        "advisory_finding_ids": [_get_fid(f) for f in advisory_findings if _get_fid(f)],
        "other_finding_ids": [_get_fid(f) for f in other_findings if _get_fid(f)],
        "summary_counts": {
            "total": len(findings),
            "mandatory": len(mandatory_violations),
            "advisory": len(advisory_findings),
            "other": len(other_findings),
            "passing": len(passing_findings),
        },
        "disclaimer": profile.disclaimer,
        "verification_source": profile.verification_source,
    }


def resolve_profiles_for_scan(
    findings: list[dict[str, Any]],
    requested_profile_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Resolves findings against multiple regulatory control profiles (§31).
    Implements 'one scan, many compliance lenses' architecture.
    """
    ids = requested_profile_ids or ["GLOBAL_WCAG_22_AA"]
    # Ensure at least GLOBAL_WCAG_22_AA is resolved
    if not ids:
        ids = ["GLOBAL_WCAG_22_AA"]

    evaluations: dict[str, dict[str, Any]] = {}
    for pid in ids:
        evaluations[pid] = evaluate_profile(pid, findings)

    return {
        "evaluated_profiles": ids,
        "profile_evaluations": evaluations,
        "summary": {
            pid: {
                "status": ev["status"],
                "mandatory_violations": ev["mandatory_violations_count"],
                "advisory_findings": ev["advisory_findings_count"],
            }
            for pid, ev in evaluations.items()
        },
    }
