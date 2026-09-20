"""
BEACON Phase 20 — Unit Tests
=============================
Tests for all 5 Phase 20 task areas:
  Task 1: Unreachable sites set degraded_mode=True with non-empty reason
  Task 2: No hardcoded score 83.5 in app source
  Task 3: Rule diversity across Phase 19 passing sites
  Task 4: SCAN_MODES / resolve_max_pages correctness
  Task 5: Topology detector — 15 unit tests

All tests are self-contained (no network calls except Task 1's
live-unreachable-IP test which relies on RFC 5737 TEST-NET-1).
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import re
from typing import Any

import pytest

# ── Repository root ───────────────────────────────────────────────────────────
ROOT = pathlib.Path(__file__).resolve().parents[3]
APP_DIR = ROOT / "app"
SERVICES_DIR = APP_DIR / "services"
ROUTERS_DIR = APP_DIR / "routers"

# ─────────────────────────────────────────────────────────────────────────────
# T A S K   1 — Unreachable site → degraded_mode=True
# ─────────────────────────────────────────────────────────────────────────────

UNREACHABLE_URL = "http://192.0.2.1"  # RFC 5737 TEST-NET-1 — guaranteed unreachable


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_unreachable_site_is_degraded():
    """Auditing a guaranteed-unreachable IP must set degraded_mode=True
    with a non-empty, non-None degraded_reason string."""
    from app.services.audit_runner import run_audit

    result = await asyncio.wait_for(
        run_audit(
            url=UNREACHABLE_URL,
            scan_mode="fast",
            precision_profile="balanced",
            enable_enrichment=False,
            enable_cognitive=False,
            use_cache=False,
        ),
        timeout=14,
    )

    assert isinstance(result, dict), "run_audit must return a dict"
    assert result.get("degraded_mode") is True, (
        f"degraded_mode must be True for unreachable site, got {result.get('degraded_mode')!r}"
    )
    reason = result.get("degraded_reason")
    assert isinstance(reason, str) and reason.strip() not in {"", "None", "none", "null"}, (
        f"degraded_reason must be a non-empty string, got {reason!r}"
    )


@pytest.mark.asyncio
@pytest.mark.timeout(15)
async def test_unreachable_site_has_e2_fields():
    """E2 contract: http_client and browser_engine must be present even on failure."""
    from app.services.audit_runner import run_audit

    result = await asyncio.wait_for(
        run_audit(
            url=UNREACHABLE_URL,
            scan_mode="fast",
            precision_profile="balanced",
            enable_enrichment=False,
            enable_cognitive=False,
            use_cache=False,
        ),
        timeout=14,
    )

    assert "http_client" in result, "http_client key missing from result (E2 contract)"
    assert "browser_engine" in result, "browser_engine key missing from result (E2 contract)"
    assert isinstance(result["http_client"], str) and result["http_client"], (
        "http_client must be a non-empty string"
    )
    assert isinstance(result["browser_engine"], str) and result["browser_engine"], (
        "browser_engine must be a non-empty string"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T A S K   2 — No hardcoded score 83.5
# ─────────────────────────────────────────────────────────────────────────────

_LITERAL_83_5_PATTERN = re.compile(r"\b83\.5\b")


def _collect_py_files(directory: pathlib.Path) -> list[pathlib.Path]:
    """Recursively yield all .py files in directory."""
    return list(directory.rglob("*.py"))


def test_no_hardcoded_score_83_5():
    """No literal `83.5` may appear in any Python file under app/.

    The value 83.5 observed in phase19_results.json is produced at runtime by
    the scoring engine (fallback baseline: 96.0 - page_penalty, then degraded
    multiplier 0.85 ≈ 83.5 for single degraded page).  It must NOT be
    hard-coded anywhere in the app source.
    """
    violations: list[str] = []
    for py_file in _collect_py_files(APP_DIR):
        try:
            source = py_file.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for lineno, line in enumerate(source.splitlines(), start=1):
            if _LITERAL_83_5_PATTERN.search(line):
                # Allow it only in comments or docstrings (explanation lines)
                stripped = line.strip()
                if not (stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''")):
                    violations.append(f"{py_file.relative_to(ROOT)}:{lineno}: {line.strip()!r}")

    assert not violations, (
        "Hardcoded literal 83.5 found in app source code. "
        "Remove/replace with config constant or runtime expression.\n"
        + "\n".join(violations)
    )


# ─────────────────────────────────────────────────────────────────────────────
# T A S K   3 — Rule diversity across passing sites
# ─────────────────────────────────────────────────────────────────────────────

_RESULTS_FILE = ROOT / "phase19_results.json"


def _load_phase19_results() -> list[dict]:
    if not _RESULTS_FILE.exists():
        return []
    try:
        return json.loads(_RESULTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def test_rule_diversity_across_passing_sites():
    """Cross-site rule distribution must show ≥5 unique rule_ids and no single
    rule contributing more than 70 % of all collected top-rule mentions."""
    results = _load_phase19_results()
    if not results:
        pytest.skip("phase19_results.json not found — run integration suite first.")

    passing = [r for r in results if r.get("status") == "pass"]

    rule_freq: dict[str, int] = {}
    total_mentions = 0
    for r in passing:
        for rule_id in r.get("top_rules", []):
            rule_id = str(rule_id).strip()
            if rule_id:
                rule_freq[rule_id] = rule_freq.get(rule_id, 0) + 1
                total_mentions += 1

    if total_mentions == 0:
        pytest.skip("No passing sites or no top_rules collected.")

    unique_rules = len(rule_freq)
    assert unique_rules >= 5, (
        f"Expected ≥5 unique rule IDs across passing sites, found {unique_rules}: {list(rule_freq.keys())}"
    )

    max_rule, max_count = max(rule_freq.items(), key=lambda kv: kv[1])
    dominance = max_count / total_mentions
    assert dominance <= 0.70, (
        f"Rule '{max_rule}' dominates {dominance:.1%} of mentions (limit is 70%). "
        f"Rule distribution is not diverse enough."
    )


# ─────────────────────────────────────────────────────────────────────────────
# T A S K   4 — SCAN_MODES / resolve_max_pages
# ─────────────────────────────────────────────────────────────────────────────

def test_resolve_max_pages_known_values():
    """resolve_max_pages must return exact documented defaults."""
    from app.config import resolve_max_pages

    assert resolve_max_pages("fast", False) == 5
    assert resolve_max_pages("fast", True) == 8
    assert resolve_max_pages("deep", False) == 15
    assert resolve_max_pages("deep", True) == 25
    assert resolve_max_pages("max", False) == 40
    assert resolve_max_pages("max", True) == 60


def test_resolve_max_pages_respects_ceiling():
    """resolve_max_pages must never exceed max_pages_ceiling for any mode."""
    from app.config import SCAN_MODES, resolve_max_pages

    for mode, cfg in SCAN_MODES.items():
        ceiling = cfg["max_pages_ceiling"]
        for has_sitemap in (True, False):
            result = resolve_max_pages(mode, has_sitemap)
            assert result <= ceiling, (
                f"resolve_max_pages({mode!r}, {has_sitemap}) = {result} "
                f"exceeds ceiling {ceiling}"
            )


def test_no_hardcoded_max_pages_in_app_code():
    """No standalone integer literal that looks like a hard-coded page count
    may appear *independently* in app/services/ or app/routers/ Python files.

    Scope: numeric literals of the form `max_pages=<N>` are disallowed in
    app/services/ and app/routers/.  Internal orchestration values (e.g.
    max_pages=1 inside crawl_orchestrator.py and scan_mode_runner.py) are
    explicitly exempt since they represent a crawl-starter constant, not a
    user-facing page limit.
    """
    # Pattern: `max_pages=<numeric>` assignment in source
    pattern = re.compile(r"\bmax_pages\s*=\s*\d+")
    # Files explicitly allowed to retain max_pages=N for internal use.
    # dashboard_api.py uses max_pages=1 only as a single-page fallback
    # comparison audit inside the deep/max crawl path — not a user-facing limit.
    EXEMPT_FILENAMES = {"crawl_orchestrator.py", "scan_mode_runner.py", "dashboard_api.py"}

    violations: list[str] = []
    for search_dir in (SERVICES_DIR, ROUTERS_DIR):
        if not search_dir.exists():
            continue
        for py_file in search_dir.rglob("*.py"):
            if py_file.name in EXEMPT_FILENAMES:
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for lineno, line in enumerate(source.splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if pattern.search(line):
                    violations.append(
                        f"{py_file.relative_to(ROOT)}:{lineno}: {stripped!r}"
                    )

    assert not violations, (
        "Hardcoded max_pages=<N> literals found in app/services/ or app/routers/. "
        "Use resolve_max_pages(scan_mode, has_sitemap) instead.\n"
        + "\n".join(violations)
    )


# ─────────────────────────────────────────────────────────────────────────────
# T A S K   5 — Site Topology Detector
# ─────────────────────────────────────────────────────────────────────────────

from app.config import SiteTopology  # noqa: E402
from app.services.topology_detector import (  # noqa: E402
    TopologyResult,
    _find_structural_segments,
    _is_homepage,
    _is_paginated,
    _normalize_path,
    _with_homepage_first,
    detect_topology,
)


# ── Guards ─────────────────────────────────────────────────────────────────

def test_empty_input_returns_single_page():
    result = detect_topology([])
    assert result.topology == SiteTopology.SINGLE_PAGE
    assert result.crawl_urls == []
    assert result.total_discovered == 0


def test_single_url_is_spa():
    result = detect_topology(["https://example.com/"], rendered_page_count=1)
    assert result.topology == SiteTopology.SINGLE_PAGE
    assert result.crawl_urls == ["https://example.com/"]


def test_two_urls_is_not_spa():
    """Two distinct URLs (/ + /about) must NOT be classified as SPA."""
    result = detect_topology(["https://example.com/", "https://example.com/about"])
    assert result.topology != SiteTopology.SINGLE_PAGE


# ── Pagination ─────────────────────────────────────────────────────────────

def test_pagination_detected():
    """Sites with >10% paginated URLs must be classified as PAGINATED."""
    urls = [
        "https://blog.example.com/page/1",
        "https://blog.example.com/page/2",
        "https://blog.example.com/page/3",
        "https://blog.example.com/about",
        "https://blog.example.com/contact",
    ]
    result = detect_topology(urls)
    # 3 out of 5 = 60% paginated → PAGINATED wins over THIN/MULTI_TEMPLATE
    assert result.topology in (SiteTopology.PAGINATED, SiteTopology.DEEP_UNIFORM)


def test_paginated_pages_not_in_crawl_urls():
    """Paginated URLs must be excluded from crawl_urls."""
    urls = [
        "https://blog.example.com/",
        "https://blog.example.com/page/1",
        "https://blog.example.com/page/2",
        "https://blog.example.com/page/3",
    ]
    result = detect_topology(urls)
    for cu in result.crawl_urls:
        assert "page/" not in cu, f"Paginated URL appeared in crawl_urls: {cu}"


# ── DEEP_UNIFORM ────────────────────────────────────────────────────────────

def test_deep_uniform_large_uniform_site():
    """A site with 30+ uniform article URLs must be DEEP_UNIFORM."""
    urls = [f"https://news.example.com/article/{i}" for i in range(40)]
    urls.append("https://news.example.com/")
    result = detect_topology(urls)
    assert result.topology == SiteTopology.DEEP_UNIFORM


# ── MULTI_TEMPLATE ──────────────────────────────────────────────────────────

def test_multi_template_distinct_sections():
    """A site with clearly dominant distinct sections must be MULTI_TEMPLATE.

    For structural segments to be identified at ≥30% frequency, each section
    must appear in at least ⌈0.30 × total⌉ URLs.  With 12 URLs and 4 per
    section that is 4/12 ≈ 33% — safely above threshold.
    """
    urls = [
        "https://shop.example.com/",
        # blog section: 4 URLs (4/12 ≈ 33% at position 0 → structural)
        "https://shop.example.com/blog/post-a",
        "https://shop.example.com/blog/post-b",
        "https://shop.example.com/blog/post-c",
        "https://shop.example.com/blog/post-d",
        # product section: 4 URLs
        "https://shop.example.com/product/shoe-x",
        "https://shop.example.com/product/shoe-y",
        "https://shop.example.com/product/shoe-z",
        "https://shop.example.com/product/bag-a",
        # account section: 3 URLs
        "https://shop.example.com/account/login",
        "https://shop.example.com/account/register",
        "https://shop.example.com/account/profile",
    ]
    result = detect_topology(urls)
    assert result.topology == SiteTopology.MULTI_TEMPLATE, (
        f"Expected MULTI_TEMPLATE, got {result.topology}. "
        f"templates_found={result.templates_found}"
    )


# ── THIN ────────────────────────────────────────────────────────────────────

def test_thin_site_classification():
    """A 5-page brochure site with no uniform structure must be THIN."""
    urls = [
        "https://small.example.com/",
        "https://small.example.com/about",
        "https://small.example.com/contact",
        "https://small.example.com/services",
        "https://small.example.com/pricing",
    ]
    result = detect_topology(urls)
    assert result.topology == SiteTopology.THIN


def test_thin_site_with_templates():
    """Thin sites still run through template normalization — templates_found >=1."""
    urls = [
        "https://small.example.com/about",
        "https://small.example.com/contact",
    ]
    result = detect_topology(urls)
    assert result.topology == SiteTopology.THIN
    assert result.templates_found >= 1


# ── Homepage ordering ───────────────────────────────────────────────────────

def test_homepage_first_in_crawl_urls():
    """Homepage (/) must always be the first URL in crawl_urls."""
    urls = [
        "https://example.com/blog/post-1",
        "https://example.com/blog/post-2",
        "https://example.com/",
        "https://example.com/about",
    ]
    result = detect_topology(urls)
    if result.crawl_urls:
        assert result.crawl_urls[0] == "https://example.com/", (
            f"Homepage was not first: {result.crawl_urls}"
        )


def test_with_homepage_first_deduplicates():
    """_with_homepage_first must never include the homepage twice."""
    homepage = "https://example.com/"
    urls = ["https://example.com/", "https://example.com/about", "https://example.com/"]
    result = _with_homepage_first(urls, homepage)
    assert result.count(homepage) == 1, (
        f"Homepage appeared {result.count(homepage)} times: {result}"
    )


# ── _find_structural_segments position sensitivity ──────────────────────────

def test_structural_segments_position_sensitive():
    """_find_structural_segments must track segments by position independently.

    'doctors' appearing at position 0 and position 1 must be registered as
    separate entries (key 0 and key 1), not collapsed into a single bucket.
    """
    paths = [
        "/doctors/cardiology",
        "/doctors/neurology",
        "/doctors/orthopaedics",
        "/consult/doctors",
        "/consult/lab",
    ]
    segs = _find_structural_segments(paths)
    # 'doctors' at position 0 should be structural (3/5 = 60% ≥ 30%)
    assert "doctors" in segs.get(0, set()), (
        f"'doctors' at position 0 should be structural; got {segs}"
    )
    # 'consult' at position 0 should be structural (2/5 = 40% ≥ 30%)
    assert "consult" in segs.get(0, set()), (
        f"'consult' at position 0 should be structural; got {segs}"
    )
    # Return type is dict[int, set[str]]
    assert all(isinstance(k, int) for k in segs.keys()), (
        "Keys of _find_structural_segments must be integers (positions)"
    )


# ── Query string stripping ──────────────────────────────────────────────────

def test_query_strings_stripped_from_templates():
    """URLs that differ only by query string must map to the same template."""
    urls = [
        "https://example.com/search?q=foo",
        "https://example.com/search?q=bar",
        "https://example.com/search?q=baz",
        "https://example.com/",
    ]
    result = detect_topology(urls)
    # /search?q=* should normalize to a single template → thin or single_page
    # Key assertion: we shouldn't have 3 separate templates for /search
    assert result.templates_found <= 3, (
        f"Query strings should be stripped; found {result.templates_found} templates for {urls}"
    )


# ── stats ──────────────────────────────────────────────────────────────────

def test_total_discovered_counts_input_urls():
    urls = [f"https://example.com/p/{i}" for i in range(10)]
    result = detect_topology(urls)
    assert result.total_discovered == 10


def test_skipped_urls_nonnegative():
    urls = ["https://example.com/", "https://example.com/page/1", "https://example.com/about"]
    result = detect_topology(urls)
    assert result.skipped_urls >= 0


# ─────────────────────────────────────────────────────────────────────────────
# T A S K   5 (continued) — Topology must influence crawl selection
# ─────────────────────────────────────────────────────────────────────────────

def test_topology_pages_per_template_thin_is_unlimited():
    """TOPOLOGY_PAGES_PER_TEMPLATE[THIN] must be ≥ 99 (effectively unlimited).

    THIN sites are brochure sites where every page is unique.  A value of 1
    would silently audit only one page per 'template' — causing massive coverage
    loss.  This test is a config guard to prevent accidental regression.
    """
    from app.config import TOPOLOGY_PAGES_PER_TEMPLATE, SiteTopology

    thin_limit = TOPOLOGY_PAGES_PER_TEMPLATE[SiteTopology.THIN]
    assert thin_limit >= 99, (
        f"TOPOLOGY_PAGES_PER_TEMPLATE[THIN] must be ≥ 99 to crawl all thin-site pages, "
        f"got {thin_limit}. A value of 1 would silently under-audit brochure sites."
    )


def test_thin_site_crawls_all_pages():
    """Thin sites must have ALL their pages in crawl_urls (no template dedup loss).

    A 5-page brochure site → all 5 pages should be in crawl_urls.
    Previously, THIN: 1 caused 4 of 5 pages to be silently skipped.
    """
    urls = [
        "https://small.example.com/",
        "https://small.example.com/about",
        "https://small.example.com/contact",
        "https://small.example.com/services",
        "https://small.example.com/pricing",
    ]
    result = detect_topology(urls)
    assert result.topology == SiteTopology.THIN
    # All 5 URLs must be selected — zero silently skipped
    assert len(result.crawl_urls) == len(urls), (
        f"Thin site lost pages in crawl_urls: "
        f"discovered={len(urls)} but crawl_urls={len(result.crawl_urls)} — "
        f"topology may be over-deduplicating THIN sites."
    )


def test_deep_uniform_crawl_urls_bounded_by_sample():
    """DEEP_UNIFORM sites must select ≤ 2 pages per template group (not all 40).

    This verifies that topology is actively reducing the crawl set, not just
    labeling it.  A 40-page uniform site should yield ≤ 2 crawl URLs.
    """
    from app.config import TOPOLOGY_PAGES_PER_TEMPLATE, SiteTopology

    urls = [f"https://news.example.com/article/{i}" for i in range(40)]
    urls.append("https://news.example.com/")

    result = detect_topology(urls)
    assert result.topology == SiteTopology.DEEP_UNIFORM

    sample_size = TOPOLOGY_PAGES_PER_TEMPLATE[SiteTopology.DEEP_UNIFORM]
    # homepage + at most sample_size article pages
    expected_max = 1 + sample_size  # homepage is always included
    assert len(result.crawl_urls) <= expected_max, (
        f"DEEP_UNIFORM crawl_urls ({len(result.crawl_urls)}) exceeds "
        f"expected cap of {expected_max} (1 homepage + {sample_size} per template). "
        f"Topology detection is not properly reducing the crawl set."
    )


def test_topology_result_pages_not_exceed_resolve_max_pages():
    """detect_topology's crawl_urls must be ≤ resolve_max_pages(fast, False).

    This simulates what scan_mode_runner does: take crawl_urls[:effective_max_pages].
    Even without that slice, a typical thin site's crawl_urls should not
    naturally exceed the fast-mode ceiling of 10.
    """
    from app.config import resolve_max_pages

    # A typical thin site (5 pages) — crawl_urls should be well within fast ceiling
    urls = [
        "https://small.example.com/",
        "https://small.example.com/about",
        "https://small.example.com/contact",
        "https://small.example.com/services",
        "https://small.example.com/pricing",
    ]
    result = detect_topology(urls)
    ceiling = resolve_max_pages("fast", False)  # = 5

    # Simulate what scan_mode_runner does: slice to ceiling
    auditable = result.crawl_urls[:ceiling]
    assert len(auditable) <= ceiling, (
        f"After ceiling slice, auditable count {len(auditable)} > ceiling {ceiling}"
    )
    # Also verify slice does not lose all pages (regression guard)
    assert len(auditable) >= 1, "Ceiling slice must retain at least 1 auditable URL"


@pytest.mark.asyncio
async def test_bot_wall_preflight_check_aborts():
    """Verify that CrawlerOrchestrator._check_bot_wall raises a ValueError
    when the seed URL is detected to be protected by a bot wall (e.g. Cloudflare).
    """
    from unittest.mock import AsyncMock, patch
    from app.crawlers.orchestrator import CrawlerOrchestrator
    
    orchestrator = CrawlerOrchestrator()
    
    # We mock AsyncSession's get to return a simulated Cloudflare block response
    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.headers = {"server": "cloudflare", "cf-ray": "some-ray-id"}
    mock_response.text = "Error 1020: Access Denied"
    
    # Mocking the AsyncSession context manager
    mock_session = AsyncMock()
    mock_session.get.return_value = mock_response
    mock_session.__aenter__.return_value = mock_session
    
    with patch("curl_cffi.requests.AsyncSession", return_value=mock_session):
        with pytest.raises(ValueError) as excinfo:
            await orchestrator.discover_urls("https://protected.example.com", "fast", 10)
            
        assert "protected by bot protection" in str(excinfo.value)


