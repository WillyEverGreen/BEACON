import asyncio
import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.services.audit_runner import run_audit

SITES = [
    # The Adversarial Set (A11y Gold Standards)
    ("https://apple.com", "Apple"),
    ("https://inclusive-components.design", "Inclusive Components"),
    ("https://www.a11yproject.com", "The A11Y Project"),
    ("https://webaim.org", "WebAIM"),
    ("https://dequeuniversity.com", "Deque University"),
]

async def diagnose(url: str, name: str):
    print(f"\n{'='*70}")
    print(f"  TESTING: {name} ({url})")
    print(f"{'='*70}")

    result = {}
    issues = []
    scan_time = 0
    start_time = time.time()
    try:
        result = await run_audit(url=url, scan_mode="fast", precision_profile="balanced")
        scan_time = time.time() - start_time
        issues = result.get("issues", [])
    except Exception as e:
        print(f"  ! ERROR during audit: {e}")

    print(f"  Score: {result.get('score', 0)}/100 | Total issues: {result.get('total_issues', 0)}")
    print(f"  Engines: {result.get('engines_used', [])}")
    print(f"  Scan Time: {scan_time:.2f}s")
    if result.get('degraded_mode'):
        print(f"  ! DEGRADED MODE TRIGGERED. Status: {result.get('degraded_mode')}")

    return {
        "name": name,
        "url": url,
        "score": result.get("score"),
        "total_issues": result.get("total_issues"),
        "scan_time_seconds": scan_time,
        "degraded_mode": result.get("degraded_mode", False),
        "issues": [
            {
                "rule_id": i.get("rule_id"),
                "severity": i.get("severity"),
                "confidence": i.get("confidence"),
                "confidence_tier": i.get("confidence_tier"),
                "needs_manual_review": i.get("needs_manual_review"),
                "element": i.get("element", "")[:200],
                "description": i.get("description", "")[:200],
            }
            for i in issues
        ]
    }

async def main():
    results = {}
    for url, name in SITES:
        print(f"Starting {name} at {url}...")
        try:
            res = await diagnose(url, name)
            results[name] = res
        except Exception as e:
            print(f"  Failed to diagnose {name}: {e}")

    with open("adversarial_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved adversarial_test_results.json")

if __name__ == "__main__":
    asyncio.run(main())
