"""
Validate detector robustness across common real-world site archetypes.

This script is deterministic (no network) and focuses on whether core
detectors behave correctly across:
- SPA shell pages (React/Next bootstrap DOM)
- dashboard-like layouts
- component-based HTML structures
- ARIA edge cases (unknown attrs, mixed/duplicate roles, partial usage)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath("."))

from app.services.heuristics import HeuristicAnalyzer
from app.services.static_checks import StaticChecker

ARCHETYPE_CASES = [
    {
        "id": "react_shell_bootstrap",
        "description": "React shell page with minimal hydrated content should not emit structural landmark noise.",
        "html": """
        <!doctype html>
        <html>
          <head><title>App Shell</title></head>
          <body>
            <div id="root"></div>
            <script src="/static/js/runtime.js"></script>
            <script src="/static/js/vendor.js"></script>
            <script src="/static/js/main.js"></script>
            <script>window.__BOOTSTRAP__ = true;</script>
          </body>
        </html>
        """,
        "expect_present": [],
        "expect_absent": ["no-main-landmark", "missing-landmark", "landmark-roles"],
    },
    {
        "id": "next_shell_bootstrap",
        "description": "Next.js shell page with __next root should avoid premature structural findings.",
        "html": """
        <!doctype html>
        <html>
          <head><title>Next Shell</title></head>
          <body>
            <div id="__next"></div>
            <script src="/_next/static/chunks/webpack.js"></script>
            <script src="/_next/static/chunks/framework.js"></script>
            <script src="/_next/static/chunks/main.js"></script>
            <script src="/_next/static/chunks/pages/_app.js"></script>
          </body>
        </html>
        """,
        "expect_present": [],
        "expect_absent": ["no-main-landmark", "missing-landmark", "landmark-roles"],
    },
    {
        "id": "dashboard_nav_without_main",
        "description": "Dashboard layout with nav but no main should trigger landmark failures.",
        "html": """
        <!doctype html>
        <html>
          <head><title>Dashboard</title></head>
          <body>
            <nav aria-label="primary navigation">
              <a href="/home">Home</a>
            </nav>
            <section>
              <h1>KPI Overview</h1>
              <div>Revenue and conversion metrics.</div>
            </section>
          </body>
        </html>
        """,
        "expect_present": ["no-main-landmark", "missing-landmark"],
        "expect_absent": [],
    },
    {
        "id": "component_main_surrogate",
        "description": "Component layout with div#main should be treated as main surrogate to avoid FP.",
        "html": """
        <!doctype html>
        <html>
          <head><title>Component App</title></head>
          <body>
            <nav aria-label="chapters">menu</nav>
            <div id="main">
              <h1>Primary Content</h1>
              <p>Rendered via components.</p>
            </div>
          </body>
        </html>
        """,
        "expect_present": [],
        "expect_absent": ["no-main-landmark", "missing-landmark"],
    },
    {
        "id": "aria_unknown_attribute",
        "description": "Unknown ARIA attribute should trigger attr allowlist violations.",
        "html": """
        <!doctype html>
        <html><body>
          <button aria-labl="Save">Save</button>
        </body></html>
        """,
        "expect_present": ["aria-valid-attr", "aria-allowed-attr"],
        "expect_absent": [],
    },
    {
        "id": "aria_mixed_role_tokens",
        "description": "Mixed valid/invalid role token list should trigger aria-roles checks.",
        "html": """
        <!doctype html>
        <html><body>
          <div role="button buton">Open</div>
        </body></html>
        """,
        "expect_present": ["aria-roles"],
        "expect_absent": [],
    },
    {
        "id": "aria_duplicate_role_tokens",
        "description": "Duplicate role tokens should be flagged.",
        "html": """
        <!doctype html>
        <html><body>
          <div role="button button">Duplicate role</div>
        </body></html>
        """,
        "expect_present": ["aria-roles"],
        "expect_absent": [],
    },
    {
        "id": "aria_partial_usage",
        "description": "aria-checked on non-supported role should trigger allowed-attr rule.",
        "html": """
        <!doctype html>
        <html><body>
          <div role="button" aria-checked="mixed">Toggle</div>
        </body></html>
        """,
        "expect_present": ["aria-allowed-attr"],
        "expect_absent": [],
    },
    {
        "id": "semantic_div_overuse",
        "description": "Container-heavy page without semantic regions should trigger semantic-html.",
        "html": """
        <!doctype html>
        <html lang="en">
          <body>
            <div>Top container</div>
            <div>Widget wrapper</div>
            <div>Stats panel</div>
            <div>Trend panel</div>
            <div>Revenue chart</div>
            <div>Conversion chart</div>
            <div>Retention chart</div>
            <div>Funnel chart</div>
            <div>Alerts and notices are shown here for monitoring and response handling.</div>
          </body>
        </html>
        """,
        "expect_present": ["semantic-html"],
        "expect_absent": [],
    },
    {
        "id": "svg_missing_name",
        "description": "Inline informative SVG without accessible name should be detected.",
        "html": """
        <!doctype html>
        <html><body>
          <svg role="img" width="32" height="32"><circle cx="16" cy="16" r="14" /></svg>
        </body></html>
        """,
        "expect_present": ["svg-no-accessible-name"],
        "expect_absent": [],
    },
]


def run_case(case: dict) -> dict:
    url = f"https://archetype.local/{case['id']}"
    static_checker = StaticChecker(case["html"], url)
    static_issues = static_checker.run_all()

    heuristic_checker = HeuristicAnalyzer(case["html"], url)
    heuristic_issues = heuristic_checker.run_all()

    rules = sorted({
        str(issue.get("rule_id") or "").strip()
        for issue in (static_issues + heuristic_issues)
        if str(issue.get("rule_id") or "").strip()
    })

    present_expected = sorted(set(case.get("expect_present", [])))
    absent_expected = sorted(set(case.get("expect_absent", [])))

    missing_expected = [rule for rule in present_expected if rule not in rules]
    unexpected_present = [rule for rule in absent_expected if rule in rules]

    passed = len(missing_expected) == 0 and len(unexpected_present) == 0
    return {
        "id": case["id"],
        "description": case["description"],
        "passed": passed,
        "detected_rules": rules,
        "expect_present": present_expected,
        "expect_absent": absent_expected,
        "missing_expected": missing_expected,
        "unexpected_present": unexpected_present,
        "static_issue_count": len(static_issues),
        "heuristic_issue_count": len(heuristic_issues),
    }


def main() -> int:
    results = [run_case(case) for case in ARCHETYPE_CASES]
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print("=== BEACON Site Archetype Validation ===")
    print(f"Cases: {total} | Passed: {passed} | Failed: {failed}")

    for row in results:
        icon = "PASS" if row["passed"] else "FAIL"
        print(f"[{icon}] {row['id']}")
        if not row["passed"]:
            print(f"  missing_expected: {row['missing_expected']}")
            print(f"  unexpected_present: {row['unexpected_present']}")

    output = {
        "summary": {
            "total_cases": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round((passed / total), 4) if total else 0.0,
        },
        "results": results,
    }
    out_path = Path("evaluation/site_archetype_validation_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Saved: {out_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
