"""
Normalizer: converts raw findings from all engines (static, browser, axe-core, heuristic)
into a unified AuditIssue schema.
"""
import hashlib
import logging

from app.config import IMPACT_SUMMARIES, RULE_DOMAIN_MAP, get_wcag_relationship
from app.services.engine_manifest import get_engine_manifest

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
    "empty-link": ("2.4.4", "A"),
    "link-purpose": ("2.4.4", "A"),
    "no-headings": ("1.3.1", "A"),
    "missing-h1": ("1.3.1", "A"),
    "table-no-headers": ("1.3.1", "A"),
    "table-layout": ("1.3.1", "A"),
    "semantic-html": ("1.3.1", "A"),
    "no-main-landmark": ("1.3.1", "A"),
    "no-nav-landmark": ("1.3.1", "A"),
    "unlabeled-icon": ("1.1.1", "A"),
    "svg-no-accessible-name": ("1.1.1", "A"),
    "input-label": ("1.3.1", "A"),
    "placeholder-as-label": ("1.3.1", "A"),
    "missing-label": ("1.3.1", "A"),
    "line-height": ("1.4.12", "AA"),
    "avoid-inline-spacing": ("1.4.12", "AA"),
    "unsafe-external-link": ("2.4.4", "A"),
    "timeout-no-warning": ("2.2.1", "A"),
    "landmark-roles": ("1.3.1", "A"),
    "skip-link": ("2.4.1", "A"),
    "missing-skip-link": ("2.4.1", "A"),
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
    "empty-link": "navigation",
    "link-purpose": "navigation",
    "no-headings": "html",
    "missing-h1": "html",
    "table-no-headers": "html",
    "table-layout": "html",
    "semantic-html": "html",
    "no-main-landmark": "navigation",
    "no-nav-landmark": "navigation",
    "unlabeled-icon": "images",
    "svg-no-accessible-name": "images",
    "input-label": "forms",
    "placeholder-as-label": "forms",
    "missing-label": "forms",
    "line-height": "color",
    "avoid-inline-spacing": "color",
    "unsafe-external-link": "navigation",
    "timeout-no-warning": "navigation",
    "landmark-roles": "navigation",
    "skip-link": "navigation",
    "missing-skip-link": "navigation",
}

# ── IBM Equal Access rule → WCAG mapping ──────────────────────

IBM_WCAG_MAP = {
    "WCAG20_Img_HasAlt": ("1.1.1", "A"),
    "WCAG20_Img_Button_HasAlt": ("1.1.1", "A"),
    "WCAG20_Html_HasLang": ("3.1.1", "A"),
    "WCAG20_Form_LabelExists": ("1.3.1", "A"),
    "WCAG20_A_HasName": ("2.4.4", "A"),
    "WCAG20_Button_HasName": ("4.1.2", "A"),
    "WCAG20_Text_Contrast": ("1.4.3", "AA"),
    "WCAG21_NameRoleValue": ("4.1.2", "A"),
}


def _infer_ibm_wcag(rule_id: str) -> tuple[str, str]:
    mapped = IBM_WCAG_MAP.get(rule_id)
    if mapped:
        return mapped

    lowered = str(rule_id or "").lower()
    if "img" in lowered and "alt" in lowered:
        return ("1.1.1", "A")
    if "contrast" in lowered:
        return ("1.4.3", "AA")
    if "lang" in lowered:
        return ("3.1.1", "A")
    if "label" in lowered or "form" in lowered:
        return ("1.3.1", "A")
    if "button" in lowered or "name" in lowered or "role" in lowered:
        return ("4.1.2", "A")
    if "link" in lowered or "anchor" in lowered:
        return ("2.4.4", "A")
    return ("", "")


def _infer_ibm_category(sc_id: str) -> str:
    if sc_id.startswith("1.1"):
        return "images"
    if sc_id.startswith("1.4"):
        return "color"
    if sc_id.startswith("1.3"):
        return "forms"
    if sc_id.startswith("2.4"):
        return "navigation"
    if sc_id.startswith("3.1"):
        return "html"
    if sc_id.startswith("4.1"):
        return "aria"
    return "general"


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


def _initial_scanner_confidence(rule_id: str, default_conf: float = 0.85) -> float:
    """Determine initial scanner engine confidence based on rule determinism vs context sensitivity."""
    if rule_id in {"image-alt", "input-image-alt", "button-name", "html-has-lang", "html-lang-valid", "document-title"}:
        return 0.92
    if rule_id in {"region", "landmark-one-main", "landmark-roles", "link-name", "bypass", "label"}:
        return 0.72
    return default_conf


def normalize_axe_results(axe_violations: list[dict], url: str) -> list[dict]:
    """
    Convert axe-core violation results into unified AuditIssue dicts.
    Groupable rules produce one representative issue with affected_count.
    """
    manifest = get_engine_manifest()
    axe_ver = manifest.get("scan_engine_versions", {}).get("axe", "4.11.1")
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
                "raw_rule_id": raw_rule_id,
                "source_engine": "axe-core",
                "engine_version": axe_ver,
                "is_grouped": True,
                "issue_type": "violation",
                "element": f"{affected} elements" if affected > 1 else selector,
                "selector": selector,
                "html": html_snippet,
                "html_snippet": html_snippet,
                "page_url": url,
                "severity": severity,
                "wcag_criterion": wcag_info[0],
                "wcag_level": wcag_info[1],
                "category": category,
                "confidence": _initial_scanner_confidence(rule_id, 0.88),
                "scanner_confidence": _initial_scanner_confidence(rule_id, 0.88),
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
                "raw_rule_id": raw_rule_id,
                "source_engine": "axe-core",
                "engine_version": axe_ver,
                "is_grouped": False,
                "issue_type": "violation",
                "element": selector,
                "selector": selector,
                "html": html_snippet,
                "html_snippet": html_snippet,
                "page_url": url,
                "severity": severity,
                "wcag_criterion": wcag_info[0],
                "wcag_level": wcag_info[1],
                "category": category,
                "confidence": _initial_scanner_confidence(rule_id, 0.88),
                "scanner_confidence": _initial_scanner_confidence(rule_id, 0.88),
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


def normalize_static_results(static_issues: list[dict], url: str = "") -> list[dict]:
    """
    Static check results are already in the unified format.
    Ensure domain, raw_rule_id, source_engine, selector/html, id, wcag_criterion, and category are populated.
    """
    manifest = get_engine_manifest()
    static_ver = manifest.get("scan_engine_versions", {}).get("beacon_static", "2.0.0")
    for issue in static_issues:
        raw_id = issue.get("raw_rule_id") or issue.get("rule_id", "")
        rule_id = _translate_rule_id(issue.get("rule_id", ""))
        issue["raw_rule_id"] = raw_id
        issue["rule_id"] = rule_id
        issue.setdefault("source_engine", "beacon_static")
        issue.setdefault("engine_version", static_ver)
        selector = str(issue.get("element", "") or issue.get("selector", "") or "")
        issue["selector"] = selector
        issue.setdefault("html", str(issue.get("html_snippet", "") or ""))

        # Ensure unique ID
        if not issue.get("issue_id") and not issue.get("id"):
            fid = _make_issue_id(url, selector, rule_id)
            issue["issue_id"] = fid
            issue["id"] = fid
            issue["finding_id"] = fid

        # Ensure WCAG mapping
        if not issue.get("wcag_criterion"):
            mapped_wcag = AXE_WCAG_MAP.get(rule_id) or AXE_WCAG_MAP.get(raw_id)
            if mapped_wcag:
                issue["wcag_criterion"] = mapped_wcag[0]
                issue["wcag_level"] = mapped_wcag[1]

        # Ensure Category mapping
        if not issue.get("category") or issue.get("category") == "general":
            mapped_cat = AXE_CATEGORY_MAP.get(rule_id) or AXE_CATEGORY_MAP.get(raw_id)
            if mapped_cat:
                issue["category"] = mapped_cat

        if not issue.get("domain"):
            issue["domain"] = RULE_DOMAIN_MAP.get(rule_id, "")
        if not isinstance(issue.get("evidence"), dict):
            issue["evidence"] = {}
    return static_issues


def normalize_heuristic_results(heuristic_issues: list[dict], url: str = "") -> list[dict]:
    """
    Heuristic results are already in unified format.
    Populate domain, raw_rule_id, source_engine, id, wcag_criterion, category, and ensure needs_manual_review is set.
    """
    manifest = get_engine_manifest()
    h_ver = manifest.get("scan_engine_versions", {}).get("beacon_heuristics", "2.0.0")
    for issue in heuristic_issues:
        raw_id = issue.get("raw_rule_id") or issue.get("rule_id", "")
        rule_id = _translate_rule_id(issue.get("rule_id", ""))
        issue["raw_rule_id"] = raw_id
        issue["rule_id"] = rule_id
        issue.setdefault("source_engine", "beacon_heuristics")
        issue.setdefault("engine_version", h_ver)
        selector = str(issue.get("element", "") or issue.get("selector", "") or "")
        issue["selector"] = selector
        issue.setdefault("html", str(issue.get("html_snippet", "") or ""))

        # Ensure unique ID
        if not issue.get("issue_id") and not issue.get("id"):
            fid = _make_issue_id(url, selector, rule_id)
            issue["issue_id"] = fid
            issue["id"] = fid
            issue["finding_id"] = fid

        # Ensure WCAG mapping
        if not issue.get("wcag_criterion"):
            mapped_wcag = AXE_WCAG_MAP.get(rule_id) or AXE_WCAG_MAP.get(raw_id)
            if mapped_wcag:
                issue["wcag_criterion"] = mapped_wcag[0]
                issue["wcag_level"] = mapped_wcag[1]

        # Ensure Category mapping
        if not issue.get("category") or issue.get("category") == "general":
            mapped_cat = AXE_CATEGORY_MAP.get(rule_id) or AXE_CATEGORY_MAP.get(raw_id)
            if mapped_cat:
                issue["category"] = mapped_cat

        if not issue.get("domain"):
            issue["domain"] = RULE_DOMAIN_MAP.get(rule_id, "")
        issue["needs_manual_review"] = True
        issue["issue_type"] = "needs-review"
        if not isinstance(issue.get("evidence"), dict):
            issue["evidence"] = {}
    return heuristic_issues


def normalize_browser_results(browser_issues: list[dict]) -> list[dict]:
    """
    Browser probe results are already in unified format.
    Populate domain, raw_rule_id, source_engine from rule_id mapping.
    """
    manifest = get_engine_manifest()
    b_ver = manifest.get("scan_engine_versions", {}).get("beacon_browser", "2.0.0")
    for issue in browser_issues:
        raw_id = issue.get("raw_rule_id") or issue.get("rule_id", "")
        issue["raw_rule_id"] = raw_id
        issue["rule_id"] = _translate_rule_id(issue.get("rule_id", ""))
        issue.setdefault("source_engine", "beacon_browser")
        issue.setdefault("engine_version", b_ver)
        issue.setdefault("selector", str(issue.get("element", "") or ""))
        issue.setdefault("html", str(issue.get("html_snippet", "") or ""))
        if not issue.get("domain"):
            issue["domain"] = RULE_DOMAIN_MAP.get(issue.get("rule_id", ""), "")
        if not isinstance(issue.get("evidence"), dict):
            issue["evidence"] = {}
    return browser_issues


def normalize_ibm_results(ibm_issues: list[dict], url: str) -> list[dict]:
    """Normalize IBM Equal Access findings into AuditIssue shape."""
    manifest = get_engine_manifest()
    ibm_ver = manifest.get("scan_engine_versions", {}).get("ibm", "3.1.60")
    normalized: list[dict] = []
    for issue in ibm_issues:
        raw_rule_id = str(issue.get("rule_id", "") or issue.get("id", "")).strip()
        if not raw_rule_id:
            continue

        rule_id = _translate_rule_id(raw_rule_id)
        selector = str(issue.get("selector", "") or issue.get("element", "")).strip()
        html_snippet = str(issue.get("html_snippet", "") or issue.get("html", "") or "")[:500]
        message = str(issue.get("message", "") or issue.get("description", "")).strip()
        severity = str(issue.get("severity", "moderate") or "moderate").lower().strip()
        if severity not in AXE_SEVERITY_MAP:
            severity = "moderate"

        wcag_criterion, wcag_level = _infer_ibm_wcag(raw_rule_id)
        category = _infer_ibm_category(wcag_criterion)

        normalized.append(
            {
                "issue_id": _make_issue_id(url, selector, rule_id),
                "rule_id": rule_id,
                "raw_rule_id": raw_rule_id,
                "source_engine": "ibm",
                "engine_version": ibm_ver,
                "is_grouped": False,
                "issue_type": "violation",
                "element": selector,
                "selector": selector,
                "html": html_snippet,
                "html_snippet": html_snippet,
                "page_url": url,
                "severity": severity,
                "wcag_criterion": wcag_criterion,
                "wcag_level": wcag_level,
                "category": category,
                "confidence": _initial_scanner_confidence(rule_id, 0.85),
                "scanner_confidence": _initial_scanner_confidence(rule_id, 0.85),
                "confidence_sources": ["ibm"],
                "needs_manual_review": False,
                "description": message,
                "suggested_fix": "",
                "code_fix": "",
                "fix_effort": "medium",
                "group_id": "",
                "domain": RULE_DOMAIN_MAP.get(rule_id, ""),
                "evidence": {
                    "ibm_rule_id": raw_rule_id,
                },
                "reproducibility": "",
            }
        )

    return normalized


def _apply_axe_ibm_corroboration(issues: list[dict]) -> None:
    """Boost confidence when axe-core and IBM report the same WCAG signal."""
    axe_indices: dict[tuple[str, str], list[int]] = {}
    ibm_indices: dict[tuple[str, str], list[int]] = {}

    for idx, issue in enumerate(issues):
        sources = issue.get("confidence_sources", [])
        if not isinstance(sources, list) or not sources:
            continue
        source_set = {str(s).strip().lower() for s in sources}

        selector = str(issue.get("element", "") or "").strip()
        wcag_or_rule = str(issue.get("wcag_criterion", "") or issue.get("rule_id", "")).strip()
        if not selector and not wcag_or_rule:
            continue

        key = (selector, wcag_or_rule)
        if "axe-core" in source_set:
            axe_indices.setdefault(key, []).append(idx)
        if "ibm" in source_set:
            ibm_indices.setdefault(key, []).append(idx)

    for key, axe_rows in axe_indices.items():
        ibm_rows = ibm_indices.get(key, [])
        if not ibm_rows:
            continue
        for row_idx in [*axe_rows, *ibm_rows]:
            issue = issues[row_idx]
            sources = issue.get("confidence_sources", [])
            if isinstance(sources, list):
                merged = sorted(set([*sources, "axe-core", "ibm"]))
                issue["confidence_sources"] = merged
            issue["confidence"] = max(0.85, float(issue.get("confidence", 0.0) or 0.0))
            evidence = issue.get("evidence")
            if not isinstance(evidence, dict):
                evidence = {}
            evidence["cross_engine_corroborated"] = True
            issue["evidence"] = evidence


def _enrich_wcag_and_impact(issue: dict) -> None:
    """Attach explicit WCAG relationship metadata and human impact summary to an issue."""
    rule_id = str(issue.get("rule_id", "") or "").strip()
    raw_id = str(issue.get("raw_rule_id", "") or "").strip()
    crit = str(issue.get("wcag_criterion", "") or "").strip()
    level = str(issue.get("wcag_level", "A") or "A").strip()
    
    wcag_rel = get_wcag_relationship(rule_id or raw_id, default_criterion=crit, default_level=level)
    issue["wcag_relationship"] = wcag_rel
    issue["conformance_type"] = wcag_rel.get("conformance_type", "normative")
    issue["wcag_display"] = wcag_rel.get("display", f"WCAG {crit}" if crit else "Best Practice")
    
    if not issue.get("impact_summary"):
        issue["impact_summary"] = IMPACT_SUMMARIES.get(rule_id, IMPACT_SUMMARIES.get(raw_id, IMPACT_SUMMARIES["_default"]))


def normalize_all(
    static_issues: list[dict],
    heuristic_issues: list[dict],
    browser_issues: list[dict],
    axe_issues: list[dict],
    url: str,
    ibm_issues: list[dict] | None = None,
) -> list[dict]:
    """
    Normalize and merge results from all engines into a single list.
    """
    all_issues = []

    all_issues.extend(normalize_static_results(static_issues, url))
    all_issues.extend(normalize_heuristic_results(heuristic_issues, url))
    all_issues.extend(normalize_browser_results(browser_issues))
    all_issues.extend(normalize_axe_results(axe_issues, url))
    all_issues.extend(normalize_ibm_results(ibm_issues or [], url))

    _apply_axe_ibm_corroboration(all_issues)

    # Attach WCAG relationships and rich impact summaries to all findings
    for issue in all_issues:
        _enrich_wcag_and_impact(issue)

    logger.info(
        f"Normalized {len(all_issues)} total issues: "
        f"{len(static_issues)} static, {len(heuristic_issues)} heuristic, "
        f"{len(browser_issues)} browser, {len(axe_issues)} axe-core, "
        f"{len(ibm_issues or [])} ibm"
    )

    return all_issues
