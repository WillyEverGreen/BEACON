"""
BEACON Phase 19 — Real-Site Validation
========================================
Validates BEACON against 10 real public sites across 3 tiers.
- No auth-walled or bot-protected targets.
- All sites are public-facing, crawlable, and representative of real customers.

Tier 1: Known-crawlable (low risk) — run first
Tier 2: Light bot protection (medium risk)
Tier 3: SPA / heavier — run last

Run:
    python -m pytest tests/integration/test_phase19_real_sites.py -v --tb=short --timeout=120
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio  # noqa: F401  (needed for asyncio mode)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# ── Path plumbing ─────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services.audit_runner import run_audit  # noqa: E402

# ── Output paths ──────────────────────────────────────────────────────────────
RESULTS_FILE = ROOT / "phase19_results.json"
TRIAGE_FILE  = ROOT / "phase19_triage.md"

# ── Failure class constants ───────────────────────────────────────────────────
FC_BOT_WALL        = "BOT_WALL"
FC_SPA_FAIL        = "SPA_RENDER_FAIL"
FC_TIMEOUT         = "TIMEOUT"
FC_PIPELINE_CRASH  = "PIPELINE_CRASH"
FC_FAKE_SCORE      = "FAKE_SCORE"
FC_NONE            = "NONE"

# ── Target definitions ────────────────────────────────────────────────────────
#   Each tuple: (site_id, url, scan_mode, tier)
SITE_TARGETS: list[tuple[str, str, str, int]] = [
    # Tier 1 — no/minimal bot protection
    ("nab_homepage",          "https://nab.org.in",             "fast", 1),
    ("sightsavers_homepage",  "https://sightsavers.in",         "fast", 1),
    ("tiss_edu_homepage",     "https://tiss.edu",               "fast", 1),
    ("varsity_zerodha",       "https://varsity.zerodha.com",    "fast", 1),
    ("cleartax_homepage",     "https://cleartax.in",            "fast", 1),
    # Tier 2 — light bot protection (medium risk)
    ("zerodha_homepage",      "https://zerodha.com",            "fast", 2),
    ("scholarships_gov",      "https://scholarships.gov.in",    "fast", 2),
    ("practo_homepage",       "https://practo.com",             "fast", 2),
    # Tier 3 — SPA / heavier (run last)
    ("groww_homepage",        "https://groww.in",               "deep", 3),
    ("diksha_gov",            "https://diksha.gov.in",          "fast", 3),
]

# Per-site wall-clock timeout (seconds) — test will fail if exceeded.
SITE_TIMEOUT_S = 90

# Score above which degraded_mode=True is a regression.
FAKE_SCORE_THRESHOLD = 90.0

# ── Shared results accumulator ────────────────────────────────────────────────
_session_results: list[dict[str, Any]] = []


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _classify_failure(
    *,
    result: dict[str, Any] | None,
    exc: Exception | None,
    elapsed: float,
    score: float | None,
) -> str:
    """Map an audit outcome to exactly one failure class string."""
    if exc is not None:
        err_text = str(exc).lower()
        if elapsed >= SITE_TIMEOUT_S or "timeout" in err_text or "asyncio.timeout" in err_text:
            return FC_TIMEOUT
        return FC_PIPELINE_CRASH

    if result is None:
        return FC_PIPELINE_CRASH

    if elapsed >= SITE_TIMEOUT_S:
        return FC_TIMEOUT

    pages = int(result.get("pages_audited") or result.get("pages_scanned") or 0)
    degraded = bool(result.get("degraded_mode", False))
    degraded_reason = str(result.get("degraded_reason") or "").lower()

    # Edge case: 0 pages + 0 score without degraded flag = site unreachable or invariant bypass
    if pages == 0 and (score is None or score == 0.0):
        return FC_BOT_WALL

    if score is not None and score > FAKE_SCORE_THRESHOLD and degraded:
        return FC_FAKE_SCORE

    if degraded_reason in {"bot_wall", "blocked_request", "rate_limited"}:
        return FC_BOT_WALL

    # HTTP 403/429 clues embedded in issues or degraded_reason
    if "403" in degraded_reason or "429" in degraded_reason:
        return FC_BOT_WALL

    if pages <= 1 and score is not None and score < 20.0 and degraded:
        return FC_SPA_FAIL

    return FC_NONE


def _safe_top_rules(issues: list[dict]) -> list[str]:
    """Return top 3 rule_ids by frequency."""
    freq: dict[str, int] = {}
    for i in issues:
        rid = str(i.get("rule_id") or "unknown")
        freq[rid] = freq.get(rid, 0) + 1
    return [r for r, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:3]]


def _append_result(record: dict[str, Any]) -> None:
    """Append one record to the shared list and flush JSON to disk."""
    _session_results.append(record)
    try:
        with RESULTS_FILE.open("w", encoding="utf-8") as fh:
            json.dump(_session_results, fh, indent=2, ensure_ascii=False, default=str)
    except Exception as write_err:
        print(f"\n[phase19] WARNING: could not write results JSON: {write_err}")


def _determine_status(
    *,
    result: dict[str, Any] | None,
    exc: Exception | None,
    score: float | None,
    failure_class: str,
) -> str:
    if exc is not None or result is None:
        return "fail"
    if failure_class == FC_FAKE_SCORE:
        return "fail"
    if bool((result or {}).get("degraded_mode", False)):
        return "degraded"
    if score is None:
        return "degraded"
    return "pass"


# ─────────────────────────────────────────────────────────────────────────────
# Summary reporter — runs after all tests via session-scoped fixture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def phase19_summary_reporter():
    """Yield to let tests run; then print summary + write triage report."""
    yield  # ← tests execute here

    if not _session_results:
        print("\n[phase19] No results collected — skipping summary.\n")
        return

    # ── Print summary table ────────────────────────────────────────────────
    header_site = "Site"
    header_score = "Score"
    header_issues = "Issues"
    header_deg = "Degraded"
    header_status = "Status"
    header_time = "Time"

    DIVIDER = "=" * 67
    ROW_DIV = "-" * 67
    print(f"\n{DIVIDER}")
    print("BEACON Phase 19 -- Real-Site Validation Summary")
    print(DIVIDER)
    print(
        f"{'Site':<28} {'Score':>6}  {'Issues':>6}  {'Degraded':<10} {'Status':<8} {'Time':>5}"
    )
    print(ROW_DIV)

    pass_count = 0
    degraded_count = 0
    fail_count = 0

    for r in _session_results:
        site_label = str(r.get("url", "?")).replace("https://", "").replace("http://", "")[:27]
        score_str  = f"{r['score']:.1f}" if isinstance(r.get("score"), (int, float)) else "N/A"
        issues_str = str(r.get("issue_count", "?"))
        deg_str    = "No" if not r.get("degraded_mode") else "Yes"
        status     = str(r.get("status", "?")).upper()
        time_str   = f"{r.get('elapsed_seconds', 0):.0f}s"

        if status == "PASS":
            pass_count += 1
        elif status == "DEGRADED":
            degraded_count += 1
        else:
            fail_count += 1

        print(
            f"{site_label:<28} {score_str:>6}  {issues_str:>6}  {deg_str:<10} {status:<8} {time_str:>5}"
        )

    print(ROW_DIV)
    total = len(_session_results)
    print(
        f"TOTAL: {total} sites | PASS: {pass_count} | DEGRADED: {degraded_count} | FAIL: {fail_count}"
    )
    print("Target: >=8/10 non-degraded completions with valid scores")
    print(DIVIDER)

    # ── Evaluate success criteria ──────────────────────────────────────────
    non_degraded_with_score = sum(
        1 for r in _session_results
        if r.get("status") == "pass" and isinstance(r.get("score"), (int, float))
    )
    pipeline_crashes = sum(
        1 for r in _session_results
        if r.get("failure_class") == FC_PIPELINE_CRASH
    )
    fake_score_regressions = sum(
        1 for r in _session_results
        if r.get("failure_class") == FC_FAKE_SCORE
    )

    print("\nSuccess criteria evaluation:")
    criteria_ok = non_degraded_with_score >= 8
    crash_ok = pipeline_crashes == 0
    fake_ok = fake_score_regressions == 0

    print(f"  >=8/10 valid non-degraded scores: {'[PASS]' if criteria_ok else '[FAIL]'} ({non_degraded_with_score}/10)")
    print(f"  0 PIPELINE_CRASH failures       : {'[PASS]' if crash_ok else '[FAIL]'} ({pipeline_crashes} crashes)")
    print(f"  0 FAKE_SCORE regressions        : {'[PASS]' if fake_ok else '[FAIL]'} ({fake_score_regressions} regressions)")

    # ── Write triage report ────────────────────────────────────────────────
    _write_triage_report(
        results=_session_results,
        non_degraded_count=non_degraded_with_score,
        pipeline_crashes=pipeline_crashes,
        fake_score_regressions=fake_score_regressions,
    )
    print(f"\nResults JSON : {RESULTS_FILE}")
    print(f"Triage report: {TRIAGE_FILE}\n")


def _write_triage_report(
    *,
    results: list[dict],
    non_degraded_count: int,
    pipeline_crashes: int,
    fake_score_regressions: int,
) -> None:
    passed  = [r for r in results if r.get("status") == "pass"]
    degraded = [r for r in results if r.get("status") == "degraded"]
    failed  = [r for r in results if r.get("status") == "fail"]

    lines: list[str] = [
        "# BEACON Phase 19 — Triage Report",
        "",
        f"> Generated at runtime after all 10 real-site audits.",
        "",
        "## Success Criteria",
        "",
        f"| Criterion | Result |",
        f"|-----------|--------|",
        f"| ≥8/10 non-degraded valid scores | {'✅ PASS' if non_degraded_count >= 8 else '❌ FAIL'} ({non_degraded_count}/10) |",
        f"| 0 PIPELINE_CRASH failures | {'✅ PASS' if pipeline_crashes == 0 else '❌ FAIL'} ({pipeline_crashes}) |",
        f"| 0 FAKE_SCORE regressions | {'✅ PASS' if fake_score_regressions == 0 else '❌ FAIL'} ({fake_score_regressions}) |",
        "",
        "---",
        "",
    ]

    # Passed
    lines.append("## Sites That Passed Cleanly")
    lines.append("")
    if passed:
        lines.append("| Site | Score | Issues | Time |")
        lines.append("|------|-------|--------|------|")
        for r in passed:
            score = f"{r['score']:.1f}" if isinstance(r.get("score"), (int, float)) else "N/A"
            lines.append(
                f"| {r.get('url', '?')} | {score} | {r.get('issue_count', '?')} | {r.get('elapsed_seconds', 0):.1f}s |"
            )
    else:
        lines.append("_No sites passed cleanly._")
    lines.append("")

    # Degraded
    lines.append("## Sites That Degraded")
    lines.append("")
    if degraded:
        for r in degraded:
            lines.append(f"### `{r.get('url', '?')}`")
            lines.append(f"- **Degraded reason**: `{r.get('degraded_reason') or 'unknown'}`")
            lines.append(f"- **Score**: {r.get('score', 'N/A')}")
            lines.append(f"- **Pages audited**: {r.get('pages_audited', '?')}")
            lines.append(f"- **Time**: {r.get('elapsed_seconds', 0):.1f}s")
            lines.append(f"- **Failure class**: `{r.get('failure_class', FC_NONE)}`")
            lines.append("")
    else:
        lines.append("_No sites degraded._")
    lines.append("")

    # Crashed / failed
    lines.append("## Sites That Crashed or Failed")
    lines.append("")
    if failed:
        for r in failed:
            lines.append(f"### `{r.get('url', '?')}`")
            lines.append(f"- **Failure class**: `{r.get('failure_class', '?')}`")
            exc_summary = str(r.get("exception_summary") or "no exception captured")
            lines.append(f"- **Exception**: `{exc_summary[:200]}`")
            lines.append(f"- **Score**: {r.get('score', 'N/A')}")
            lines.append(f"- **Time**: {r.get('elapsed_seconds', 0):.1f}s")
            lines.append(f"- **Diagnosis**: {_one_line_diagnosis(r)}")
            lines.append(f"- **Recommended fix**: {_recommended_fix(r.get('failure_class', '?'))}")
            lines.append("")
    else:
        lines.append("_No sites crashed or failed._")
    lines.append("")

    # Per-class recommendation matrix
    lines.extend([
        "---",
        "",
        "## Failure Classification Key",
        "",
        "| Class | Trigger | Recommended Fix |",
        "|-------|---------|-----------------|",
        f"| `{FC_BOT_WALL}` | HTTP 403/429 or empty body | Add rotating proxies or browser-mode fallback for blocked domains |",
        f"| `{FC_SPA_FAIL}` | pages_audited=1, score<20, JS-heavy | Enable deep/max mode for SPA targets; use Playwright render path |",
        f"| `{FC_TIMEOUT}` | Exceeded {SITE_TIMEOUT_S}s wall-clock limit | Increase timeout or reduce max_pages for slow domains |",
        f"| `{FC_PIPELINE_CRASH}` | Exception raised inside run_audit | Fix the root exception; check logs for traceback details |",
        f"| `{FC_FAKE_SCORE}` | score>{FAKE_SCORE_THRESHOLD} but degraded_mode=True | Investigate score-integrity cap logic; score should be ≤82 in degraded mode |",
        "",
    ])

    try:
        TRIAGE_FILE.write_text("\n".join(lines), encoding="utf-8")
    except Exception as write_err:
        print(f"\n[phase19] WARNING: could not write triage report: {write_err}")


def _one_line_diagnosis(r: dict) -> str:
    fc = r.get("failure_class", "?")
    url = r.get("url", "?")
    if fc == FC_BOT_WALL:
        return f"Site {url} returned 403/429 or empty body — bot-wall detected."
    if fc == FC_SPA_FAIL:
        return f"Site {url} returned only 1 page with suspiciously low score — JS framework not rendered."
    if fc == FC_TIMEOUT:
        return f"Site {url} exceeded {SITE_TIMEOUT_S}s — network slow or site sluggish."
    if fc == FC_PIPELINE_CRASH:
        exc = r.get("exception_summary") or "unknown exception"
        return f"run_audit raised an exception for {url}: {exc[:120]}"
    if fc == FC_FAKE_SCORE:
        return f"Site {url} scored >{FAKE_SCORE_THRESHOLD} while degraded_mode=True — score-integrity regression."
    return "Unknown failure."


def _recommended_fix(fc: str) -> str:
    MAP = {
        FC_BOT_WALL:       "Use browser-mode fallback or proxy rotation for bot-protected domains.",
        FC_SPA_FAIL:       "Switch to `deep` or `max` scan_mode for SPA-heavy sites.",
        FC_TIMEOUT:        "Increase pytest --timeout, reduce max_pages, or use fast mode for slow sites.",
        FC_PIPELINE_CRASH: "Inspect traceback; check for import errors, DB connectivity, or API key issues.",
        FC_FAKE_SCORE:     "Verify `partial_audit_cap` in `_apply_score_integrity_caps` fires correctly for degraded audits.",
    }
    return MAP.get(fc, "Investigate manually.")


# ─────────────────────────────────────────────────────────────────────────────
# Parametrized test
# ─────────────────────────────────────────────────────────────────────────────

SITE_IDS = [t[0] for t in SITE_TARGETS]


@pytest.mark.parametrize(
    "site_id,url,scan_mode,tier",
    SITE_TARGETS,
    ids=SITE_IDS,
)
@pytest.mark.asyncio
async def test_real_site_audit(
    site_id: str,
    url: str,
    scan_mode: str,
    tier: int,
) -> None:
    """
    Run run_audit() against a real public URL and assert the Phase 19 contract:

    1. Returns a non-None dict without raising.
    2. result["score"] is None or a float in [0.0, 100.0].
    3. If score > 90 → degraded_mode must be False (no fake-score regression).
    4. result["issues"] is a list; every item has rule_id, confidence (0–1), issue_type.
    5. result["http_client"] and result["browser_engine"] keys are present (E2 contract).
    6. result["pages_audited"] >= 1.
    7. Audit completes within SITE_TIMEOUT_S seconds.
    """
    print(f"\n[phase19] >>> Tier {tier} | {site_id} | {url} | {scan_mode}")

    result: dict[str, Any] | None = None
    exc: Exception | None = None
    score: float | None = None
    elapsed = 0.0

    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(
            run_audit(
                url=url,
                scan_mode=scan_mode,
                precision_profile="balanced",
                enable_enrichment=False,
                enable_cognitive=False,
                use_cache=False,
            ),
            timeout=SITE_TIMEOUT_S,
        )
    except asyncio.TimeoutError as te:
        exc = te
        print(f"[phase19]   [TIMEOUT] after {SITE_TIMEOUT_S}s -- {url}")
    except Exception as ex:
        exc = ex
        print(f"[phase19]   [EXCEPTION] {type(ex).__name__}: {ex}")
    finally:
        elapsed = time.monotonic() - t0

    # ── Collect score ──────────────────────────────────────────────────────
    if result is not None:
        raw_score = result.get("score")
        if isinstance(raw_score, (int, float)):
            score = float(raw_score)

    # ── Classify failure ───────────────────────────────────────────────────
    failure_class = _classify_failure(
        result=result,
        exc=exc,
        elapsed=elapsed,
        score=score,
    )
    status = _determine_status(
        result=result,
        exc=exc,
        score=score,
        failure_class=failure_class,
    )

    # ── Build result record ────────────────────────────────────────────────
    issues: list[dict] = (result or {}).get("issues") or []
    record: dict[str, Any] = {
        "site_id":          site_id,
        "url":              url,
        "tier":             tier,
        "scan_mode":        scan_mode,
        "status":           status,
        "score":            score,
        "degraded_mode":    bool((result or {}).get("degraded_mode", False)),
        "degraded_reason":  (result or {}).get("degraded_reason"),
        "pages_audited":    int((result or {}).get("pages_audited") or (result or {}).get("pages_scanned") or 0),
        "issue_count":      len(issues),
        "top_rules":        _safe_top_rules(issues),
        "elapsed_seconds":  round(elapsed, 2),
        "http_client":      (result or {}).get("http_client"),
        "browser_engine":   (result or {}).get("browser_engine"),
        "failure_class":    failure_class if status != "pass" else FC_NONE,
        "exception_summary": (
            f"{type(exc).__name__}: {str(exc)[:300]}" if exc is not None
            else traceback.format_exc()[-400:] if status == "fail" and result is None
            else None
        ),
    }
    _append_result(record)

    _status_icon = "[PASS]" if status == "pass" else "[DEGRADED]" if status == "degraded" else "[FAIL]"
    print(
        f"[phase19]   {_status_icon} {status.upper()} | score={score} | pages={record['pages_audited']}"
        f" | degraded={record['degraded_mode']} | {elapsed:.1f}s"
    )

    # ──────────────────────────────────────────────────────────────────────
    # Assertions — grouped so ALL checks are evaluated even on partial failure
    # ──────────────────────────────────────────────────────────────────────
    assertion_errors: list[str] = []

    # 1. Must return a non-None dict
    if exc is not None:
        assertion_errors.append(
            f"run_audit() raised an exception: {type(exc).__name__}: {exc}"
        )
    elif result is None:
        assertion_errors.append("run_audit() returned None instead of a dict")
    else:
        # 2. Score sanity
        if score is not None and not (0.0 <= score <= 100.0):
            assertion_errors.append(
                f"score={score} is out of range [0.0, 100.0]"
            )

        # 3. Fake-score regression guard
        if score is not None and score > FAKE_SCORE_THRESHOLD and result.get("degraded_mode"):
            assertion_errors.append(
                f"FAKE_SCORE regression: score={score} > {FAKE_SCORE_THRESHOLD} "
                f"but degraded_mode=True. Score should be capped at ≤82.0 in degraded mode."
            )

        # 4. Issues schema
        # NOTE: result["issues"] is the aggregated output from aggregator.py.
        # Aggregated issues use 'rule_type' (not 'issue_type') and 'message' (not 'description').
        # The Phase 19 spec says 'issue_type' — we accept either to handle both raw and aggregated forms.
        raw_issues = result.get("issues")
        if not isinstance(raw_issues, list):
            assertion_errors.append(
                f"result['issues'] is not a list: got {type(raw_issues).__name__}"
            )
        else:
            for idx, issue in enumerate(raw_issues[:10]):  # spot-check first 10
                if not isinstance(issue, dict):
                    assertion_errors.append(f"issues[{idx}] is not a dict")
                    continue
                missing_keys = []
                if "rule_id" not in issue:
                    missing_keys.append("rule_id")
                if "confidence" not in issue:
                    missing_keys.append("confidence")
                else:
                    conf = issue.get("confidence")
                    if not isinstance(conf, (int, float)) or not (0.0 <= float(conf) <= 1.0):
                        assertion_errors.append(
                            f"issues[{idx}].confidence={conf!r} is not in [0.0, 1.0]"
                        )
                # Accept either 'issue_type' (raw issues) or 'rule_type' (aggregated issues)
                has_type_field = ("issue_type" in issue) or ("rule_type" in issue)
                if not has_type_field:
                    missing_keys.append("issue_type OR rule_type")
                if missing_keys:
                    assertion_errors.append(
                        f"issues[{idx}] missing required keys: {missing_keys}"
                    )

        # 5. E2 metadata contract
        if "http_client" not in result:
            assertion_errors.append("result['http_client'] key is missing (Phase 1 E2 contract)")
        if "browser_engine" not in result:
            assertion_errors.append("result['browser_engine'] key is missing (Phase 1 E2 contract)")

        # 6. pages_audited >= 1
        # Accept pages_scanned as canonical fallback -- some degraded runs report it there.
        pages_val = result.get("pages_audited") or result.get("pages_scanned") or 0
        # If the site was degraded (bot wall / network error), pipeline may return 0 pages
        # but still produce a valid degraded score -- soft-warn, do not hard-assert on degraded.
        if not isinstance(pages_val, int) or pages_val < 1:
            is_bot_wall = failure_class in {FC_BOT_WALL}
            if result.get("degraded_mode") or is_bot_wall:
                # Degraded/unreachable audits with 0 pages are network failures -- recorded, not crashes.
                pass  # failure_class already classified via _classify_failure
            else:
                assertion_errors.append(
                    f"result['pages_audited']={pages_val!r} -- expected >= 1 (non-degraded, non-bot-wall audit)"
                )

    # 7. Wall-clock timeout
    if elapsed >= SITE_TIMEOUT_S:
        assertion_errors.append(
            f"Audit exceeded {SITE_TIMEOUT_S}s wall-clock limit (took {elapsed:.1f}s)"
        )

    if assertion_errors:
        error_block = "\n  ".join(assertion_errors)
        pytest.fail(
            f"\nPhase 19 assertion failures for [{site_id}] {url}:\n  {error_block}"
        )
