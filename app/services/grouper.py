"""
Issue grouper: organizes issues by domain and rule family, ranks by severity.
"""
import logging
from collections import defaultdict

from app.config import RULE_DOMAIN_MAP

logger = logging.getLogger(__name__)

SEVERITY_RANK = {"critical": 4, "serious": 3, "moderate": 2, "minor": 1}


def _get_rule_family(rule_id: str) -> str:
    """Extract rule family from rule_id (e.g., 'missing-alt' → 'alt')."""
    families = {
        "alt": ["missing-alt", "empty-alt", "alt-quality", "alt-is-filename", "alt-too-long", "svg-no-accessible-name"],
        "heading": ["no-headings", "no-h1", "multiple-h1", "heading-skip", "empty-heading"],
        "label": ["missing-label", "vague-label", "label-clarity"],
        "link": ["empty-link", "generic-link-text", "short-link-text", "unsafe-external-link", "link-no-underline"],
        "button": ["button-no-name", "vague-button-text", "clickable-no-role"],
        "aria": ["role-no-name", "aria-hidden-focusable", "no-aria-live", "aria-tree-no-name"],
        "contrast": ["color-contrast", "color-contrast-enhanced", "small-font-size"],
        "keyboard": ["positive-tabindex", "keyboard-unreachable", "no-focus-style", "focus-trap"],
        "landmark": ["no-main-landmark", "no-nav-landmark", "no-header-landmark", "no-footer-landmark"],
        "table": ["table-no-headers", "table-no-caption", "th-no-scope"],
        "form": ["no-fieldset-legend", "missing-autocomplete", "error-not-linked"],
        "media": ["autoplay-media", "missing-captions", "missing-transcript"],
        "nav": ["missing-skip-link", "nav-complexity"],
        "readability": ["readability", "jargon"],
        "cognitive": ["cta-clarity", "form-usability", "form-no-progress", "error-message-quality"],
    }

    for family, rules in families.items():
        if rule_id in rules:
            return family
    return rule_id  # Use rule_id itself as family if not mapped


def _worst_severity(issues: list[dict]) -> str:
    """Get the worst severity from a list of issues."""
    worst = "minor"
    worst_rank = 0
    for issue in issues:
        sev = issue.get("severity", "minor")
        rank = SEVERITY_RANK.get(sev, 0)
        if rank > worst_rank:
            worst = sev
            worst_rank = rank
    return worst


def group_issues(issues: list[dict]) -> list[dict]:
    """
    Group issues by domain and rule family, rank by severity.
    
    Returns list of IssueGroup dicts:
    [{
        "group_id": "navigation:link",
        "domain": "navigation",
        "rule_family": "link",
        "issues": [...],
        "count": N,
        "worst_severity": "critical"
    }]
    """
    if not issues:
        return []

    # Assign domain to each issue if not set
    for issue in issues:
        if not issue.get("domain"):
            issue["domain"] = RULE_DOMAIN_MAP.get(issue.get("rule_id", ""), "general")

    # Group by domain → rule_family
    domain_groups = defaultdict(lambda: defaultdict(list))
    for issue in issues:
        domain = issue.get("domain", "general")
        rule_family = _get_rule_family(issue.get("rule_id", ""))
        domain_groups[domain][rule_family].append(issue)

    # Build group objects
    groups = []
    for domain, families in domain_groups.items():
        for family, family_issues in families.items():
            group_id = f"{domain}:{family}"

            # Set group_id on each issue
            for issue in family_issues:
                issue["group_id"] = group_id

            # Sort issues within group by severity (worst first)
            family_issues.sort(
                key=lambda x: SEVERITY_RANK.get(x.get("severity", "minor"), 0),
                reverse=True
            )

            groups.append({
                "group_id": group_id,
                "domain": domain,
                "rule_family": family,
                "issues": family_issues,
                "count": len(family_issues),
                "worst_severity": _worst_severity(family_issues),
            })

    # Sort groups by worst severity, then by count
    groups.sort(
        key=lambda g: (SEVERITY_RANK.get(g["worst_severity"], 0), g["count"]),
        reverse=True
    )

    logger.info(
        f"Grouped {len(issues)} issues into {len(groups)} groups "
        f"across {len(domain_groups)} domains"
    )

    return groups
