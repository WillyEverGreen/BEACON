"""
Report generator: produces markdown accessibility audit reports.
Executive summary → grouped findings → code fixes → evidence.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SEVERITY_EMOJI = {
    "critical": "🔴",
    "major": "🟠",
    "minor": "🟢",
}

DOMAIN_EMOJI = {
    "navigation": "🧭",
    "forms": "📝",
    "content": "📄",
    "media": "🎬",
    "structure": "🏗️",
    "cognitive": "🧠",
    "keyboard": "⌨️",
    "aria": "♿",
    "images": "🖼️",
    "color": "🎨",
    "html": "📋",
    "general": "📌",
}


def generate_markdown_report(
    url: str,
    scan_mode: str,
    score: float,
    issues: list[dict],
    groups: list[dict],
    severity_breakdown: dict[str, int] = None,
    prioritized_issues: list[dict] = None,
    recommendations: list[str] = None,
    score_breakdown: dict[str, float] = None,
    cognitive_scores: dict = None,
    scan_time: float = 0.0,
    engines_used: list[str] = None,
) -> str:
    """Generate a comprehensive markdown accessibility report."""
    lines = []

    # Title
    lines.append("# ♿ Accessibility Audit Report")
    lines.append("")
    lines.append(f"**URL:** {url}")
    lines.append(f"**Scan Mode:** {scan_mode.upper()}")
    lines.append(f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    if scan_time > 0:
        lines.append(f"**Scan Time:** {scan_time:.1f}s")
    if engines_used:
        lines.append(f"**Engines:** {', '.join(engines_used)}")
    lines.append("")

    # ── Executive Summary ──────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("## 📊 Executive Summary")
    lines.append("")

    # Score
    score_emoji = "🟢" if score >= 80 else "🟡" if score >= 60 else "🟠" if score >= 40 else "🔴"
    lines.append(f"### Accessibility Score: {score_emoji} **{score:.0f}/100**")
    lines.append("")

    if score_breakdown:
        lines.append("| Score Detail | Value |")
        lines.append("|-------------|-------|")
        lines.append(f"| Critical penalty | {score_breakdown.get('critical_penalty', 0):.2f} |")
        lines.append(f"| Major penalty | {score_breakdown.get('major_penalty', 0):.2f} |")
        lines.append(f"| Minor penalty | {score_breakdown.get('minor_penalty', 0):.2f} |")
        lines.append("")

    # Issue counts by severity
    severity_counts = {"critical": 0, "major": 0, "minor": 0}
    if severity_breakdown:
        severity_counts.update({k: int(v) for k, v in severity_breakdown.items() if k in severity_counts})
    else:
        for issue in issues:
            sev = issue.get("severity", "moderate")
            if sev == "critical":
                severity_counts["critical"] += 1
            elif sev in {"serious", "major"}:
                severity_counts["major"] += 1
            else:
                severity_counts["minor"] += 1

    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    for sev in ["critical", "major", "minor"]:
        count = severity_counts.get(sev, 0)
        emoji = SEVERITY_EMOJI.get(sev, "")
        lines.append(f"| {emoji} {sev.capitalize()} | {count} |")
    lines.append(f"| **Total** | **{len(issues)}** |")
    lines.append("")

    if prioritized_issues:
        lines.append("### 🔎 What to Fix First")
        lines.append("")
        for index, issue in enumerate(prioritized_issues[:5], start=1):
            lines.append(
                f"{index}. **{issue.get('issue_type', 'unknown')}** "
                f"({issue.get('severity', 'minor')}, score {float(issue.get('priority_score', 0.0)):.3f})"
            )
            why = issue.get("why_important") or issue.get("component")
            if why:
                lines.append(f"   - {why}")
            fix = issue.get("fix")
            if fix:
                lines.append(f"   - Fix: {fix}")
        lines.append("")

    # Cognitive scores
    if cognitive_scores:
        lines.append("### 🧠 Cognitive Accessibility")
        lines.append("")
        cog_score = cognitive_scores.get("overall_cognitive_score", 100)
        cog_emoji = "🟢" if cog_score >= 80 else "🟡" if cog_score >= 60 else "🟠" if cog_score >= 40 else "🔴"
        lines.append(f"**Cognitive Score:** {cog_emoji} {cog_score:.0f}/100")
        lines.append("")
        lines.append(f"- **Readability Grade:** {cognitive_scores.get('readability_grade', 'N/A')}")
        lines.append(f"- **Reading Ease:** {cognitive_scores.get('readability_ease', 'N/A')}/100")
        lines.append(f"- **Jargon Density:** {cognitive_scores.get('jargon_density', 0):.1f}%")
        lines.append(f"- **Navigation Complexity:** {cognitive_scores.get('nav_complexity', 'N/A')}")
        lines.append(f"- **Form Usability:** {cognitive_scores.get('form_usability', 'N/A')}")
        lines.append("")

    # ── Grouped Findings ───────────────────────────────────────
    if groups:
        lines.append("---")
        lines.append("")
        lines.append("## 🔍 Findings by Category")
        lines.append("")

        for group in groups:
            domain = group.get("domain", "general")
            family = group.get("rule_family", "")
            count = group.get("count", 0)
            worst = group.get("worst_severity", "minor")
            domain_emoji = DOMAIN_EMOJI.get(domain, "📌")
            sev_emoji = SEVERITY_EMOJI.get(worst, "")

            lines.append(f"### {domain_emoji} {domain.capitalize()} — {family} {sev_emoji}")
            lines.append(f"*{count} issue(s), worst: {worst}*")
            lines.append("")

            for issue in group.get("issues", []):
                sev = issue.get("severity", "moderate")
                se = SEVERITY_EMOJI.get(sev, "")
                lines.append(f"#### {se} {issue.get('rule_id', 'unknown')} ({sev})")
                lines.append("")

                if issue.get("description"):
                    lines.append(f"**Issue:** {issue['description']}")
                    lines.append("")

                if issue.get("wcag_criterion"):
                    wcag_level = issue.get("wcag_level", "")
                    lines.append(f"**WCAG:** {issue['wcag_criterion']} (Level {wcag_level})")
                    lines.append("")

                if issue.get("element"):
                    lines.append(f"**Element:** `{issue['element']}`")
                    lines.append("")

                if issue.get("html_snippet"):
                    lines.append("**HTML:**")
                    lines.append("```html")
                    lines.append(issue["html_snippet"][:300])
                    lines.append("```")
                    lines.append("")

                confidence = issue.get("confidence", 0)
                sources = issue.get("confidence_sources", [])
                lines.append(f"**Confidence:** {confidence:.0%} ({', '.join(sources)})")

                if issue.get("needs_manual_review"):
                    lines.append("⚠️ *Needs manual review*")
                lines.append("")

                if issue.get("suggested_fix"):
                    lines.append(f"**Fix:** {issue['suggested_fix']}")
                    lines.append("")

                if issue.get("code_fix"):
                    lines.append("**Code Fix:**")
                    lines.append("```html")
                    lines.append(issue["code_fix"][:500])
                    lines.append("```")
                    lines.append("")

                lines.append("---")
                lines.append("")

    # ── Summary Footer ─────────────────────────────────────────
    lines.append("## 📋 Recommendations")
    lines.append("")

    if recommendations:
        for recommendation in recommendations:
            lines.append(f"- {recommendation}")
        lines.append("")

    if severity_counts["critical"] > 0:
        lines.append(f"1. **Fix {severity_counts['critical']} critical issues immediately** — these prevent some users from accessing content")
    if severity_counts["major"] > 0:
        lines.append(f"2. **Address {severity_counts['major']} major issues** — these significantly impact accessibility")
    if severity_counts["minor"] > 0:
        lines.append(f"3. **Review {severity_counts['minor']} minor issues** — these affect user experience")

    needs_review = sum(1 for i in issues if i.get("needs_manual_review"))
    if needs_review > 0:
        lines.append(f"4. **Manually verify {needs_review} flagged items** — automated checks have lower confidence")
    lines.append("")

    lines.append("---")
    lines.append(f"*Report generated by Accessibility Intelligence Engine — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}*")

    return "\n".join(lines)
