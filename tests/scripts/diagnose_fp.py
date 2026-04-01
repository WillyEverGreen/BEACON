"""
Deep diagnostic: inspect every issue found on GitHub and GOV.UK to verify
whether they are genuine violations or false positives.
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.audit_runner import run_audit


async def diagnose(url: str, name: str):
    print(f"\n{'='*70}")
    print(f"  DIAGNOSING: {name} ({url})")
    print(f"{'='*70}")

    result = await run_audit(url=url, scan_mode="fast", precision_profile="balanced")

    print(f"  Score: {result['score']}/100 | Total issues: {result['total_issues']}")
    print(f"  Engines: {result.get('engines_used', [])}")

    issues = result.get("issues", [])

    # Group by rule_id for analysis
    from collections import Counter, defaultdict
    rule_counts = Counter(i.get("rule_id", "?") for i in issues)
    rule_issues = defaultdict(list)
    for i in issues:
        rule_issues[i.get("rule_id", "?")].append(i)

    print(f"\n  Issues by rule_id:")
    for rule_id, count in rule_counts.most_common():
        print(f"    {rule_id}: {count}")

    print(f"\n  --- DETAILED ISSUE DUMP ---")
    for rule_id in sorted(rule_issues.keys()):
        group = rule_issues[rule_id]
        print(f"\n  [{rule_id}] ({len(group)} instance(s))")
        print(f"  Severity: {group[0].get('severity')} | Confidence: {group[0].get('confidence')} | Tier: {group[0].get('confidence_tier')}")
        print(f"  Reason: {group[0].get('confidence_reason', 'N/A')}")
        print(f"  Impact: {group[0].get('impact_summary', 'N/A')}")
        print(f"  Needs review: {group[0].get('needs_manual_review')}")

        for idx, iss in enumerate(group[:3]):  # Show max 3 instances per rule
            snippet = iss.get("html_snippet", "")[:150].replace("\n", " ")
            element = iss.get("element", "")[:100]
            desc = iss.get("description", "")[:120]
            print(f"    [{idx+1}] element: {element}")
            print(f"        snippet: {snippet}")
            print(f"        desc: {desc}")
        if len(group) > 3:
            print(f"    ... and {len(group) - 3} more")

    return issues


async def main():
    github_issues = await diagnose("https://github.com", "GitHub")
    govuk_issues = await diagnose("https://www.gov.uk", "GOV.UK")

    # Save raw for offline analysis
    output = {
        "github": [
            {
                "rule_id": i.get("rule_id"),
                "severity": i.get("severity"),
                "confidence": i.get("confidence"),
                "confidence_tier": i.get("confidence_tier"),
                "confidence_reason": i.get("confidence_reason"),
                "needs_manual_review": i.get("needs_manual_review"),
                "element": i.get("element", "")[:200],
                "html_snippet": i.get("html_snippet", "")[:300],
                "description": i.get("description", "")[:200],
                "impact_summary": i.get("impact_summary"),
            }
            for i in github_issues
        ],
        "govuk": [
            {
                "rule_id": i.get("rule_id"),
                "severity": i.get("severity"),
                "confidence": i.get("confidence"),
                "confidence_tier": i.get("confidence_tier"),
                "confidence_reason": i.get("confidence_reason"),
                "needs_manual_review": i.get("needs_manual_review"),
                "element": i.get("element", "")[:200],
                "html_snippet": i.get("html_snippet", "")[:300],
                "description": i.get("description", "")[:200],
                "impact_summary": i.get("impact_summary"),
            }
            for i in govuk_issues
        ],
    }
    with open("diagnostic_deep_dive.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(f"\n\nSaved diagnostic_deep_dive.json")


if __name__ == "__main__":
    asyncio.run(main())
