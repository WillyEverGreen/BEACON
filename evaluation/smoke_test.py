"""Quick smoke test for the Accessibility Intelligence Engine."""
import asyncio
import ssl
import httpx
from app.services.static_checks import StaticChecker
from app.services.heuristics import HeuristicAnalyzer
from app.services.normalizer import normalize_all
from app.services.dedup_engine import deduplicate
from app.services.confidence import apply_confidence_rules
from app.services.grouper import group_issues
from app.services.report import generate_markdown_report
from app.services.cognitive_checks import CognitiveAnalyzer


async def test():
    print("=" * 60)
    print("  Accessibility Intelligence Engine — Smoke Test")
    print("=" * 60)
    print()

    url = "https://example.com"

    # Fetch with SSL verification disabled for testing
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, verify=False) as client:
            response = await client.get(url)
            html = response.text
            print(f"Fetched {url} ({len(html)} chars)")
    except Exception as e:
        print(f"Fetch failed: {e}")
        # Use a minimal HTML page for testing
        html = """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
<h1>Welcome</h1>
<h3>Skipped heading</h3>
<img src="test.jpg">
<a href="#">Click here</a>
<a href="https://external.com" target="_blank">External</a>
<form><input type="text" name="email"></form>
<button></button>
<div onclick="alert()">Clickable div</div>
</body>
</html>"""
        url = "http://test.local"
        print(f"Using test HTML instead ({len(html)} chars)")

    print()

    # Run pipeline manually
    print("--- Static Checks ---")
    checker = StaticChecker(html, url)
    static = checker.run_all()
    print(f"  Found {len(static)} issues")

    print("--- Heuristic Checks ---")
    heuristic = HeuristicAnalyzer(html, url)
    heur = heuristic.run_all()
    print(f"  Found {len(heur)} issues")

    print("--- Normalize ---")
    all_issues = normalize_all(
        static_issues=static,
        heuristic_issues=heur,
        browser_issues=[],
        axe_issues=[],
        url=url,
        ibm_issues=[],
    )
    print(f"  Total: {len(all_issues)}")

    print("--- Dedup ---")
    deduped = deduplicate(all_issues)
    print(f"  After dedup: {len(deduped)}")

    print("--- Confidence ---")
    scored = apply_confidence_rules(deduped)
    print(f"  Scored: {len(scored)}")

    print("--- Cognitive ---")
    cog = CognitiveAnalyzer(html, url)
    cog_result = cog.run_all()
    cog_issues = cog_result.pop("issues", [])
    scored.extend(cog_issues)
    print(f"  Cognitive issues: {len(cog_issues)}")
    print(f"  Readability grade: {cog_result.get('readability_grade', 'N/A')}")
    print(f"  Cognitive score: {cog_result.get('overall_cognitive_score', 'N/A')}")

    print("--- Grouping ---")
    groups = group_issues(scored)
    print(f"  Groups: {len(groups)}")

    print()
    print("All Issues:")
    for i in scored:
        conf = i.get("confidence", 0)
        review = " REVIEW" if i.get("needs_manual_review") else ""
        sources = ",".join(i.get("confidence_sources", []))
        print(f"  [{i['severity']:>8}] {i['rule_id']:<30} conf={conf:.2f} [{sources}]{review}")

    print()
    print("Groups:")
    for g in groups:
        print(f"  [{g['worst_severity']:>8}] {g['domain']}:{g['rule_family']} ({g['count']} issues)")

    print()

    # Generate report
    report = generate_markdown_report(
        url=url, scan_mode="fast", score=75,
        issues=scored, groups=groups,
        cognitive_scores=cog_result,
        scan_time=1.5, engines_used=["static", "heuristic", "cognitive"]
    )
    print(f"Markdown Report: {len(report)} characters")
    print("--- Report Preview ---")
    print(report[:800])
    print("...")

    print()
    print("=" * 60)
    print("  SMOKE TEST PASSED" if len(scored) > 0 else "  WARNING: No issues found")
    print("=" * 60)


asyncio.run(test())
