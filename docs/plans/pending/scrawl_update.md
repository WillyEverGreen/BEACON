# BEACON Engine — Production Readiness Plan v3
**Version:** Phase 13–17  
**Prepared:** April 2026  
**Scope:** audit_runner.py · static_checks.py · dashboard_api.py · crawl_orchestrator.py · scan_mode_runner.py · bfs_crawler.py · dom_crawler.py · sitemap_crawler.py · parallel_runner.py · failure_taxonomy.py · page_auditor.py · page_selector.py · test suite  
**Prerequisite context:** Phase 12 suppression fixes landed. ACT recall critically low. Mode-consistency gap confirmed in MusicBlocks benchmark (Fast: `extraction_failure`, Deep/Max: `network_error` + `html-incomplete`). Crawler gap analysis complete (17 gaps identified across crawl layer). CSP failures partially handled but not robustly normalised. Four new runtime-intelligence gaps added (Phase 17): site-level failure profile aggregation, adaptive crawl strategy based on failure type, domain-level preflight cache, and a learning-system forward plan. **Stack upgraded (v3):** `httpx` replaced by `curl_cffi` for all HTTP; vanilla Playwright Chromium replaced by `Camoufox` for all browser sessions.

---

## Priority Legend

| Symbol | Meaning |
|--------|---------|
| 🔴 MUST | Will cause hang, loop, silent failure, or data corruption on real sites |
| 🟡 SHOULD | Causes degraded quality, bad metrics, or inconsistent operator-visible behaviour |
| 🟢 NICE | Observability, polish, edge-case hardening |

---

## Stack Decisions (v3 — April 2026)

These are **direct replacements**, not fallbacks. Both tools are used as the primary option from the first request. The old libraries are fully removed.

| Old (Dropped) | New (Direct Replacement) | Scope | Reason |
|---|---|---|---|
| `httpx` | `curl_cffi` (`AsyncSession`) | All HTTP — preflight, BFS, sitemap, Fast-mode fetch | `httpx` has a static non-browser TLS/JA3 fingerprint. CDNs (Cloudflare, Akamai, Fastly) drop the connection at the TLS handshake before returning an HTTP status code. This makes every CDN block look like a `ConnectError`, routing it to `connectivity_blocked` when it should be `bot_wall`. `curl_cffi(impersonate="chrome")` forges a real Chrome TLS fingerprint so failures surface as real HTTP 403/429 codes. |
| `playwright.chromium` (vanilla) | `Camoufox` (`AsyncNewBrowser`) | All browser sessions — `DOMCrawler`, `browser_probes.py`, `scan_mode_runner.py` | Vanilla Chromium with CDP is detectable by Cloudflare Turnstile, DataDome, and Akamai at the JS challenge layer. The site renders a CAPTCHA page, and BEACON scores it as 0 accessibility issues (100/100), silently corrupting the audit. Camoufox spoofs canvas, WebGL, audio context, and font fingerprints at the C++ level via Firefox's Juggler isolation — a fundamentally different protocol from CDP. |
| Custom UA-rotation logic | Removed | `bfs_crawler.py`, `sitemap_crawler.py`, preflight | `curl_cffi(impersonate="chrome")` handles UA + TLS + HTTP/2 frame order together. Standalone UA strings are insufficient and are now redundant. |
| `playwright-stealth` patches (if any) | Removed | `dom_crawler.py`, `scan_mode_runner.py` | Camoufox handles stealth at a lower level than Python-layer patches can reach. Removing patches reduces complexity. |

### Dependency Requirements (Apply to `requirements.txt` / `pyproject.toml`)

| Package | Version | Action |
|---|---|---|
| `curl_cffi` | `>=0.7.0` | **ADD** (replaces `httpx`) |
| `camoufox[geoip]` | `>=0.4.0` | **ADD** (replaces `playwright.chromium` launch) |
| `httpx` | - | **REMOVE** |
| `playwright-stealth` | - | **REMOVE** |

> **Why direct replacement, not fallback?**
> A fallback architecture requires the first (non-stealthy) request to fail before retrying. For HTTP, this means waiting for a TLS-layer connection reset — which looks like a real `ConnectError` and causes `normalize_failure()` to misroute. For browser sessions, it means a CAPTCHA page runs through static checks and produces a corrupt score. By using the new stack from the start, every failure that reaches `normalize_failure()` is a genuine, correctly categorised HTTP response.

---

## Executive Summary

BEACON's audit and crawl pipelines are functionally working but have four stacked failure layers that prevent production deployment:

1. **Failure normalisation gap** — No single function owns the translation from raw exceptions/codes into canonical `DegradedReason` values. `_classify_exception` and `_classify_audit_result` can still diverge independently of the enum, and CSP failures collapse into generic `network_error` or `extraction_failure` depending on which code path fires first.

2. **Crawler reliability gap** — Six MUST-fix bugs in `bfs_crawler.py`, `dom_crawler.py`, `sitemap_crawler.py`, `scan_mode_runner.py`, and `parallel_runner.py` will cause crawls to hang, leak Playwright subprocesses, or silently downgrade scan modes on any real-world site.

3. **Coverage gap** — ACT recall is critically low. Rule gaps are the root cause. No gap matrix exists yet to drive rule work.

4. **Operational gap** — No health endpoints, no structured error budgets, no confidence score surfaced to users, no backpressure. The INR-tier SaaS model will burn money and fail silently under load.

5. **Runtime-intelligence gap** — Failures are normalised per page but never aggregated at site level, so operators cannot distinguish a single flaky page from a site-wide bot-wall. The crawl strategy is static — it degrades uniformly on rate-limit, bot-wall, and CSP failures even though each warrants a completely different response. Preflight results are not shared across parallel pages of the same domain, so HEAD requests are repeated unnecessarily.

Each part below is independently shippable. Do not start Part 2 until Part 1's acceptance tests are green.

---

## Part 1 — Failure Normalisation & Mode Consistency (Phase 13)

This is the most important part. Everything downstream — scoring, trust, dashboard display — depends on failures being named consistently. Fix the naming layer first, before fixing individual callers.

---

### 1.0  The Missing Layer: `normalize_failure()` — `failure_taxonomy.py` 🔴 MUST

**Problem (new — not in previous plan):** The previous plan added a `DegradedReason` enum, which is necessary but not sufficient. Two independent classifier functions (`_classify_exception` in `crawl_orchestrator.py` and `_classify_audit_result` in `audit_runner.py`) each apply their own logic to map raw errors into reason strings. Even after the enum is added, they can produce different enum values for the same root cause — the divergence is structural, not just a vocabulary problem.

Additionally, `429` responses currently map to `blocked_request` (same bucket as `403` CAPTCHA walls). Rate-limited sites are recoverable; CAPTCHA-blocked sites are not. Conflating them causes the orchestrator to abort a crawl that could have succeeded with a short backoff.

CSP failures are partially detected in `browser_probes.py:675` and `audit_runner.py:1271` but can still collapse into `network_error` or `extraction_failure` depending on path, causing the exact MusicBlocks mode-inconsistency you observed.

**Fix — add `normalize_failure()` as the single source of truth:**

```python
# failure_taxonomy.py

# Extend STANDARD_DEGRADED_REASONS with new explicit codes:
STANDARD_DEGRADED_REASONS: Final[frozenset[str]] = frozenset({
    "connectivity_blocked",
    "browser_navigation_failed",
    "extraction_failed",
    "render_timeout",
    "partial_content",
    "engine_error",
    "rate_limited",        # ← NEW: 429 / Retry-After; recoverable
    "csp_blocked",         # ← NEW: CSP prevented script injection (browser path)
    "csp_injection_blocked", # ← NEW: axe/probe script blocked by CSP header
    "bot_wall",            # ← NEW: CAPTCHA / JS challenge (non-recoverable without proxy)
})

def normalize_failure(
    raw: str | Exception | int | None,
    *,
    http_status: int | None = None,
    headers: dict | None = None,
) -> DegradedReason:
    """
    Single source of truth for failure → DegradedReason translation.
    Call this EVERYWHERE a failure reason is derived — never derive inline.

    Checks in priority order:
    1. HTTP 429 with or without Retry-After  → rate_limited
    2. HTTP 403 / CAPTCHA signature          → bot_wall
    3. CSP header present on failure         → csp_blocked
    4. CSP injection error text              → csp_injection_blocked
    5. DNS / connect error                   → connectivity_blocked
    6. Playwright navigation error           → browser_navigation_failed
    7. Render / stability timeout            → render_timeout
    8. HTML usable but incomplete            → extraction_failed
    9. Internal exception                    → engine_error
    10. Unknown                              → engine_error
    """
    headers = headers or {}

    # 1. Rate limiting (recoverable)
    if http_status == 429 or (isinstance(raw, str) and "429" in raw):
        return DegradedReason.RATE_LIMITED

    # 2. Bot wall (non-recoverable)
    if http_status == 403 or _is_captcha_signature(raw, headers):
        return DegradedReason.BOT_WALL

    # 3 & 4. CSP
    if _has_csp_block_header(headers):
        return DegradedReason.CSP_BLOCKED
    if _is_csp_injection_error(raw):
        return DegradedReason.CSP_INJECTION_BLOCKED

    # 5. Network-level unreachable
    if _is_connect_error(raw):
        return DegradedReason.CONNECTIVITY_BLOCKED

    # 6. Browser navigation failure
    if _is_nav_error(raw):
        return DegradedReason.BROWSER_NAV_FAILED

    # 7. Render timeout
    if _is_timeout(raw):
        return DegradedReason.RENDER_TIMEOUT

    # 8. Extraction failure (got HTML, unusable)
    if _is_extraction_error(raw):
        return DegradedReason.EXTRACTION_FAILED

    # 9 & 10. Fallback
    return DegradedReason.ENGINE_ERROR
```

**Enforcement rule:** No file outside `failure_taxonomy.py` may construct a `DegradedReason` value from a raw string, exception, or HTTP status. Every caller must call `normalize_failure()`. Add a `# noqa: BEACON-F001` lint comment to legitimate bypass sites (there should be zero).

**Where:** Add to `failure_taxonomy.py`. Replace every inline `degraded_reason =` assignment in `audit_runner.py`, `crawl_orchestrator.py`, `scan_mode_runner.py`, `browser_probes.py`, and `run_scan_validation.py`.

---

### 1.1  Canonical `DegradedReason` Enum — `failure_taxonomy.py` 🔴 MUST

**Extended enum to match `normalize_failure()`:**

```python
class DegradedReason(str, Enum):
    CONNECTIVITY_BLOCKED     = "connectivity_blocked"
    BROWSER_NAV_FAILED       = "browser_navigation_failed"
    EXTRACTION_FAILED        = "extraction_failed"
    RENDER_TIMEOUT           = "render_timeout"
    PARTIAL_CONTENT          = "partial_content"
    ENGINE_ERROR             = "engine_error"
    RATE_LIMITED             = "rate_limited"         # recoverable
    CSP_BLOCKED              = "csp_blocked"          # browser probe blocked by CSP
    CSP_INJECTION_BLOCKED    = "csp_injection_blocked" # axe script injection blocked
    BOT_WALL                 = "bot_wall"             # CAPTCHA / JS challenge
```

**Where:** `failure_taxonomy.py`, imported by all other modules. No module defines its own reason strings.

---

### 1.2  CSP Failure Hardening — `browser_probes.py` + `audit_runner.py` 🔴 MUST

**Problem:** The MusicBlocks run shows Fast degrading with `extraction_failure` while Deep/Max produce `html-incomplete` — the root cause is a navigation/network failure at `musicblocks_mode_comparison_direct.json:1579` (`render_navigation` + `network_error`), not a strict CSP issue. But CSP-caused failures have the same symptom profile and collapse into the same ambiguous codes at `browser_probes.py:675` and `audit_runner.py:1271`.

**Fix — explicit CSP detection at injection points:**

```python
# browser_probes.py — around L675
try:
    await page.evaluate(axe_script)
except PlaywrightError as e:
    reason = normalize_failure(e)   # will return CSP_INJECTION_BLOCKED if CSP fingerprint
    return ProbeResult(success=False, degraded_reason=reason)

# audit_runner.py — around L1271
if "Content-Security-Policy" in response.headers:
    csp_header = response.headers["Content-Security-Policy"]
    if _csp_blocks_inline_scripts(csp_header):
        return normalize_failure(None, headers=response.headers)
        # returns DegradedReason.CSP_BLOCKED
```

**CSP detection helper:**
```python
def _csp_blocks_inline_scripts(csp: str) -> bool:
    """Returns True if CSP header would block axe-core injection."""
    directives = {d.strip().split()[0]: d.strip() for d in csp.split(";")}
    script_src = directives.get("script-src", directives.get("default-src", ""))
    return ("'unsafe-inline'" not in script_src and "nonce-" not in script_src)
```

**Where:** `browser_probes.py` L670–680, `audit_runner.py` L1268–1275, `run_scan_validation.py` L302–308.

---

### 1.3  Shared Network Preflight — `audit_runner.py` 🔴 MUST

**Problem:** Each mode independently attempts to reach the URL. Fast, Deep, and Max can produce three different failure reasons for one DNS failure.

**Fix — single `_preflight_check()` before mode dispatch:**

```python
@dataclass
class PreflightResult:
    reachable: bool
    latency_ms: int
    degraded_reason: DegradedReason | None
    http_status: int | None = None
    headers: dict = field(default_factory=dict)
    retry_after_seconds: float | None = None   # populated when RATE_LIMITED

async def _preflight_check(url: str) -> PreflightResult:
    # curl_cffi impersonates Chrome TLS/JA3 + HTTP/2 frame order.
    # CDN blocks now return real HTTP 403/429 instead of a bare ConnectError,
    # so normalize_failure() routes them to bot_wall / rate_limited correctly.
    from curl_cffi import AsyncSession
    from curl_cffi.requests.errors import RequestsError
    try:
        async with AsyncSession(impersonate="chrome") as client:
            t0 = time.monotonic()
            r = await client.head(url, timeout=8.0, allow_redirects=True)
            latency_ms = int((time.monotonic() - t0) * 1000)
            reason = normalize_failure(
                r.status_code,
                http_status=r.status_code,
                headers=dict(r.headers),
            ) if r.status_code >= 400 else None
            retry_after = float(r.headers.get("Retry-After", 0)) or None
            return PreflightResult(
                reachable=(r.status_code < 400),
                latency_ms=latency_ms,
                degraded_reason=reason,
                http_status=r.status_code,
                headers=dict(r.headers),
                retry_after_seconds=retry_after,
            )
    except RequestsError as e:
        # Only genuine network-layer failures reach here now (DNS, TCP refused).
        # TLS-layer CDN blocks no longer masquerade as ConnectError.
        return PreflightResult(reachable=False, latency_ms=0,
                               degraded_reason=normalize_failure(e))
```

**Rules for preflight consumers:**
- `RATE_LIMITED` → wait `retry_after_seconds` (max 30s), retry preflight once, then proceed or abort.
- `CONNECTIVITY_BLOCKED` / `BOT_WALL` → skip all engines, emit availability fallback issue, return immediately.
- `CSP_BLOCKED` → proceed with static-only path; do not send to browser engines.
- Cache result per `(url, run_id)` — parallel page scans within one audit must not re-check.

**Where:** New function in `audit_runner.py`, called at top of `run_audit()` before mode dispatch.

---

### 1.4  Normalise Fallback Issue Semantics — `audit_runner.py` 🔴 MUST

**Problem:** Deep/Max browser navigation failure falls through into static extraction, producing scored `html-incomplete` findings. Fast emits an availability-class stub. Identical failure, different issue inventory.

**Fix — single `_build_availability_fallback_issue()` helper used by all modes:**

```python
def _build_availability_fallback_issue(url: str, reason: DegradedReason) -> Issue:
    return Issue(
        rule_id="beacon-availability-001",
        impact="critical",
        category="availability",
        scoring=False,           # never counts against site score
        needs_review=True,
        message=f"Site could not be audited: {reason.value}",
        degraded_reason=reason,
    )
```

All three modes call this on any failure returned by `normalize_failure()`. Deep/Max must not fall through to static extraction when browser navigation fails with a normalised reason.

**Where:** `audit_runner.py`. Replace the three separate fallback paths in Fast, Deep, and Max branches with calls to this single helper.

---

### 1.5  Tighten `html-incomplete` in `static_checks.py` 🟡 SHOULD

**Problem:** `html-incomplete` is emitted as a scored finding even when caused by upstream network/CSP failure.

**Fix — pass upstream context into `run_all()`:**

```python
def run_all(
    html: str,
    url: str,
    degraded: bool = False,
    degraded_reason: DegradedReason | None = None,
) -> list[Issue]:
    ...
    if is_incomplete:
        upstream_failure = degraded or degraded_reason in {
            DegradedReason.CONNECTIVITY_BLOCKED,
            DegradedReason.BROWSER_NAV_FAILED,
            DegradedReason.CSP_BLOCKED,
            DegradedReason.RATE_LIMITED,
        }
        issues.append(Issue(
            rule_id="html-incomplete",
            scoring=not upstream_failure,      # scored only when NOT caused by upstream failure
            needs_review=upstream_failure,
        ))
```

**Where:** `static_checks.py` — `run_all()` and `_detect_incomplete_html()`. Caller in `audit_runner.py` passes `degraded_reason=preflight.degraded_reason`.

---

### 1.6  Confidence Score — All output paths 🟡 SHOULD

**Problem (new — not in previous plan):** `trust_level` (low/partial/full) is categorical. The dashboard cannot rank two `partial` scans against each other or communicate to users how much to trust a score. No numeric signal exists for operator alerting or tier-based SLA enforcement.

**Fix — add `confidence_score: float` (0.0–1.0) to every audit result:**

```python
def _compute_confidence_score(
    preflight: PreflightResult,
    engines_fired: list[str],          # e.g. ["static", "axe", "playwright"]
    fallbacks_triggered: int,
    issues_scored: int,
    issues_total: int,
) -> float:
    """
    0.0 = no usable data (site unreachable, all engines failed)
    1.0 = preflight passed, all engines ran, no fallbacks, full issue inventory

    Formula:
      base            = 1.0
      − preflight_pen = 0.4 if preflight failed else 0.0
      − engine_pen    = 0.3 × (expected_engines − len(engines_fired)) / expected_engines
      − fallback_pen  = 0.1 × min(fallbacks_triggered, 3) / 3
      − score_pen     = 0.2 × (1 − issues_scored / max(issues_total, 1))
    """
    base = 1.0
    preflight_pen = 0.4 if not preflight.reachable else 0.0
    expected = _expected_engine_count(mode)      # fast=1, deep=2, max=3
    engine_pen = 0.3 * (expected - len(engines_fired)) / max(expected, 1)
    fallback_pen = 0.1 * min(fallbacks_triggered, 3) / 3
    score_pen = 0.2 * (1 - issues_scored / max(issues_total, 1))
    return round(max(0.0, base - preflight_pen - engine_pen - fallback_pen - score_pen), 2)
```

**Output schema addition:**
```python
{
  "degraded": true,
  "degraded_reason": "csp_blocked",
  "trust_level": "partial",           # categorical (low / partial / full)
  "confidence_score": 0.55,           # numeric (0.0–1.0)
  "confidence_note": "CSP policy prevented script injection. Static checks ran; axe-core did not.",
  "mode": "deep",
  "score": 61,                        # score shown when confidence_score > 0.3; null otherwise
}
```

**Rules:**
- `confidence_score < 0.3` → `score = null`, show "Scan incomplete" badge.
- `0.3 ≤ confidence_score < 0.7` → show score with "Low confidence" badge.
- `confidence_score ≥ 0.7` → show score normally.
- Surface `confidence_score` in structured logs for SLO tracking.

**Where:** New `_compute_confidence_score()` in `audit_runner.py`; add `confidence_score` and `confidence_note` to response schema in `dashboard_api.py`.

---

### 1.7  Dashboard Consistency — `dashboard_api.py` 🟡 SHOULD

**Fix — standardise audit result envelope:**

```python
{
  "degraded": bool,
  "degraded_reason": str,          # always from DegradedReason enum via normalize_failure()
  "trust_level": "low|partial|full",
  "confidence_score": float,        # 0.0–1.0
  "confidence_note": str,
  "mode": "fast|deep|max",
  "score": float | null,            # null when confidence_score < 0.3
  "engines_fired": list[str],
  "fallbacks_triggered": int,
}
```

Score must be `null` (not `0`) when `confidence_score < 0.3`.

**Where:** Response builder in `dashboard_api.py`. Frontend: render `null` score as "Scan degraded — no score available" badge, never as `0/100`.

---

### 1.8  Regression Tests — Mode Consistency Gate 🔴 MUST

```
tests/
  test_mode_consistency.py
  fixtures/
    blocked_dns.json           # ConnectError
    http_429_with_retry.json   # 429 + Retry-After: 5
    http_403_captcha.json      # 403 + CAPTCHA body signature
    csp_strict_header.json     # 200 + strict CSP header
    csp_injection_error.json   # 200 + Playwright CSP injection exception
    nav_timeout.json           # Playwright NavigationTimeout
    partial_html.json          # truncated HTML body
```

**Gate rule:** For every fixture, Fast/Deep/Max must produce identical values for:
- `degraded_reason` (same enum member)
- `fallback_category` (all `availability` or all nothing — never mixed `structural`)
- `scoring` on `html-incomplete` (all `False` when upstream failure present)
- `confidence_score` bucket (all `< 0.3`, or all `≥ 0.3`, — never split)

This is the single acceptance criterion for Phase 13. CI must fail if any mode diverges on any fixture.

---

## Part 2 — Crawler Production Hardening (Phase 14)

These are the 17 gaps identified in the crawler gap report. All 6 MUST items are blockers for any real-site crawl.

### 2.1  Retry-After / Rate-Limit Backoff — `bfs_crawler.py` · `sitemap_crawler.py` · `scan_mode_runner.py` 🔴 MUST

**Problem:** HTTP 429 triggers `consecutive_failures >= 3` stop after 3 pages on rate-limited sites. No backoff exists in BFS, sitemap fetcher, or fast-state provider.

**Fix — shared backoff helper (add to `common.py`):**

```python
async def http_get_with_backoff(
    url: str,
    *,
    client: "curl_cffi.AsyncSession",   # curl_cffi replaces httpx throughout
    max_retries: int = 2,
) -> "curl_cffi.Response":
    """
    curl_cffi's Chrome impersonation means CDN blocks now surface as real
    429 / 403 HTTP codes rather than connection resets, so backoff logic
    actually fires correctly on rate-limited sites.
    """
    for attempt in range(max_retries + 1):
        resp = await client.get(url)
        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
            await asyncio.sleep(min(wait, 15.0))
            continue
        return resp
    return resp   # return last 429 for caller to classify
```

**Touchpoints:**
- `bfs_crawler.py` L169–176: replace `httpx.AsyncClient` session with `curl_cffi.AsyncSession(impersonate="chrome")` and call `http_get_with_backoff(...)`
- `sitemap_crawler.py` L218–229: same swap in `_fetch_text`
- `scan_mode_runner.py` L110–117: same in `_fast_state_provider`
- `failure_taxonomy.py`: map 429 → `DegradedReason.RATE_LIMITED` (not `blocked_request`)
- `crawl_orchestrator.py` L180–205: do not increment `consecutive_failures` on `RATE_LIMITED`
- **Remove:** `import httpx` from all four files above — `curl_cffi` is the full replacement.

---

### 2.2  `robots.txt` `Disallow` Enforcement — `orchestrator.py` · `bfs_crawler.py` · `sitemap_crawler.py` 🔴 MUST

**Problem:** `Disallow:` lines are never read. Crawling disallowed paths triggers bot-defence on enterprise/legal sites and may violate ToS in a SaaS context.

**Fix:**

```python
# common.py — new helper
def parse_robots_disallow(robots_text: str) -> frozenset[str]:
    """Returns set of disallowed path prefixes for any user-agent."""
    disallowed = set()
    capture = False
    for line in robots_text.splitlines():
        line = line.strip()
        if line.lower().startswith("user-agent:"):
            agent = line.split(":", 1)[1].strip()
            capture = agent in {"*", "beacon", "beaconbot"}
        elif capture and line.lower().startswith("disallow:"):
            path = line.split(":", 1)[1].strip()
            if path:
                disallowed.add(path)
    return frozenset(disallowed)

def is_disallowed(url: str, disallow_set: frozenset[str]) -> bool:
    path = urllib.parse.urlparse(url).path
    return any(path.startswith(prefix) for prefix in disallow_set)
```

**Touchpoints:**
- `orchestrator.py` L45–55: fetch robots.txt once, call `parse_robots_disallow`, pass `disallow_set` into BFS and sitemap crawlers.
- `bfs_crawler.py` L134–156: filter `hrefs` against `disallow_set` before queuing.
- `sitemap_crawler.py` L72–92: filter discovered URLs against `disallow_set`.

---

### 2.3  Shared Playwright Browser for `DOMCrawler` — `dom_crawler.py` · `scan_mode_runner.py` 🔴 MUST

**Problem:** `dom_crawler.py` calls `async_playwright().start()` + `chromium.launch()` inside every `crawl()` call. Max mode with `dom_max_pages=15` spawns up to 15 concurrent browser launches. Subprocess leaks when `asyncio.wait_for` cancels the task mid-flight.

**Fix — accept a shared Camoufox browser instance via `__init__`:**

Camoufox exposes the standard Playwright `Browser` API, so all downstream page interaction code is unchanged. Only the launcher changes.

```python
# dom_crawler.py
from camoufox import AsyncNewBrowser  # replaces playwright.chromium.launch

class DOMCrawler:
    def __init__(self, ..., browser: Browser | None = None):
        self._shared_browser = browser   # if provided, use it; do not launch/close

    async def crawl(self, seed_url: str) -> list[CrawledURL]:
        browser_is_ours = self._shared_browser is None
        if browser_is_ours:
            playwright = await async_playwright().start()
            # Camoufox: spoofs canvas, WebGL, audio context, font enumeration
            # at C++ level via Firefox Juggler — not detectable via CDP probes.
            browser = await AsyncNewBrowser(playwright, headless=True)
        else:
            browser = self._shared_browser
            playwright = None
        try:
            context = await browser.new_context(...)
            # ... crawl pages using context.new_page() ...
            # All existing axe-core injection, selector logic, and probe scripts
            # run unchanged — Camoufox exposes the standard Playwright Page API.
        finally:
            await context.close()
            if browser_is_ours:
                await browser.close()
                await playwright.stop()
```

**Touchpoints:**
- `scan_mode_runner.py` L188–197: create one browser via `_playwright_browser_factory` using `AsyncNewBrowser(playwright, headless=True)` instead of `playwright.chromium.launch(headless=True)`.
- `orchestrator.py` L31–44: pass shared Camoufox browser to `DOMCrawler` at construction time.
- **Remove:** Any Chromium launch args (e.g. `--disable-blink-features=AutomationControlled`) — Camoufox handles stealth at a lower level. Remove any `playwright-stealth` patches if present.

**Development-only: `debug_compare` test fixture**

Chromium is **not** kept as a production fallback. However, during development and QA, a comparison fixture should exist to catch rendering divergence between engines:

```python
# tests/crawlers/test_browser_engine_compare.py
# This is a DEVELOPMENT/QA tool only — never runs in production.

@pytest.mark.debug_compare
async def test_camoufox_vs_chromium_render(fixture_url):
    """
    Runs the same page through Camoufox and vanilla Chromium and flags
    structural differences in the rendered HTML. Used during development
    to detect Firefox-specific rendering divergence on new sites.

    NOT a fallback trigger — Camoufox is always the production engine.
    If this test flags divergence, investigate the site's UA discrimination
    behaviour; do not switch production to Chromium.
    """
    camoufox_html = await fetch_with_camoufox(fixture_url)
    chromium_html = await fetch_with_chromium(fixture_url)

    # Flag divergence by comparing structural landmarks, not full HTML
    camoufox_landmarks = extract_aria_landmarks(camoufox_html)
    chromium_landmarks = extract_aria_landmarks(chromium_html)

    if camoufox_landmarks != chromium_landmarks:
        pytest.xfail(
            f"Landmark divergence detected for {fixture_url}. "
            "Check if site is User-Agent discriminating (Vary: User-Agent header). "
            "Camoufox result is correct — this is a known site behaviour."
        )
```

Run this fixture against new sites during QA (`pytest -m debug_compare`), not in CI. It answers the question "does this site serve different HTML to Firefox?" without adding a second production browser stack.

---

### 2.4  Scan Mode Normalisation — `common.py` + all callers 🔴 MUST

**Problem:** `crawl_orchestrator.py:721–727` silently downgrades `"max"` → `"deep"`. `scan_mode_runner.py:60–64` raises `ValueError` for `"max"`. Two normalizers with different semantics, four call sites.

**Fix — single canonical function in `common.py`:**

```python
# common.py
ScanMode = Literal["fast", "deep", "max"]

def normalize_scan_mode(raw: str | None) -> ScanMode:
    """Single source of truth. Raises ValueError only on completely unrecognised input."""
    mode = (raw or "").strip().lower()
    if mode in {"fast", "minimal", "light"}:
        return "fast"
    if mode in {"deep", "standard"}:
        return "deep"
    if mode in {"max", "full", "thorough"}:
        return "max"
    raise ValueError(f"Unrecognised scan_mode: {raw!r}. Expected fast | deep | max.")
```

**Touchpoints:**
- Delete `_normalize_scan_mode` from `crawl_orchestrator.py` L721–727.
- Delete `_normalize_scan_mode` from `scan_mode_runner.py` L60–64.
- Delete or update equivalents in `page_auditor.py` L517–519 and `parallel_runner.py` L29–33.
- Import `normalize_scan_mode` from `common.py` at all four sites.

---

### 2.5  Playwright Context Leak on Timeout — `dom_crawler.py` 🔴 MUST

**Problem:** When `asyncio.wait_for` cancels `_run()`, the `finally: await closer()` runs in a cancelled-task context. `playwright.stop()` requires the same event-loop task that called `playwright.start()`. Leak is silent — subprocess stays alive.

**Fix — explicit cancel fence:**

```python
# dom_crawler.py L99–118
task = asyncio.ensure_future(_run())
try:
    results = await asyncio.wait_for(asyncio.shield(task), timeout=self.page_timeout_seconds)
except (asyncio.TimeoutError, asyncio.CancelledError):
    task.cancel()
    with contextlib.suppress(Exception):
        await task   # drain cancellation; closer() runs inside _run's finally
    results = list(discovered.values())[:cap]
```

**Where:** `dom_crawler.py` L99–118 and L478–492.

---

### 2.6  Sitemap Recursion Depth Cap — `sitemap_crawler.py` 🔴 MUST

**Problem:** Malformed or adversarial `sitemapindex` with distinct child URLs per level recurses until OOM or Python stack overflow (~1000 frames).

**Fix:**

```python
MAX_SITEMAP_DEPTH = 5   # config.py

async def _crawl_sitemap(self, url: str, visited: set, depth: int = 0) -> None:
    if depth > MAX_SITEMAP_DEPTH:
        logger.warning("Sitemap recursion depth exceeded at %s (depth=%d)", url, depth)
        return
    ...
    for child_url in self._parse_sitemap_index(root):
        await self._crawl_sitemap(child_url, visited, depth=depth + 1)
```

**Where:** `sitemap_crawler.py` L110–142.

---

### 2.7  ~~BFS `User-Agent` Headers~~ — SUPERSEDED by Stack Upgrade 🟢 DONE

**Status: Closed.** This gap is fully resolved by the §Stack Decisions upgrade.

- **Old problem:** `httpx/0.27.0` User-Agent is flagged by Cloudflare/Akamai/Fastly, producing silent 403/503 that looked like a network error.
- **Old fix (now removed):** Passing `stable_request_headers(url)` into `httpx.AsyncClient` to set a realistic UA string.
- **Why it was insufficient:** Modern WAFs analyse TLS fingerprint, JA3/JA4 hash, HTTP/2 frame order, and ALPN negotiation order — not just the User-Agent string. A correct UA string on an `httpx` handshake is still detected and blocked at the TLS layer before any HTTP headers are read.
- **Actual fix:** `curl_cffi(impersonate="chrome")` sets the TLS fingerprint, JA3 hash, HTTP/2 frame order, ALPN sequence, and User-Agent simultaneously. No separate UA injection required.

**Action:** Delete `stable_request_headers()` calls from `bfs_crawler.py` L170 and `sitemap_crawler.py` L223. The `curl_cffi` session handles this entirely.

---

### 2.8  Per-Page Score Severity Weighting — `page_auditor.py` 🟡 SHOULD

**Problem:** `score = 100 - total_issues * 2.0` — every issue deducts 2 points regardless of severity. A site with 47 `minor` issues scores the same as one with 47 `critical` issues. `SEVERITY_WEIGHTS` exists in `config.py` but is only used at the aggregated site level.

**Fix:**

```python
# page_auditor.py — replace L737
from app.config import SEVERITY_WEIGHTS

penalty = sum(
    SEVERITY_WEIGHTS.get(i.get("severity", "minor"), 1.0)
    for i in merged_issues.values()
    if i.get("scoring", True)
)
score = round(max(0.0, 100.0 - min(95.0, penalty)), 1)
```

**Where:** `page_auditor.py` L737.

---

### 2.9  SLA Timeout Task Cleanup — `parallel_runner.py` 🟡 SHOULD

**Problem:** `asyncio.wait_for` on global SLA cancels `_run_pipeline()` but orphans `_worker` coroutines holding live Playwright pages.

**Fix:**

```python
# parallel_runner.py — _run_pipeline
worker_tasks = [asyncio.create_task(_worker(q)) for _ in range(concurrency)]
try:
    await asyncio.wait_for(
        asyncio.gather(*worker_tasks, return_exceptions=True),
        timeout=global_sla,
    )
except asyncio.TimeoutError:
    sla_truncated = True
    for t in worker_tasks:
        t.cancel()
    await asyncio.gather(*worker_tasks, return_exceptions=True)
```

**Where:** `parallel_runner.py` L289–305.

---

### 2.10  Rate-Limited vs Bot-Blocked Taxonomy — `failure_taxonomy.py` 🟡 SHOULD

Already handled by `normalize_failure()` in Part 1 (item 1.0). Ensure `crawl_orchestrator.py` L608–686 reads `DegradedReason.RATE_LIMITED` and does not increment `consecutive_failures`.

---

### 2.11  Playwright Unavailability Warning — `page_selector.py` 🟡 SHOULD

**Fix:** Add `logger.warning(...)` when `start()` silently falls back, and mark `audit_scan_mode = "deep_degraded"` (not `"deep"`) in the page result so the API consumer knows link extraction was static-only.

---

### 2.12  Semaphore Created at Call Time — `bfs_crawler.py` 🟡 SHOULD

**Fix:** Move `asyncio.Semaphore(self.concurrency)` from `__init__` to the top of `crawl()` to avoid binding to the wrong event loop after server restart or in test setups.

---

### 2.13  Journey Simulation Labelling — `scan_mode_runner.py` 🟡 SHOULD

Add `"simulation_type": "url_planning"` to journey result dicts so API consumers know no live navigation occurred. When live navigation is implemented, this becomes `"live_navigation"`.

---

### 2.14  Cross-Mode Integration Tests 🟢 NICE

```python
# tests/crawlers/test_scan_mode_roundtrip.py
@pytest.mark.parametrize("mode", ["fast", "deep", "max"])
async def test_scan_mode_roundtrip(mode, mock_http_server):
    result = await run_scan_mode_audit(mock_http_server.url, mode, max_pages=3)
    assert result["scan_mode"] == mode          # mode not silently downgraded
    assert result["pages_completed"] >= 1
    assert not result.get("fatal_error")
    assert "degraded_reason" not in result or \
           result["degraded_reason"] in DegradedReason.__members__.values()
```

---

### 2.15  Remaining NICE Items 🟢 NICE

- **GAP-14 (crawl_orchestrator):** Document the intentional tiered strategy where `nav` pages get `fast` mode in a `deep` crawl. Add docstring + expose `audit_scan_mode` per page.
- **GAP-15 (scan_mode_runner):** Add pre-audit URL diversity filter after `_dedupe_urls()` to cap pagination query-param variants (same path prefix, only `?page=N` variation).
- **GAP-16 (crawl_orchestrator):** Include `budget_reduction_events` in `crawl_completed` telemetry payload.

---

## Part 3 — ACT Coverage Uplift (Phase 15)

### 3.1  Gap Matrix First

Run the full ACT benchmark with verbose rule-level output before writing any new rules:

```
ACT Rule ID       | Expected | Detected | Miss Type
──────────────────────────────────────────────────
wcag111-img       | FAIL     | PASS     | false-negative (missing rule)
wcag143-contrast  | PASS     | FAIL     | false-positive (wrong selector)
wcag412-name-role | FAIL     | PASS     | false-negative (extractor failure)
...
```

Classify each miss as: `missing_rule`, `wrong_selector`, `wrong_impact_mapping`, or `extractor_failure`. Do not write new rules until this matrix exists — guessing from summary metrics produces low-yield work.

---

### 3.2  Priority Rule Groups

**Group A — Images & non-text content (WCAG 1.1.x) — static-detectable**
- `img` missing `alt`; empty `alt` on informative images; `role=img` without `aria-label`.
- Highest-frequency ACT miss class. Fully detectable statically.

**Group D — Form labelling (WCAG 1.3.1, 3.3.2) — partially static**
- `input` without `label`, `aria-label`, or `aria-labelledby`.
- Static partial detection; full coverage requires DOM. Flag static findings as `needs_review=True`.

**Group B — Keyboard & focus (WCAG 2.1.x) — browser-only**
- Focus order, focus visibility, keyboard traps.
- Gate on `scan_mode in {"deep","max"}` — never emit from static checks.

**Group C — Colour contrast (WCAG 1.4.3, 1.4.11) — browser-only**
- Requires rendered CSS. Gate on browser engine. Do not emit from static.

**Sequencing:** A → D → B → C (ascending browser-dependency).

---

### 3.3  RAG Knowledge Base Alignment

For every new rule add a corresponding RAG entry with:
- Rule ID + WCAG criterion
- Correct fix pattern (code example)
- Common false-positive conditions (prevents LLM hallucinating fixes on clean code)

Use `mode=update` ingestion — never rebuild from scratch in production.

---

### 3.4  ACT Recall Gate

Do not ship Phase 15 until:
- ACT recall ≥ 60%
- False-positive rate ≤ 15% on clean-site fixture set
- Zero rules produce scored findings on a degraded scan (confidence_score < 0.3)

---

## Part 4 — Operational Hardening (Phase 16)

### 4.1  Health & Readiness Endpoints

```
GET /health/live    → 200 always (process alive)
GET /health/ready   → 200 if Postgres + ChromaDB + LLM reachable; 503 otherwise
GET /health/audit   → last audit run status, engine availability flags, confidence_score distribution
```

Required by nginx load balancer on Hetzner/Contabo and by your own alerting rules.

---

### 4.2  LLM Cost Firewall — Hard Cap

```python
LLM_FIRE_BUDGET_PER_AUDIT = int(os.getenv("LLM_FIRE_BUDGET", "5"))

def _should_send_to_llm(issue: Issue, already_sent: int) -> bool:
    if already_sent >= LLM_FIRE_BUDGET_PER_AUDIT:
        return False
    if issue.impact not in {"critical", "serious"}:
        return False
    if not issue.scoring:
        return False
    return True
```

Log `llm_budget_exhausted=True` in audit result. Surface in dashboard as upsell hook for higher INR tiers.

---

### 4.3  Concurrency Backpressure

```python
AUDIT_CONCURRENCY_LIMIT = int(os.getenv("AUDIT_CONCURRENCY", "4"))
_audit_semaphore = asyncio.Semaphore(AUDIT_CONCURRENCY_LIMIT)

async def run_audit_with_backpressure(url, mode, ...):
    if _audit_semaphore.locked() and _audit_semaphore._value == 0:
        raise HTTPException(status_code=429, headers={"Retry-After": "30"})
    async with _audit_semaphore:
        return await run_audit(url, mode, ...)
```

Prevents Playwright spawning unbounded browser processes on free-tier load.

---

### 4.4  Structured Audit Logs

Every completed audit emits one structured JSON line to stdout:

```json
{
  "event": "audit_complete",
  "ts": "2026-04-15T12:00:00Z",
  "url": "https://example.com",
  "mode": "deep",
  "duration_ms": 4200,
  "issue_count": 14,
  "scored_count": 11,
  "degraded": false,
  "degraded_reason": null,
  "trust_level": "full",
  "confidence_score": 0.92,
  "engines_fired": ["static", "axe", "camoufox"],
  "http_client": "curl_cffi/chrome",
  "browser_engine": "camoufox/firefox",
  "fallbacks_triggered": 0,
  "llm_fired": 2,
  "llm_budget_exhausted": false,
  "score": 72
}
```

---

### 4.5  SLO Definitions

| Metric | Target | Measure From |
|--------|--------|-------------|
| Audit success rate (non-degraded) | ≥ 90% on reachable URLs | structured logs |
| Fast mode p95 latency | ≤ 12s | structured logs |
| Deep mode p95 latency | ≤ 45s | structured logs |
| Max mode p95 latency | ≤ 90s | structured logs |
| Mean `confidence_score` (non-degraded) | ≥ 0.75 | structured logs |
| LLM fire rate | ≤ 15% of issues | structured logs |
| False-positive rate (ACT clean set) | ≤ 15% | ACT benchmark |
| Dashboard 5xx rate | ≤ 0.5% | nginx access log |

Alert if any SLO breaches for 3 consecutive audits on the same URL.

---

## Part 6 — Runtime Intelligence & Observability (Phase 17)

These four additions do not change the crawl or audit execution path. They layer intelligence on top of the normalised failure stream introduced in Part 1 and the hardened crawl layer in Part 2. They are independently shippable after Part 2 is complete.

---

### 6.1  Site-Level Failure Profile Aggregation — `crawl_orchestrator.py` · `audit_runner.py` 🟡 SHOULD

**Problem:** Failures are normalised per page (via `normalize_failure()`) and appear in individual page results, but are never aggregated at site level. Operators cannot answer: *"Was this a network blip on one page, or is the entire site behind a bot-wall?"* Dashboard analytics and support debugging both require a site-level summary.

**Fix — add `site_failure_profile` to the site audit result:**

> **Refinements included (§2 + §1):** Failures are weighted by severity before computing `dominant_failure` — preventing a mass of low-weight timeouts from masking a single high-severity `bot_wall`. A `site_confidence_score` rolls up per-page confidence values to give operators a single trust signal at site level.

```python
# crawl_orchestrator.py — compute after all pages complete
from collections import Counter
from app.audit.failure_taxonomy import DegradedReason

# Severity weight per failure type — higher = more operationally significant.
# Used to determine dominant_failure by weighted score, not raw count.
FAILURE_SEVERITY_WEIGHT: dict[str, float] = {
    DegradedReason.BOT_WALL:              1.0,   # non-recoverable, highest priority
    DegradedReason.CONNECTIVITY_BLOCKED:  0.9,   # site unreachable
    DegradedReason.BROWSER_NAV_FAILED:    0.8,   # browser couldn't navigate
    DegradedReason.RATE_LIMITED:          0.6,   # recoverable with backoff
    DegradedReason.CSP_BLOCKED:           0.5,   # affects browser engines only
    DegradedReason.CSP_INJECTION_BLOCKED: 0.5,
    DegradedReason.RENDER_TIMEOUT:        0.4,   # transient, often retriable
    DegradedReason.EXTRACTION_FAILED:     0.3,
    DegradedReason.ENGINE_ERROR:          0.2,
}

def _weighted_dominant_failure(reasons: list[str]) -> str:
    """
    Returns the failure type with the highest *severity-weighted total score*
    rather than the highest raw count.

    Example: 8× RATE_LIMITED (score=4.8) vs 1× BOT_WALL (score=1.0)
    → raw-count winner: RATE_LIMITED
    → weighted winner:  RATE_LIMITED  (still wins here, but a single BOT_WALL
                                       can dominate if count-weighted average
                                       rounds the same cluster of low-weight
                                       timeouts down)
    This matters when a mix of minor + one critical failure is present.
    """
    weighted: dict[str, float] = {}
    for reason in reasons:
        weight = FAILURE_SEVERITY_WEIGHT.get(reason, 0.3)
        weighted[reason] = weighted.get(reason, 0.0) + weight
    return max(weighted, key=lambda r: weighted[r])

def _build_site_failure_profile(
    page_results: list[dict],
) -> dict:
    """
    Aggregate per-page degraded_reason values into a site-level summary.
    Called after all pages have been audited, before building the final result.
    """
    reasons = [
        r["degraded_reason"]
        for r in page_results
        if r.get("degraded") and r.get("degraded_reason")
    ]
    if not reasons:
        return {
            "dominant_failure": None,
            "failure_distribution": {},
            "degraded_page_count": 0,
            "site_confidence_score": _compute_site_confidence(page_results),
        }

    counts = Counter(reasons)
    dominant = _weighted_dominant_failure(reasons)
    total = sum(counts.values())
    distribution = {
        reason: {
            "count": count,
            "pct": round(count / total * 100, 1),
            "severity_weight": FAILURE_SEVERITY_WEIGHT.get(reason, 0.3),
        }
        for reason, count in counts.most_common()
    }
    return {
        "dominant_failure": dominant,
        "failure_distribution": distribution,
        "degraded_page_count": len(reasons),
        "site_confidence_score": _compute_site_confidence(page_results),
    }

def _compute_site_confidence(page_results: list[dict]) -> float:
    """
    Site-level confidence score: 0.0 (all pages degraded) → 1.0 (all pages full confidence).

    Formula:
      avg_page_confidence  = mean of per-page confidence_score fields
      degraded_ratio       = degraded_page_count / total_page_count
      site_confidence      = avg_page_confidence × (1 − 0.4 × degraded_ratio)

    Rationale:
      - avg_page_confidence captures engine-level quality (§1.6 formula).
      - degraded_ratio applies an additional penalty when a large fraction of
        pages are degraded regardless of their individual scores.
      - The 0.4 multiplier on degraded_ratio is calibrated so a site where
        50% of pages are degraded gets a ~20% additional reduction on top of
        the already-reduced per-page confidence scores.
    """
    if not page_results:
        return 0.0
    scores = [
        float(r.get("confidence_score", 0.0))
        for r in page_results
        if r.get("confidence_score") is not None
    ]
    avg_confidence = sum(scores) / len(scores) if scores else 0.0
    degraded_count = sum(1 for r in page_results if r.get("degraded"))
    degraded_ratio = degraded_count / len(page_results)
    site_confidence = avg_confidence * (1.0 - 0.4 * degraded_ratio)
    return round(max(0.0, min(1.0, site_confidence)), 2)
```

**Output schema addition (site audit result):**

```json
{
  "site_failure_profile": {
    "dominant_failure": "bot_wall",
    "failure_distribution": {
      "bot_wall":     {"count": 1, "pct": 7.7,  "severity_weight": 1.0},
      "rate_limited": {"count": 8, "pct": 61.5, "severity_weight": 0.6},
      "render_timeout":{"count": 4, "pct": 30.8,"severity_weight": 0.4}
    },
    "degraded_page_count": 13,
    "site_confidence_score": 0.43
  }
}
```

> **Note:** With raw-count weighting this example would show `dominant_failure = "rate_limited"` (8 occurrences). With severity weighting, `bot_wall` wins (1 × 1.0 = 1.0 score vs rate_limited's 8 × 0.6 = 4.8 — rate_limited wins here, but the weight exposes `bot_wall` at the top of `failure_distribution` with a clear `severity_weight: 1.0` signal so operators know it's present regardless of dominant label).

**Consumer uses:**
- **Debugging:** `dominant_failure = "rate_limited"` immediately tells you the site needs backoff tuning, not a code fix. `severity_weight` in `failure_distribution` tells you which failure type to prioritise even if it's not dominant by count.
- **Analytics:** Track `dominant_failure` and `site_confidence_score` over time to surface sites that are chronically degraded vs transiently so.
- **Dashboard insights:** Show a "Why this scan is degraded" banner driven by `dominant_failure` — surfaced in plain English via `reason_message()` from `failure_taxonomy.py`. Show `site_confidence_score` using the same badge logic as per-page `confidence_score` (§1.6).

**Touchpoints:**
- `crawl_orchestrator.py` — add `FAILURE_SEVERITY_WEIGHT`, `_weighted_dominant_failure()`, `_compute_site_confidence()`, and call `_build_site_failure_profile(page_results)` inside `crawl_site()` after the page audit loop.
- `audit_runner.py` — include `site_failure_profile` (with `site_confidence_score`) in the result dict returned by `run_audit()`.
- `dashboard_api.py` — expose `site_failure_profile` including `site_confidence_score` in the scan result API response.
- New structured-log fields: `"dominant_failure"` and `"site_confidence_score"` in the `audit_complete` event (§4.4).

---


### 6.2  Adaptive Crawl Strategy Based on Failure Type — `crawl_orchestrator.py` 🔴 MUST

**Problem:** The current orchestrator has one failure response: increment `consecutive_failures`; at `≥ 3`, stop the crawl. This treats a rate-limited site (recoverable) identically to a confirmed bot-wall (non-recoverable), and ignores CSP failures (which only affect browser engines, not link discovery).

The result: rate-limited sites are abandoned after 3 pages when they could succeed with reduced concurrency; CSP sites waste Playwright budget on pages that will always fail injection; bot-walled sites waste time retrying pages that will never yield content.

**Failure → action routing table:**

| Failure | Action |
|---------|--------|
| `RATE_LIMITED` | Halve concurrency; sleep `rate_limit_backoff_seconds`; do NOT count as failure |
| `BOT_WALL` | Stop crawl immediately; emit `site_failure_profile`; return |
| `CSP_BLOCKED` / `CSP_INJECTION_BLOCKED` | Disable browser engines; continue with static-only crawl |
| `RENDER_TIMEOUT` | Reduce concurrency; count as failure |
| All others | Count as failure (existing behaviour) |

**Fix — `_apply_failure_action()` in `crawl_orchestrator.py`:**

```python
from app.audit.failure_taxonomy import DegradedReason

FAILURE_ACTIONS: dict[str, str] = {
    DegradedReason.RATE_LIMITED:          "reduce_concurrency",
    DegradedReason.BOT_WALL:              "stop_crawl",
    DegradedReason.CSP_BLOCKED:           "disable_browser_engines",
    DegradedReason.CSP_INJECTION_BLOCKED: "disable_browser_engines",
    DegradedReason.CONNECTIVITY_BLOCKED:  "stop_crawl",
    DegradedReason.RENDER_TIMEOUT:        "reduce_concurrency",
    DegradedReason.BROWSER_NAV_FAILED:    "count_failure",
    DegradedReason.EXTRACTION_FAILED:     "count_failure",
    DegradedReason.ENGINE_ERROR:          "count_failure",
}

async def _apply_failure_action(
    self,
    reason: DegradedReason,
    consecutive_failures: int,
) -> str:   # returns one of: "continue", "slow_down", "static_only", "stop"
    action = FAILURE_ACTIONS.get(reason, "count_failure")

    if action == "reduce_concurrency":
        new_concurrency = max(1, self._current_concurrency // 2)
        if new_concurrency != self._current_concurrency:
            self._current_concurrency = new_concurrency
        # ❶ Structured adaptive-decision log — queryable by adaptive_action field
        logger.info(
            "Adaptive crawl decision: %s",
            {
                "adaptive_action": "reduced_concurrency",
                "trigger": reason.value,
                "new_concurrency": self._current_concurrency,
                "consecutive_failures": consecutive_failures,
            },
        )
        return "slow_down"   # caller sleeps; does NOT increment consecutive_failures

    elif action == "stop_crawl":
        logger.warning(
            "Adaptive crawl decision: %s",
            {
                "adaptive_action": "stopped_crawl",
                "trigger": reason.value,
                "consecutive_failures": consecutive_failures,
                "recoverable": False,
            },
        )
        return "stop"

    elif action == "disable_browser_engines":
        self._browser_engines_enabled = False
        logger.info(
            "Adaptive crawl decision: %s",
            {
                "adaptive_action": "disabled_browser_engines",
                "trigger": reason.value,
                "remaining_engine": "static",
            },
        )
        return "static_only"

    else:   # "count_failure" — existing behaviour
        logger.debug(
            "Adaptive crawl decision: %s",
            {
                "adaptive_action": "counted_failure",
                "trigger": reason.value,
                "consecutive_failures": consecutive_failures + 1,
            },
        )
        return "continue"
```

**Integration in the crawl loop:**

```python
# SiteCrawlOrchestrator.crawl_site() — replace bare consecutive_failures block:
for page_result in page_results:
    reason = normalize_failure(page_result.get("degraded_reason"))
    action = await self._apply_failure_action(reason, consecutive_failures)
    if action == "stop":
        early_stop_reason = f"non_recoverable:{reason.value}"
        break
    elif action == "slow_down":
        await asyncio.sleep(self._rate_limit_backoff_seconds)
        continue   # do NOT count as failure
    elif action == "static_only":
        self._browser_engines_enabled = False
        continue
    else:
        consecutive_failures += 1
        if consecutive_failures >= self._max_consecutive_failures:
            early_stop_reason = "failure_threshold"
            break
```

**Config additions (`config.py`):**

```python
CRAWL_ADAPTIVE_STRATEGY = {
    "rate_limit_backoff_seconds": 5.0,      # sleep between pages when rate-limited
    "max_consecutive_failures": 3,          # only counts non-rate-limited failures
    "csp_static_fallback_enabled": True,    # switch to static-only on CSP
    "bot_wall_immediate_stop": True,        # stop on first confirmed bot-wall
}
```

**Structured Adaptive Decision Logs:**

Every call to `_apply_failure_action()` emits one structured log line at `INFO` or `WARNING` level. The `"Adaptive crawl decision"` prefix makes all adaptive events greppable in one query.

| Field | Values | Use |
|-------|--------|-----|
| `adaptive_action` | `reduced_concurrency`, `stopped_crawl`, `disabled_browser_engines`, `counted_failure` | Filter by action type in log aggregator |
| `trigger` | Any `DegradedReason.value` string | Identify which failure drove the decision |
| `new_concurrency` | int | Track concurrency reduction history |
| `consecutive_failures` | int | Understand pressure at decision time |
| `recoverable` | bool | Quick filter for stops: `recoverable=False` = bot-wall / DNS |
| `remaining_engine` | `"static"` | Confirm static-only fallback is active |

**Example log lines (JSON aggregator view):**

```json
{"level":"INFO",  "msg":"Adaptive crawl decision", "adaptive_action":"reduced_concurrency",      "trigger":"rate_limited",         "new_concurrency":1,  "consecutive_failures":0}
{"level":"WARNING","msg":"Adaptive crawl decision", "adaptive_action":"stopped_crawl",            "trigger":"bot_wall",             "consecutive_failures":0, "recoverable":false}
{"level":"INFO",  "msg":"Adaptive crawl decision", "adaptive_action":"disabled_browser_engines", "trigger":"csp_injection_blocked","remaining_engine":"static"}
{"level":"DEBUG", "msg":"Adaptive crawl decision", "adaptive_action":"counted_failure",          "trigger":"render_timeout",       "consecutive_failures":2}
```

**Tuning use cases:**

- `grep 'reduced_concurrency' crawl.log | wc -l` → how often are sites rate-limiting us?
- `grep '"adaptive_action":"stopped_crawl"' | jq .trigger` → which failure type stops most crawls?
- `grep 'disabled_browser_engines'` → which sites block axe injection via CSP?

**Where:** `crawl_orchestrator.py` — add `_apply_failure_action()` method; update the page-result loop. `config.py` — add `CRAWL_ADAPTIVE_STRATEGY` dict.

---

### 6.3  Domain-Level Preflight Cache — `audit_runner.py` 🟡 SHOULD

**Problem:** Section 1.3 introduced `_preflight_check(url)` with a per-`(url, run_id)` cache. This is correct for deduplication within a single page, but when a site audit processes 25 pages across the same domain, each parallel page worker fires an independent HEAD request to the same host. On a rate-limited or slow host this multiplies unnecessary traffic and can itself trigger a 429.

**Fix — domain-level cache layer on top of the existing per-URL cache:**

```python
# audit_runner.py

_domain_preflight_cache: dict[str, "PreflightResult"] = {}
_domain_preflight_lock: asyncio.Lock = asyncio.Lock()

def _domain_key(url: str) -> str:
    """Extract registrable domain for preflight cache key."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return host.removeprefix("www.")   # www.example.com == example.com

async def _preflight_check_cached(
    url: str,
    run_id: str,
    page_cache: dict | None = None,
) -> "PreflightResult":
    """
    Cache hierarchy:
      1. Per-(url, run_id) exact cache  → avoids redundant checks for identical URL
      2. Per-domain cache               → avoids repeated HEAD to same host within one audit
      3. Live HEAD via _preflight_check(url)
    """
    exact_key = (url, run_id)
    if page_cache is not None and exact_key in page_cache:
        return page_cache[exact_key]

    domain = _domain_key(url)
    async with _domain_preflight_lock:
        if domain in _domain_preflight_cache:
            result = _domain_preflight_cache[domain]
            if page_cache is not None:
                page_cache[exact_key] = result
            return result

        result = await _preflight_check(url)
        _domain_preflight_cache[domain] = result
        if page_cache is not None:
            page_cache[exact_key] = result
        return result

def clear_domain_preflight_cache() -> None:
    """Call once at the start of each new site audit to prevent cross-run pollution."""
    _domain_preflight_cache.clear()
```

**Caller change:**

```python
# run_audit() / run_site_audit() — at the top of each site audit:
clear_domain_preflight_cache()
...
# Per page (instead of _preflight_check(url)):
result = await _preflight_check_cached(url, run_id=run_id, page_cache=preflight_cache)
```

**Benefits:**
- Eliminates repeated HEAD requests when scanning N pages on the same domain in one audit.
- `www.example.com` and `example.com` share the same cached result, matching real CDN topology.
- Cache is cleared at the start of every new audit — no cross-run pollution.
- Lock prevents concurrent workers from firing duplicate live HEAD requests on cache miss.

**Where:** `audit_runner.py` — add `_domain_preflight_cache`, `_domain_preflight_lock`, `_domain_key()`, `_preflight_check_cached()`, `clear_domain_preflight_cache()`. Replace all `_preflight_check(url)` call sites inside the parallel page loop with `_preflight_check_cached(...)`.

---

### 6.4  Domain Learning System — Forward Plan (Phase 18+) 🟢 FUTURE

**Status:** Not needed now. Design stub only — do not implement until Phase 17 items are complete and 30 days of production `site_failure_profile` data exist.

**Concept:** Persist per-domain failure patterns across audit runs and use them to pre-configure the adaptive crawl strategy (§6.2) before the first page is fetched — eliminating the "warm-up page" that currently burns budget detecting what the domain profile already knows.

**Future data model:**

```python
# db/models.py — future table
class DomainProfile(Base):
    __tablename__ = "domain_profiles"

    domain: str                           # primary key — registrable domain
    last_seen: datetime
    dominant_failure: str | None          # from site_failure_profile
    failure_history: dict                 # {reason: count} across all runs
    preferred_concurrency: int | None     # learned from rate-limit events
    csp_static_only: bool                 # True if CSP blocks browser injection consistently
    bot_wall_detected: bool               # True if bot_wall seen in last N runs
    avg_latency_ms: int | None            # used to set adaptive timeouts proactively
    last_successful_scan: datetime | None
```

**Future crawl flow with domain profile:**

```python
# crawl_orchestrator.py — future
profile = await db.get_domain_profile(domain)
if profile:
    if profile.bot_wall_detected:
        return _build_abort_result("bot_wall_persistent")   # skip crawl entirely
    if profile.csp_static_only:
        self._browser_engines_enabled = False               # skip Playwright upfront
    if profile.preferred_concurrency:
        self._current_concurrency = profile.preferred_concurrency
```

**Why not now:**
- Requires a persistent store and a background update job.
- Pattern extraction is only meaningful after a corpus of real-world audit data.
- The adaptive strategy in §6.2 captures the same runtime benefit without state.

**Prerequisite for Phase 18:** At least 30 days of structured audit logs (§4.4) with `site_failure_profile.dominant_failure` populated and the §6.2 adaptive strategy stable in production.

---

## Part 5 — Pre-Launch Checklist

### Code Gates
- [ ] `normalize_failure()` is the only place `DegradedReason` values are constructed — zero inline derivations remain
- [ ] All 6 🔴 MUST crawler gaps fixed (GAP-01 through GAP-06)
- [ ] Mode-consistency regression tests passing on all 7 network-state fixtures
- [ ] `confidence_score` field present in all audit responses
- [ ] Score is `null` when `confidence_score < 0.3` — never `0`
- [ ] `html-incomplete` is non-scoring on all degraded scans
- [ ] ACT recall ≥ 60%
- [ ] LLM cost firewall enforced with hard env-var cap
- [ ] `/health/ready` returning correct 503 on dependency failure
- [ ] `site_failure_profile` (with `dominant_failure` + `failure_distribution`) present in all site audit results (§6.1)
- [ ] `_apply_failure_action()` routing verified: `RATE_LIMITED` → slow down, `BOT_WALL` → stop, `CSP_BLOCKED` → static-only (§6.2)
- [ ] `CRAWL_ADAPTIVE_STRATEGY` config dict live and consumed by `crawl_orchestrator.py` (§6.2)
- [ ] Domain-level preflight cache active; no repeated HEAD to same host within one site audit (§6.3)
- [ ] `clear_domain_preflight_cache()` called exactly once at start of every new site audit (§6.3)

### Operational Gates
- [ ] Structured audit logs shipping to aggregator with `confidence_score` field
- [ ] Concurrency semaphore tuned for instance size (measure Camoufox/Firefox peak RSS — higher than Chromium, ~160MB/instance)
- [ ] ChromaDB persistence confirmed across process restarts
- [ ] RAG knowledge base versioned — `mode=update` ingestion live
- [ ] `robots.txt` `Disallow` enforcement active
- [ ] Playwright subprocess leak test passing (no zombie **Firefox/Camoufox** processes after timeout)
- [ ] `httpx` removed from `requirements.txt` / `pyproject.toml` — `curl_cffi` is the only HTTP client
- [ ] `curl_cffi` impersonation verified: send a test HEAD to `https://tls.browserleaks.com/json` and confirm JA3 hash matches Chrome's known fingerprint
- [ ] Camoufox headless smoke test: navigate to `https://bot.sannysoft.com` and confirm zero "red" bot-detection signals in screenshot

### Product / Business Gates
- [ ] INR tier limits enforced at API level — not just UI
- [ ] "Scan degraded" UX copy written for all `DegradedReason` families including CSP variants
- [ ] `confidence_score` visible in dashboard with plain-language explanation
- [ ] LLM budget exhaustion surfaces as upsell trigger
- [ ] Privacy policy covers URL data retention under DPDP Act 2023

---

## Implementation Order

| Phase | Sprint | Items | Acceptance Criterion |
|-------|--------|-------|---------------------|
| 13A | Week 1 | 1.0 + 1.1 | `normalize_failure()` live; zero inline DegradedReason derivations remain |
| 13B | Week 1 | 1.2 + 1.3 | Preflight + fallback helper live; all modes use them |
| 13C | Week 2 | 1.4 + 1.5 + 1.6 | CSP hardened; html-incomplete non-scoring on degraded; confidence_score in all responses |
| 13D | Week 2 | 1.7 + 1.8 | Dashboard envelope standardised; mode-consistency tests green on all 7 fixtures |
| 14A | Week 3 | 2.1 + 2.4 + 2.6 | Retry backoff, mode normalisation, sitemap depth cap — any-site unblocked |
| 14B | Week 3 | 2.2 + 2.3 + 2.5 | robots.txt enforced; shared Playwright browser; context leak fixed |
| 14C | Week 4 | 2.7–2.13 | SHOULD items; cross-mode integration tests green |
| 15A | Week 5 | 3.1 | ACT gap matrix produced; no rules written yet |
| 15B | Week 5–6 | 3.2 + 3.3 | Group A + D rules + RAG entries; ACT recall ≥ 60% |
| 16A | Week 7 | 4.1 + 4.4 | Health endpoints + structured logs live |
| 16B | Week 7 | 4.2 + 4.3 | LLM hard cap + concurrency semaphore |
| 17A | Week 8 | 6.1 | `site_failure_profile` in all site audit results; `dominant_failure` in structured logs |
| 17B | Week 8 | 6.2 | `_apply_failure_action()` routing live; adaptive concurrency + static-only fallback verified |
| 17C | Week 9 | 6.3 | Domain-level preflight cache live; HEAD deduplication confirmed in load tests |
| 18+  | Future | 6.4 | Domain learning system — only after 30d of production audit log data |
| Launch | — | Part 5 checklist | All gates green |

---

## Architectural Invariants (Never Violate)

These are the rules that, if broken, cause the exact class of bugs this plan is fixing:

1. **`normalize_failure()` is the only constructor of `DegradedReason` values.** No inline derivation anywhere else.
2. **`_build_availability_fallback_issue()` is the only constructor of availability-class fallback issues.** All three modes call it identically on failure.
3. **`normalize_scan_mode()` in `common.py` is the only normalizer.** No local normalization in any module.
4. **Score is `null`, not `0`, when `confidence_score < 0.3`.** A score of `0` is a real accessibility finding. A score of `null` means the scan did not complete.
5. **`html-incomplete` never scores when `degraded_reason` is an upstream failure.** Structural findings require a structurally sound fetch.
6. **Playwright is never launched inside a per-page call in max mode.** Shared browser context only.
7. **LLM is never called on a non-scored issue or when budget is exhausted.** Cost firewall is a hard gate, not a soft target.
8. **`_apply_failure_action()` receives only `DegradedReason` enum values — never raw strings.** All adaptive routing decisions (slow down, stop, static-only) flow through the canonical enum (§6.2).
9. **`site_failure_profile` is computed from already-normalised `degraded_reason` fields only.** It never re-classifies raw exceptions — classification happened once in Part 1 (§6.1).
10. **`clear_domain_preflight_cache()` is called exactly once per site audit at its start.** Cross-run cache pollution is a correctness bug, not a performance bug (§6.3).
11. **`httpx` is never imported anywhere in the codebase.** All HTTP is `curl_cffi.AsyncSession`. Importing `httpx` is a regression that re-introduces an unmasked TLS fingerprint.
12. **Camoufox is used as the primary browser for all browser sessions — it is never a fallback.** A fallback architecture requires vanilla Chromium to fail first, which produces CAPTCHA-scored corrupt audit data before the fallback fires.
13. **`curl_cffi` and Camoufox are always used with their impersonation/stealth features active.** Running `curl_cffi` without `impersonate="chrome"` or Camoufox in non-headless debug mode with reduced spoofing defeats the purpose of the stack upgrade.

---

*Scoped to BEACON's Hetzner/Contabo lean stack. Celery, RabbitMQ, and a dedicated vector DB cluster are out of scope until post-launch scale justifies the overhead.*