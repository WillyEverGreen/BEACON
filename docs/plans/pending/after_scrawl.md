# BEACON Engine — Post-Scraping Pipeline Hardening Plan
**Version:** Phase 18 (Post-Scraping)
**Prepared:** April 2026
**Prerequisite:** `scrawl_update.md` (Phases 13–17) fully implemented and all pre-launch checklist gates green.
**Scope:** `audit_runner.py` · `failure_taxonomy.py` · `dedup_engine.py` · `confidence.py` · `prioritizer.py`

**Purpose:** This plan closes the gaps found in the post-scraping pipeline via a live code audit conducted after the v3 stack upgrade was documented. These are bugs in the *processing* layers — normalization, dedup, confidence, scoring, and output invariants — that exist independently of the scraping stack and are not addressed by `scrawl_update.md`.

---

## Priority Legend

| Symbol | Meaning |
|--------|---------|
| 🔴 MUST | Will cause incorrect scores, silent data corruption, or miscategorised failures on real sites |
| 🟡 SHOULD | Causes inaccurate telemetry, misleading explanations, or processing inefficiency |
| 🟢 NICE | Observability, documentation, minor accuracy improvements |

---

## Executive Summary

Four critical bugs were found in the live code that will produce wrong results even after the `scrawl_update.md` stack upgrade is fully applied:

1. **`httpx` is still in `_fetch_html()`** — the plan replaces it everywhere except the actual live fetch function, which still uses `httpx.AsyncClient`. The plan is documented but not implemented here.
2. **429 hits `_is_blocked_status()` and is misclassified as non-retryable** — even after `curl_cffi` correctly returns a real HTTP 429, the retry logic short-circuits before any backoff fires.
3. **`failure_taxonomy.py` has not been updated** — the new reason codes (`rate_limited`, `bot_wall`, `csp_blocked`) required by `normalize_failure()` in §1.0–1.1 of `scrawl_update.md` do not exist yet.
4. **`proximity_dedup()` is dead code** — fully implemented in `dedup_engine.py` but never called from `audit_runner.py`, causing near-duplicate issues to inflate all scoring.

These four must be fixed in order before any other item in this plan.

---

## Part A — Taxonomy Foundation (Must execute first)

### A.1  `failure_taxonomy.py` — Extend STANDARD_DEGRADED_REASONS + Add `normalize_failure()` 🔴 MUST

**Problem:** The live `failure_taxonomy.py` has six reason codes in `STANDARD_DEGRADED_REASONS`. `scrawl_update.md` §1.0–1.1 requires four new ones, and `normalize_failure()` — the single authoritative translator — does not exist yet. Without this, every downstream fix in `scrawl_update.md` that calls `normalize_failure()` will fail with `AttributeError` or fall back to incorrect legacy codes.

**Additionally:** `classify_failure_reason()` currently maps both 403 and 429 to `"blocked_request"`. A 429 is *recoverable with backoff*; a 403 is not. This conflation is the root cause of the "rate-limited site aborts after 3 pages" bug.

**Fix — replace `failure_taxonomy.py` entirely:**

```python
# failure_taxonomy.py — full replacement (Phase 18-A.1)
from __future__ import annotations
from enum import Enum
from typing import Any, Final

STANDARD_DEGRADED_REASONS: Final[frozenset[str]] = frozenset({
    # Legacy codes (kept for backwards compatibility with cached results)
    "dom_parse_error",
    "render_timeout",
    "extraction_failure",
    "network_error",
    "dns_failure",
    "blocked_request",          # legacy alias → mapped to bot_wall or connectivity below

    # v3 codes (introduced Phase 18)
    "connectivity_blocked",     # DNS / TCP connect failed — genuinely unreachable
    "browser_navigation_failed",# Playwright navigation threw before page loaded
    "rate_limited",             # HTTP 429 + Retry-After — recoverable with backoff
    "csp_blocked",              # CSP header prevents browser engine access
    "csp_injection_blocked",    # CSP prevents axe-core script injection
    "bot_wall",                 # 403 / CAPTCHA / JS challenge — non-recoverable without proxy
    "partial_content",          # HTML retrieved but truncated / incomplete
    "engine_error",             # Internal BEACON exception during processing
})


class DegradedReason(str, Enum):
    CONNECTIVITY_BLOCKED     = "connectivity_blocked"
    BROWSER_NAV_FAILED       = "browser_navigation_failed"
    EXTRACTION_FAILED        = "extraction_failure"
    RENDER_TIMEOUT           = "render_timeout"
    PARTIAL_CONTENT          = "partial_content"
    ENGINE_ERROR             = "engine_error"
    RATE_LIMITED             = "rate_limited"
    CSP_BLOCKED              = "csp_blocked"
    CSP_INJECTION_BLOCKED    = "csp_injection_blocked"
    BOT_WALL                 = "bot_wall"


# ── Detection helpers ──────────────────────────────────────────────

def _is_captcha_signature(raw: Any, headers: dict) -> bool:
    text = str(raw or "").lower()
    captcha_tokens = ("captcha", "are you a robot", "security check",
                      "bot protection", "cloudflare", "access denied")
    if any(token in text for token in captcha_tokens):
        return True
    server = str(headers.get("server", "")).lower()
    return "cloudflare" in server or "datadome" in server

def _has_csp_block_header(headers: dict) -> bool:
    csp = str(headers.get("content-security-policy", "")).lower()
    if not csp:
        return False
    return "script-src" in csp and "'unsafe-inline'" not in csp and "nonce-" not in csp

def _is_csp_injection_error(raw: Any) -> bool:
    text = str(raw or "").lower()
    return any(t in text for t in ("content security policy", "csp", "script-src", "evaluate"))

def _is_connect_error(raw: Any) -> bool:
    text = str(raw or "").lower()
    return any(t in text for t in (
        "dns", "getaddrinfo", "name not resolved", "name resolution",
        "nxdomain", "eai_again", "timed out connecting", "connection refused",
        "network is unreachable", "nodename nor servname",
    ))

def _is_nav_error(raw: Any) -> bool:
    text = str(raw or "").lower()
    return any(t in text for t in (
        "navigation", "net::", "page.goto", "target closed",
        "frame was detached",
    ))

def _is_timeout(raw: Any) -> bool:
    text = str(raw or "").lower()
    return any(t in text for t in ("timeout", "timed out", "navigation timeout"))

def _is_extraction_error(raw: Any) -> bool:
    text = str(raw or "").lower()
    return any(t in text for t in (
        "extraction", "snapshot", "evaluate", "selector",
        "execution context", "detached", "frame", "script",
    ))


# ── Public API ────────────────────────────────────────────────────

def normalize_failure(
    raw: str | Exception | int | None,
    *,
    http_status: int | None = None,
    headers: dict | None = None,
) -> DegradedReason:
    """
    Single source of truth for failure → DegradedReason translation.

    Checks in priority order:
    1. HTTP 429 with or without Retry-After  → rate_limited   (recoverable)
    2. HTTP 403 / CAPTCHA signature          → bot_wall       (non-recoverable)
    3. CSP header present on failure         → csp_blocked
    4. CSP injection error text              → csp_injection_blocked
    5. DNS / connect errors                  → connectivity_blocked
    6. Playwright navigation error           → browser_navigation_failed
    7. Render / stability timeout            → render_timeout
    8. HTML usable but incomplete            → extraction_failure
    9. Internal exception / unknown          → engine_error
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

    # 8. Extraction failure
    if _is_extraction_error(raw):
        return DegradedReason.EXTRACTION_FAILED

    # 9. Fallback
    return DegradedReason.ENGINE_ERROR


# ── Legacy compatibility wrappers ──────────────────────────────────
# Keep old function signatures alive so existing callers don't break
# before they are individually migrated.

def classify_failure_reason(exc: Exception | str | None) -> str:
    """Legacy wrapper — migrate callers to normalize_failure()."""
    return normalize_failure(exc).value


def normalize_reason(reason: Any) -> str:
    """Normalize legacy or unknown reason strings into the standard taxonomy."""
    text = str(reason or "").strip().lower()
    if not text:
        return ""

    legacy_map = {
        "browser_timeout": DegradedReason.RENDER_TIMEOUT.value,
        "script_failure": DegradedReason.EXTRACTION_FAILED.value,
        "unknown": DegradedReason.ENGINE_ERROR.value,
        "dns_error": DegradedReason.CONNECTIVITY_BLOCKED.value,
        "name_resolution_failed": DegradedReason.CONNECTIVITY_BLOCKED.value,
        "blocked": DegradedReason.BOT_WALL.value,
        "access_denied": DegradedReason.BOT_WALL.value,
        "cloudflare_block": DegradedReason.BOT_WALL.value,
        "blocked_request": DegradedReason.BOT_WALL.value,  # legacy → bot_wall
        "network_error": DegradedReason.CONNECTIVITY_BLOCKED.value,
        "dns_failure": DegradedReason.CONNECTIVITY_BLOCKED.value,
    }
    if text in legacy_map:
        return legacy_map[text]
    if text in STANDARD_DEGRADED_REASONS:
        return text
    return normalize_failure(text).value


def reason_message(reason_code: str, detail: str | None = None) -> str:
    """Return user-readable message for a degraded reason code."""
    normalized = normalize_reason(reason_code) or DegradedReason.ENGINE_ERROR.value
    messages = {
        DegradedReason.CONNECTIVITY_BLOCKED.value: "Site could not be reached. DNS resolution or TCP connection failed.",
        DegradedReason.RATE_LIMITED.value: "Site is rate-limiting requests. Scan will retry with backoff.",
        DegradedReason.BOT_WALL.value: "Site is blocking automated access (WAF / CAPTCHA). Scan results may be incomplete.",
        DegradedReason.CSP_BLOCKED.value: "Site's Content Security Policy prevents browser engine access.",
        DegradedReason.CSP_INJECTION_BLOCKED.value: "Site's CSP blocked axe-core injection; accessibility probes could not run.",
        DegradedReason.BROWSER_NAV_FAILED.value: "Browser navigation failed before page loaded.",
        DegradedReason.RENDER_TIMEOUT.value: "Rendering exceeded timeout; scan continued from latest DOM snapshot.",
        DegradedReason.EXTRACTION_FAILED.value: "DOM extraction encountered runtime failures; scan continued with partial coverage.",
        DegradedReason.PARTIAL_CONTENT.value: "HTML retrieved but was incomplete; static checks ran on partial document.",
        DegradedReason.ENGINE_ERROR.value: "Internal engine error during scan. Score may be lower confidence.",
    }
    base = messages.get(normalized, messages[DegradedReason.ENGINE_ERROR.value])
    return f"{base} ({detail})" if detail else base
```

**Where:** Replace `failure_taxonomy.py` entirely. The legacy wrapper functions (`classify_failure_reason`, `normalize_reason`) keep all existing callers working during migration.

**Migration gate:** After this change, grep for `classify_failure_reason` across the codebase. Each call site should be migrated to `normalize_failure()` over the next sprint. Add a deprecation warning to `classify_failure_reason`.

---

## Part B — HTTP Fetch Layer (Must execute after A.1)

### B.1  Replace `httpx` in `_fetch_html()` with `curl_cffi` 🔴 MUST

**Problem:** `audit_runner.py` L802 uses `httpx.AsyncClient` in the `_attempt()` inner function of `_fetch_html()`. This is the live HTML fetch for Fast mode. It is the only remaining `httpx` usage after the BFS/sitemap/preflight swaps in `scrawl_update.md`.

**Fix — replace the `_attempt()` function body in `_fetch_html()`:**

```python
# audit_runner.py — inside _fetch_html(), replace _attempt() body

from curl_cffi import AsyncSession
from curl_cffi.requests.errors import RequestsError

async def _attempt(
    *,
    attempt_timeout: float,
    lightweight: bool,
    attempt_index: int,
) -> tuple[Optional[str], Optional[int], str, bool]:
    try:
        async with AsyncSession(impersonate="chrome") as client:
            if lightweight:
                # Range request for partial body on unstable/CSP-heavy pages
                r = await client.get(
                    url,
                    timeout=attempt_timeout,
                    allow_redirects=True,
                    headers={"Range": f"bytes=0-{_FETCH_PARTIAL_BODY_LIMIT - 1}"},
                )
                body = r.text[:_FETCH_PARTIAL_BODY_LIMIT] if r.text else ""
            else:
                r = await client.get(url, timeout=attempt_timeout, allow_redirects=True)
                body = r.text or ""

            status_code = int(r.status_code)

        if status_code >= 400:
            logger.warning("Fetch returned status=%s for %s", status_code, url)
            if body.strip():
                return _coerce_partial_html(body), status_code, "", False
            reason = normalize_failure(status_code, http_status=status_code).value
            return None, status_code, reason, False

        if body.strip():
            return _coerce_partial_html(body), status_code, "", False
        return None, status_code, "extraction_failure", False

    except RequestsError as exc:
        # Only genuine network-layer failures reach here after curl_cffi swap.
        # TLS-layer CDN blocks now surface as real HTTP 403/429 status codes.
        reason = normalize_failure(exc).value
        retryable = reason == DegradedReason.CONNECTIVITY_BLOCKED.value
        return None, None, reason, retryable
```

**Remove:** `import httpx` from `audit_runner.py` top-level imports.

**Where:** `audit_runner.py` — replace `_attempt()` inner function (~L787–839).

---

### B.2  Fix `_is_blocked_status()` to Exclude 429 🔴 MUST

**Problem:** `_is_blocked_status()` at L773 includes `429` in the blocked set. This causes the retry loop to `break` immediately on a 429 response, returning `None, "blocked_request"` without ever calling `http_get_with_backoff`. The backoff helper from `scrawl_update.md` §2.1 is bypassed.

**Fix:**

```python
# audit_runner.py L773 — split into two functions

def _is_blocked_status(status_code: int | None) -> bool:
    """Non-recoverable block — do not retry."""
    return status_code in {401, 403, 407}

def _is_rate_limited_status(status_code: int | None) -> bool:
    """Rate-limited — recoverable with backoff."""
    return status_code == 429
```

**Update the retry loop (L872–883):**

```python
# audit_runner.py — _fetch_html retry loop
if _is_blocked_status(status_code):
    # Non-recoverable. Stop immediately.
    reason = reason or normalize_failure(status_code, http_status=status_code).value
    break

if _is_rate_limited_status(status_code):
    # Recoverable. Honour Retry-After if present, then continue.
    retry_after = float(meta.get("retry_after_seconds") or 2 ** (idx + 1))
    await asyncio.sleep(min(retry_after, 15.0))
    continue  # do NOT count as failure; do NOT break

should_retry = retryable_exc or _is_retryable_http_status(status_code)
if should_retry and idx < len(attempt_budgets) - 1:
    continue
break
```

**Where:** `audit_runner.py` L773–883.

---

## Part C — Deduplication Layer

### C.1  Wire `proximity_dedup()` — Currently Dead Code 🔴 MUST

**Problem:** `proximity_dedup()` is fully implemented in `dedup_engine.py` but is never imported or called from `audit_runner.py`. Near-duplicate issues (same rule, slightly different CSS selector paths — e.g. `div.container > img` vs `div.container > img:nth-child(2)`) survive the primary dedup pass and double-count in the scoring penalty calculation.

**Fix — add import and call in `audit_runner.py`:**

```python
# audit_runner.py — top of file imports
from app.services.dedup_engine import deduplicate, proximity_dedup  # add proximity_dedup

# audit_runner.py — in run_audit(), after the existing deduplicate() call:
issues = deduplicate(issues)
issues = proximity_dedup(issues)   # ← ADD THIS LINE
```

This is a 2-line change. No other modifications required.

**Where:** `audit_runner.py` — import line + one call in the main pipeline.

**Expected impact:** 5–15% reduction in issue count on real sites with repeated structural violations (landmark rules, list rules, heading hierarchy). Scoring will become more accurate for these patterns.

---

## Part D — Processing Layer Fixes

### D.1  Reorder Hybrid Enforcement Before Precision Profile Filter 🟡 SHOULD

**Problem:** In `audit_runner.py`, the current execution order is:

```
apply_confidence_rules(issues)
→ _apply_precision_profile(issues)      ← filters by min_confidence
→ _enforce_hybrid_required_rules(issues) ← checks for required signal presence
```

If an issue contributing a required signal for a hybrid rule (e.g. `focus-management`) scores below `min_confidence` and is filtered by the precision profile, `_enforce_hybrid_required_rules` never sees it. It reports the signal as missing and penalises the hybrid rule — even though BEACON did detect the signal, it was just filtered for being low-confidence.

**Fix — move `_enforce_hybrid_required_rules` before the precision profile filter:**

```python
# audit_runner.py — reorder in run_audit()

issues = apply_confidence_rules(issues, html=html)

# Run hybrid check on FULL pre-filtered set to capture all observed signals.
issues, hybrid_telemetry = _enforce_hybrid_required_rules(issues)

# THEN filter by precision profile (may drop low-confidence issues).
issues, profile_telemetry = _apply_precision_profile(issues, profile=precision_profile)
```

**Where:** `audit_runner.py` — reorder three function calls.

---

### D.2  Document and Consolidate the Double Confidence Boost 🟡 SHOULD

**Problem:** `apply_confidence_rules()` applies two separate confidence boosts that overlap:

1. `_apply_production_confidence_boost()` per-issue (L373): boosts by +0.15 when `source_count >= 2`
2. `_boost_cross_engine_agreement()` at the end (L447): floors to 0.85 when any two engines report the same `rule_id` across all issues

A 2-engine finding can receive both boosts. The 0.95 cap in `_apply_production_confidence_boost` and the `max(current, floor)` approach in `_boost_cross_engine_agreement` prevent runaway values, so the output is numerically correct — but the intent is not documented.

**Fix — add contract comment and consolidate into one pass:**

```python
# confidence.py — apply_confidence_rules() — replace the two-boost pattern:

# NOTE: Confidence boosts are applied in two passes by design:
# Pass 1 (_apply_production_confidence_boost): per-issue boost based on
#         source count, recurrence, and structural trust. Capped at 0.95.
# Pass 2 (_boost_cross_engine_agreement): rule-level floor boost when
#         2+ independent engines report the same rule_id. Uses max(current, floor)
#         so Pass 1 results are never lowered.
# These are intentionally additive — Pass 2 is a floor, not an addition.
# A finding that scores 0.92 from Pass 1 will not be raised further by
# the 0.85 floor in Pass 2. A finding scoring 0.70 from Pass 1 will be
# floored to 0.85.
```

**Long term:** Consolidate into a single `_apply_all_confidence_boosts()` function so the interaction is explicit in one place.

**Where:** `confidence.py` — add docstring comment after L447. Consolidation can be done in a follow-up sprint.

---

### D.3  Clarify the Degraded Penalty Dual-Application 🟡 SHOULD

**Problem:** The degraded penalty is applied in two separate files with no shared contract:

1. `prioritizer.build_scoring_summary()` L629: `score = max(0.0, score * 0.85)`
2. `audit_runner._apply_score_integrity_caps()`: caps `score` at `82.0` when `degraded_mode`

These interact correctly (the `*0.85` reducer and the `82.0` cap are not double-applied on the same issue), but the logic is split across files without explanation. The `score_explanation.degraded_mode_penalty` field further reports an approximation rather than the exact applied value.

**Fix — add a shared contract constant and fix the explanation field:**

```python
# config.py — add to scoring constants
DEGRADED_MODE_MULTIPLIER = 0.85       # multiplier applied in build_scoring_summary
DEGRADED_MODE_MAX_SCORE  = 82.0       # hard cap applied in _apply_score_integrity_caps
# These two work in sequence: multiplier runs first, cap enforces the ceiling.
# Do NOT apply both as additive penalties — they are a multiplier+ceiling pair.

# prioritizer.py L672 — fix score_explanation to report actual penalty:
"degraded_mode_penalty": round(pre_adjusted_score - score, 3) if degraded_mode else 0.0,
# pre_adjusted_score is the score before *0.85; score is after. The delta is the true applied penalty.
```

**Where:** `config.py` (add constants), `prioritizer.py` L672 (fix explanation field).

---

## Part E — Observability Additions

### E.1  Log Trust Payload Regeneration in `_enforce_audit_invariants` 🟢 NICE

**Problem:** When `_enforce_audit_invariants` detects a missing `trust` payload and regenerates it from available telemetry (L523–552), this is a sign that the main pipeline failed to produce a trust payload. This is a correctness event — a regenerated payload is less accurate than the original — but it is currently silent.

**Fix:**

```python
# audit_runner.py L524 — add structured warning before regeneration:
if not isinstance(trust_payload, dict) or not trust_payload:
    logger.warning(
        "Invariant: trust payload missing for audit_id=%s. "
        "Regenerating from available telemetry. "
        "Root cause: trust payload not produced by main pipeline path.",
        result.get("audit_id", "unknown"),
        extra={"invariant_trust_regenerated": True},
    )
    # ... existing regeneration code ...
```

**Where:** `audit_runner.py` ~L524.

---

### E.2  Add `http_client` and `browser_engine` to Structured Audit Logs 🟢 NICE

The `scrawl_update.md` §4.4 updated the structured audit log schema to include `http_client` and `browser_engine` fields. These need to be populated in `_finalize_result()`.

```python
# audit_runner.py — in _finalize_result() before record_audit_event():
result.setdefault("http_client", "curl_cffi/chrome")
result.setdefault("browser_engine", "camoufox/firefox")
```

**Where:** `audit_runner.py` — `_finalize_result()`.

---

## Part F — Dashboard Transparency

### F.1  Expose `urls_audited` to Dashboard API 🟢 NICE

**Problem:** Automated scanners act as black boxes. When BEACON audits 15 pages in max mode, the user only sees "15 pages scanned". They do not know *which* pages were scanned, leading to reduced trust and questions like "Did it scan the checkout flow?"

**Fix — pass `urls_audited` through the normalizer to the database:**

1. **Backend (`dashboard_api.py`) L236:**
Update `_normalize_site_scan_result()` to return `scraped_pages`:
```python
    return {
        # ... existing ...
        "scraped_pages": site_payload.get("urls_audited", []),
    }
```

2. **Backend (`dashboard_api.py`) L690:**
Ensure `scraped_pages` flows into `scan_record`:
```python
            scan_record["scraped_pages"] = result.get("scraped_pages", [])
```

3. **Frontend:** Update the UI payload to consume `scraped_pages` and display a "Pages Audited" accordion in the scan report.

**Where:** `dashboard_api.py`.

---

## Part G — Premium UX: Code Snippets & Remediation UI

### G.1 Display Actionable Code Snippets and Fixes 🟢 NICE

**Problem:** Users do not just want to know they have "23 issues". They need to know *where* the issue is and *how* to fix it. Without snippets, an error like "Image missing alt text" is unactionable. 

**Fix — Front-end UI enhancement using existing backend payloads:**
The `AuditIssue` model in `app/models.py` already computes and truncates `html_snippet` (≤500 chars) and generates a `code_fix`. The backend already supports this; we only need to surface it in the UI properly.

1. **The Issue Header:** Show the `description` and the `severity` badge.
2. **The "Where" Block (Read-Only):**
   Render the `html_snippet` inside a syntax-highlighted code block.
3. **The "Fix" Block (Interactive):**
   Render the `code_fix` in a distinct (e.g., green-tinted) code box with a **[Copy Fix]** button. 
4. **Noise Filtering:**
   Only display snippet blocks for structural issues (`issue_type == "violation"`). Hide them for system-level errors (like `bot_wall` or `render_timeout`).

**Where:** Frontend Component Repository (UI layer).

---

## Implementation Order

| Phase | Sprint | Items | Acceptance Criterion |
|-------|--------|-------|---------------------|
| 18-A | Week 1, Day 1 | A.1 | `failure_taxonomy.py` replaced; `normalize_failure()` exists; legacy wrappers pass all existing tests |
| 18-B | Week 1, Day 2–3 | B.1 + B.2 | `httpx` removed from `audit_runner.py`; `curl_cffi` in `_fetch_html()`; 429 triggers backoff not break; `import httpx` deleted |
| 18-C | Week 1, Day 4 | C.1 | `proximity_dedup()` called; integration test confirms near-dupe reduction on a site with repeated `region`/`list` violations |
| 18-D | Week 2 | D.1 + D.2 + D.3 | Hybrid telemetry accurate on pre-filter issue set; degraded penalty documented; score_explanation accurate |
| 18-E | Week 2 | E.1 + E.2 | Trust regeneration events visible in structured logs; `http_client` + `browser_engine` in every audit log line |
| 18-F | Week 2 | F.1 | Dashboard API returns `scraped_pages` list for multi-page scans |
| 18-G | Week 3 (UX) | G.1 | Frontend gracefully renders code snippets and fix blocks, masking system-level degraded failures |
| Launch | — | All gates below | All gates green → production-ready |

---

## Pre-Launch Checklist (Phase 18 Additions)

These stack on top of the `scrawl_update.md` §5 checklist.

### Code Gates
- [ ] `import httpx` does not appear anywhere in `audit_runner.py`
- [ ] `_fetch_html()` uses `curl_cffi.AsyncSession(impersonate="chrome")` internally
- [ ] `normalize_failure()` exists in `failure_taxonomy.py` and is the only constructor of `DegradedReason` values
- [ ] `classify_failure_reason()` carries a `DeprecationWarning` log on every call
- [ ] `429` responses from `_fetch_html()` trigger `asyncio.sleep(retry_after)` and retry — not an immediate `break`
- [ ] `proximity_dedup()` is called in `audit_runner.py` after `deduplicate()`
- [ ] `_enforce_hybrid_required_rules()` runs before `_apply_precision_profile()` in the pipeline order
- [ ] `score_explanation.degraded_mode_penalty` reflects the exact applied penalty, not an approximation
- [ ] `DEGRADED_MODE_MULTIPLIER` and `DEGRADED_MODE_MAX_SCORE` constants exist in `config.py`
- [ ] Trust payload regeneration emits a structured `WARNING` log with `invariant_trust_regenerated=True`
- [ ] `scraped_pages` array containing the executed URLs is returned in the API payload for multi-page scans

### Test Gates
- [ ] New fixture: `http_429_with_retry_after.json` → audit returns `degraded_reason: "rate_limited"`, not `"bot_wall"` or `"blocked_request"`
- [ ] New fixture: `near_dupe_selectors.html` → `proximity_dedup` reduces issue count before it reaches scoring
- [ ] Hybrid enforcement test: a `focus-management` issue filtered by precision profile does not cause "missing signal" warning
- [ ] Mode consistency tests from `scrawl_update.md` §1.8 still green after `failure_taxonomy.py` replacement

---

## Architectural Invariants (Phase 18 Additions)

These extend the 13 invariants in `scrawl_update.md`.

14. **`normalize_failure()` is the only place that constructs `DegradedReason` values. `classify_failure_reason()` is a deprecated shim — do not add new call sites.**
15. **`429` is never treated as `_is_blocked_status()`. Rate limiting is recoverable; a blocked status is not. These must be two separate functions.**
16. **`proximity_dedup()` always runs after `deduplicate()` in the main pipeline. Removing either call invalidates the dedup contract.**
17. **`_enforce_hybrid_required_rules()` always runs on the full pre-filter issue set. Running it after `_apply_precision_profile()` is a correctness bug, not an optimisation.**
18. **`score_explanation.degraded_mode_penalty` must reflect the exact difference between pre- and post-degraded scores. Approximations that diverge by more than 1.0 are reportable invariant violations.**

---

*This plan is a direct continuation of `scrawl_update.md`. Execute `scrawl_update.md` in full first, then execute this plan in the order above. After both are complete, all pre-launch checklist gates across both documents must be green before production deployment.*

---

## Part H — Environment & Dependency Gaps (Missing from Both Plans)

These gaps will break a clean installation even after all code changes are applied.

### H.1  Update `requirements.txt` 🔴 MUST

**Problem:** `curl_cffi` and `camoufox[geoip]` are not in `requirements.txt`. `httpx` is still listed. Any fresh `pip install -r requirements.txt` installs the wrong stack and breaks everything.

**Fix:**
```
# Remove:
httpx==0.27.2

# Add:
curl_cffi>=0.7.0
camoufox[geoip]>=0.4.0
```

**Where:** `requirements.txt`.

---

### H.2  Download Camoufox Browser Binaries 🔴 MUST

**Problem:** Installing `camoufox` as a Python package does NOT download the actual Firefox stealth browser binary. Without running `camoufox fetch`, any call to `AsyncNewBrowser()` will raise `RuntimeError: Camoufox binary not found`.

**Fix — add a one-time setup step to the project README and Dockerfile:**
```bash
pip install "camoufox[geoip]"
python -m camoufox fetch   # downloads stealth Firefox binary (~120MB)
```

**Where:** `README.md` (setup section), `Dockerfile` (if containerized), CI pipeline pre-build step.

---

### H.3  Remove Stray `httpx` Imports Not Covered by Either Plan 🔴 MUST

The live code scan shows `httpx` is still imported in **four files** not addressed by either plan:

| File | Line | Purpose | Fix |
|---|---|---|---|
| `app/audit/scan_mode_runner.py` | L8 | `_fast_state_provider` HTTP fetch | Replace with `curl_cffi.AsyncSession` |
| `app/observability/alerts.py` | L10 | Likely HTTP webhook or health-check | Replace or remove if unused |
| `app/crawlers/page_selector.py` | L11 | HTTP fallback in link extractor | Replace with `curl_cffi.AsyncSession` |
| `app/crawlers/bfs_crawler.py` | L11 | BFS link fetcher | Covered by `scrawl_update.md §2.1` — confirm done |

**Where:** Each file listed above.

---

### H.4  `robots.txt` `Disallow` Enforcement 🟡 SHOULD

**Problem:** `scrawl_update.md §2.2` documents this fix but it is **not marked as implemented**. The BFS crawler still crawls paths listed under `Disallow:` in `robots.txt`. This will trigger bot-defenses on enterprise/legal sites and may violate ToS in a commercial SaaS context.

**Fix:** As specified in `scrawl_update.md §2.2` — implement `parse_robots_disallow()` in `common.py` and wire it into `bfs_crawler.py` and `sitemap_crawler.py`.

---

### H.5  Sitemap Recursion Depth Cap 🟡 SHOULD

**Problem:** `scrawl_update.md §2.6` documents this fix but is **not marked as implemented**. A malformed or adversarial `sitemapindex` XML with unique child URLs at each level will recurse until Python stack overflow or OOM.

**Fix:** Add `MAX_SITEMAP_DEPTH = 5` to `config.py` and add a `depth` parameter to `_crawl_sitemap()` with an early-return guard.

**Where:** `sitemap_crawler.py` L110–142 and `config.py`.

---

## Part I — Database Schema Gap

### I.1  Add `scraped_pages` Column to Dashboard Scans Table 🔴 MUST

**Problem:** Part F wires `scraped_pages` into the `scan_record` dict, but the dashboard uses its own SQL-backed scan model (in `app/db/dashboard_repository.py`). There is no `scraped_pages` column in the scans table. The data will be silently lost on every write.

**Fix:**

1. **`app/db/dashboard_repository.py`:** Ensure `scraped_pages` is serialized/deserialized alongside other JSON fields (like `issues` and `groups`).
2. **`alembic`:** Create a new migration:
```python
# alembic/versions/xxxx_add_scraped_pages.py
def upgrade():
    op.add_column("scans", sa.Column("scraped_pages", sa.Text(), nullable=True, server_default="[]"))
```
3. **`scan_record` initialization** in `dashboard_api.py` L600 block: add `"scraped_pages": []` to the initial record dict.

**Where:** `dashboard_api.py`, `app/db/dashboard_repository.py`, new `alembic` migration.

---

## Part J — Frontend UI Gaps

These are issues found directly in `frontend/src/app/dashboard/[projectId]/page.tsx` that are not addressed in any existing plan.

### J.1  "Copy Fix" Button on Code Snippets 🟢 NICE

**Problem:** The `code_fix` field is rendered inside a read-only `<pre>` block (L696–707). There is **no copy button**. Developers must manually select and copy multi-line HTML fixes, which is clunky.

**Fix — add a [Copy] button above the code fix block:**
```tsx
// Inside renderIssueCard, wrap the code_fix block:
<div className="relative">
  <button
    onClick={() => navigator.clipboard.writeText(issue.code_fix)}
    className="absolute top-2 right-2 text-[9px] font-black uppercase tracking-widest
               bg-[var(--beacon-success)]/20 border border-[var(--beacon-success)]/40
               text-[var(--beacon-success)] px-2 py-1 rounded hover:bg-[var(--beacon-success)]/40
               transition-colors"
  >
    Copy
  </button>
  <pre>...</pre>
</div>
```

**Where:** `[projectId]/page.tsx` — `renderIssueCard` function around L696.

---

### J.2  "Pages Audited" Accordion (Scraped Pages Transparency) 🟢 NICE

**Problem:** Even after Part F and I.1 persist `scraped_pages`, the frontend **never renders them**. Users continue to see only the integer `pages_scanned` count.

**Fix — add a collapsible "Pages Audited" section in the Overview tab, visible only when `scan_mode` is `deep` or `max`:**
```tsx
{latestScan.scraped_pages?.length > 1 && (
  <details className="glass-card p-5 mt-4 group">
    <summary className="text-xs font-bold uppercase tracking-widest cursor-pointer
                        text-[var(--beacon-text-muted)] flex items-center gap-2">
      <IconChevron className="w-4 h-4 transition-transform group-open:rotate-180" />
      Pages Audited ({latestScan.scraped_pages.length})
    </summary>
    <ul className="mt-4 space-y-1.5 max-h-64 overflow-y-auto">
      {latestScan.scraped_pages.map((url: string) => (
        <li key={url} className="text-xs font-mono text-[var(--beacon-text-soft)]
                                  bg-[var(--beacon-surface)] border border-[var(--beacon-border)]
                                  px-3 py-1.5 rounded truncate">
          {url}
        </li>
      ))}
    </ul>
  </details>
)}
```

**Where:** `[projectId]/page.tsx` — Overview tab, below the AI Analysis card.

---

### J.3  Degraded Mode Banner 🟡 SHOULD

**Problem:** When `latestScan.degraded_mode === true`, users currently see **no visual indication** that the scan ran in a degraded state (e.g., bot wall prevented browser probes). The score is shown as if it were a full-confidence audit.

**Fix — add a warning banner at the top of the result whenever `degraded_mode` is `true`:**
```tsx
{latestScan?.degraded_mode && (
  <div className="glass-card p-4 mb-6 border-l-[6px] border-l-[var(--beacon-warning)]
                  bg-[var(--beacon-warning)]/5 flex items-start gap-3">
    <span className="text-xl shrink-0">⚠️</span>
    <div>
      <p className="text-sm font-bold text-[var(--beacon-warning)] uppercase tracking-wider mb-1">
        Degraded Scan
      </p>
      <p className="text-sm font-medium text-[var(--beacon-text-soft)]">
        {latestScan.degraded_reason
          ? `Some audit engines could not run: ${latestScan.degraded_reason}.`
          : "Some audit engines could not run."}
        {" "}Results may be incomplete. Run a new scan to get a full result.
      </p>
    </div>
  </div>
)}
```

**Where:** `[projectId]/page.tsx` — immediately after the Score Strip block.

---

### J.4  `null` Score Handling 🟡 SHOULD

**Problem:** `scrawl_update.md §1.7` specifies that when `confidence_score < 0.3`, the score should be `null` (not `0`), and the UI should show `"Scan incomplete"` instead of `0/100`. Currently the UI renders `null` as `"—"` in the score strip, which is correct, but there is **no explanatory badge or message** explaining why the score is missing.

**Fix — add conditional text below the score stat card:**
```tsx
{score === null && (
  <p className="text-[9px] font-bold uppercase tracking-wider
                text-center text-[var(--beacon-error)] mt-1">
    Scan Incomplete
  </p>
)}
```

**Where:** `[projectId]/page.tsx` — inside the score stat card block around L876.

---

## Updated Implementation Order

| Phase | Sprint | Items | Acceptance Criterion |
|-------|--------|-------|---------------------|
| 18-A | Week 1, Day 1 | A.1 | `failure_taxonomy.py` replaced; `normalize_failure()` exists |
| 18-B | Week 1, Day 2–3 | B.1 + B.2 | `httpx` removed from `audit_runner.py`; 429 triggers backoff |
| 18-C | Week 1, Day 4 | C.1 | `proximity_dedup()` called |
| 18-H | Week 1, Day 1 (alongside A) | H.1 + H.2 + H.3 | `requirements.txt` updated; Camoufox binary downloaded; all stray `httpx` imports removed |
| 18-I | Week 1, Day 1 (alongside A) | I.1 | `scraped_pages` column added via Alembic migration |
| 18-D | Week 2 | D.1 + D.2 + D.3 | Hybrid telemetry accurate; degraded penalty documented |
| 18-E | Week 2 | E.1 + E.2 | Trust logs visible; `http_client` + `browser_engine` in audit logs |
| 18-F | Week 2 | F.1 | Dashboard API returns `scraped_pages` list |
| 18-G | Week 3 (UX) | G.1 | Code snippets render with type-based noise filtering |
| 18-J | Week 3 (UX) | J.1 + J.2 + J.3 + J.4 | Copy button on fixes; Pages Audited accordion; Degraded banner; null score badge |
| 18-H-post | Week 3 | H.4 + H.5 | `robots.txt` disallow enforced; sitemap depth cap active |
| Launch | — | All gates below | All gates green → production-ready |

---

## Pre-Launch Checklist Additions (Parts H, I, J)

### Code Gates
- [ ] `httpx` does not appear in `requirements.txt`
- [ ] `curl_cffi>=0.7.0` and `camoufox[geoip]>=0.4.0` are in `requirements.txt`
- [ ] `camoufox fetch` is documented in `README.md` setup section
- [ ] `import httpx` does not appear in `scan_mode_runner.py`, `alerts.py`, or `page_selector.py`
- [ ] `scraped_pages` column exists in the dashboard scans SQL table
- [ ] Alembic migration for `scraped_pages` is committed and applied
- [ ] `MAX_SITEMAP_DEPTH` constant exists in `config.py`
- [ ] `parse_robots_disallow()` is called and wired into BFS and sitemap crawlers
- [ ] Degraded mode banner renders in the UI when `degraded_mode === true`
- [ ] "Copy Fix" button present on `code_fix` blocks in issue cards
- [ ] "Pages Audited" accordion renders for deep/max scans with `scraped_pages.length > 1`
- [ ] Score strip shows "Scan Incomplete" text when `score === null`



## 🟢 PHASE 17 CERTIFICATION STATUS

**STATUS: CERTIFIED (PRODUCTION-READY)**

The runtime success rate blockages from httpx->curl_cffi migration (wrong kwargs, allow_redirects API mismatch, and degraded_reason enum serialization) were resolved in the Phase 17 Certification Audit.

* **Unit Test Pass Rate:** 100% (75/75)
* **Runtime Benchmark Success Rate:** 91.7%

Full certification report stored at: `docs/reports/phase17_certification_audit.md`
