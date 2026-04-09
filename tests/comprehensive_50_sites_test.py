"""
BEACON Engine — World-Class 50-Site Comprehensive Test Suite
=============================================================

This test suite validates BEACON against 50 diverse real-world sites covering:
- Simple HTML sites
- Complex SPAs (React, Angular, Vue)
- Government & accessibility-focused sites  
- E-commerce platforms
- Social media
- News & media sites
- Educational platforms
- Financial services
- Healthcare
- Tech companies
- Internationalized sites

Goal: Achieve world-class accessibility auditing beyond YC-level quality.
"""
import asyncio
import json
import sys
import os
import time
import logging
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Any, Optional
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.audit.failure_taxonomy import classify_failure_reason, normalize_reason
from app.observability.telemetry import record_operational_event
from app.services.spa_classifier import compute_confusion_matrix, precision_recall

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress verbose logs during bulk testing
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("playwright").setLevel(logging.WARNING)

REQUIRED_AUDIT_FIELDS = (
    "overall_score",
    "severity_breakdown",
    "priority_score_distribution",
    "issue_groupings",
    "score_explanation",
)

REQUIRED_TELEMETRY_FIELDS = (
    "overall_score_distribution",
    "severity_counts",
    "priority_score_distribution",
    "top_issue_types",
    "degraded_reason",
)


def _derive_mode_timeouts(max_site_time: int) -> tuple[int, int]:
    safe_site_time = max(15, int(max_site_time or 30))
    fast_timeout = max(6, int(safe_site_time * 0.35))
    deep_timeout = max(8, int(safe_site_time * 0.6))

    # Keep fast+deep within site cap with a small scheduling buffer.
    available = max(12, safe_site_time - 2)
    total = fast_timeout + deep_timeout
    if total > available:
        scale = available / total
        fast_timeout = max(5, int(fast_timeout * scale))
        deep_timeout = max(6, int(deep_timeout * scale))

    return fast_timeout, deep_timeout


def _classify_runtime_failure_reason(
    *,
    error: Optional[str],
    degraded_reason: Optional[str],
    degraded: bool,
) -> str:
    combined = " ".join([str(error or ""), str(degraded_reason or "")]).lower()
    normalized_reason = normalize_reason(degraded_reason) or classify_failure_reason(error)

    if (
        "content security policy" in combined
        or "csp" in combined
        or "refused to execute inline script" in combined
        or "blocked by csp" in combined
    ):
        return "csp_block"

    if "timeout" in combined or normalized_reason == "render_timeout":
        return "timeout"

    navigation_tokens = (
        "navigation",
        "page.goto",
        "execution context was destroyed",
        "target page, context or browser has been closed",
        "net::err",
    )
    if any(token in combined for token in navigation_tokens):
        return "navigation_error"

    if normalized_reason == "dns_failure":
        return "dns_failure"
    if normalized_reason == "blocked_request":
        return "blocked_request"
    if normalized_reason == "network_error":
        return "network_error"

    if degraded and not error:
        return "partial_load"

    if normalized_reason in {"dom_parse_error", "extraction_failure"}:
        return "partial_load"

    return "unknown"


def _normalize_site_url(url: str) -> str:
    return _normalize_truth_url(url)


def _read_subset_config(subset_path: str) -> list[dict[str, Any]]:
    path = Path(subset_path)
    if not path.exists():
        raise FileNotFoundError(f"Subset file not found: {subset_path}")

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict):
        entries = payload.get("sites", [])
    elif isinstance(payload, list):
        entries = payload
    else:
        entries = []

    normalized_entries: list[dict[str, Any]] = []
    for entry in entries:
        if isinstance(entry, str):
            normalized_entries.append({"url": entry})
        elif isinstance(entry, dict):
            normalized_entries.append(entry)

    if not normalized_entries:
        raise ValueError(f"Subset file has no valid site entries: {subset_path}")

    return normalized_entries


def _load_subset_sites(subset_path: str, available_sites: list["SiteTestCase"]) -> list["SiteTestCase"]:
    entries = _read_subset_config(subset_path)
    by_url = {_normalize_site_url(site.url): site for site in available_sites}
    by_name = {site.name.strip().lower(): site for site in available_sites}

    selected: list[SiteTestCase] = []
    seen: set[str] = set()

    for entry in entries:
        url = _normalize_site_url(str(entry.get("url", "")))
        name = str(entry.get("name", "")).strip().lower()

        candidate = None
        if url and url in by_url:
            candidate = by_url[url]
        elif name and name in by_name:
            candidate = by_name[name]

        if candidate is None:
            logger.warning("Subset entry did not match any predefined test site: %s", entry)
            continue

        key = _normalize_site_url(candidate.url)
        if key in seen:
            continue

        selected.append(candidate)
        seen.add(key)

    if not selected:
        raise ValueError(f"Subset file did not resolve to known test sites: {subset_path}")

    return selected


def _safe_avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values) / len(values))


def _extract_quality_metrics(audit_result: dict) -> tuple[float, float]:
    rag_issues = [
        issue
        for issue in (audit_result.get("issues", []) or [])
        if bool(issue.get("rag_context"))
    ]
    if not rag_issues:
        return 0.0, 0.0

    issue_quality_scores: list[float] = []
    issue_acceptance_scores: list[float] = []

    for issue in rag_issues:
        quality = issue.get("quality_scores", {})
        if not isinstance(quality, dict):
            continue

        usefulness = float(quality.get("usefulness_score", 0.0) or 0.0)
        correctness = float(quality.get("correctness_score", 0.0) or 0.0)
        if usefulness > 0 or correctness > 0:
            issue_quality_scores.append((usefulness + correctness) / 2.0)

        predicted_acceptance = float(
            quality.get("predicted_acceptance_rate", quality.get("acceptance_rate", 0.0)) or 0.0
        )
        if predicted_acceptance > 0:
            issue_acceptance_scores.append(predicted_acceptance)

    meta_quality = ((audit_result.get("enrichment_meta") or {}).get("quality") or {})
    rag_effectiveness = _safe_avg(issue_quality_scores)
    if rag_effectiveness <= 0:
        rag_effectiveness = float(meta_quality.get("rag_effectiveness", 0.0) or 0.0)

    fix_acceptance_rate = _safe_avg(issue_acceptance_scores)
    if fix_acceptance_rate <= 0:
        fix_acceptance_rate = float(
            meta_quality.get("fix_acceptance_rate", meta_quality.get("acceptance_rate", 0.0)) or 0.0
        )

    return round(rag_effectiveness, 1), round(fix_acceptance_rate, 1)


@dataclass
class SiteTestCase:
    """Represents a site to test with expected characteristics."""
    url: str
    name: str
    category: str
    complexity: str  # simple, moderate, complex
    expected_score_range: tuple[int, int]  # (min, max) acceptable score
    notes: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# 50 DIVERSE TEST SITES - Carefully selected for comprehensive coverage
# ══════════════════════════════════════════════════════════════════════════════

TEST_SITES = [
    # ─── ACCESSIBILITY-FOCUSED SITES (should score well) ───────────────────────
    SiteTestCase("https://www.a11yproject.com/", "A11y Project", "accessibility", "simple", (70, 100)),
    SiteTestCase("https://webaim.org/", "WebAIM", "accessibility", "simple", (70, 100)),
    SiteTestCase("https://www.w3.org/WAI/", "W3C WAI", "accessibility", "moderate", (60, 100)),
    SiteTestCase("https://dequeuniversity.com/", "Deque University", "accessibility", "moderate", (65, 100)),
    SiteTestCase("https://inclusive-components.design/", "Inclusive Components", "accessibility", "simple", (70, 100)),
    
    # ─── GOVERNMENT SITES (legally required to be accessible) ──────────────────
    SiteTestCase("https://www.usa.gov/", "USA.gov", "government", "moderate", (50, 95)),
    SiteTestCase("https://www.gov.uk/", "GOV.UK", "government", "moderate", (60, 100)),
    SiteTestCase("https://www.canada.ca/en.html", "Canada.ca", "government", "moderate", (55, 95)),
    SiteTestCase("https://www.digital.gov/", "Digital.gov", "government", "simple", (60, 100)),
    SiteTestCase("https://www.section508.gov/", "Section508.gov", "government", "moderate", (65, 100)),
    
    # ─── TECH GIANTS (complex, should handle) ──────────────────────────────────
    SiteTestCase("https://www.microsoft.com/", "Microsoft", "tech", "complex", (10, 70)),
    SiteTestCase("https://www.apple.com/", "Apple", "tech", "complex", (5, 60)),
    SiteTestCase("https://www.google.com/", "Google", "tech", "moderate", (30, 80)),
    SiteTestCase("https://github.com/", "GitHub", "tech", "complex", (20, 70)),
    SiteTestCase("https://about.meta.com/", "Meta", "tech", "complex", (10, 60)),
    
    # ─── E-COMMERCE (complex with dynamic content) ─────────────────────────────
    SiteTestCase("https://www.amazon.com/", "Amazon", "ecommerce", "complex", (0, 50)),
    SiteTestCase("https://www.ebay.com/", "eBay", "ecommerce", "complex", (10, 60)),
    SiteTestCase("https://www.etsy.com/", "Etsy", "ecommerce", "complex", (15, 65)),
    SiteTestCase("https://www.target.com/", "Target", "ecommerce", "complex", (20, 70)),
    SiteTestCase("https://www.bestbuy.com/", "Best Buy", "ecommerce", "complex", (15, 65)),
    
    # ─── SOCIAL MEDIA (highly dynamic) ─────────────────────────────────────────
    SiteTestCase("https://twitter.com/", "Twitter/X", "social", "complex", (0, 50)),
    SiteTestCase("https://www.linkedin.com/", "LinkedIn", "social", "complex", (10, 60)),
    SiteTestCase("https://www.reddit.com/", "Reddit", "social", "complex", (0, 50)),
    SiteTestCase("https://www.pinterest.com/", "Pinterest", "social", "complex", (5, 55)),
    SiteTestCase("https://www.tumblr.com/", "Tumblr", "social", "complex", (10, 60)),
    
    # ─── NEWS & MEDIA ──────────────────────────────────────────────────────────
    SiteTestCase("https://www.bbc.com/", "BBC", "news", "complex", (30, 75)),
    SiteTestCase("https://www.nytimes.com/", "NY Times", "news", "complex", (20, 70)),
    SiteTestCase("https://www.theguardian.com/", "The Guardian", "news", "complex", (25, 70)),
    SiteTestCase("https://www.washingtonpost.com/", "Washington Post", "news", "complex", (15, 65)),
    SiteTestCase("https://news.ycombinator.com/", "Hacker News", "news", "simple", (0, 40), "Intentionally minimal HTML"),
    
    # ─── EDUCATIONAL ───────────────────────────────────────────────────────────
    SiteTestCase("https://www.wikipedia.org/", "Wikipedia", "education", "moderate", (40, 85)),
    SiteTestCase("https://www.khanacademy.org/", "Khan Academy", "education", "complex", (35, 80)),
    SiteTestCase("https://www.coursera.org/", "Coursera", "education", "complex", (30, 75)),
    SiteTestCase("https://developer.mozilla.org/en-US/", "MDN Web Docs", "education", "moderate", (50, 90)),
    SiteTestCase("https://stackoverflow.com/", "Stack Overflow", "education", "moderate", (25, 70)),
    
    # ─── FINANCIAL SERVICES ────────────────────────────────────────────────────
    SiteTestCase("https://www.chase.com/", "Chase", "finance", "complex", (20, 70)),
    SiteTestCase("https://www.bankofamerica.com/", "Bank of America", "finance", "complex", (25, 75)),
    SiteTestCase("https://www.paypal.com/", "PayPal", "finance", "complex", (30, 75)),
    SiteTestCase("https://stripe.com/", "Stripe", "finance", "moderate", (40, 85)),
    SiteTestCase("https://www.mint.com/", "Mint", "finance", "complex", (25, 70)),
    
    # ─── HEALTHCARE ────────────────────────────────────────────────────────────
    SiteTestCase("https://www.webmd.com/", "WebMD", "healthcare", "complex", (20, 65)),
    SiteTestCase("https://www.mayoclinic.org/", "Mayo Clinic", "healthcare", "moderate", (35, 80)),
    SiteTestCase("https://www.healthline.com/", "Healthline", "healthcare", "moderate", (30, 75)),
    SiteTestCase("https://www.cdc.gov/", "CDC", "healthcare", "moderate", (45, 90)),
    SiteTestCase("https://www.who.int/", "WHO", "healthcare", "moderate", (40, 85)),
    
    # ─── SIMPLE HTML / BLOGS ───────────────────────────────────────────────────
    SiteTestCase("https://www.paulgraham.com/", "Paul Graham Essays", "blog", "simple", (30, 80)),
    SiteTestCase("https://motherfuckingwebsite.com/", "MFWS", "blog", "simple", (40, 100), "Ultra-minimal HTML"),
    SiteTestCase("https://bettermotherfuckingwebsite.com/", "Better MFWS", "blog", "simple", (50, 100)),
    SiteTestCase("https://www.craigslist.org/", "Craigslist", "blog", "simple", (20, 70), "Intentionally basic"),
    SiteTestCase("https://lite.cnn.com/", "CNN Lite", "blog", "simple", (50, 95), "Accessibility-first design"),
]


@dataclass
class TestResult:
    """Result from testing a single site."""
    site: SiteTestCase
    fast_score: Optional[int] = None
    deep_score: Optional[int] = None
    fast_issues: int = 0
    deep_issues: int = 0
    fast_time: float = 0.0
    deep_time: float = 0.0
    fast_rag_effectiveness: float = 0.0
    fast_fix_acceptance_rate: float = 0.0
    deep_rag_effectiveness: float = 0.0
    deep_fix_acceptance_rate: float = 0.0
    fast_enrichment_status: str = "off"
    deep_enrichment_status: str = "off"
    fast_engines: list = None
    deep_engines: list = None
    wcag_scs: list = None
    severity_breakdown: dict = None
    error: Optional[str] = None
    passed: bool = False
    fast_degraded: bool = False
    deep_degraded: bool = False
    fast_degraded_reason: Optional[str] = None
    deep_degraded_reason: Optional[str] = None
    degraded: bool = False
    degraded_reason: Optional[str] = None
    site_status: str = "runtime_failed"  # completed | runtime_failed
    failure_reason: Optional[str] = None
    runtime_failure_type: Optional[str] = None
    scoring_completed: bool = False
    required_scoring_fields: bool = False
    spa_framework: Optional[str] = None
    is_spa: bool = False
    browser_probe_metadata: dict = None
    deep_skipped: bool = False
    deep_skip_reason: Optional[str] = None
    early_stop_reason: Optional[str] = None
    pages_skipped_low_value: int = 0
    avg_page_time: float = 0.0
    
    def __post_init__(self):
        if self.fast_engines is None:
            self.fast_engines = []
        if self.deep_engines is None:
            self.deep_engines = []
        if self.wcag_scs is None:
            self.wcag_scs = []
        if self.severity_breakdown is None:
            self.severity_breakdown = {}
        if self.browser_probe_metadata is None:
            self.browser_probe_metadata = {}


def _normalize_truth_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if not parsed.netloc:
        return ""
    scheme = (parsed.scheme or "https").lower()
    host = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return f"{scheme}://{host}{path}"


def _load_spa_truth_labels(truth_set_path: Optional[str] = None) -> dict[str, bool]:
    default_path = Path(__file__).resolve().parents[1] / "evaluation" / "spa_truth_set.json"
    path = Path(truth_set_path) if truth_set_path else default_path
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
    except Exception as exc:
        logger.warning(f"Failed to load SPA truth set from {path}: {exc}")
        return {}

    cases: list[dict] = []
    if isinstance(payload, dict):
        raw_cases = payload.get("cases")
        if isinstance(raw_cases, list):
            cases = [row for row in raw_cases if isinstance(row, dict)]
    elif isinstance(payload, list):
        cases = [row for row in payload if isinstance(row, dict)]

    labels: dict[str, bool] = {}
    for case in cases:
        normalized = _normalize_truth_url(case.get("url", ""))
        if not normalized:
            continue
        labels[normalized] = bool(case.get("is_spa", False))
    return labels


def _compute_spa_truth_metrics(results: list[TestResult], labels: dict[str, bool]) -> Optional[dict]:
    if not labels:
        return None

    rows: list[tuple[bool, bool]] = []
    for result in results:
        normalized = _normalize_truth_url(result.site.url)
        if not normalized or normalized not in labels:
            continue
        rows.append((bool(labels[normalized]), bool(result.is_spa)))

    if not rows:
        return None

    confusion = compute_confusion_matrix(rows)
    precision, recall = precision_recall(confusion)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "evaluated_sites": len(rows),
        "confusion_matrix": confusion,
        "spa_precision": round(precision, 4),
        "spa_recall": round(recall, 4),
        "spa_f1": round(f1, 4),
    }


async def run_single_site_test(
    site: SiteTestCase,
    max_site_time: int = 30,
    use_rag: bool = False,
    max_enrich_issues: int = 20,
    enable_cognitive: bool = True,
) -> TestResult:
    """Run fast + deep scan on a single site with timeout protection."""
    from app.services.audit_runner import run_audit

    result = TestResult(site=site)

    effective_site_time = min(180, max(15, int(max_site_time or 30)))
    fast_timeout_hint, deep_timeout_hint = _derive_mode_timeouts(effective_site_time)
    site_start = time.monotonic()
    current_stage = "fast"

    def _remaining_budget(reserve_s: float = 0.0) -> float:
        elapsed = time.monotonic() - site_start
        return max(0.0, float(effective_site_time) - elapsed - reserve_s)

    async def _run_scans() -> None:
        nonlocal current_stage
        # ── FAST MODE ──────────────────────────────────────────────
        current_stage = "fast"
        fast_timeout = max(1.0, min(float(fast_timeout_hint), _remaining_budget(1.0)))
        logger.info(f"[FAST] Testing {site.name}: {site.url} (timeout={fast_timeout:.1f}s)")
        fast_start = time.time()

        fast_result = await asyncio.wait_for(
            run_audit(
                site.url,
                scan_mode="fast",
                precision_profile="balanced",
                enable_enrichment=use_rag,
                max_enrich_issues=max_enrich_issues if use_rag else 0,
                enable_cognitive=False,
                await_enrichment=use_rag,
            ),
            timeout=fast_timeout,
        )

        result.fast_time = time.time() - fast_start
        result.fast_score = fast_result.get("score", 0)
        result.fast_issues = fast_result.get("total_issues", 0)
        result.fast_engines = fast_result.get("engines_used", [])
        result.fast_rag_effectiveness, result.fast_fix_acceptance_rate = _extract_quality_metrics(fast_result)
        result.fast_enrichment_status = fast_result.get("enrichment_status", "off")
        result.fast_degraded = bool(fast_result.get("degraded_mode", False))
        result.fast_degraded_reason = fast_result.get("degraded_reason") or fast_result.get("degradation_reason")

        # Brief pause between scans
        pause_s = min(0.25, _remaining_budget(0.5))
        if pause_s > 0:
            await asyncio.sleep(pause_s)

        # ── DEEP MODE ──────────────────────────────────────────────
        current_stage = "deep"
        remaining_before_deep = _remaining_budget(0.0)
        if remaining_before_deep < 20.0:
            result.deep_skipped = True
            result.deep_skip_reason = "insufficient_budget_for_deep"
            result.early_stop_reason = result.deep_skip_reason
            result.avg_page_time = round(_safe_avg([result.fast_time] if result.fast_time > 0 else []), 3)

            score = result.fast_score or 0
            min_exp, max_exp = site.expected_score_range
            result.passed = min_exp <= score <= max_exp

            logger.info(
                "[DEEP-SKIP] %s: remaining budget %.1fs is below 20s threshold",
                site.name,
                remaining_before_deep,
            )
            return

        deep_phase_budget = float(effective_site_time) * 0.60
        deep_timeout = max(
            1.0,
            min(
                float(deep_timeout_hint),
                deep_phase_budget,
                _remaining_budget(0.25),
            ),
        )
        logger.info(
            "[DEEP] Testing %s: %s (timeout=%.1fs, hint=%ss, deep_budget_cap=%.1fs)",
            site.name,
            site.url,
            deep_timeout,
            deep_timeout_hint,
            deep_phase_budget,
        )
        deep_start = time.time()

        deep_result = await asyncio.wait_for(
            run_audit(
                site.url,
                scan_mode="deep",
                precision_profile="balanced",
                enable_enrichment=use_rag,
                max_enrich_issues=max_enrich_issues if use_rag else 0,
                enable_cognitive=enable_cognitive,
                await_enrichment=use_rag,
            ),
            timeout=deep_timeout,
        )

        result.deep_time = time.time() - deep_start
        result.deep_score = deep_result.get("score", 0)
        result.deep_issues = deep_result.get("total_issues", 0)
        result.deep_engines = deep_result.get("engines_used", [])
        result.deep_rag_effectiveness, result.deep_fix_acceptance_rate = _extract_quality_metrics(deep_result)
        result.deep_enrichment_status = deep_result.get("enrichment_status", "off")
        result.wcag_scs = deep_result.get("wcag_scs_covered", [])
        result.deep_degraded = bool(deep_result.get("degraded_mode", False))
        result.deep_degraded_reason = deep_result.get("degraded_reason") or deep_result.get("degradation_reason")
        result.degraded = bool(result.fast_degraded or result.deep_degraded)
        result.degraded_reason = result.deep_degraded_reason or result.fast_degraded_reason

        crawl_meta = deep_result.get("crawl_meta") or {}
        site_result = deep_result.get("site_result") or {}
        if not crawl_meta and isinstance(site_result, dict):
            crawl_meta = site_result.get("crawl_meta") or {}
        if isinstance(crawl_meta, dict):
            result.early_stop_reason = str(crawl_meta.get("early_stop_reason") or "") or None
            result.pages_skipped_low_value = int(crawl_meta.get("pages_skipped_low_value", 0) or 0)
            result.avg_page_time = float(crawl_meta.get("avg_page_time", 0.0) or 0.0)

        if result.avg_page_time <= 0.0:
            stage_times = [value for value in (result.fast_time, result.deep_time) if value > 0.0]
            result.avg_page_time = round(_safe_avg(stage_times), 3)

        # SPA detection info
        result.spa_framework = deep_result.get("spa_framework")
        result.is_spa = deep_result.get("is_spa", False)
        result.browser_probe_metadata = deep_result.get("browser_probe_metadata", {})

        # Ensure Phase 5 scoring payload is fully present.
        result.required_scoring_fields = all(field in deep_result for field in REQUIRED_AUDIT_FIELDS)

        # Severity breakdown
        issues = deep_result.get("issues", [])
        for issue in issues:
            sev = issue.get("severity", "unknown")
            result.severity_breakdown[sev] = result.severity_breakdown.get(sev, 0) + 1

        # Check if result is within expected range
        score = result.deep_score or result.fast_score or 0
        min_exp, max_exp = site.expected_score_range
        result.passed = min_exp <= score <= max_exp

    try:
        await _run_scans()

        if result.degraded:
            result.site_status = "runtime_failed"
            result.failure_reason = _classify_runtime_failure_reason(
                error=None,
                degraded_reason=result.degraded_reason,
                degraded=True,
            )
            result.runtime_failure_type = result.failure_reason
            result.scoring_completed = False
        else:
            result.site_status = "completed"
            result.scoring_completed = bool(result.required_scoring_fields)

    except asyncio.TimeoutError:
        result.error = "TIMEOUT"
        result.site_status = "runtime_failed"
        result.failure_reason = "timeout"
        result.runtime_failure_type = "timeout"
        result.scoring_completed = False
        logger.warning(
            f"[TIMEOUT] {site.name} exceeded {effective_site_time}s limit during {current_stage} scan"
        )
    except Exception as e:
        result.error = str(e)[:200]
        result.site_status = "runtime_failed"
        result.failure_reason = _classify_runtime_failure_reason(
            error=result.error,
            degraded_reason=result.degraded_reason,
            degraded=bool(result.degraded),
        )
        result.runtime_failure_type = result.failure_reason
        result.scoring_completed = False
        logger.error(f"[ERROR] {site.name}: {e}")

    return result


async def run_50_site_test(
    parallel_limit: int = 3,
    sites: list[SiteTestCase] = None,
    use_rag: bool = False,
    max_enrich_issues: int = 20,
    enable_cognitive: bool = True,
    spa_truth_set_path: Optional[str] = None,
    max_site_time: int = 30,
    output_path: Optional[str] = None,
) -> dict:
    """
    Run comprehensive 50-site test with parallel execution.
    
    Returns detailed report with:
    - Per-site results
    - Category summaries
    - Failure analysis
    - Performance metrics
    - Recommendations
    """
    if sites is None:
        sites = TEST_SITES
    
    print("\n" + "="*80)
    print("  [BEACON ENGINE] 50-SITE WORLD-CLASS AUDIT TEST")
    print("="*80)
    print(f"  Sites to test: {len(sites)}")
    print(f"  Parallel limit: {parallel_limit}")
    print(f"  Max site time: {max_site_time}s")
    print(f"  RAG enrichment: {'ON' if use_rag else 'OFF'}")
    if use_rag:
        print(f"  Max enrich issues: {max_enrich_issues}")
    print(f"  Cognitive checks: {'ON' if enable_cognitive else 'OFF'}")
    print(f"  Started: {datetime.now().isoformat()}")
    print("="*80 + "\n")
    
    results: list[TestResult] = []
    semaphore = asyncio.Semaphore(parallel_limit)
    
    async def run_with_semaphore(site: SiteTestCase) -> TestResult:
        async with semaphore:
            return await run_single_site_test(
                site,
                max_site_time=max_site_time,
                use_rag=use_rag,
                max_enrich_issues=max_enrich_issues,
                enable_cognitive=enable_cognitive,
            )
    
    # Run all tests with controlled parallelism
    start_time = time.time()
    tasks = [run_with_semaphore(site) for site in sites]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    total_time = time.time() - start_time
    
    # Process results (handle any exceptions that slipped through)
    processed_results: list[TestResult] = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            processed_results.append(TestResult(
                site=sites[i],
                error=str(r)[:200],
                site_status="runtime_failed",
                failure_reason="unknown",
                runtime_failure_type="unknown",
                scoring_completed=False,
            ))
        else:
            processed_results.append(r)
    
    # ══════════════════════════════════════════════════════════════════════════
    # ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    # Category analysis
    category_stats = defaultdict(lambda: {
        "sites": 0,
        "passed": 0,
        "failed": 0,
        "runtime_failed": 0,
        "errors": 0,
        "avg_fast_score": 0,
        "avg_deep_score": 0,
        "avg_fast_time": 0,
        "avg_deep_time": 0,
        "total_issues": 0,
    })
    
    # Complexity analysis
    complexity_stats = defaultdict(lambda: {
        "sites": 0,
        "passed": 0,
        "runtime_failed": 0,
        "errors": 0,
    })
    
    # Collect all failures for analysis
    expectation_failures = []
    expectation_passes = []
    runtime_failures = []
    runtime_successes = []
    errors = []
    degraded_sites = []
    degraded_reason_counts = defaultdict(int)
    failure_reason_counts = defaultdict(int)
    deep_skipped_sites = []
    early_stop_reason_counts = defaultdict(int)
    pages_skipped_low_value_total = 0
    avg_page_time_values: list[float] = []

    def _is_runtime_failure(row: TestResult) -> bool:
        return row.site_status == "runtime_failed" or bool(row.error or row.degraded)

    def _failure_type(row: TestResult) -> Optional[str]:
        if _is_runtime_failure(row):
            return "runtime_failure"
        if not row.passed:
            return "score_out_of_range"
        return None

    def _runtime_failure_type(row: TestResult) -> Optional[str]:
        if not _is_runtime_failure(row):
            return None
        if row.runtime_failure_type:
            return row.runtime_failure_type
        return _classify_runtime_failure_reason(
            error=row.error,
            degraded_reason=row.degraded_reason,
            degraded=bool(row.degraded),
        )
    
    for r in processed_results:
        cat = r.site.category
        comp = r.site.complexity
        
        category_stats[cat]["sites"] += 1
        complexity_stats[comp]["sites"] += 1
        
        if _is_runtime_failure(r):
            category_stats[cat]["runtime_failed"] += 1
            complexity_stats[comp]["runtime_failed"] += 1
            runtime_failures.append(r)

            reason_key = r.failure_reason or _runtime_failure_type(r) or "unknown"
            failure_reason_counts[reason_key] += 1

            if r.error:
                category_stats[cat]["errors"] += 1
                complexity_stats[comp]["errors"] += 1
                errors.append(r)
        else:
            runtime_successes.append(r)

        if (not _is_runtime_failure(r)) and r.passed:
            category_stats[cat]["passed"] += 1
            complexity_stats[comp]["passed"] += 1
            expectation_passes.append(r)
        elif not _is_runtime_failure(r):
            category_stats[cat]["failed"] += 1
            expectation_failures.append(r)
        
        if r.degraded:
            degraded_sites.append(r)
            reason_key = r.failure_reason or _runtime_failure_type(r) or "partial_load"
            degraded_reason_counts[reason_key] += 1

        if r.deep_skipped:
            deep_skipped_sites.append(r)

        if r.early_stop_reason:
            early_stop_reason_counts[str(r.early_stop_reason)] += 1

        pages_skipped_low_value_total += int(r.pages_skipped_low_value or 0)
        if float(r.avg_page_time or 0.0) > 0.0:
            avg_page_time_values.append(float(r.avg_page_time))
        
        # Accumulate scores/times
        if r.fast_score is not None:
            category_stats[cat]["avg_fast_score"] += r.fast_score
        if r.deep_score is not None:
            category_stats[cat]["avg_deep_score"] += r.deep_score
        category_stats[cat]["avg_fast_time"] += r.fast_time
        category_stats[cat]["avg_deep_time"] += r.deep_time
        category_stats[cat]["total_issues"] += r.deep_issues
    
    # Calculate averages
    for cat, stats in category_stats.items():
        n = stats["sites"]
        if n > 0:
            stats["avg_fast_score"] = round(stats["avg_fast_score"] / n, 1)
            stats["avg_deep_score"] = round(stats["avg_deep_score"] / n, 1)
            stats["avg_fast_time"] = round(stats["avg_fast_time"] / n, 2)
            stats["avg_deep_time"] = round(stats["avg_deep_time"] / n, 2)
    
    # ══════════════════════════════════════════════════════════════════════════
    # REPORT
    # ══════════════════════════════════════════════════════════════════════════
    
    print("\n" + "="*80)
    print("  [SUMMARY] TEST RESULTS SUMMARY")
    print("="*80)
    
    total = len(processed_results)
    runtime_success_count = len(runtime_successes)
    runtime_failure_count = len(runtime_failures)
    expectation_pass_count = len(expectation_passes)
    expectation_fail_count = len(expectation_failures)
    errored = len(errors)
    scoring_completed_count = sum(1 for r in processed_results if r.scoring_completed)
    total_safe = max(1, total)
    
    print(f"\n  Total Sites:     {total}")
    print(f"  [RUN] Runtime Success: {runtime_success_count} ({100*runtime_success_count/total_safe:.1f}%)")
    print(f"  [RUN] Runtime Fail:    {runtime_failure_count} ({100*runtime_failure_count/total_safe:.1f}%)")
    print(f"  [RUN] Deep Skipped:    {len(deep_skipped_sites)}")
    print(f"  [SCORE] Completed:     {scoring_completed_count} ({100*scoring_completed_count/total_safe:.1f}%)")
    print(f"  [EXP] Expectation Pass: {expectation_pass_count} ({100*expectation_pass_count/total_safe:.1f}%)")
    print(f"  [EXP] Out of Range:     {expectation_fail_count} ({100*expectation_fail_count/total_safe:.1f}%)")
    print(f"  [ERR] Errors:       {errored} ({100*errored/total_safe:.1f}%)")
    print(f"  [DEG] Degraded:     {len(degraded_sites)} (browser fallback)")
    print(f"  [TIME] Total Time:   {total_time:.1f}s ({total_time/total_safe:.1f}s avg)")

    if use_rag and processed_results:
        rag_effectiveness_values = [r.deep_rag_effectiveness for r in processed_results if r.deep_rag_effectiveness > 0]
        fix_acceptance_values = [r.deep_fix_acceptance_rate for r in processed_results if r.deep_fix_acceptance_rate > 0]
        print(f"  [RAG] Effectiveness: {_safe_avg(rag_effectiveness_values):.1f}%")
        print(f"  [RAG] Fix Acceptance: {_safe_avg(fix_acceptance_values):.1f}%")
    
    # SPA detection stats
    spa_sites = [r for r in runtime_successes if r.is_spa]
    spa_frameworks = {}
    for r in spa_sites:
        fw = r.spa_framework or "generic"
        spa_frameworks[fw] = spa_frameworks.get(fw, 0) + 1

    spa_truth_labels = _load_spa_truth_labels(spa_truth_set_path)
    spa_truth_metrics = _compute_spa_truth_metrics(runtime_successes, spa_truth_labels)
    
    if spa_sites:
        print(f"\n  [SPA] SPA Sites:     {len(spa_sites)} detected")
        for fw, count in sorted(spa_frameworks.items(), key=lambda x: -x[1]):
            print(f"      {fw}: {count}")

    if spa_truth_metrics:
        cm = spa_truth_metrics["confusion_matrix"]
        print(
            f"  [SPA-TRUTH] Evaluated {spa_truth_metrics['evaluated_sites']} labeled sites "
            f"| TP/FP/FN/TN={cm['tp']}/{cm['fp']}/{cm['fn']}/{cm['tn']}"
        )
        print(
            f"              Precision={spa_truth_metrics['spa_precision']:.2%} "
            f"Recall={spa_truth_metrics['spa_recall']:.2%} "
            f"F1={spa_truth_metrics['spa_f1']:.2%}"
        )
    
    # Category breakdown
    print("\n" + "-"*80)
    print("  BY CATEGORY")
    print("-"*80)
    print(f"  {'Category':<15} {'Sites':>6} {'Pass':>6} {'Fail':>6} {'RunFail':>8} {'Err':>5} {'AvgScore':>9} {'AvgTime':>8}")
    print("-"*80)
    for cat in sorted(category_stats.keys()):
        s = category_stats[cat]
        print(f"  {cat:<15} {s['sites']:>6} {s['passed']:>6} {s['failed']:>6} {s['runtime_failed']:>8} {s['errors']:>5} {s['avg_deep_score']:>8.1f} {s['avg_deep_time']:>7.1f}s")
    
    # Complexity breakdown
    print("\n" + "-"*80)
    print("  BY COMPLEXITY")
    print("-"*80)
    for comp in ["simple", "moderate", "complex"]:
        s = complexity_stats[comp]
        rate = 100 * s["passed"] / s["sites"] if s["sites"] > 0 else 0
        print(f"  {comp:<12}: {s['passed']}/{s['sites']} expectation-pass ({rate:.0f}%), runtime-fail={s['runtime_failed']}")
    
    # SPA vs Non-SPA comparison
    spa_passed = sum(1 for r in spa_sites if r.passed)
    non_spa_sites = [r for r in runtime_successes if not r.is_spa]
    non_spa_passed = sum(1 for r in non_spa_sites if r.passed)
    
    print("\n" + "-"*80)
    print("  SPA vs NON-SPA PERFORMANCE")
    print("-"*80)
    if spa_sites:
        spa_pass_rate = 100 * spa_passed / len(spa_sites)
        print(f"  SPA sites:     {spa_passed}/{len(spa_sites)} passed ({spa_pass_rate:.0f}%)")
    if non_spa_sites:
        non_spa_pass_rate = 100 * non_spa_passed / len(non_spa_sites)
        print(f"  Non-SPA sites: {non_spa_passed}/{len(non_spa_sites)} passed ({non_spa_pass_rate:.0f}%)")
    
    # Failed sites detail
    if expectation_failures:
        print("\n" + "-"*80)
        print("  [FAIL] FAILED SITES (score outside expected range)")
        print("-"*80)
        for r in expectation_failures:
            exp_min, exp_max = r.site.expected_score_range
            spa_tag = f" [SPA:{r.spa_framework}]" if r.is_spa else ""
            print(f"  • {r.site.name:<25} Score: {r.deep_score:>3}/100  Expected: {exp_min}-{exp_max}{spa_tag}")
            if r.severity_breakdown:
                print(f"    Severity: {r.severity_breakdown}")

    if runtime_failures:
        print("\n" + "-"*80)
        print("  [RUN] RUNTIME FAILURES")
        print("-"*80)
        for r in runtime_failures:
            reason = r.failure_reason or _runtime_failure_type(r) or r.degraded_reason or r.error or "unknown"
            print(
                f"  • {r.site.name:<25} Type: runtime_failure"
                f" | Status: {r.site_status}"
                f" | Reason: {str(reason)[:70]}"
            )
    
    # Error sites detail
    if errors:
        print("\n" + "-"*80)
        print("  [ERR] ERROR SITES (could not complete scan)")
        print("-"*80)
        for r in errors:
            print(f"  • {r.site.name:<25} Error: {r.error[:50]}")
    
    # Degraded sites
    if degraded_sites:
        print("\n" + "-"*80)
        print("  [DEG] DEGRADED SCANS (browser engines failed, static-only results)")
        print("-"*80)
        for r in degraded_sites:
            print(
                f"  • {r.site.name:<25} Engines: {', '.join(r.deep_engines)} "
                f"| Reason: {r.degraded_reason or 'unknown'}"
            )

        if degraded_reason_counts:
            print("\n  Top degraded causes:")
            for reason, count in sorted(degraded_reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]:
                print(f"    - {reason}: {count}")
    
    # Top performing sites
    print("\n" + "-"*80)
    print("  [TOP10] TOP 10 PERFORMERS")
    print("-"*80)
    sorted_by_score = sorted(
        [r for r in processed_results if r.deep_score is not None],
        key=lambda x: x.deep_score,
        reverse=True
    )[:10]
    for i, r in enumerate(sorted_by_score, 1):
        spa_tag = f" [SPA]" if r.is_spa else ""
        print(f"  {i:2}. {r.site.name:<25} Score: {r.deep_score}/100 ({r.deep_time:.1f}s){spa_tag}")
    
    # Worst performing sites
    print("\n" + "-"*80)
    print("  [BOTTOM10] BOTTOM 10 PERFORMERS")
    print("-"*80)
    sorted_by_score_asc = sorted(
        [r for r in processed_results if r.deep_score is not None],
        key=lambda x: x.deep_score,
    )[:10]
    for i, r in enumerate(sorted_by_score_asc, 1):
        print(f"  {i:2}. {r.site.name:<25} Score: {r.deep_score}/100 Issues: {r.deep_issues}")
    
    # Performance outliers
    print("\n" + "-"*80)
    print("  [PERF] PERFORMANCE ANALYSIS")
    print("-"*80)
    fast_times = [r.fast_time for r in processed_results if r.fast_time > 0]
    deep_times = [r.deep_time for r in processed_results if r.deep_time > 0]
    
    if fast_times:
        print(f"  Fast mode:  avg={sum(fast_times)/len(fast_times):.1f}s  min={min(fast_times):.1f}s  max={max(fast_times):.1f}s")
    if deep_times:
        print(f"  Deep mode:  avg={sum(deep_times)/len(deep_times):.1f}s  min={min(deep_times):.1f}s  max={max(deep_times):.1f}s")
    
    slow_sites = [r for r in processed_results if (r.fast_time + r.deep_time) > float(max_site_time)]
    if slow_sites:
        print(f"\n  Slow sites (>{max_site_time}s cap): {len(slow_sites)}")
        for r in slow_sites:
            print(f"    • {r.site.name}: {(r.fast_time + r.deep_time):.1f}s")
    
    # ══════════════════════════════════════════════════════════════════════════
    # IMPROVEMENT RECOMMENDATIONS
    # ══════════════════════════════════════════════════════════════════════════
    
    print("\n" + "="*80)
    print("  [REC] IMPROVEMENT RECOMMENDATIONS")
    print("="*80)
    
    recommendations = []
    
    # Analyze failure patterns
    if degraded_sites:
        recommendations.append({
            "priority": "HIGH",
            "area": "Browser Engine",
            "issue": f"{len(degraded_sites)} sites had degraded scans (browser failure)",
            "action": "Improve Playwright stability, add retry logic, handle CSP/Cloudflare better"
        })
    
    complex_failures = [r for r in expectation_failures if r.site.complexity == "complex"]
    if expectation_failures and len(complex_failures) > len(expectation_failures) * 0.5:
        recommendations.append({
            "priority": "HIGH", 
            "area": "Complex Site Support",
            "issue": f"{len(complex_failures)} complex sites failed",
            "action": "Improve SPA detection, handle React/Angular hydration, wait for dynamic content"
        })
    
    if errors:
        timeout_errors = [r for r in errors if r.error == "TIMEOUT"]
        if timeout_errors:
            recommendations.append({
                "priority": "MEDIUM",
                "area": "Performance",
                "issue": f"{len(timeout_errors)} sites timed out",
                "action": "Optimize slow checks, add early-exit for problematic sites"
            })
    
    ecommerce_failures = [r for r in expectation_failures if r.site.category == "ecommerce"]
    if ecommerce_failures:
        recommendations.append({
            "priority": "MEDIUM",
            "area": "E-commerce Support",
            "issue": f"{len(ecommerce_failures)} e-commerce sites failed",
            "action": "Improve handling of lazy-loaded products, modal dialogs, cart systems"
        })
    
    social_failures = [r for r in expectation_failures if r.site.category == "social"]
    if social_failures:
        recommendations.append({
            "priority": "MEDIUM",
            "area": "Social Media Support",  
            "issue": f"{len(social_failures)} social media sites failed",
            "action": "Handle infinite scroll, embedded media, dynamic feeds"
        })
    
    # SPA-specific recommendations
    spa_failures = [r for r in expectation_failures if r.is_spa]
    if spa_failures:
        frameworks_failed = set(r.spa_framework or "generic" for r in spa_failures)
        recommendations.append({
            "priority": "MEDIUM",
            "area": "SPA Framework Support",
            "issue": f"{len(spa_failures)} SPA sites failed ({', '.join(frameworks_failed)})",
            "action": "Improve hydration detection and waiting logic for these frameworks"
        })
    
    for rec in recommendations:
        print(f"\n  [{rec['priority']}] {rec['area']}")
        print(f"    Issue:  {rec['issue']}")
        print(f"    Action: {rec['action']}")
    
    if not recommendations:
        print("\n  [OK] No critical issues found! Engine performing well.")
    
    # ══════════════════════════════════════════════════════════════════════════
    # SAVE REPORT
    # ══════════════════════════════════════════════════════════════════════════

    timeout_count = sum(1 for r in errors if str(r.error).upper() == "TIMEOUT")
    scoring_completed_count = sum(1 for r in processed_results if r.scoring_completed)
    required_fields_complete_count = sum(1 for r in processed_results if r.required_scoring_fields)
    runtime_success_rate = round((runtime_success_count / total) * 100, 1) if total else 0.0
    expectation_pass_rate = round((expectation_pass_count / total) * 100, 1) if total else 0.0
    degraded_rate = round((len(degraded_sites) / total) * 100, 1) if total else 0.0
    timeout_rate = round((timeout_count / total) * 100, 1) if total else 0.0
    failure_rate = round((runtime_failure_count / total) * 100, 1) if total else 0.0
    scoring_completed_rate = round((scoring_completed_count / total) * 100, 1) if total else 0.0
    required_fields_rate = round((required_fields_complete_count / total) * 100, 1) if total else 0.0
    avg_runtime = round(total_time / total, 2) if total else 0.0
    if not avg_page_time_values:
        avg_page_time_values = [
            (r.fast_time + r.deep_time) / max(1, int((r.fast_time > 0) + (r.deep_time > 0)))
            for r in processed_results
            if (r.fast_time + r.deep_time) > 0
        ]
    avg_page_time = round(_safe_avg(avg_page_time_values), 3)

    dominant_early_stop_reason = None
    if early_stop_reason_counts:
        dominant_early_stop_reason = sorted(
            early_stop_reason_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )[0][0]

    fast_mode_usage = round(
        (sum(1 for r in processed_results if r.fast_score is not None) / total) * 100,
        1,
    ) if total else 0.0

    def _p95(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        idx = max(0, min(len(ordered) - 1, int(0.95 * (len(ordered) - 1))))
        return round(float(ordered[idx]), 2)

    rag_completion_rate = None
    rag_effectiveness_rate = None
    fix_acceptance_rate = None
    if use_rag and processed_results:
        terminal_statuses = {"complete", "failed", "skipped", "off"}
        rag_terminal = sum(
            1
            for r in processed_results
            if str(r.deep_enrichment_status).strip().lower() in terminal_statuses
        )
        rag_completion_rate = round((rag_terminal / len(processed_results)) * 100, 1)
        effectiveness_values = [r.deep_rag_effectiveness for r in processed_results if r.deep_rag_effectiveness > 0]
        acceptance_values = [r.deep_fix_acceptance_rate for r in processed_results if r.deep_fix_acceptance_rate > 0]
        rag_effectiveness_rate = round(_safe_avg(effectiveness_values), 1) if effectiveness_values else 0.0
        fix_acceptance_rate = round(_safe_avg(acceptance_values), 1) if acceptance_values else 0.0
    
    failure_classification = []
    for r in processed_results:
        failure_type = _failure_type(r)
        if not failure_type:
            continue
        runtime_failure_type = _runtime_failure_type(r)
        failure_classification.append(
            {
                "name": r.site.name,
                "url": r.site.url,
                "failure_type": failure_type,
                "runtime_failure_type": runtime_failure_type,
                "site_status": r.site_status,
                "failure_reason": r.failure_reason,
                "scoring_completed": r.scoring_completed,
                "required_scoring_fields": r.required_scoring_fields,
                "score": r.deep_score,
                "expected": list(r.site.expected_score_range),
                "error": r.error,
                "degraded": r.degraded,
                "degraded_reason": r.degraded_reason,
            }
        )

    runtime_failure_classification = [
        {
            "name": r.site.name,
            "url": r.site.url,
            "failure_type": _runtime_failure_type(r),
            "site_status": r.site_status,
            "failure_reason": r.failure_reason,
            "scoring_completed": r.scoring_completed,
            "error": r.error,
            "degraded_reason": r.degraded_reason,
        }
        for r in runtime_failures
    ]

    report = {
        "timestamp": datetime.now().isoformat(),
        "total_time_seconds": round(total_time, 2),
        "configuration": {
            "rag_enabled": use_rag,
            "max_enrich_issues": max_enrich_issues if use_rag else 0,
            "cognitive_enabled": enable_cognitive,
            "max_site_time": int(max_site_time),
        },
        "summary": {
            "total": total,
            "runtime_successful": runtime_success_count,
            "runtime_failed": runtime_failure_count,
            "scoring_completed": scoring_completed_count,
            "required_scoring_fields_complete": required_fields_complete_count,
            "expectation_passed": expectation_pass_count,
            "expectation_failed": expectation_fail_count,
            "errors": errored,
            "degraded": len(degraded_sites),
            "spa_detected": len(spa_sites),
            "runtime_success_rate": runtime_success_rate,
            "timeout_rate": timeout_rate,
            "failure_rate": failure_rate,
            "avg_page_time": avg_page_time,
            "early_stop_reason": dominant_early_stop_reason,
            "pages_skipped_low_value": pages_skipped_low_value_total,
            "scoring_completed_rate": scoring_completed_rate,
            "required_scoring_fields_rate": required_fields_rate,
            "expectation_pass_rate": expectation_pass_rate,
        },
        "kpi": {
            "runtime_success_rate": runtime_success_rate,
            "timeout_rate": timeout_rate,
            "failure_rate": failure_rate,
            "avg_page_time": avg_page_time,
            "early_stop_reason": dominant_early_stop_reason,
            "pages_skipped_low_value": pages_skipped_low_value_total,
            "expectation_pass_rate": expectation_pass_rate,
            "degraded_rate": degraded_rate,
            "scoring_completed_rate": scoring_completed_rate,
            "required_scoring_fields_rate": required_fields_rate,
            "precision": None,
            "recall": None,
            "f1": None,
            "spa_precision": spa_truth_metrics["spa_precision"] if spa_truth_metrics else None,
            "spa_recall": spa_truth_metrics["spa_recall"] if spa_truth_metrics else None,
            "spa_f1": spa_truth_metrics["spa_f1"] if spa_truth_metrics else None,
            "rag_completion": rag_completion_rate,
            "rag_effectiveness": rag_effectiveness_rate,
            "fix_acceptance_rate": fix_acceptance_rate,
            "avg_runtime": avg_runtime,
            "fast_mode_p95_time": _p95(fast_times),
            "fast_mode_usage": fast_mode_usage,
        },
        "spa_detection": {
            "total_spa_sites": len(spa_sites),
            "frameworks": spa_frameworks,
            "spa_pass_rate": round(100 * spa_passed / len(spa_sites), 1) if spa_sites else 0,
        },
        "spa_confusion_matrix": spa_truth_metrics,
        "degraded_failure_analysis": {
            "top_causes": [
                {"reason": reason, "count": count}
                for reason, count in sorted(degraded_reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
            ]
        },
        "failure_breakdown": {
            "timeout": int(failure_reason_counts.get("timeout", 0)),
            "csp_block": int(failure_reason_counts.get("csp_block", 0)),
            "navigation_error": int(failure_reason_counts.get("navigation_error", 0)),
            "partial_load": int(failure_reason_counts.get("partial_load", 0)),
            "network_error": int(failure_reason_counts.get("network_error", 0)),
            "blocked_request": int(failure_reason_counts.get("blocked_request", 0)),
            "dns_failure": int(failure_reason_counts.get("dns_failure", 0)),
            "unknown": int(failure_reason_counts.get("unknown", 0)),
            # Backward-compatible legacy keys.
            "dom_parse_error": int(failure_reason_counts.get("dom_parse_error", 0)),
            "render_timeout": int(failure_reason_counts.get("render_timeout", 0)),
            "extraction_failure": int(failure_reason_counts.get("extraction_failure", 0)),
        },
        "category_stats": dict(category_stats),
        "complexity_stats": dict(complexity_stats),
        "results": [
            {
                "name": r.site.name,
                "url": r.site.url,
                "category": r.site.category,
                "complexity": r.site.complexity,
                "fast_score": r.fast_score,
                "deep_score": r.deep_score,
                "fast_issues": r.fast_issues,
                "deep_issues": r.deep_issues,
                "fast_time": round(r.fast_time, 2),
                "deep_time": round(r.deep_time, 2),
                "fast_rag_effectiveness": r.fast_rag_effectiveness,
                "deep_rag_effectiveness": r.deep_rag_effectiveness,
                "fast_fix_acceptance_rate": r.fast_fix_acceptance_rate,
                "deep_fix_acceptance_rate": r.deep_fix_acceptance_rate,
                "fast_enrichment_status": r.fast_enrichment_status,
                "deep_enrichment_status": r.deep_enrichment_status,
                "engines": r.deep_engines,
                "wcag_scs": r.wcag_scs,
                "severity": r.severity_breakdown,
                "passed": r.passed,
                "site_status": r.site_status,
                "failure_reason": r.failure_reason,
                "scoring_completed": r.scoring_completed,
                "required_scoring_fields": r.required_scoring_fields,
                "failure_type": _failure_type(r),
                "runtime_failure_type": _runtime_failure_type(r),
                "fast_degraded": r.fast_degraded,
                "fast_degraded_reason": r.fast_degraded_reason,
                "deep_degraded": r.deep_degraded,
                "deep_degraded_reason": r.deep_degraded_reason,
                "degraded": r.degraded,
                "degraded_reason": r.degraded_reason,
                "error": r.error,
                "is_spa": r.is_spa,
                "spa_framework": r.spa_framework,
                "deep_skipped": r.deep_skipped,
                "deep_skip_reason": r.deep_skip_reason,
                "early_stop_reason": r.early_stop_reason,
                "pages_skipped_low_value": r.pages_skipped_low_value,
                "avg_page_time": r.avg_page_time,
            }
            for r in processed_results
        ],
        "failure_classification": failure_classification,
        "runtime_failure_classification": runtime_failure_classification,
        "failures": [
            {
                "name": row["name"],
                "url": row["url"],
                "failure_type": row["failure_type"],
                "score": row["score"],
                "expected": row["expected"],
            }
            for row in failure_classification
        ],
        "errors": [
            {"name": r.site.name, "error": r.error}
            for r in errors
        ],
        "recommendations": recommendations,
    }

    record_operational_event(
        "benchmark_run_summary",
        {
            "run_type": "50_site",
            "timestamp": report.get("timestamp"),
            "total_sites": total,
            "runtime_success_rate": runtime_success_rate,
            "timeout_rate": timeout_rate,
            "failure_rate": failure_rate,
            "avg_page_time": avg_page_time,
            "early_stop_reason": dominant_early_stop_reason,
            "pages_skipped_low_value": pages_skipped_low_value_total,
            "deep_skipped_sites": len(deep_skipped_sites),
        },
    )
    
    # Save to file
    if output_path:
        out_path = output_path
    else:
        filename = "50_sites_test_results_rag.json" if use_rag else "50_sites_test_results.json"
        out_path = os.path.join(os.path.dirname(__file__), filename)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n  [REPORT] Full report saved to: {out_path}")
    print("="*80 + "\n")
    
    return report


def _compact_run_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": report.get("timestamp"),
        "total_time_seconds": report.get("total_time_seconds", 0.0),
        "summary": report.get("summary", {}),
        "kpi": report.get("kpi", {}),
        "results": [
            {
                "name": row.get("name"),
                "url": row.get("url"),
                "site_status": row.get("site_status"),
                "scoring_completed": row.get("scoring_completed"),
                "required_scoring_fields": row.get("required_scoring_fields"),
                "deep_score": row.get("deep_score"),
                "failure_reason": row.get("failure_reason") or row.get("runtime_failure_type"),
            }
            for row in report.get("results", [])
        ],
    }


def _completed_order_signature(report: dict[str, Any], include_site_keys: Optional[set[str]] = None) -> list[str]:
    completed_rows = [
        row
        for row in report.get("results", [])
        if row.get("site_status") == "completed" and isinstance(row.get("deep_score"), (int, float))
    ]
    if include_site_keys is not None:
        completed_rows = [
            row
            for row in completed_rows
            if (_normalize_site_url(str(row.get("url") or "")) or str(row.get("name") or "")) in include_site_keys
        ]
    ordered = sorted(
        completed_rows,
        key=lambda row: (-float(row.get("deep_score") or 0.0), str(row.get("name") or "").lower()),
    )
    return [f"{row.get('name')}:{float(row.get('deep_score') or 0.0):.1f}" for row in ordered]


def _compute_determinism(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        return {
            "deterministic_score_variance": 0.0,
            "deterministic_order_variance": 0,
            "status_consistency_rate": 0.0,
            "score_variance_by_site": {},
            "order_signatures": [],
        }

    site_runs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run_idx, report in enumerate(reports, start=1):
        for row in report.get("results", []):
            site_key = _normalize_site_url(str(row.get("url") or "")) or str(row.get("name") or f"site-{run_idx}")
            site_runs[site_key].append(
                {
                    "run": run_idx,
                    "name": row.get("name"),
                    "deep_score": row.get("deep_score"),
                    "site_status": row.get("site_status"),
                }
            )

    score_variance_by_site: dict[str, Any] = {}
    max_score_variance = 0.0
    consistent_status_sites = 0

    for site_key, rows in site_runs.items():
        status_values = [str(item.get("site_status") or "") for item in rows]
        status_consistent = len(set(status_values)) == 1 and len(status_values) == len(reports)
        if status_consistent:
            consistent_status_sites += 1

        score_values = [item.get("deep_score") for item in rows]
        numeric_scores = [float(value) for value in score_values if isinstance(value, (int, float))]
        variance = None
        if len(numeric_scores) == len(reports):
            variance = round(max(numeric_scores) - min(numeric_scores), 3)
            max_score_variance = max(max_score_variance, variance)

        score_variance_by_site[site_key] = {
            "name": rows[0].get("name"),
            "scores": score_values,
            "status_values": status_values,
            "status_consistent": status_consistent,
            "variance": variance,
        }

    common_completed_site_keys: set[str] = set()
    for site_key, rows in site_runs.items():
        if len(rows) != len(reports):
            continue
        if all(
            str(item.get("site_status") or "") == "completed"
            and isinstance(item.get("deep_score"), (int, float))
            for item in rows
        ):
            common_completed_site_keys.add(site_key)

    order_signatures = [
        _completed_order_signature(report, include_site_keys=common_completed_site_keys)
        for report in reports
    ]
    base_signature = order_signatures[0] if order_signatures else []
    deterministic_order_variance = 0
    for signature in order_signatures[1:]:
        max_len = max(len(base_signature), len(signature))
        for idx in range(max_len):
            left = base_signature[idx] if idx < len(base_signature) else None
            right = signature[idx] if idx < len(signature) else None
            if left != right:
                deterministic_order_variance += 1

    status_consistency_rate = round((consistent_status_sites / max(1, len(site_runs))) * 100, 1)
    return {
        "deterministic_score_variance": round(max_score_variance, 3),
        "deterministic_order_variance": int(deterministic_order_variance),
        "status_consistency_rate": status_consistency_rate,
        "common_completed_site_count": len(common_completed_site_keys),
        "score_variance_by_site": score_variance_by_site,
        "order_signatures": order_signatures,
    }


def _run_sensitivity_checks() -> dict[str, Any]:
    from app.services.prioritizer import build_scoring_summary

    def issue(
        rule_id: str,
        *,
        issue_type: str,
        wcag_level: str,
        element_type: str,
        frequency: int,
        user_impact: str,
        severity: str,
    ) -> dict[str, Any]:
        return {
            "rule_id": rule_id,
            "issue_type": issue_type,
            "wcag_level": wcag_level,
            "element_type": element_type,
            "frequency": frequency,
            "user_impact": user_impact,
            "severity": severity,
            "message": f"{rule_id} issue",
            "domain": "forms" if element_type in {"input", "button", "form"} else "structure",
            "fix": {"description": f"Fix {rule_id}"},
        }

    baseline = build_scoring_summary(
        [issue("color-contrast", issue_type="violation", wcag_level="AA", element_type="text", frequency=2, user_impact="confusing", severity="moderate")]
    )
    with_critical = build_scoring_summary(
        [
            issue("color-contrast", issue_type="violation", wcag_level="AA", element_type="text", frequency=2, user_impact="confusing", severity="moderate"),
            issue("missing-label", issue_type="violation", wcag_level="A", element_type="input", frequency=1, user_impact="blocks action", severity="critical"),
        ]
    )
    score_sensitivity_drop_critical = round(float(baseline.get("overall_score", 0.0)) - float(with_critical.get("overall_score", 0.0)), 3)

    with_major_group = build_scoring_summary(
        [
            issue("link-purpose", issue_type="violation", wcag_level="AA", element_type="link", frequency=7, user_impact="confusing", severity="major"),
            issue("link-purpose", issue_type="violation", wcag_level="AA", element_type="link", frequency=5, user_impact="confusing", severity="major"),
            issue("missing-alt", issue_type="violation", wcag_level="AA", element_type="image", frequency=1, user_impact="minor", severity="minor"),
        ]
    )
    without_major_group = build_scoring_summary(
        [issue("missing-alt", issue_type="violation", wcag_level="AA", element_type="image", frequency=1, user_impact="minor", severity="minor")]
    )
    score_sensitivity_gain_fix = round(float(without_major_group.get("overall_score", 0.0)) - float(with_major_group.get("overall_score", 0.0)), 3)

    duplicate_pattern_summary = build_scoring_summary(
        [
            issue("missing-alt", issue_type="violation", wcag_level="AA", element_type="image", frequency=2, user_impact="minor", severity="minor"),
            issue("missing-alt", issue_type="violation", wcag_level="AA", element_type="image", frequency=3, user_impact="minor", severity="minor"),
            issue("missing-alt", issue_type="violation", wcag_level="AA", element_type="image", frequency=1, user_impact="minor", severity="minor"),
        ]
    )
    pattern_groups = ((duplicate_pattern_summary.get("issue_groupings") or {}).get("by_pattern") or [])
    grouping_stable = bool(pattern_groups and len(pattern_groups) == 1 and int(pattern_groups[0].get("issue_count", 0)) == 3)

    severity_probe = build_scoring_summary(
        [
            issue("critical-form", issue_type="violation", wcag_level="A", element_type="input", frequency=3, user_impact="blocks action", severity="critical"),
            issue("major-nav", issue_type="violation", wcag_level="AA", element_type="link", frequency=2, user_impact="confusing", severity="major"),
            issue("minor-text", issue_type="violation", wcag_level="AAA", element_type="text", frequency=1, user_impact="minor", severity="minor"),
        ]
    )
    breakdown = severity_probe.get("severity_breakdown", {})
    expected = {"critical": 1, "major": 1, "minor": 1}
    matched = sum(1 for key, expected_count in expected.items() if int(breakdown.get(key, 0)) == expected_count)
    severity_bucket_accuracy = round(matched / len(expected), 3)

    return {
        "score_sensitivity_drop_critical": score_sensitivity_drop_critical,
        "score_sensitivity_gain_fix": score_sensitivity_gain_fix,
        "grouping_stability": grouping_stable,
        "severity_bucket_accuracy": severity_bucket_accuracy,
        "passed": bool(
            score_sensitivity_drop_critical > 0
            and score_sensitivity_gain_fix > 0
            and grouping_stable
            and severity_bucket_accuracy == 1.0
        ),
    }


def _verify_telemetry_fields(subset_sites: list["SiteTestCase"]) -> dict[str, Any]:
    from app.config import settings

    logs_dir = Path(getattr(settings, "logs_dir", "./logs"))
    telemetry_path = logs_dir / str(getattr(settings, "telemetry_filename", "telemetry.jsonl"))
    if not telemetry_path.exists():
        return {
            "telemetry_path": str(telemetry_path),
            "events_scanned": 0,
            "field_coverage": {field: 0 for field in REQUIRED_TELEMETRY_FIELDS},
            "missing_fields": list(REQUIRED_TELEMETRY_FIELDS),
            "passed": False,
        }

    subset_urls = {_normalize_site_url(site.url) for site in subset_sites}
    relevant_events: list[dict[str, Any]] = []

    with telemetry_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if payload.get("event_type") != "audit":
                continue
            event_url = _normalize_site_url(str(payload.get("url") or ""))
            if event_url in subset_urls:
                relevant_events.append(payload)

    field_coverage = {field: 0 for field in REQUIRED_TELEMETRY_FIELDS}
    for event in relevant_events:
        for field in REQUIRED_TELEMETRY_FIELDS:
            if field in event:
                field_coverage[field] += 1

    missing_fields = [field for field, count in field_coverage.items() if count == 0]
    return {
        "telemetry_path": str(telemetry_path),
        "events_scanned": len(relevant_events),
        "field_coverage": field_coverage,
        "missing_fields": missing_fields,
        "passed": bool(relevant_events) and not missing_fields,
    }


def _write_json(path: str, payload: dict[str, Any]) -> str:
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return str(out_path)


async def run_phase5_clean_validation(
    *,
    sites: list["SiteTestCase"],
    parallel_limit: int,
    use_rag: bool,
    max_enrich_issues: int,
    enable_cognitive: bool,
    spa_truth_set_path: Optional[str],
    max_site_time: int,
    repeat: int,
    output_path: Optional[str],
    clean_validation_out: str,
    kpi_report_out: str,
) -> dict[str, Any]:
    if repeat < 1:
        repeat = 1

    run_reports: list[dict[str, Any]] = []
    run_output_paths: list[str] = []

    for run_idx in range(1, repeat + 1):
        if output_path:
            base = Path(output_path)
            if base.suffix.lower() == ".json":
                run_output = str(base.with_name(f"{base.stem}_run_{run_idx}{base.suffix}"))
            else:
                run_output = str(base / f"phase5_run_{run_idx}.json")
        else:
            run_output = str(Path(__file__).resolve().parent / f"phase5_subset_run_{run_idx}.json")

        logger.info("Phase5 validation run %s/%s starting", run_idx, repeat)
        report = await run_50_site_test(
            parallel_limit=parallel_limit,
            sites=sites,
            use_rag=use_rag,
            max_enrich_issues=max_enrich_issues,
            enable_cognitive=enable_cognitive,
            spa_truth_set_path=spa_truth_set_path,
            max_site_time=max_site_time,
            output_path=run_output,
        )
        run_reports.append(report)
        run_output_paths.append(run_output)

    determinism_check = _compute_determinism(run_reports)
    sensitivity_tests = _run_sensitivity_checks()
    telemetry_verification = _verify_telemetry_fields(sites)

    run_durations = [float(report.get("total_time_seconds", 0.0) or 0.0) for report in run_reports]
    runtime_success_rates = [float((report.get("kpi") or {}).get("runtime_success_rate", 0.0) or 0.0) for report in run_reports]
    timeout_cap_violations = 0
    for report in run_reports:
        for row in report.get("results", []):
            elapsed = float(row.get("fast_time", 0.0) or 0.0) + float(row.get("deep_time", 0.0) or 0.0)
            if elapsed > (float(max_site_time) + 1.0):
                timeout_cap_violations += 1

    runtime_stability = {
        "max_site_time": int(max_site_time),
        "repeat_runs": int(repeat),
        "run_output_paths": run_output_paths,
        "run_durations_seconds": [round(value, 2) for value in run_durations],
        "all_runs_within_15_min": all(value <= 900.0 for value in run_durations),
        "site_timeout_cap_violations": int(timeout_cap_violations),
        "sites_completed_without_abort": min(int((report.get("summary") or {}).get("total", 0) or 0) for report in run_reports),
        "runtime_success_rate_avg": round(_safe_avg(runtime_success_rates), 1),
        "telemetry_verification": telemetry_verification,
        "required_audit_fields": list(REQUIRED_AUDIT_FIELDS),
        "required_telemetry_fields": list(REQUIRED_TELEMETRY_FIELDS),
    }

    clean_validation_payload = {
        "subset_sites": [
            {
                "name": site.name,
                "url": site.url,
                "category": site.category,
                "complexity": site.complexity,
            }
            for site in sites
        ],
        "run_1": _compact_run_report(run_reports[0]) if len(run_reports) >= 1 else {},
        "run_2": _compact_run_report(run_reports[1]) if len(run_reports) >= 2 else {},
        "run_3": _compact_run_report(run_reports[2]) if len(run_reports) >= 3 else {},
        "determinism_check": determinism_check,
        "sensitivity_tests": sensitivity_tests,
        "runtime_stability": runtime_stability,
    }

    kpi_payload = {
        "deterministic_score_variance": determinism_check.get("deterministic_score_variance", 0.0),
        "deterministic_order_variance": determinism_check.get("deterministic_order_variance", 0),
        "score_sensitivity_drop_critical": sensitivity_tests.get("score_sensitivity_drop_critical", 0.0),
        "score_sensitivity_gain_fix": sensitivity_tests.get("score_sensitivity_gain_fix", 0.0),
        "severity_bucket_accuracy": sensitivity_tests.get("severity_bucket_accuracy", 0.0),
        "runtime_success_rate": runtime_stability.get("runtime_success_rate_avg", 0.0),
        "sites_completed_without_abort": runtime_stability.get("sites_completed_without_abort", 0),
        "grouping_stability": sensitivity_tests.get("grouping_stability", False),
        "telemetry_fields_present": telemetry_verification.get("passed", False),
    }

    clean_validation_path = _write_json(clean_validation_out, clean_validation_payload)
    kpi_report_path = _write_json(kpi_report_out, kpi_payload)

    logger.info("Phase5 clean validation artifact: %s", clean_validation_path)
    logger.info("Phase5 KPI artifact: %s", kpi_report_path)

    return {
        "clean_validation_path": clean_validation_path,
        "kpi_report_path": kpi_report_path,
        "determinism_check": determinism_check,
        "sensitivity_tests": sensitivity_tests,
        "runtime_stability": runtime_stability,
    }


async def run_quick_test(n_sites: int = 10):
    """Run a quick test with first N sites for rapid iteration."""
    return await run_50_site_test(parallel_limit=2, sites=TEST_SITES[:n_sites])


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="BEACON 50-Site Test Suite")
    parser.add_argument("--quick", type=int, default=0, help="Quick test with N sites")
    parser.add_argument("--parallel", type=int, default=3, help="Parallel site limit")
    parser.add_argument("--category", type=str, default=None, help="Test specific category only")
    parser.add_argument("--subset", type=str, default=None, help="Optional subset JSON (15-20 stable sites)")
    parser.add_argument("--rag", action="store_true", help="Enable RAG enrichment during fast and deep scans")
    parser.add_argument("--max-enrich-issues", type=int, default=20, help="Max issues to enrich with RAG context")
    parser.add_argument("--no-cognitive", action="store_true", help="Disable cognitive checks for deep scan")
    parser.add_argument("--spa-truth-set", type=str, default=None, help="Optional SPA truth-set JSON for confusion metrics")
    parser.add_argument("--max-site-time", type=int, default=30, help="Hard per-site runtime cap in seconds")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat full run N times for stability validation")
    parser.add_argument(
        "--phase5-clean-validation-out",
        type=str,
        default="tests/phase5_clean_validation.json",
        help="Output path for Phase 5 clean validation artifact",
    )
    parser.add_argument(
        "--phase5-kpi-report-out",
        type=str,
        default="tests/phase5_kpi_report.json",
        help="Output path for Phase 5 KPI artifact",
    )
    parser.add_argument("--output", type=str, default=None, help="Custom output JSON path")
    args = parser.parse_args()
    
    if args.category:
        sites = [s for s in TEST_SITES if s.category == args.category]
        print(f"Testing {len(sites)} sites in category: {args.category}")
    elif args.quick > 0:
        sites = TEST_SITES[:args.quick]
        print(f"Quick test with {args.quick} sites")
    else:
        sites = TEST_SITES

    if args.subset:
        sites = _load_subset_sites(args.subset, TEST_SITES)
        print(f"Loaded deterministic subset: {len(sites)} sites from {args.subset}")

    if args.repeat > 1:
        validation_result = asyncio.run(
            run_phase5_clean_validation(
                sites=sites,
                parallel_limit=args.parallel,
                use_rag=args.rag,
                max_enrich_issues=args.max_enrich_issues,
                enable_cognitive=not args.no_cognitive,
                spa_truth_set_path=args.spa_truth_set,
                max_site_time=args.max_site_time,
                repeat=args.repeat,
                output_path=args.output,
                clean_validation_out=args.phase5_clean_validation_out,
                kpi_report_out=args.phase5_kpi_report_out,
            )
        )
        print(f"Phase5 clean validation artifact: {validation_result['clean_validation_path']}")
        print(f"Phase5 KPI artifact: {validation_result['kpi_report_path']}")
    else:
        asyncio.run(
            run_50_site_test(
                parallel_limit=args.parallel,
                sites=sites,
                use_rag=args.rag,
                max_enrich_issues=args.max_enrich_issues,
                enable_cognitive=not args.no_cognitive,
                spa_truth_set_path=args.spa_truth_set,
                max_site_time=args.max_site_time,
                output_path=args.output,
            )
        )
