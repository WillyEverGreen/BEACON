"""
Normalizer: converts raw findings from all engines (static, browser, axe-core, heuristic)
into a unified AuditIssue schema.
"""
import hashlib
import logging

from app.config import RULE_DOMAIN_MAP

logger = logging.getLogger(__name__)

# ── axe-core severity mapping ──────────────────────────────────

AXE_SEVERITY_MAP = {
    "critical": "critical",
    "serious": "serious",
    "moderate": "moderate",
    "minor": "minor",
}

# ── axe-core rule → WCAG mapping ──────────────────────────────

AXE_WCAG_MAP = {
    "color-contrast": ("1.4.3", "AA"),
    "color-contrast-enhanced": ("1.4.6", "AAA"),
    "image-alt": ("1.1.1", "A"),
    "input-image-alt": ("1.1.1", "A"),
    "area-alt": ("1.1.1", "A"),
    "label": ("1.3.1", "A"),
    "button-name": ("4.1.2", "A"),
    "link-name": ("2.4.4", "A"),
    "html-has-lang": ("3.1.1", "A"),
    "html-lang-valid": ("3.1.1", "A"),
    "document-title": ("2.4.2", "A"),
    "bypass": ("2.4.1", "A"),
    "heading-order": ("1.3.1", "A"),
    "aria-roles": ("4.1.2", "A"),
    "aria-valid-attr": ("4.1.2", "A"),
    "aria-valid-attr-value": ("4.1.2", "A"),
    "aria-required-attr": ("4.1.2", "A"),
    "aria-required-parent": ("4.1.2", "A"),
    "aria-required-children": ("4.1.2", "A"),
    "aria-hidden-focus": ("4.1.2", "A"),
    "tabindex": ("2.4.3", "A"),
    "landmark-one-main": ("1.3.1", "A"),
    "region": ("1.3.1", "A"),
    "meta-viewport": ("1.4.4", "AA"),
    "video-caption": ("1.2.2", "A"),
    "td-headers-attr": ("1.3.1", "A"),
    "th-has-data-cells": ("1.3.1", "A"),
    "definition-list": ("1.3.1", "A"),
    "list": ("1.3.1", "A"),
    "listitem": ("1.3.1", "A"),
    "form-field-multiple-labels": ("1.3.1", "A"),
}

# ── axe-core rule → category mapping ──────────────────────────

AXE_CATEGORY_MAP = {
    "color-contrast": "color",
    "color-contrast-enhanced": "color",
    "image-alt": "images",
    "input-image-alt": "images",
    "area-alt": "images",
    "label": "forms",
    "button-name": "forms",
    "link-name": "navigation",
    "html-has-lang": "html",
    "html-lang-valid": "html",
    "document-title": "html",
    "bypass": "navigation",
    "heading-order": "html",
    "aria-roles": "aria",
    "aria-valid-attr": "aria",
    "aria-valid-attr-value": "aria",
    "aria-required-attr": "aria",
    "aria-required-parent": "aria",
    "aria-required-children": "aria",
    "aria-hidden-focus": "aria",
    "tabindex": "keyboard",
    "landmark-one-main": "html",
    "region": "html",
    "meta-viewport": "html",
    "video-caption": "media",
}


# ── Rule Translation Map ──────────────────────────────────────
# Maps internal engine/axe IDs to standard ACT benchmark expects.
RULE_TRANSLATIONS = {
    "svg-img-alt": "svg-no-accessible-name",
    "image-redundant-alt": "redundant-alt",
    "invalid-role": "aria-role",
    "aria-roles": "aria-role",
    "link-text-missing": "link-name",
    "empty-anchor": "empty-link",
    "missing-alt": "image-alt",
    "missing-lang": "no-lang",
    "missing-lang-attr": "no-lang",
    "html-has-lang": "no-lang",
}


def _translate_rule_id(rule_id: str) -> str:
    clean = str(rule_id or "").strip()
    return RULE_TRANSLATIONS.get(clean, clean)

# ── High-Frequency Rules that should be grouped ───────────────
AXE_GROUPABLE_RULES = {
    "region", "list", "listitem", "definition-list", "landmark-unique",
    "landmark-one-main", "landmark-no-duplicate-banner",
    "landmark-no-duplicate-contentinfo", "landmark-no-duplicate-main",
    "landmark-banner-is-top-level", "landmark-contentinfo-is-top-level",
    "landmark-main-is-top-level", "form-field-multiple-labels",
}


def _make_issue_id(url: str, selector: str, rule_id: str) -> str:
    """Generate unique issue ID."""
    raw = f"{url}|{selector}|{rule_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def normalize_axe_results(axe_violations: list[dict], url: str) -> list[dict]:
    """
    Convert axe-core violation results into unified AuditIssue dicts.
    Groupable rules produce one representative issue with affected_count.
    """
    issues = []
    for violation in axe_violations:
        raw_rule_id = violation.get("id", "unknown")
        rule_id = _translate_rule_id(raw_rule_id)
        severity = AXE_SEVERITY_MAP.get(violation.get("impact", "moderate"), "moderate")
        wcag_info = AXE_WCAG_MAP.get(raw_rule_id, AXE_WCAG_MAP.get(rule_id, ("", "")))
        category = AXE_CATEGORY_MAP.get(raw_rule_id, AXE_CATEGORY_MAP.get(rule_id, "general"))
        nodes = violation.get("nodes", [])

        if raw_rule_id in AXE_GROUPABLE_RULES and nodes:
            affected = len(nodes)
            first = nodes[0]
            targets = first.get("target", [])
            selector = targets[0] if targets else ""
            html_snippet = first.get("html", "")[:500]
            
            desc = violation.get("description", "")
            if affected > 1:
                desc = f"{desc} ({affected} elements affected)"
                
            issues.append({
                "issue_id": _make_issue_id(url, f"{rule_id}:grouped", rule_id),
                "rule_id": rule_id,
                "is_grouped": True,
                "issue_type": "violation",
                "element": f"{affected} elements" if affected > 1 else selector,
                "html_snippet": html_snippet,
                "page_url": url,
                "severity": severity,
                "wcag_criterion": wcag_info[0],
                "wcag_level": wcag_info[1],
                "category": category,
                "confidence": 0.9,
                "confidence_sources": ["axe-core"],
                "needs_manual_review": False,
                "description": desc,
                "suggested_fix": violation.get("help", ""),
                "code_fix": first.get("failureSummary", ""),
                "fix_effort": "medium" if affected > 10 else "low",
                "group_id": "",
                "domain": RULE_DOMAIN_MAP.get(rule_id, ""),
                "evidence": {
                    "axe_help_url": violation.get("helpUrl", ""),
                    "axe_tags": violation.get("tags", []),
                    "affected_count": affected,
                },
                "reproducibility": "",
            })
            continue

        for node in nodes:
            targets = node.get("target", [])
            selector = targets[0] if targets else ""
            html_snippet = node.get("html", "")[:500]

            issues.append({
                "issue_id": _make_issue_id(url, selector, rule_id),
                "rule_id": rule_id,
                "is_grouped": False,
                "issue_type": "violation",
                "element": selector,
                "html_snippet": html_snippet,
                "page_url": url,
                "severity": severity,
                "wcag_criterion": wcag_info[0],
                "wcag_level": wcag_info[1],
                "category": category,
                "confidence": 0.9,
                "confidence_sources": ["axe-core"],
                "needs_manual_review": False,
                "description": violation.get("description", ""),
                "suggested_fix": violation.get("help", ""),
                "code_fix": node.get("failureSummary", ""),
                "fix_effort": "low",
                "group_id": "",
                "domain": RULE_DOMAIN_MAP.get(rule_id, ""),
                "evidence": {
                    "axe_help_url": violation.get("helpUrl", ""),
                    "axe_tags": violation.get("tags", []),
                },
                "reproducibility": "",
            })

    return issues


def normalize_static_results(static_issues: list[dict]) -> list[dict]:
    """
    Static check results are already in the unified format.
    Just ensure domain is populated from the rule_id mapping.
    """
    for issue in static_issues:
        issue["rule_id"] = _translate_rule_id(issue.get("rule_id", ""))
        if not issue.get("domain"):
            issue["domain"] = RULE_DOMAIN_MAP.get(issue.get("rule_id", ""), "")
    return static_issues


def normalize_heuristic_results(heuristic_issues: list[dict]) -> list[dict]:
    """
    Heuristic results are already in unified format.
    Populate domain and ensure needs_manual_review is set.
    """
    for issue in heuristic_issues:
        issue["rule_id"] = _translate_rule_id(issue.get("rule_id", ""))
        if not issue.get("domain"):
            issue["domain"] = RULE_DOMAIN_MAP.get(issue.get("rule_id", ""), "")
        issue["needs_manual_review"] = True
        issue["issue_type"] = "needs-review"
    return heuristic_issues


def normalize_browser_results(browser_issues: list[dict]) -> list[dict]:
    """
    Browser probe results are already in unified format.
    Populate domain from rule_id mapping.
    """
    for issue in browser_issues:
        issue["rule_id"] = _translate_rule_id(issue.get("rule_id", ""))
        if not issue.get("domain"):
            issue["domain"] = RULE_DOMAIN_MAP.get(issue.get("rule_id", ""), "")
    return browser_issues


def normalize_all(
    static_issues: list[dict],
    heuristic_issues: list[dict],
    browser_issues: list[dict],
    axe_issues: list[dict],
    url: str,
) -> list[dict]:
    """
    Normalize and merge results from all engines into a single list.
    """
    all_issues = []

    all_issues.extend(normalize_static_results(static_issues))
    all_issues.extend(normalize_heuristic_results(heuristic_issues))
    all_issues.extend(normalize_browser_results(browser_issues))
    all_issues.extend(normalize_axe_results(axe_issues, url))

    logger.info(
        f"Normalized {len(all_issues)} total issues: "
        f"{len(static_issues)} static, {len(heuristic_issues)} heuristic, "
        f"{len(browser_issues)} browser, {len(axe_issues)} axe-core"
    )

    return all_issues
