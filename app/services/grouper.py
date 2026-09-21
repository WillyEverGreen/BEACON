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
        "alt": ["missing-alt", "empty-alt", "alt-quality", "alt-is-filename", "alt-too-long", "svg-no-accessible-name", "image-alt", "input-image-alt"],
        "heading": ["no-headings", "no-h1", "multiple-h1", "heading-skip", "empty-heading", "heading-order"],
        "label": ["missing-label", "vague-label", "label-clarity", "label", "form-field-multiple-labels"],
        "link": ["empty-link", "generic-link-text", "short-link-text", "unsafe-external-link", "link-no-underline", "link-name"],
        "button": ["button-no-name", "button-name", "vague-button-text", "clickable-no-role"],
        "aria": ["role-no-name", "aria-hidden-focusable", "no-aria-live", "aria-tree-no-name", "aria-roles", "aria-valid-attr", "aria-valid-attr-value"],
        "contrast": ["color-contrast", "color-contrast-enhanced", "small-font-size"],
        "keyboard": ["positive-tabindex", "keyboard-unreachable", "no-focus-style", "focus-trap", "tabindex"],
        "landmark": [
            "no-main-landmark", "no-nav-landmark", "no-header-landmark", "no-footer-landmark",
            "landmark-one-main", "landmark-roles", "region", "aria_content_in_landmark",
            "landmark-unique"
        ],
        "table": ["table-no-headers", "table-no-caption", "th-no-scope", "td-headers-attr", "th-has-data-cells"],
        "form": ["no-fieldset-legend", "missing-autocomplete", "error-not-linked"],
        "media": ["autoplay-media", "missing-captions", "missing-transcript", "video-caption"],
        "nav": ["missing-skip-link", "nav-complexity", "bypass"],
        "readability": ["readability", "jargon"],
        "cognitive": ["cta-clarity", "form-usability", "form-no-progress", "error-message-quality"],
    }

    for family, rules in families.items():
        if rule_id in rules:
            return family
    return rule_id  # Use rule_id itself as family if not mapped


def cluster_root_causes(issues: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Cluster multiple overlapping symptom detections into single primary root-cause findings.
    
    Transforms (for example):
      [region, aria_content_in_landmark, no-main-landmark, landmark-roles, landmark-one-main]
    into:
      1 Primary Finding: "Primary content is not clearly exposed through a main landmark" (WCAG 1.3.1)
      with secondary issues archived and cross-referenced.
      
    Returns:
        (primary_issues, secondary_clustered_issues)
    """
    if not issues:
        return [], []

    LANDMARK_CLUSTER_RULES = {
        "region", "aria_content_in_landmark", "no-main-landmark",
        "landmark-roles", "landmark-one-main", "landmark-unique"
    }

    BYPASS_CLUSTER_RULES = {
        "bypass", "missing-skip-link", "skip-main-exists"
    }

    landmark_group: list[dict] = []
    bypass_group: list[dict] = []
    other_issues: list[dict] = []

    for issue in issues:
        rid = str(issue.get("rule_id", "")).strip().lower()
        if rid in LANDMARK_CLUSTER_RULES:
            landmark_group.append(issue)
        elif rid in BYPASS_CLUSTER_RULES:
            bypass_group.append(issue)
        else:
            other_issues.append(issue)

    primary_issues: list[dict] = []
    secondary_issues: list[dict] = []

    # 1. Process Landmark Cluster
    if len(landmark_group) >= 2:
        # Pick the most prominent representative or create unified finding
        contributing_rids = sorted(list(set(str(i.get("rule_id", "")) for i in landmark_group)))
        primary = dict(landmark_group[0])
        gid = "structure:main-landmark"
        primary["group_id"] = gid
        primary["root_cause_id"] = gid
        primary["is_root_cause_primary"] = True
        primary["rule_id"] = "landmark-primary-content"
        primary["wcag_criterion"] = "1.3.1"
        primary["wcag_level"] = "A"
        primary["category"] = "html"
        primary["description"] = "Primary content is not clearly exposed through a main landmark."
        primary["suggested_fix"] = "Wrap primary page content in a single <main> landmark or element with role='main'."
        primary["contributing_rules"] = contributing_rids

        # Merge evidence & engines
        all_sources = set()
        for i in landmark_group:
            all_sources.update(i.get("confidence_sources", []))
        primary["confidence_sources"] = sorted(list(all_sources))
        primary["consensus_confidence"] = min(0.96, 0.75 + (0.05 * len(contributing_rids)))
        primary["confidence"] = max(primary.get("confidence", 0.85), primary["consensus_confidence"])

        existing_evidence = primary.get("evidence") if isinstance(primary.get("evidence"), dict) else {}
        primary["evidence"] = {
            **existing_evidence,
            "root_cause_cluster": True,
            "underlying_issue_count": 1,
            "contributing_checks_count": len(landmark_group),
            "contributing_rules": contributing_rids,
        }
        primary_issues.append(primary)

        # Mark secondaries
        for sec in landmark_group[1:]:
            sec_copy = dict(sec)
            sec_copy["group_id"] = gid
            sec_copy["root_cause_id"] = gid
            sec_copy["is_root_cause_primary"] = False
            secondary_issues.append(sec_copy)

    elif landmark_group:
        primary_issues.extend(landmark_group)

    # 2. Process Bypass Cluster
    if len(bypass_group) >= 2:
        contributing_rids = sorted(list(set(str(i.get("rule_id", "")) for i in bypass_group)))
        primary = dict(bypass_group[0])
        gid = "navigation:bypass-blocks"
        primary["group_id"] = gid
        primary["root_cause_id"] = gid
        primary["is_root_cause_primary"] = True
        primary["rule_id"] = "bypass-blocks"
        primary["wcag_criterion"] = "2.4.1"
        primary["wcag_level"] = "A"
        primary["category"] = "navigation"
        primary["description"] = "No mechanism provided to bypass repeated blocks of content."
        primary["suggested_fix"] = "Provide a skip link as the first focusable element, or structure main content with <main> and headings."
        primary["contributing_rules"] = contributing_rids

        existing_evidence = primary.get("evidence") if isinstance(primary.get("evidence"), dict) else {}
        primary["evidence"] = {
            **existing_evidence,
            "root_cause_cluster": True,
            "underlying_issue_count": 1,
            "contributing_checks_count": len(bypass_group),
            "contributing_rules": contributing_rids,
        }
        primary_issues.append(primary)

        for sec in bypass_group[1:]:
            sec_copy = dict(sec)
            sec_copy["group_id"] = gid
            sec_copy["root_cause_id"] = gid
            sec_copy["is_root_cause_primary"] = False
            secondary_issues.append(sec_copy)

    elif bypass_group:
        primary_issues.extend(bypass_group)

    primary_issues.extend(other_issues)
    return primary_issues, secondary_issues


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
