"""
Issue Prioritization Layer — computes a fix-priority score for each issue.

Formula: priority = impact × frequency × visibility

- impact:     severity weight (critical=4, serious=3, moderate=2, minor=1)
- frequency:  how many elements are affected (capped to avoid spam domination)
- visibility: rule_type weight (hard/confirmed > visual > contextual/heuristic)

Output adds a `priority_score` field to each issue and returns a
`priority_ranking` list of (rule_id, score, summary) for the top-5 "fix first" list.

This is what makes BEACON usable, not just technically correct.
"""
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# ── Weights ───────────────────────────────────────────────────────────
SEVERITY_IMPACT: dict[str, float] = {
    "critical": 4.0,
    "serious":  3.0,
    "moderate": 2.0,
    "minor":    1.0,
}

RULE_TYPE_VISIBILITY: dict[str, float] = {
    "hard":       1.0,   # Deterministic, confirmed violations
    "visual":     0.8,   # Requires rendering — reliable but not 100% deterministic
    "contextual": 0.6,   # Interpretive — mark lower because subject to judgment
}

EFFORT_MULTIPLIER: dict[str, float] = {
    "low":    1.2,   # Easy to fix → boost as quick wins
    "medium": 1.0,
    "high":   0.6,   # Hard to fix → lower priority for moderate/minor ONLY
}

# Cap frequency contribution so a 200-node rule doesn't monopolise the list
MAX_FREQUENCY_CAP = 10.0

# Critical/serious issues are NEVER demoted by effort.
# Compliance buyers must fix these regardless of difficulty.
_EFFORT_EXEMPT_SEVERITIES = {"critical", "serious"}


def _calc_frequency(issue: dict) -> float:
    """
    How many elements are affected?
    Uses affected_count if available, else 1.
    Capped at MAX_FREQUENCY_CAP to prevent spammy rules from dominating.
    """
    count = issue.get("affected_count", 1) or 1
    return min(float(count), MAX_FREQUENCY_CAP)


def _calc_effort(issue: dict) -> float:
    """
    Effort multiplier with compliance guard:
    - Critical/Serious: effort is always ≥ 1.0 (never demoted, can still be boosted)
    - Moderate/Minor: full effort curve applies (low=1.2, medium=1.0, high=0.6)
    """
    severity = issue.get("severity", "minor")
    raw_effort = EFFORT_MULTIPLIER.get(issue.get("fix_effort", "medium"), 1.0)

    if severity in _EFFORT_EXEMPT_SEVERITIES:
        # Never penalise, but still reward quick wins
        return max(raw_effort, 1.0)
    return raw_effort


def prioritize_issues(issues: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Compute priority scores for all issues and return:
    1. The same issue list, each with a `priority_score` field added.
    2. A `priority_ranking` — top-5 rule groups to fix first, as a summary list.

    Args:
        issues: List of scored AccessibilityIssue dicts

    Returns:
        (scored_issues, priority_ranking)
    """
    if not issues:
        return [], []

    # ── Score each issue ──────────────────────────────────────────
    for issue in issues:
        severity    = issue.get("severity", "minor")
        rule_type   = issue.get("rule_type", "hard")
        confidence  = issue.get("confidence", 0.5)

        impact     = SEVERITY_IMPACT.get(severity, 1.0)
        frequency  = _calc_frequency(issue)
        visibility = RULE_TYPE_VISIBILITY.get(rule_type, 0.6)
        effort     = _calc_effort(issue)

        # Confidence acts as a multiplier: low-confidence issues score lower
        priority = round(impact * frequency * visibility * confidence * effort, 3)
        issue["priority_score"] = priority


    # ── Aggregate by rule_id for the "fix first" ranking ─────────
    rule_totals: dict[str, float] = defaultdict(float)
    rule_counts: dict[str, int]   = defaultdict(int)
    rule_meta: dict[str, dict]    = {}

    for issue in issues:
        rid = issue.get("rule_id", "unknown")
        rule_totals[rid] += issue["priority_score"]
        rule_counts[rid] += 1
        if rid not in rule_meta:
            rule_meta[rid] = {
                "rule_id":   rid,
                "severity":  issue.get("severity", "minor"),
                "domain":    issue.get("domain", "general"),
                "message":   issue.get("message", rid),
            }

    # ── Build top-5 ranking ───────────────────────────────────────
    ranked = sorted(rule_totals.items(), key=lambda x: x[1], reverse=True)[:5]

    priority_ranking = []
    for rank, (rid, total_score) in enumerate(ranked, start=1):
        meta = rule_meta[rid]
        priority_ranking.append({
            "rank":          rank,
            "rule_id":       rid,
            "total_score":   round(total_score, 2),
            "affected_count": rule_counts[rid],
            "severity":      meta["severity"],
            "domain":        meta["domain"],
            "message":       meta["message"],
            "fix_first_reason": _explain_priority(rank, meta, rule_counts[rid]),
        })

    logger.info(
        f"Prioritization: {len(issues)} issues → top fix: "
        f"{priority_ranking[0]['rule_id'] if priority_ranking else 'none'}"
    )

    return issues, priority_ranking


def _explain_priority(rank: int, meta: dict, count: int) -> str:
    """Generate a human-readable reason why this issue is ranked here."""
    severity = meta.get("severity", "moderate")
    rule_id  = meta.get("rule_id", "")
    domain   = meta.get("domain", "general")

    if rank == 1:
        return (
            f"Highest combined impact: {count} {severity} '{rule_id}' "
            f"issues in the {domain} domain block the most users."
        )
    return (
        f"#{rank} priority: {count} {severity} violations in '{rule_id}' "
        f"({domain}) — fixing these unlocks significant accessibility gains."
    )
