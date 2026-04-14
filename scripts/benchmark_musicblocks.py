"""
BEACON Max-Mode Scan — musicblocks.sugarlabs.org
Run: python -m scripts.benchmark_musicblocks
"""
import asyncio
import json
import os
import sys
import time

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

TARGET_URL = "https://musicblocks.sugarlabs.org"
SCAN_MODE  = "max"
MAX_PAGES  = 12


async def main() -> None:
    from app.audit.scan_mode_runner import run_scan_mode_audit
    from app.routers.dashboard_api import _normalize_site_scan_result

    print(f"\n{'='*60}")
    print(f"  BEACON Max-Mode Scan — {TARGET_URL}")
    print(f"{'='*60}\n")

    t0 = time.perf_counter()
    try:
        raw = await run_scan_mode_audit(
            seed_url=TARGET_URL,
            scan_mode=SCAN_MODE,
            max_pages=MAX_PAGES,
        )
    except Exception as exc:
        print(f"[ERROR] Scan failed: {exc}")
        raise

    elapsed = time.perf_counter() - t0

    # Normalize through the same pipeline the dashboard uses
    result = _normalize_site_scan_result(raw, SCAN_MODE, elapsed)

    # ── Summary ──────────────────────────────────────────────
    score           = result.get("score", 0)
    total_issues    = result.get("total_issues", 0)
    issue_types     = result.get("issue_types_count", 0)
    failing_els     = result.get("failing_elements_count", 0)
    pages_scanned   = result.get("pages_scanned", 1)
    pages_disc      = result.get("pages_discovered", 1)
    engines         = result.get("engines_used", [])
    degraded        = result.get("degraded_mode", False)
    trust           = result.get("trust", {})
    issues_list     = result.get("issues", [])

    print(f"  Score           : {score}/100")
    print(f"  Failing elements: {failing_els}")
    print(f"  Issue types     : {issue_types}")
    print(f"  Total issues    : {total_issues}")
    print(f"  Pages scanned   : {pages_scanned}  (discovered: {pages_disc})")
    print(f"  Scan time       : {elapsed:.1f}s")
    print(f"  Engines used    : {', '.join(engines)}")
    print(f"  Degraded mode   : {degraded}")

    warnings = trust.get("calibration_warnings", [])
    if warnings:
        print(f"  Trust warnings  : {', '.join(warnings)}")

    # ── Issue breakdown ───────────────────────────────────────
    if issues_list:
        print(f"\n  Issues found ({len(issues_list)}):\n")
        by_severity: dict[str, list] = {}
        for issue in issues_list:
            sev = str(issue.get("severity") or "unknown")
            by_severity.setdefault(sev, []).append(issue)

        for sev in ("critical", "serious", "moderate", "minor", "unknown"):
            bucket = by_severity.get(sev, [])
            if not bucket:
                continue
            print(f"  [{sev.upper()}] ({len(bucket)} issues)")
            for iss in bucket:
                rule  = iss.get("rule_id") or iss.get("issue_type") or "?"
                wcag  = iss.get("wcag_criterion") or ""
                desc  = (iss.get("description") or "")[:80]
                conf  = iss.get("confidence", 0)
                print(f"    • {rule:<40} wcag={wcag:<8} conf={conf:.0%}  {desc}")
        print()
    else:
        print("\n  ✅  No issues found by BEACON engines.\n")

    # Dump raw issues as JSON for further analysis
    out_path = os.path.join(os.path.dirname(__file__), "musicblocks_scan_result.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(
            {
                "url": TARGET_URL,
                "scan_mode": SCAN_MODE,
                "score": score,
                "issues": issues_list,
                "pages_scanned": pages_scanned,
                "pages_discovered": pages_disc,
                "engines_used": engines,
                "trust": trust,
                "elapsed_s": round(elapsed, 2),
            },
            fh,
            indent=2,
            default=str,
        )
    print(f"  Full result saved → {out_path}\n")


if __name__ == "__main__":
    asyncio.run(main())
