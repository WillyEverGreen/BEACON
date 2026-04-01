"""
Schema Compatibility Layer — maps between DJ HACK engine's AuditIssue format
and the DJ FR Localbros3000 app's AccessibilityIssue / RagFinding formats.

This ensures the upgraded engine can be dropped into the full app without
breaking Firestore storage, PDF reports, or the GitHub auto-fix pipeline.
"""
from typing import Any, Optional

# ── WCAG → Disability Group Mapping ───────────────────────────
# Maps WCAG success criterion prefixes to affected disability groups.
# Used by the full app for per-issue disability impact tagging.

WCAG_DISABILITY_MAP: dict[str, list[str]] = {
    # 1.x — Perceivable
    "1.1": ["vision", "cognitive"],           # Non-text content
    "1.2": ["vision", "hearing"],             # Time-based media
    "1.3": ["vision", "cognitive"],           # Adaptable
    "1.4": ["vision"],                        # Distinguishable
    # 2.x — Operable
    "2.1": ["motor"],                         # Keyboard accessible
    "2.2": ["motor", "cognitive"],            # Enough time
    "2.3": ["photosensitive"],                # Seizures / physical
    "2.4": ["vision", "cognitive", "motor"],  # Navigable
    "2.5": ["motor"],                         # Input modalities
    # 3.x — Understandable
    "3.1": ["cognitive", "vision"],           # Readable
    "3.2": ["cognitive"],                     # Predictable
    "3.3": ["cognitive", "motor"],            # Input assistance
    # 4.x — Robust
    "4.1": ["vision"],                        # Compatible
}


def get_disability_groups(wcag_criterion: str) -> list[str]:
    """
    Get affected disability groups for a WCAG success criterion.
    
    Args:
        wcag_criterion: e.g. "1.1.1", "2.4.7", "3.3.1"
    
    Returns:
        List of disability group strings, e.g. ["vision", "cognitive"]
    """
    if not wcag_criterion:
        return ["general"]
    
    # Try exact prefix match (first two levels: "1.1", "2.4", etc.)
    parts = wcag_criterion.split(".")
    if len(parts) >= 2:
        prefix = f"{parts[0]}.{parts[1]}"
        if prefix in WCAG_DISABILITY_MAP:
            return WCAG_DISABILITY_MAP[prefix]
    
    # Try first level
    if parts[0] in WCAG_DISABILITY_MAP:
        return WCAG_DISABILITY_MAP[parts[0]]
    
    return ["general"]


# ── Severity Mapping ──────────────────────────────────────────

SEVERITY_TO_IMPACT = {
    "critical": "critical",
    "serious": "serious",
    "moderate": "moderate",
    "minor": "minor",
}


# ── Core Mapping Functions ────────────────────────────────────

def audit_issue_to_accessibility_issue(issue: dict) -> dict:
    """
    Map DJ HACK AuditIssue → DJ FR AccessibilityIssue.
    
    Field mapping:
        AuditIssue.element        → AccessibilityIssue.css_selector
        AuditIssue.suggested_fix  → AccessibilityIssue.fix_suggestion
        AuditIssue.html_snippet   → AccessibilityIssue.html_snippet  (same)
        AuditIssue.rule_id        → AccessibilityIssue.rule_id       (same)
        AuditIssue.severity       → AccessibilityIssue.impact
        AuditIssue.wcag_criterion → AccessibilityIssue.wcag_sc
        (computed)                → AccessibilityIssue.affected_disability_groups
    """
    wcag = issue.get("wcag_criterion", "")
    
    return {
        # Identity
        "rule_id": issue.get("rule_id", "unknown"),
        "description": issue.get("description", ""),
        
        # Mapped fields
        "css_selector": issue.get("element", ""),
        "fix_suggestion": issue.get("suggested_fix", issue.get("code_fix", "")),
        "impact": SEVERITY_TO_IMPACT.get(issue.get("severity", "moderate"), "moderate"),
        "wcag_sc": wcag,
        "wcag_level": issue.get("wcag_level", ""),
        
        # Computed fields
        "affected_disability_groups": get_disability_groups(wcag),
        
        # Pass-through fields
        "html_snippet": issue.get("html_snippet", ""),
        "page_url": issue.get("page_url", ""),
        "source": issue.get("source", "static"),
        "confidence": issue.get("confidence", 0.5),
        "needs_manual_review": issue.get("needs_manual_review", False),
        
        # Enrichment fields (if present)
        "human_impact": issue.get("human_impact", ""),
        "wcag_intent": issue.get("wcag_intent", ""),
        "test_procedure": issue.get("test_procedure", ""),
        "framework_fixes": issue.get("framework_fixes", {}),
    }


def audit_issue_to_rag_finding(issue: dict) -> dict:
    """
    Map DJ HACK AuditIssue → DJ FR RagFinding for Layer 2 results.
    
    RagFinding is used when merging RAG-detected issues into the
    main issue list via to_accessibility_issue().
    """
    return {
        "wcag_criterion": issue.get("wcag_criterion", ""),
        "wcag_level": issue.get("wcag_level", "A"),
        "severity": issue.get("severity", "moderate"),
        "description": issue.get("description", ""),
        "affected_element": issue.get("element", ""),
        "page_url": issue.get("page_url", ""),
        "fix_suggestion": issue.get("suggested_fix", ""),
        "source": "rag",
        "retrieved_context": issue.get("retrieved_context", ""),
    }


def checklist_to_app_format(
    check_results: dict[str, dict],
    categories: Optional[dict] = None,
) -> dict:
    """
    Convert engine check_results into the DJ FR checklist_summary format.
    
    Expected output format:
    {
        "categories": {
            "HTML & Structure": {
                "passed": N, "failed": N, "warnings": N,
                "checks": [{"id": .., "status": .., "detail": ..}]
            }
        },
        "total_passed": N, "total_failed": N, "score": 0-100
    }
    """
    # Group by category if categories mapping provided
    cat_results: dict[str, dict] = {}
    
    total_passed = 0
    total_failed = 0
    total_warnings = 0
    
    for check_id, result in check_results.items():
        status = result.get("status", "warn")
        
        if status == "pass":
            total_passed += 1
        elif status == "fail":
            total_failed += 1
        else:
            total_warnings += 1
        
        # Default category
        cat_name = "General"
        if categories:
            for name, check_ids in categories.items():
                if check_id in check_ids:
                    cat_name = name
                    break
        
        if cat_name not in cat_results:
            cat_results[cat_name] = {
                "passed": 0, "failed": 0, "warnings": 0, "checks": []
            }
        
        cat = cat_results[cat_name]
        if status == "pass":
            cat["passed"] += 1
        elif status == "fail":
            cat["failed"] += 1
        else:
            cat["warnings"] += 1
        
        cat["checks"].append({
            "id": check_id,
            "status": status,
            "detail": result.get("detail", ""),
        })
    
    total = total_passed + total_failed
    score = round((total_passed / total * 100) if total > 0 else 100, 1)
    
    return {
        "categories": cat_results,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_warnings": total_warnings,
        "score": score,
    }
