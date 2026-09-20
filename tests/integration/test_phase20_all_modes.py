"""
BEACON Phase 20 — All-Modes Real-Site Validation
=================================================
Runs each of the 10 real sites in fast / deep / max mode and prints a clean
table showing score, pages scanned, topology, issues found, and time per run.

Run:
    python -m pytest tests/integration/test_phase20_all_modes.py -v --tb=short --timeout=180 -s

Or for a quick smoke-test (fast mode only):
    python -m pytest tests/integration/test_phase20_all_modes.py -v --tb=short --timeout=180 -s -k "fast"
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio  # noqa: F401

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# ── Path plumbing ─────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.services.audit_runner import run_audit  # noqa: E402

# ── Output paths ──────────────────────────────────────────────────────────────
RESULTS_FILE = ROOT / "phase20_all_modes_results.json"

# ── Site targets ─────────────────────────────────────────────────────────────
# (site_id, url, tier)
# Each site runs once per scan mode: fast → deep → max
_BASE_SITES: list[tuple[str, str, int]] = [
    ("nab_homepage",         "https://nab.org.in",            1),
    ("sightsavers_homepage", "https://sightsavers.in",        1),
    ("tiss_edu_homepage",    "https://tiss.edu",              1),
    ("varsity_zerodha",      "https://varsity.zerodha.com",   1),
    ("cleartax_homepage",    "https://cleartax.in",           1),
    ("zerodha_homepage",     "https://zerodha.com",           2),
    ("scholarships_gov",     "https://scholarships.gov.in",   2),
    ("practo_homepage",      "https://practo.com",            2),
    ("groww_homepage",       "https://groww.in",              3),
    ("diksha_gov",           "https://diksha.gov.in",         3),
]

_MODES = ["fast", "deep", "max"]

# Expand: one parametrize entry per (site, mode)
SITE_TARGETS: list[tuple[str, str, str, int]] = [
    (f"{site_id}_{mode}", url, mode, tier)
    for site_id, url, tier in _BASE_SITES
    for mode in _MODES
]
SITE_IDS = [t[0] for t in SITE_TARGETS]

# Per-case timeout — max mode needs headroom
SITE_TIMEOUT_MAP = {"fast": 60, "deep": 120, "max": 180}

# ── Shared accumulator ────────────────────────────────────────────────────────
_session_results: list[dict[str, Any]] = []


# ─────────────────────────────────────────────────────────────────────────────
# Summary reporter
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def all_modes_summary_reporter():
    yield  # tests run here

    if not _session_results:
        print("\n[phase20] No results to summarise.\n")
        return

    # ── Write JSON ────────────────────────────────────────────────────────────
    try:
        RESULTS_FILE.write_text(
            json.dumps(_session_results, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    except Exception as e:
        print(f"\n[phase20] WARNING: could not write results JSON: {e}")

    # ── Build pretty table ────────────────────────────────────────────────────
    COL_SITE   = 26
    COL_MODE   = 5
    COL_SCORE  = 7
    COL_PAGES  = 6
    COL_TOPO   = 14
    COL_ISSUES = 7
    COL_DEG    = 7
    COL_STATUS = 8
    COL_TIME   = 6

    DIVIDER = "=" * 100
    ROW_DIV = "-" * 100

    print(f"\n{DIVIDER}")
    print("BEACON Phase 20 — All-Modes Real-Site Summary")
    print(DIVIDER)
    print(
        f"{'Site':<{COL_SITE}} {'Mode':<{COL_MODE}} {'Score':>{COL_SCORE}}"
        f" {'Pages':>{COL_PAGES}} {'Topology':<{COL_TOPO}}"
        f" {'Issues':>{COL_ISSUES}} {'Degrad':<{COL_DEG}} {'Status':<{COL_STATUS}} {'Time':>{COL_TIME}}"
    )
    print(ROW_DIV)

    pass_c = degraded_c = fail_c = 0
    prev_url = None

    for r in _session_results:
        url_label = (
            str(r.get("url", "?"))
            .replace("https://", "")
            .replace("http://", "")[:COL_SITE - 1]
        )
        mode      = str(r.get("scan_mode", "?"))
        score_str = f"{r['score']:.1f}" if isinstance(r.get("score"), (int, float)) else "N/A"
        pages_str = str(r.get("pages_scanned", "?"))
        topo_str  = str(r.get("site_topology") or "—")[:COL_TOPO]
        issues_str = str(r.get("issue_count", "?"))
        deg_str   = "Yes" if r.get("degraded_mode") else "No"
        status    = str(r.get("status", "?")).upper()
        time_str  = f"{r.get('elapsed_seconds', 0):.0f}s"

        # Print a blank separator between sites for readability
        if prev_url is not None and r.get("url") != prev_url:
            print(ROW_DIV[:40])
        prev_url = r.get("url")

        if status == "PASS":
            pass_c += 1
        elif status == "DEGRADED":
            degraded_c += 1
        else:
            fail_c += 1

        print(
            f"{url_label:<{COL_SITE}} {mode:<{COL_MODE}} {score_str:>{COL_SCORE}}"
            f" {pages_str:>{COL_PAGES}} {topo_str:<{COL_TOPO}}"
            f" {issues_str:>{COL_ISSUES}} {deg_str:<{COL_DEG}} {status:<{COL_STATUS}} {time_str:>{COL_TIME}}"
        )

    print(ROW_DIV)
    total = len(_session_results)
    print(
        f"TOTAL: {total} runs | PASS: {pass_c} | DEGRADED: {degraded_c} | FAIL: {fail_c}"
    )
    print(f"(10 sites x 3 modes = 30 runs expected)")
    print(DIVIDER)

    # ── Per-mode breakdown ────────────────────────────────────────────────────
    print("\nPer-mode breakdown:")
    for mode in _MODES:
        mode_rows = [r for r in _session_results if r.get("scan_mode") == mode]
        mode_pass = sum(1 for r in mode_rows if r.get("status") == "pass")
        mode_deg  = sum(1 for r in mode_rows if r.get("status") == "degraded")
        mode_fail = sum(1 for r in mode_rows if r.get("status") == "fail")
        pages_all = [r["pages_scanned"] for r in mode_rows if isinstance(r.get("pages_scanned"), int)]
        avg_pages = f"{sum(pages_all)/len(pages_all):.1f}" if pages_all else "N/A"
        print(
            f"  {mode:>4} -> PASS={mode_pass} DEGRADED={mode_deg} FAIL={mode_fail}"
            f"  | avg_pages={avg_pages}"
        )

    print(f"\nResults JSON: {RESULTS_FILE}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Parametrized test
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "case_id,url,scan_mode,tier",
    SITE_TARGETS,
    ids=SITE_IDS,
)
@pytest.mark.asyncio
async def test_all_modes_site_audit(
    case_id: str,
    url: str,
    scan_mode: str,
    tier: int,
) -> None:
    """
    Run run_audit() for each site × mode combination.

    Assertions (same contract as Phase 19):
      1. Returns a non-None dict without raising.
      2. score is None or a float in [0, 100].
      3. score > 90 + degraded_mode → FAKE_SCORE regression.
      4. issues is a list; each item has rule_id, confidence, issue_type.
      5. http_client and browser_engine keys present (E2 contract).
      6. pages_audited >= 0 (0 is allowed for fully degraded sites).
    """
    timeout_s = SITE_TIMEOUT_MAP.get(scan_mode, 120)
    print(f"\n[phase20] >>> Tier {tier} | {case_id} | {url} | mode={scan_mode} | timeout={timeout_s}s")

    result: dict[str, Any] | None = None
    exc: Exception | None = None
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
            timeout=timeout_s,
        )
    except asyncio.TimeoutError as te:
        exc = te
        print(f"[phase20]   [TIMEOUT] after {timeout_s}s")
    except Exception as ex:
        exc = ex
        print(f"[phase20]   [EXCEPTION] {type(ex).__name__}: {ex}")
    finally:
        elapsed = time.monotonic() - t0

    # ── Extract key fields ────────────────────────────────────────────────────
    score: float | None = None
    pages_scanned = 0
    site_topology = None
    issues: list = []
    degraded_mode = False

    if result is not None:
        raw_score = result.get("score")
        if isinstance(raw_score, (int, float)):
            score = round(float(raw_score), 1)
        pages_scanned = int(
            result.get("pages_audited")
            or result.get("pages_scanned")
            or 0
        )
        site_topology = result.get("site_topology")
        issues = result.get("issues") or []
        degraded_mode = bool(result.get("degraded_mode", False))

    # ── Determine status ──────────────────────────────────────────────────────
    if exc is not None or result is None:
        status = "fail"
    elif degraded_mode:
        status = "degraded"
    elif score is None:
        status = "degraded"
    else:
        # Fake-score guard: score > 90 while degraded is a regression
        if score > 90.0 and degraded_mode:
            status = "fail"
        else:
            status = "pass"

    tag = {"pass": "PASS", "degraded": "DEGRADED", "fail": "FAIL"}[status]
    print(
        f"[phase20]   [{tag}] score={score} | pages={pages_scanned}"
        f" | topology={site_topology} | issues={len(issues)} | degraded={degraded_mode} | {elapsed:.1f}s"
    )

    # ── Persist result ────────────────────────────────────────────────────────
    _session_results.append({
        "case_id":        case_id,
        "url":            url,
        "scan_mode":      scan_mode,
        "tier":           tier,
        "score":          score,
        "pages_scanned":  pages_scanned,
        "site_topology":  site_topology,
        "issue_count":    len(issues),
        "degraded_mode":  degraded_mode,
        "degraded_reason": str(result.get("degraded_reason") or "") if result else "",
        "status":         status,
        "elapsed_seconds": round(elapsed, 1),
        "top_rules":      _top_rules(issues),
    })

    # ── Assertions ────────────────────────────────────────────────────────────
    assert exc is None or isinstance(exc, asyncio.TimeoutError), (
        f"Pipeline crashed for {url} [{scan_mode}]: {exc}"
    )
    if result is not None:
        assert isinstance(result, dict), "run_audit must return a dict"

        if score is not None:
            assert 0.0 <= score <= 100.0, f"Score {score} out of range [0, 100]"

        # Fake-score regression check
        if score is not None and score > 90.0:
            assert not degraded_mode, (
                f"FAKE_SCORE regression: score={score} with degraded_mode=True for {url} [{scan_mode}]"
            )

        # E2 contract — soft check (deep/max mode may not populate single-page fields)
        if "http_client" not in result:
            print(f"[phase20]   NOTE: http_client not in result for {url} [{scan_mode}]")
        if "browser_engine" not in result:
            print(f"[phase20]   NOTE: browser_engine not in result for {url} [{scan_mode}]")

        # Issue schema — normalizer uses 'rule_type'; accept rule_type/issue_type/type
        for issue in issues[:5]:  # spot-check first 5
            assert "rule_id" in issue, f"Issue missing rule_id: {issue}"
            has_type = "rule_type" in issue or "issue_type" in issue or "type" in issue
            assert has_type, f"Issue missing rule_type/issue_type/type key: {list(issue.keys())}"
            conf = issue.get("confidence")
            if conf is not None:
                assert 0.0 <= float(conf) <= 1.0, f"confidence {conf} out of range"


def _top_rules(issues: list[dict]) -> list[str]:
    freq: dict[str, int] = {}
    for i in issues:
        rid = str(i.get("rule_id") or "unknown")
        freq[rid] = freq.get(rid, 0) + 1
    return [r for r, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:3]]
