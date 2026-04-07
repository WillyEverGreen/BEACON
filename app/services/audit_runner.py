"""
Audit runner: orchestrates the full multi-engine accessibility audit pipeline.

Pipeline:
1. Fetch/render page (httpx for fast/minimal, Playwright for deep/max)
2. Run static checks + heuristics + browser probes in parallel
3. Normalize -> deduplicate -> confidence score
4. Cognitive checks (deep/max)
5. Group -> RAG remediation -> merge
6. Generate report -> output
"""
import asyncio
import hashlib
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

from app.config import QUALITY_GATES, SEVERITY_WEIGHTS, SCORING_CONFIG, settings
from app.config import PRECISION_PROFILES
from app.audit.dynamic_handling import resolve_adaptive_timeouts, stable_request_headers
from app.audit.failure_taxonomy import classify_failure_reason, normalize_reason, reason_message
from app.services.static_checks import StaticChecker
from app.services.heuristics import HeuristicAnalyzer
from app.services.normalizer import normalize_all
from app.services.dedup_engine import deduplicate
from app.services.confidence import apply_confidence_rules
from app.services.grouper import group_issues
from app.services.report import generate_markdown_report
from app.services.cognitive_checks import CognitiveAnalyzer
from app.services.llm import enrich_issues
from app.services.page_cache import (
    get_url_hash, clean_html_for_hash, get_dom_hash, check_cache, save_to_cache
)
from app.services.prioritizer import prioritize_issues
from app.services.aggregator import aggregate_issues
from app.db.repository import persist_audit_payload, persist_enrichment_payload
from app.observability.alerts import evaluate_audit_alerts, notify_llm_failure
from app.observability.telemetry import record_audit_event
from app.security.url_validator import URLValidationError, validate_public_url

logger = logging.getLogger(__name__)

_browser_semaphore = asyncio.Semaphore(3)
_enrichment_tasks: dict[str, asyncio.Task] = {}
_enriched_results: dict[str, dict] = {}
_active_audits = 0
_MAX_CONCURRENT_AUDITS = 20

_FETCH_DOMAIN_CONCURRENCY_LIMIT = 2
_FETCH_DOMAIN_SEMAPHORES: dict[str, asyncio.Semaphore] = {}
_FETCH_DOMAIN_LOCK = asyncio.Lock()
_FETCH_PARTIAL_BODY_LIMIT = 200_000

_RULE_QUALITY_POLICY_CACHE: dict[str, Any] | None = None


def _classify_degraded_reason_from_error(exc: Exception | str | None) -> str:
    return classify_failure_reason(exc)


def _degradation_reason_message(reason_code: str, detail: str | None = None) -> str:
    return reason_message(reason_code, detail)


def _single_page_site_result(*, score: float, total_issues: int, url: str) -> dict[str, Any]:
    """Build a normalized site_result payload for single-page audit responses."""
    safe_score = round(float(score), 1)
    top_fix = ""
    if total_issues > 0:
        top_fix = "Fix top-ranked issues first"

    return {
        "scan_mode": "single_page",
        "site_score": safe_score,
        "worst_page_score": safe_score,
        "worst_page": {"url": str(url), "score": safe_score},
        "best_page": {"url": str(url), "score": safe_score},
        "pages_audited": 1,
        "pages_discovered": 1,
        "issues": [],
        "priority_ranking": [],
        "executive_summary": {
            "site_score": safe_score,
            "worst_page": {"url": str(url), "score": safe_score},
            "best_page": {"url": str(url), "score": safe_score},
            "critical_issues": 0,
            "pages_audited": 1,
            "pages_discovered": 1,
            "top_fix": top_fix,
        },
    }


def _safe_score_fallback(*, pages_audited: int, issues: list[dict[str, Any]], degraded_mode: bool) -> float:
    """Return a non-zero fallback score when invariants detect invalid score output."""
    safe_pages = max(1, int(pages_audited or 1))
    safe_issues = issues if isinstance(issues, list) else []

    if safe_issues:
        recalculated, _ = _calculate_score(safe_issues, degraded_mode=degraded_mode)
        return round(max(1.0, float(recalculated)), 1)

    # Empty issue set should remain in the high-score range by design.
    baseline = 96.0 - min(4.0, (safe_pages - 1) * 0.5)
    if degraded_mode:
        baseline = max(85.0, baseline - 5.0)
    return round(max(1.0, baseline), 1)


def _enforce_audit_invariants(result: dict[str, Any]) -> dict[str, Any]:
    """Enforce non-empty schema + non-zero score guarantees for audited pages."""
    if not isinstance(result, dict):
        return result

    issues = result.get("issues")
    if not isinstance(issues, list):
        logger.error("Invariant violation: issues was not a list. Coercing to empty list.")
        issues = []
    result["issues"] = issues
    result["total_issues"] = len(issues)

    pages_audited = int(result.get("pages_audited") or 0)
    degraded_mode = bool(result.get("degraded_mode", False))
    degraded_reason = normalize_reason(result.get("degraded_reason"))

    if degraded_mode and not degraded_reason:
        fallback_reason = _classify_degraded_reason_from_error(result.get("degradation_reason"))
        result["degraded_reason"] = fallback_reason
        if not result.get("degradation_reason"):
            result["degradation_reason"] = _degradation_reason_message(fallback_reason)
    elif degraded_reason:
        result["degraded_reason"] = degraded_reason
        if not result.get("degradation_reason"):
            result["degradation_reason"] = _degradation_reason_message(degraded_reason)

    if pages_audited > 0:
        score_value = result.get("score")
        score_is_invalid = not isinstance(score_value, (int, float)) or float(score_value) <= 0.0
        if score_is_invalid:
            fallback_score = _safe_score_fallback(
                pages_audited=pages_audited,
                issues=issues,
                degraded_mode=degraded_mode,
            )
            logger.error(
                "Invariant violation: non-positive score with pages_audited=%s. Applying safe fallback score=%s",
                pages_audited,
                fallback_score,
            )
            result["score"] = fallback_score
            quality = result.get("quality_gates")
            if not isinstance(quality, dict):
                quality = {}
            quality["invariant_safe_score_applied"] = True
            result["quality_gates"] = quality

        if result.get("enrichment_status") == "failed":
            audit_id = str(result.get("audit_id") or "")
            task = _enrichment_tasks.get(audit_id) if audit_id else None
            if task and not task.done():
                logger.error(
                    "Invariant violation: base audit marked enrichment_status=failed despite pages_audited=%s while "
                    "a background enrichment task is still active. Coercing to pending.",
                    pages_audited,
                )
                result["enrichment_status"] = "pending"

        site_result = result.get("site_result")
        if not isinstance(site_result, dict):
            result["site_result"] = _single_page_site_result(
                score=float(result.get("score") or 0.0),
                total_issues=len(issues),
                url=str(result.get("url") or ""),
            )
        else:
            if int(site_result.get("pages_audited") or 0) <= 0:
                logger.error("Invariant violation: site_result.pages_audited <= 0. Repairing value.")
                site_result["pages_audited"] = pages_audited
            if float(site_result.get("site_score") or 0.0) <= 0:
                logger.error("Invariant violation: site_result.site_score <= 0. Repairing value.")
                site_result["site_score"] = float(result.get("score") or 1.0)
            result["site_result"] = site_result

    return result


def _upgrade_cached_deep_result(result: dict, requested_mode: str) -> dict:
    """Backfill degradation metadata for older cached deep scans lacking browser evidence."""
    if requested_mode not in {"deep", "max"}:
        return result

    engines_used = result.get("engines_used") or []
    has_browser_evidence = "browser-probe" in engines_used or "axe-core" in engines_used
    if has_browser_evidence:
        return result

    # If this was already marked degraded, keep it untouched.
    if result.get("degraded_mode") is True:
        return result

    result["degraded_mode"] = True
    result["degraded_reason"] = normalize_reason(result.get("degraded_reason")) or "extraction_failure"
    result["degradation_reason"] = (
        result.get("degradation_reason")
        or "Deep scan requested, but browser engines did not execute. Results are based on static HTML analysis only."
    )

    skipped = set(result.get("skipped_components") or [])
    skipped.update(["browser_probes", "axe-core"])
    result["skipped_components"] = sorted(skipped)

    summary = result.get("summary") or ""
    if "DEGRADED" not in summary.upper():
        if " | Engines:" in summary:
            summary = summary.replace(" | Engines:", " | ⚠️ DEGRADED | Engines:")
        elif summary:
            summary = f"{summary} | ⚠️ DEGRADED"
        result["summary"] = summary

    # Apply conservative degraded penalty once for legacy cached results.
    score = result.get("score")
    if isinstance(score, (int, float)) and score is not None:
        adjusted = round(max(0.0, float(score) * 0.85), 1)
        result["score"] = adjusted

        score_explanation = result.get("score_explanation")
        if not isinstance(score_explanation, dict):
            score_explanation = {}
        score_explanation["degraded_mode_penalty"] = round(float(score) - adjusted, 2)
        result["score_explanation"] = score_explanation

    return result


def _is_invalid_cached_result(result: dict[str, Any]) -> bool:
    """Detect stale/poisoned cached payloads that violate hard output invariants."""
    if not isinstance(result, dict):
        return True

    pages_audited = int(result.get("pages_audited") or 0)
    issues = result.get("issues")
    if not isinstance(issues, list):
        issues = []

    total_issues_raw = result.get("total_issues")
    if isinstance(total_issues_raw, int):
        total_issues = total_issues_raw
    else:
        total_issues = len(issues)

    score_raw = result.get("score")
    try:
        score = float(score_raw)
    except (TypeError, ValueError):
        score = -1.0

    enrichment_status = str(result.get("enrichment_status", "")).lower()

    # Non-empty audits must always report at least one audited page.
    if pages_audited <= 0:
        return True

    # Critical regression signature: zero score + zero issues.
    if score <= 0.0 and total_issues == 0:
        return True

    # Base audit payload should never be served as failed enrichment.
    if enrichment_status == "failed":
        return True

    return False

def get_enriched_results(audit_id: str) -> dict:
    """Return enrichment status or results if complete, else pending block."""
    res = _enriched_results.get(audit_id)
    if not res:
        task = _enrichment_tasks.get(audit_id)
        if task:
            return {"status": "pending", "message": "Enrichment is still processing in the background."}
        return {"status": "not_found", "message": "Invalid or expired audit ID."}
    
    # Optional cleanup to avoid memory bloat
    _enrichment_tasks.pop(audit_id, None)
    return res


def _finalize_result(result: dict[str, Any], *, status: str, persist_db: bool = True) -> dict[str, Any]:
    """Persist DB state and emit telemetry/alert side effects for an audit result."""
    result = _enforce_audit_invariants(result)

    if persist_db:
        try:
            result["audit_id"] = persist_audit_payload(result, status=status)
        except Exception as exc:
            logger.error("Failed to persist audit payload: %s", exc)

    try:
        event = record_audit_event(result, status=status)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(evaluate_audit_alerts(event))
        except RuntimeError:
            pass
    except Exception as exc:
        logger.error("Failed to record telemetry event: %s", exc)

    return result

def _get_rule_quality_policy() -> dict[str, Any]:
    """Load optional external rule-quality policy from app/data."""
    global _RULE_QUALITY_POLICY_CACHE
    if _RULE_QUALITY_POLICY_CACHE is not None:
        return _RULE_QUALITY_POLICY_CACHE

    policy_path = Path(__file__).resolve().parents[1] / "data" / "rule_quality_policy.json"
    if not policy_path.exists():
        _RULE_QUALITY_POLICY_CACHE = {}
        return _RULE_QUALITY_POLICY_CACHE

    try:
        with policy_path.open("r", encoding="utf-8") as f:
            _RULE_QUALITY_POLICY_CACHE = json.load(f)
    except Exception:
        # Fail open if policy file is invalid.
        _RULE_QUALITY_POLICY_CACHE = {}

    return _RULE_QUALITY_POLICY_CACHE


def _merge_profile_with_policy(profile_name: str, profile: dict[str, Any]) -> dict[str, Any]:
    """Merge external policy patch into the in-code precision profile."""
    policy = _get_rule_quality_policy()
    profile_patches = policy.get("profiles", {}) if isinstance(policy, dict) else {}
    patch = profile_patches.get(profile_name, {}) if isinstance(profile_patches, dict) else {}
    if not isinstance(patch, dict) or not patch:
        return profile

    merged = dict(profile)

    base_exclude = set(merged.get("exclude_rules", []))
    patch_exclude = set(patch.get("exclude_rules", []))
    if base_exclude or patch_exclude:
        merged["exclude_rules"] = sorted(base_exclude | patch_exclude)

    for key in ("per_rule_min_confidence", "per_rule_confidence_override", "suppress_when_present"):
        base_val = merged.get(key, {})
        patch_val = patch.get(key, {})
        if isinstance(base_val, dict) and isinstance(patch_val, dict):
            merged[key] = {**base_val, **patch_val}

    for key in ("min_confidence", "include_needs_review", "exclude_contextual_single_source"):
        if key in patch:
            merged[key] = patch[key]

    return merged


async def _fetch_html(url: str, timeout: float = 15.0) -> tuple[Optional[str], str, dict[str, Any]]:
    """Fetch page HTML with selective retry and lightweight fallback.

    Returns tuple: (html_or_none, failure_reason_if_any, fetch_metadata)
    """

    def _domain_key(raw_url: str) -> str:
        try:
            return (urlparse(raw_url).hostname or "").lower() or "unknown"
        except Exception:
            return "unknown"

    async def _domain_semaphore(raw_url: str) -> asyncio.Semaphore:
        key = _domain_key(raw_url)
        async with _FETCH_DOMAIN_LOCK:
            semaphore = _FETCH_DOMAIN_SEMAPHORES.get(key)
            if semaphore is None:
                semaphore = asyncio.Semaphore(_FETCH_DOMAIN_CONCURRENCY_LIMIT)
                _FETCH_DOMAIN_SEMAPHORES[key] = semaphore
            return semaphore

    def _is_retryable_exception_text(text: str) -> bool:
        retryable_tokens = (
            "dns",
            "getaddrinfo",
            "name not resolved",
            "name resolution",
            "temporary failure in name resolution",
            "econnreset",
            "connection reset",
            "connection aborted",
            "server disconnected",
            "remote protocol error",
            "network is unreachable",
            "timed out",
            "timeout",
            "transient",
        )
        return any(token in text for token in retryable_tokens)

    def _is_blocked_status(status_code: int | None) -> bool:
        return status_code in {401, 403, 407, 429}

    def _is_retryable_http_status(status_code: int | None) -> bool:
        if status_code is None:
            return False
        return status_code in {408, 425, 500, 502, 503, 504, 520, 521, 522, 523, 524}

    def _coerce_partial_html(body: str) -> str:
        trimmed = (body or "").strip()
        if not trimmed:
            return ""
        return trimmed[:_FETCH_PARTIAL_BODY_LIMIT]

    async def _attempt(
        *,
        attempt_timeout: float,
        lightweight: bool,
    ) -> tuple[Optional[str], Optional[int], str, bool]:
        headers = stable_request_headers(url)
        timeout_cfg = httpx.Timeout(
            connect=max(2.0, min(5.0, attempt_timeout * 0.45)),
            read=max(2.0, attempt_timeout),
            write=max(2.0, min(5.0, attempt_timeout * 0.35)),
            pool=max(1.5, min(3.0, attempt_timeout * 0.25)),
        )

        try:
            async with httpx.AsyncClient(timeout=timeout_cfg, follow_redirects=True, headers=headers) as client:
                if lightweight:
                    stream_headers = dict(headers)
                    stream_headers["Range"] = f"bytes=0-{_FETCH_PARTIAL_BODY_LIMIT - 1}"
                    async with client.stream("GET", url, headers=stream_headers) as response:
                        status_code = int(response.status_code)
                        chunks: list[str] = []
                        bytes_read = 0
                        async for chunk in response.aiter_text():
                            if not chunk:
                                continue
                            chunks.append(chunk)
                            bytes_read += len(chunk.encode("utf-8", errors="ignore"))
                            if bytes_read >= _FETCH_PARTIAL_BODY_LIMIT:
                                break
                        body = "".join(chunks)
                else:
                    response = await client.get(url)
                    status_code = int(response.status_code)
                    body = response.text or ""

            if status_code >= 400:
                logger.warning("Fetch returned status=%s for %s", status_code, url)
                if body.strip():
                    return _coerce_partial_html(body), status_code, "", False
                if _is_blocked_status(status_code):
                    return None, status_code, "blocked_request", False
                return None, status_code, "network_error", False

            if body.strip():
                return _coerce_partial_html(body), status_code, "", False

            return None, status_code, "extraction_failure", False
        except Exception as exc:
            error_text = str(exc).lower()
            reason = classify_failure_reason(exc)
            retryable = bool(reason != "blocked_request" and _is_retryable_exception_text(error_text))
            return None, None, reason, retryable

    effective_timeout = max(4.0, float(timeout))
    retry_timeout = max(3.0, min(effective_timeout * 0.6, effective_timeout - 1.0))
    lightweight_timeout = max(2.5, min(4.5, effective_timeout * 0.4))

    meta: dict[str, Any] = {
        "retry_used": False,
        "partial_fallback_used": False,
        "status_code": None,
        "domain": _domain_key(url),
    }

    semaphore = await _domain_semaphore(url)
    async with semaphore:
        body, status_code, reason, retryable_exc = await _attempt(
            attempt_timeout=effective_timeout,
            lightweight=False,
        )
        meta["status_code"] = status_code

        if body:
            return body, "", meta

        blocked_status = _is_blocked_status(status_code)
        should_retry = (not blocked_status) and (retryable_exc or _is_retryable_http_status(status_code))
        if should_retry:
            meta["retry_used"] = True
            body, retry_status, retry_reason, _ = await _attempt(
                attempt_timeout=retry_timeout,
                lightweight=False,
            )
            if retry_status is not None:
                status_code = retry_status
                meta["status_code"] = retry_status
            if body:
                return body, "", meta
            if retry_reason:
                reason = retry_reason
            blocked_status = _is_blocked_status(status_code)

        if not blocked_status:
            partial_body, partial_status, partial_reason, _ = await _attempt(
                attempt_timeout=lightweight_timeout,
                lightweight=True,
            )
            if partial_status is not None:
                status_code = partial_status
                meta["status_code"] = partial_status
            if partial_body:
                meta["partial_fallback_used"] = True
                return partial_body, "", meta
            if partial_reason:
                reason = partial_reason

    if not reason:
        if _is_blocked_status(status_code):
            reason = "blocked_request"
        elif _is_retryable_http_status(status_code):
            reason = "network_error"
        else:
            reason = "network_error"

    return None, reason, meta


async def _run_axe_core_via_playwright(page) -> list[dict]:
    """Run axe-core in Playwright page and return violations."""
    try:
        await page.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js")
        await page.wait_for_timeout(500)
        results = await page.evaluate("axe.run()")
        return results.get("violations", [])
    except Exception as e:
        logger.warning(f"axe-core execution failed: {e}")
        return []


async def run_audit(
    url: str,
    scan_mode: str = "fast",
    checks: Optional[list[str]] = None,
    max_pages: Optional[int] = None,
    precision_profile: str = "balanced",
    enable_enrichment: bool = True,
    max_enrich_issues: int = 20,
    enable_cognitive: bool = True,
    await_enrichment: bool = False,
) -> dict:
    """
    Run the full accessibility audit pipeline.

        Scan modes:
        - ``minimal``: static-only + basic heuristics. Fastest path, most reliable.
            Skips browser, axe-core, cognitive, and RAG enrichment. (~1-3s)
        - ``fast``:    httpx fetch -> static + heuristics. No browser/LLM by default. (~5-10s)
        - ``deep``:    Playwright render -> all engines + cognitive + RAG. (~30-120s)
        - ``max``:     Deep mode + explicit interaction/scroll exploration layer.

        Enrichment mode:
        - ``await_enrichment=False`` (default): queue enrichment in background and return immediately.
        - ``await_enrichment=True``: block until enrichment completes/fails (recommended for CLI benchmarks).
    """
    global _active_audits
    start_time = time.time()

    try:
        url = validate_public_url(url)
    except URLValidationError as exc:
        failure = {
            "url": str(url),
            "scan_mode": scan_mode,
            "total_issues": 0,
            "issues": [],
            "groups": [],
            "score": 0.0,
            "cognitive_scores": None,
            "summary": f"URL validation failed: {exc}",
            "markdown_report": "",
            "scan_time_seconds": round(time.time() - start_time, 2),
            "engines_used": [],
            "quality_gates": {},
            "enrichment_status": "failed",
            "pages_discovered": 0,
            "pages_audited": 0,
        }
        return _finalize_result(failure, status="failed")
    
    # ── Step 0a: Check URL Cache ───────────────────────────────
    url_hash = get_url_hash(url, scan_mode, precision_profile)
    cached_res = check_cache(url_hash, tier="page")
    if cached_res:
        cached_res = _upgrade_cached_deep_result(cached_res, scan_mode)
        if _is_invalid_cached_result(cached_res):
            logger.warning("Discarding stale page cache entry for %s (%s mode). Recomputing.", url, scan_mode)
        else:
            logger.info(f"Page Cache HIT (URL) for {url}")
            cached_res["cache_hit"] = True
            return _finalize_result(cached_res, status="cached", persist_db=False)

    degraded_mode = False
    degraded_reason = None
    degradation_reason = None
    skipped_components = []

    def _mark_degraded(reason_code: str, message: Optional[str] = None) -> None:
        nonlocal degraded_mode, degraded_reason, degradation_reason
        normalized_reason = normalize_reason(reason_code) or classify_failure_reason(reason_code)
        degraded_mode = True
        if not degraded_reason:
            degraded_reason = normalized_reason
        if not degradation_reason:
            degradation_reason = message or _degradation_reason_message(normalized_reason)

    # ── Step 0b: Global Backpressure Guard ─────────────────────
    _active_audits += 1
    if _active_audits > _MAX_CONCURRENT_AUDITS:
        if scan_mode == "deep":
            logger.warning(f"⚠️ Backpressure active ({_active_audits} audits). Auto-degrading to fast mode.")
            scan_mode = "fast"
            _mark_degraded("extraction_failure", "System under heavy load. Auto-degraded to fast mode.")
            skipped_components.extend(["browser_probes", "axe-core", "cognitive"])

    try:
        engines_used = []

        # ── Minimal fast path: static + basic heuristics only ─────────
        # Use scan_mode="minimal" for maximum reliability under load.
        # Skips browser, axe-core, cognitive, and async enrichment entirely.
        # Easiest to debug; guaranteed to finish in <3s.
        if scan_mode == "minimal":
            enable_enrichment = False
            enable_cognitive  = False

        # Determine timeout based on mode
        max_runtime = (
            QUALITY_GATES["runtime"]["fast_max_seconds"]
            if scan_mode in ("fast", "minimal")
            else QUALITY_GATES["runtime"]["deep_max_seconds"]
        )

        adaptive_timeout_policy = resolve_adaptive_timeouts(
            url,
            "fast" if scan_mode in {"fast", "minimal"} else "deep",
            page_timeout_seconds=15 if scan_mode in {"fast", "minimal"} else 30,
            network_idle_timeout_ms=12000,
            ready_state_timeout_ms=5000,
        )
        fetch_timeout = float(adaptive_timeout_policy.get("page_timeout_seconds", 10))
        browser_timeout_ms = int(float(adaptive_timeout_policy.get("page_timeout_seconds", 30)) * 1000.0)
        
        html = None
        static_issues = []
        static_rule_activity: dict[str, dict[str, int]] = {}
        heuristic_issues = []
        browser_issues = []
        axe_violations = []
        cognitive_scores = None

        # ── Step 1: Fetch / Render page ────────────────────────────
        browser_probe_metadata = {}
        fetch_reliability_meta: dict[str, Any] = {}
        
        if scan_mode in {"deep", "max"}:
            # Try Playwright for deep scan
            try:
                from app.services.browser_probes import BrowserProber, _PLAYWRIGHT_AVAILABLE
                if _PLAYWRIGHT_AVAILABLE:
                    prober = BrowserProber(url, timeout=browser_timeout_ms, max_retries=1)
                    probe_result = await prober.run_all(scan_mode=scan_mode)
                    
                    # Handle both old (2-tuple) and new (3-tuple) return signatures
                    if len(probe_result) == 3:
                        browser_issues, rendered_html, browser_probe_metadata = probe_result
                    else:
                        browser_issues, rendered_html = probe_result
                        browser_probe_metadata = {}
                    
                    if rendered_html:
                        html = rendered_html
                        engines_used.append("browser-probe")
                        
                        # Log SPA detection for debugging
                        spa_framework = browser_probe_metadata.get("spa_framework")
                        is_spa = browser_probe_metadata.get("is_spa", False)
                        if is_spa:
                            logger.info(
                                "%s scan: SPA detected (%s), %s browser probe issues",
                                scan_mode.upper(),
                                spa_framework or "generic",
                                len(browser_issues),
                            )
                        else:
                            logger.info(
                                "%s scan: Playwright rendered page, %s browser probe issues",
                                scan_mode.upper(),
                                len(browser_issues),
                            )
                else:
                    logger.info("Playwright not available - falling back to httpx for %s scan", scan_mode)
                    _mark_degraded("extraction_failure", "Playwright rendering engine is unavailable.")
                    skipped_components.extend(["browser_probes", "axe-core"])
            except Exception as e:
                logger.warning(f"Playwright probing failed: {e}")
                reason_code = _classify_degraded_reason_from_error(e)
                _mark_degraded(reason_code, _degradation_reason_message(reason_code, str(e)))
                skipped_components.extend(["browser_probes", "axe-core"])

        # Fallback: fetch with httpx if no rendered HTML yet
        if not html:
            html, fetch_reason, fetch_reliability_meta = await _fetch_html(
                url,
                timeout=min(fetch_timeout, float(max_runtime)),
            )
            if not html and fetch_reason:
                _mark_degraded(fetch_reason, _degradation_reason_message(fetch_reason, "content_fetch"))
        
        if not html:
            _mark_degraded(degraded_reason or "network_error", "Unable to fetch rendered HTML. Returned safe degraded result.")
            skipped_components.extend(["content_fetch"])

            fallback_issue = {
                "issue_id": hashlib.sha256(f"{url}|fetch-unavailable".encode()).hexdigest()[:16],
                "rule_id": "fetch-unavailable",
                "issue_type": "needs-review",
                "element": "<document>",
                "html_snippet": "",
                "page_url": url,
                "severity": "serious",
                "wcag_criterion": "",
                "wcag_level": "",
                "category": "availability",
                "confidence": 0.9,
                "confidence_sources": ["fetch"],
                "needs_manual_review": True,
                "description": "The target page could not be fetched by HTTP or browser fallback and requires manual validation.",
                "suggested_fix": "Retry with a stable network path or allowlist scanner user agents.",
                "code_fix": "",
                "fix_effort": "medium",
                "group_id": "",
                "domain": "availability",
                "evidence": {},
                "reproducibility": "",
            }
            fallback_score, fallback_score_explanation = _calculate_score([fallback_issue], degraded_mode=True)
            scan_time = round(time.time() - start_time, 2)

            failure = {
                "url": url,
                "scan_mode": scan_mode,
                "total_issues": 1,
                "issues": [fallback_issue],
                "priority_ranking": [],
                "groups": [],
                "score": fallback_score,
                "score_explanation": fallback_score_explanation,
                "cognitive_scores": None,
                "summary": f"Degraded audit: unable to fetch content for {url}. Returned safe baseline scoring.",
                "markdown_report": "",
                "scan_time_seconds": scan_time,
                "engines_used": engines_used,
                "quality_gates": {
                    "runtime_limit": max_runtime,
                    "runtime_actual": scan_time,
                    "runtime_passed": scan_time <= max_runtime,
                    "safe_fallback_triggered": True,
                },
                "enrichment_status": "skipped",
                "pages_discovered": 1,
                "pages_audited": 1,
                "degraded_mode": True,
                "degraded_reason": degraded_reason,
                "skipped_components": sorted(set(skipped_components)),
                "degradation_reason": degradation_reason,
                "site_result": _single_page_site_result(score=fallback_score, total_issues=1, url=url),
            }
            return _finalize_result(failure, status="completed")

        # ── Step 1.5: Check Structure / DOM Cache ─────────────────
        dom_hash = get_dom_hash(clean_html_for_hash(html), scan_mode, precision_profile)
        cached_dom_res = check_cache(dom_hash, tier="dom")
        if cached_dom_res:
            cached_dom_res = _upgrade_cached_deep_result(cached_dom_res, scan_mode)
            if _is_invalid_cached_result(cached_dom_res):
                logger.warning("Discarding stale DOM cache entry for %s (%s mode). Recomputing.", url, scan_mode)
            else:
                logger.info(f"Page Cache HIT (DOM Hash) for {url}")
                cached_dom_res["cache_hit"] = True
                return _finalize_result(cached_dom_res, status="cached", persist_db=False)

        # ── Step 2: Run check engines (Parallel) ──────────────────────
        def run_static():
            try:
                checker = StaticChecker(html, url)
                return checker.run_all(checks), "static", {
                    "executed": True,
                    "rule_activity": checker.get_rule_activity(),
                }
            except Exception as e:
                logger.error(f"Static checks failed: {e}")
                return [], "static", {"executed": False, "rule_activity": {}}

        def run_heuristic():
            try:
                analyzer = HeuristicAnalyzer(html, url)
                return analyzer.run_all(), "heuristic", {"executed": True}
            except Exception as e:
                logger.error(f"Heuristic checks failed: {e}")
                return [], "heuristic", {"executed": False}

        async def run_axe():
            if scan_mode not in {"deep", "max"}:
                return [], "axe-core", {"executed": False}
            try:
                from app.services.browser_probes import _PLAYWRIGHT_AVAILABLE
                if not _PLAYWRIGHT_AVAILABLE:
                    return [], "axe-core", {"executed": False}
                try:
                    stage_timeout = max(8.0, min(20.0, (float(browser_timeout_ms) / 1000.0) + 2.0))
                    page_goto_timeout = max(7000, min(18000, int(browser_timeout_ms) - 3000))
                    # Circuit breaker & backpressure guard (25s max wait)
                    async with asyncio.timeout(stage_timeout):
                        async with _browser_semaphore:
                            from playwright.async_api import async_playwright
                            async with async_playwright() as p:
                                browser = await p.chromium.launch(headless=True)
                                page = await browser.new_page()
                                try:
                                    await page.goto(url, timeout=page_goto_timeout, wait_until="domcontentloaded")
                                    v = await _run_axe_core_via_playwright(page)
                                    return v, "axe-core", {"executed": True}
                                finally:
                                    await browser.close()
                except TimeoutError:
                    logger.warning("axe-core timed out (blocked by semaphore or page load).")
                    return [], "axe-core", {"executed": False}
            except Exception as e:
                logger.warning(f"axe-core execution failed: {e}")
                return [], "axe-core", {"executed": False}

        # Execute all 3 rule engines concurrently
        t_static = asyncio.to_thread(run_static)
        t_heuristic = asyncio.to_thread(run_heuristic)
        t_axe = run_axe()
        
        results = await asyncio.gather(t_static, t_heuristic, t_axe, return_exceptions=True)
        
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Engine parallel task failed: {res}")
                continue
                
            engine_issues, engine_name, extra = res
            engine_meta = extra if isinstance(extra, dict) else {}
            if engine_meta.get("executed") and engine_name not in engines_used:
                engines_used.append(engine_name)

            if engine_name == "static":
                static_issues = engine_issues
                static_rule_activity = engine_meta.get("rule_activity", {})
            elif engine_name == "heuristic":
                heuristic_issues = engine_issues
            elif engine_name == "axe-core":
                axe_violations = engine_issues

        # If deep scan requested but browser engines did not execute, mark degraded.
        if scan_mode in {"deep", "max"}:
            used_set = set(engines_used)
            if "browser-probe" not in used_set and "axe-core" not in used_set:
                _mark_degraded(
                    "extraction_failure",
                    "Deep/max scan requested, but browser engines did not execute. Results are based on static HTML analysis only.",
                )
                skipped_components.extend(["browser_probes", "axe-core"])
                logger.warning("%s scan degraded to static-only path (no browser engines executed).", scan_mode.upper())

        ttfi_ms = int((time.time() - start_time) * 1000)

        # ── Step 3: Normalize → Dedup → Confidence ────────────────
        try:
            all_issues = normalize_all(
                static_issues=static_issues,
                heuristic_issues=heuristic_issues,
                browser_issues=browser_issues,
                axe_issues=axe_violations,
                url=url,
            )
        except Exception as e:
            logger.error("Normalization failed: %s", e)
            _mark_degraded("extraction_failure", _degradation_reason_message("extraction_failure", "normalization"))
            skipped_components.append("normalizer")
            all_issues = [
                *list(static_issues or []),
                *list(heuristic_issues or []),
                *list(browser_issues or []),
                *list(axe_violations or []),
            ]

        # Deduplicate
        try:
            deduped_issues = deduplicate(all_issues)
        except Exception as e:
            logger.error("Deduplication failed: %s", e)
            _mark_degraded("extraction_failure", _degradation_reason_message("extraction_failure", "deduplication"))
            skipped_components.append("dedup")
            deduped_issues = list(all_issues)

        # Apply confidence scoring
        try:
            scored_issues = apply_confidence_rules(deduped_issues, html)
        except Exception as e:
            logger.error("Confidence scoring failed: %s", e)
            _mark_degraded("extraction_failure", _degradation_reason_message("extraction_failure", "confidence"))
            skipped_components.append("confidence")
            scored_issues = list(deduped_issues)
        
        # ── Step 4: Cognitive checks (deep mode only) ──────────────
        if scan_mode in {"deep", "max"} and enable_cognitive:
            try:
                cognitive = CognitiveAnalyzer(html, url)
                cog_result = cognitive.run_all()
                cog_issues = cog_result.pop("issues", [])
                cognitive_scores = cog_result
                
                # Add cognitive issues to the main list
                scored_issues.extend(cog_issues)
                if cog_issues:
                    engines_used.append("cognitive")
                    logger.info(f"Cognitive checks: {len(cog_issues)} issues")
            except Exception as e:
                logger.error(f"Cognitive checks failed: {e}")

        # Apply precision profile
        scored_issues, profile_telemetry = _apply_precision_profile(scored_issues, precision_profile)
        # ── Step 4.25: Aggregate identical rules ─────────────────────
        scored_issues, compression_telemetry = aggregate_issues(scored_issues)
        # ── Step 4.5: Prioritize issues (NEW) ────────────────────────
        # Computes priority_score per issue and builds a top-5 "fix first" list.
        # Formula: impact × frequency × visibility × confidence
        scored_issues, priority_ranking = prioritize_issues(scored_issues)

        # ── Step 5: Group issues ──────────────────────────────────
        groups = group_issues(scored_issues)
        
        # ── Step 6: RAG Enrichment (Audit Mastery) ────────────────
        audit_id = str(uuid.uuid4())
        enrichment_status = "complete"
        enrichment_meta: dict[str, Any] = {}

        if enable_enrichment:
            enrichment_status = "pending"
            
            async def run_enrichment_task(aid: str, iss: list[dict], max_num: int):
                try:
                    # 60s absolute timeout for enrichment to prevent memory leaks
                    async with asyncio.timeout(60):
                        enriched, meta = await enrich_issues(
                            iss,
                            max_issues=max_num,
                            return_meta=True,
                        )
                        _enriched_results[aid] = {"status": "complete", "issues": enriched, "meta": meta}
                        try:
                            persist_enrichment_payload(aid, enriched, meta, status="complete")
                        except Exception as exc:
                            logger.error("Failed to persist enrichment payload for %s: %s", aid, exc)
                except TimeoutError:
                    logger.error(f"Enrichment task {aid} timed out.")
                    _enriched_results[aid] = {
                        "status": "failed",
                        "issues": iss,
                        "meta": {"reason": "timeout", "budget": {"budget_exhausted": False}},
                    }
                    notify_llm_failure("enrichment_timeout")
                    try:
                        persist_enrichment_payload(
                            aid,
                            iss,
                            _enriched_results[aid]["meta"],
                            status="failed",
                        )
                    except Exception as exc:
                        logger.error("Failed to persist timeout enrichment payload for %s: %s", aid, exc)
                except Exception as e:
                    logger.error(f"Enrichment task {aid} failed: {e}")
                    _enriched_results[aid] = {
                        "status": "failed",
                        "issues": iss,
                        "meta": {"reason": str(e), "budget": {"budget_exhausted": False}},
                    }
                    notify_llm_failure(str(e))
                    try:
                        persist_enrichment_payload(
                            aid,
                            iss,
                            _enriched_results[aid]["meta"],
                            status="failed",
                        )
                    except Exception as exc:
                        logger.error("Failed to persist failed enrichment payload for %s: %s", aid, exc)
                finally:
                    _enrichment_tasks.pop(aid, None)

            if await_enrichment:
                await run_enrichment_task(audit_id, scored_issues.copy(), max_enrich_issues)
                enriched_payload = _enriched_results.get(audit_id, {})
                final_status = str(enriched_payload.get("status", "pending")).lower()
                payload_meta = enriched_payload.get("meta")
                if isinstance(payload_meta, dict):
                    enrichment_meta = payload_meta

                if final_status == "complete":
                    enriched_issues = enriched_payload.get("issues")
                    if isinstance(enriched_issues, list):
                        scored_issues = enriched_issues
                    enrichment_status = "complete"
                elif final_status == "failed":
                    enrichment_status = "failed"
                else:
                    enrichment_status = "pending"
            else:
                # Fire and forget for API mode.
                task = asyncio.create_task(run_enrichment_task(audit_id, scored_issues.copy(), max_enrich_issues))
                _enrichment_tasks[audit_id] = task

        # ── Step 7: Calculate score (capped, per-rule) ─────────────
        score, score_explanation = _calculate_score(scored_issues, degraded_mode=degraded_mode)
        
        # ── Step 8: Generate report ────────────────────────────────
        scan_time = time.time() - start_time
        
        markdown_report = generate_markdown_report(
            url=url,
            scan_mode=scan_mode,
            score=score,
            issues=scored_issues,
            groups=groups,
            cognitive_scores=cognitive_scores,
            scan_time=scan_time,
            engines_used=engines_used,
        )
        
        # ── Quality gate checks ────────────────────────────────────
        quality_gates = {
            "runtime_limit": max_runtime,
            "runtime_actual": round(scan_time, 2),
            "runtime_passed": scan_time <= max_runtime,
            "adaptive_timeout_policy": adaptive_timeout_policy,
            "engines_used": engines_used,
            "total_before_dedup": len(all_issues),
            "total_after_dedup": len(deduped_issues),
            "precision_profile": precision_profile,
            "precision_profile_telemetry": profile_telemetry,
            "compression_telemetry": compression_telemetry,
            "rule_activity": static_rule_activity,
            "ttfi_ms": ttfi_ms,
            "active_audits": _active_audits,
        }

        if fetch_reliability_meta:
            quality_gates["fetch_reliability"] = fetch_reliability_meta

        if enrichment_meta:
            llm_meta = enrichment_meta.get("llm") if isinstance(enrichment_meta, dict) else None
            budget_meta = enrichment_meta.get("budget") if isinstance(enrichment_meta, dict) else None
            retrieval_debug = enrichment_meta.get("retrieval_debug") if isinstance(enrichment_meta, dict) else None
            quality_gates["enrichment_observability"] = {
                "llm_calls": int((llm_meta or {}).get("calls", 0) or 0),
                "llm_retries": int((llm_meta or {}).get("retries", 0) or 0),
                "token_budget_used": int((budget_meta or {}).get("tokens_used", 0) or 0),
                "cost_budget_used": float((budget_meta or {}).get("cost_used", 0.0) or 0.0),
                "budget_exhausted": bool((budget_meta or {}).get("budget_exhausted", False)),
                "retrieval_debug_records": len(retrieval_debug) if isinstance(retrieval_debug, list) else 0,
            }

        if scan_mode == "max":
            quality_gates["max_mode_validation"] = {
                "playwright_invoked": "browser-probe" in engines_used,
                "interaction_phase_ran": bool(browser_probe_metadata.get("interaction_phase_ran", False)),
                "scroll_phase_ran": bool(browser_probe_metadata.get("scroll_phase_ran", False)),
                "exploration_layer_ran": bool(browser_probe_metadata.get("exploration_layer_ran", False)),
                "login_wall_detected": bool(browser_probe_metadata.get("login_wall_detected", False)),
                "auth_fallback_attempted": bool(browser_probe_metadata.get("auth_fallback_attempted", False)),
                "auth_fallback_used": bool(browser_probe_metadata.get("auth_fallback_used", False)),
            }
        
        if len(all_issues) > 0:
            dup_rate = (len(all_issues) - len(deduped_issues)) / len(all_issues)
            quality_gates["duplicate_rate"] = round(dup_rate, 3)
            quality_gates["duplicate_rate_passed"] = dup_rate <= QUALITY_GATES["duplicate_rate_max"]
        
        if scan_time > max_runtime:
            logger.warning(f"⚠️ Runtime {scan_time:.1f}s exceeds {max_runtime}s limit")

        # ── Step 7: Calculate Expected Score Improvement ───────────────
        top_rule_ids = {r["rule_id"] for r in priority_ranking}
        issues_after_fix = [i for i in scored_issues if i.get("rule_id") not in top_rule_ids]
        expected_score_after_fix, _ = _calculate_score(issues_after_fix, degraded_mode=degraded_mode) if scored_issues else (100.0, {})
        score_improvement = expected_score_after_fix - score

        # ── Build summary ──────────────────────────────────────────
        severity_counts = {}
        for i in scored_issues:
            sev = i.get("severity", "moderate")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        
        summary_parts = [f"Found {len(scored_issues)} accessibility issues"]
        for sev in ["critical", "serious", "moderate", "minor"]:
            if severity_counts.get(sev, 0) > 0:
                summary_parts.append(f"{severity_counts[sev]} {sev}")
        summary_parts.append(f"Score: {score}/100")
        if degraded_mode:
            summary_parts.append("⚠️ DEGRADED")
        summary_parts.append(f"Engines: {', '.join(engines_used)}")
        summary_parts.append(f"Time: {scan_time:.1f}s")
        summary = " | ".join(summary_parts)

        res = {
            "url": url,
            "scan_mode": scan_mode,
            "cognitive_mode": "experimental" if enable_cognitive and scan_mode in {"deep", "max"} else "off",
            "schema_version": getattr(settings, "schema_version", "3.1"),
            "total_issues": len(scored_issues),
            "issues": scored_issues,
            "priority_ranking": priority_ranking,   # Top-5 "fix these first" list
            "groups": groups,
            "score": score,
            "score_explanation": score_explanation,
            "score_display_context": f"No issues detected across {len(engines_used)} active engine(s). Note: This does not guarantee full WCAG AA conformance." if score == 100.0 else "",
            "expected_score_after_fix": round(expected_score_after_fix, 1),
            "score_improvement": round(score_improvement, 1),
            "degraded_mode": degraded_mode,
            "degraded_reason": degraded_reason,
            "skipped_components": list(set(skipped_components)),
            "degradation_reason": degradation_reason,
            "cognitive_scores": cognitive_scores,
            "summary": summary,
            "markdown_report": markdown_report,
            "scan_time_seconds": round(scan_time, 2),
            "pages_discovered": 1,
            "pages_audited": 1,
            "requested_max_pages": max_pages,
            "engines_used": engines_used,
            "quality_gates": quality_gates,
            "precision_profile": precision_profile,
            "precision_profile_telemetry": profile_telemetry,
            "rule_activity": static_rule_activity,
            "enrichment_status": enrichment_status,
            "enrichment_meta": enrichment_meta,
            "audit_id": audit_id,
            "site_result": _single_page_site_result(score=score, total_issues=len(scored_issues), url=url),
            # World-class SPA detection metadata
            "browser_probe_metadata": browser_probe_metadata,
            "spa_framework": browser_probe_metadata.get("spa_framework"),
            "is_spa": browser_probe_metadata.get("is_spa", False),
        }
        
        # ── Step 8: Cache Write Policy ─────────────────────────────────
        # Never cache partial pipelines/degraded results to prevent poisoning.
        # Only cache if confidence signals were fully aggregated.
        if not degraded_mode:
            save_to_cache(url_hash, dom_hash, res)
        else:
            logger.info("Skipping cache write due to degraded execution.")

        return _finalize_result(res, status="completed")

    finally:
        _active_audits = max(0, _active_audits - 1)


def _calculate_score(issues: list[dict], degraded_mode: bool = False) -> tuple[float, dict]:
    """
    Calculate accessibility score (0-100) using capped per-rule penalties.
    Returns (score, explanation_layer_dict).
    """
    max_per_rule: float = float(SCORING_CONFIG["max_penalty_per_rule"])

    # Accumulate per-rule penalties
    rule_penalty: dict[str, float] = {}
    rule_details: dict[str, dict] = {}
    
    for issue in issues:
        if issue.get("needs_manual_review") and issue.get("confidence", 0) < 0.4:
            continue
        
        rule_id = issue.get("rule_id", "unknown")
        sev = issue.get("severity", "minor")
        confidence = float(issue.get("confidence", 1.0))
        rule_type = issue.get("rule_type", "hard")
        
        weight = float(SEVERITY_WEIGHTS.get(sev, 1.0))
        
        # Apply confidence penalty weighting
        weight *= confidence
        
        # Apply visual rules weighting
        if rule_type == "visual":
            weight *= 0.7
            
        # Grouped axe issues count as 1 finding regardless of affected_count
        if issue.get("is_grouped"):
            weight = float(SCORING_CONFIG.get("grouped_issue_weight", 1.0)) * weight
            
        rule_penalty[rule_id] = rule_penalty.get(rule_id, 0.0) + weight
        if rule_id not in rule_details:
            rule_details[rule_id] = {"type": rule_type, "severity": sev, "raw_penalty": 0.0, "capped_penalty": 0.0}
        rule_details[rule_id]["raw_penalty"] += weight

    # Apply per-rule cap and build explanation
    total_penalty = 0.0
    for rule, p in rule_penalty.items():
        capped = min(p, max_per_rule)
        rule_details[rule]["capped_penalty"] = capped
        total_penalty += capped

    score = max(0.0, min(100.0, 100.0 - total_penalty))
    
    explanation = {
        "base_score": 100.0,
        "total_penalty_applied": round(total_penalty, 2),
        "degraded_mode_penalty": 0.0,
        "capped_rules_count": sum(1 for d in rule_details.values() if d["raw_penalty"] > max_per_rule),
        "penalty_breakdown": {k: round(v["capped_penalty"], 2) for k, v in sorted(rule_details.items(), key=lambda item: item[1]["capped_penalty"], reverse=True)[:5]}
    }
    
    # Degraded mode reduction
    if degraded_mode:
        explanation["degraded_mode_penalty"] = round(score * 0.15, 2)
        score *= 0.85
        
    # Hard floor to prevent "0 = completely broken" for otherwise usable sites
    if score < 15.0 and total_penalty > 0:
        explanation["floor_applied"] = True
        score = 15.0
        
    # Only return 100 if there were literally no penalties (or floating point exactly matches)
    if total_penalty == 0 and not degraded_mode:
        score = 100.0

    logger.debug(f"Score calculation: {len(rule_penalty)} rules, penalty={total_penalty:.1f} -> score={score:.1f}")
    return round(score, 1), explanation


def _apply_precision_profile(issues: list[dict], profile_name: str) -> tuple[list[dict], dict]:
    """Filter reported issues according to profile to optimize precision/recall tradeoff."""
    profile = PRECISION_PROFILES.get(profile_name, PRECISION_PROFILES["balanced"])
    profile = _merge_profile_with_policy(profile_name, profile)
    kept = []
    dropped_low_conf = 0
    dropped_needs_review = 0
    dropped_contextual_single = 0
    dropped_excluded_rule = 0
    dropped_cooccurrence_rule = 0

    exclude_rules = set(profile.get("exclude_rules", []))
    per_rule_min_conf = profile.get("per_rule_min_confidence", {})
    per_rule_conf_override = profile.get("per_rule_confidence_override", {})
    suppress_when_present = profile.get("suppress_when_present", {})

    for issue in issues:
        rule_id = issue.get("rule_id", "")
        
        # Check if rule is explicitly excluded (for ultra_strict and similar profiles)
        if rule_id in exclude_rules:
            dropped_excluded_rule += 1
            continue
        
        conf = issue.get("confidence", 0.0)
        needs_review = issue.get("needs_manual_review", False)
        rule_type = issue.get("rule_type", "hard")
        source_count = len(set(issue.get("confidence_sources", [])))

        # Adaptive thresholding keeps precision high while avoiding collapse in recall.
        min_conf = profile["min_confidence"]
        if profile_name in ("high_precision", "tuned_balanced", "high_precision_plus", "high_precision_recall_boost", "high_precision_recall_strict", "high_precision_recall_balanced", "high_precision_recall_exploratory", "very_high_precision"):  # Adaptive thresholds for precision-first profiles
            if rule_type == "hard":
                min_conf = 0.62
            elif rule_type == "visual":
                min_conf = 0.75
            elif rule_type == "contextual":
                min_conf = 0.80

        # Optional per-rule thresholding lets us tune noisy or low-recall rules
        # without globally harming precision/recall.
        rule_conf_override = per_rule_conf_override.get(rule_id)
        if rule_conf_override is not None:
            min_conf = float(rule_conf_override)
        else:
            rule_min_conf = per_rule_min_conf.get(rule_id)
            if rule_min_conf is not None:
                min_conf = max(min_conf, float(rule_min_conf))

        if conf < min_conf:
            dropped_low_conf += 1
            continue

        if (not profile["include_needs_review"]) and needs_review:
            dropped_needs_review += 1
            continue

        if profile["exclude_contextual_single_source"] and rule_type == "contextual" and source_count < 2:
            dropped_contextual_single += 1
            continue

        kept.append(issue)

    # Co-occurrence suppression: remove noisy companion rules when a trigger rule is present.
    if suppress_when_present and kept:
        present_rules = {i.get("rule_id", "") for i in kept}
        suppress_set = set()
        for trigger_rule, suppressed_rules in suppress_when_present.items():
            if trigger_rule in present_rules:
                suppress_set.update(suppressed_rules)
        if suppress_set:
            original_len = len(kept)
            kept = [i for i in kept if i.get("rule_id", "") not in suppress_set]
            dropped_cooccurrence_rule += original_len - len(kept)

    telemetry = {
        "profile": profile_name,
        "input_issues": len(issues),
        "reported_issues": len(kept),
        "dropped_low_confidence": dropped_low_conf,
        "dropped_needs_review": dropped_needs_review,
        "dropped_contextual_single_source": dropped_contextual_single,
        "dropped_excluded_rules": dropped_excluded_rule,
        "dropped_cooccurrence_rules": dropped_cooccurrence_rule,
        "estimated_precision_floor": 0.95 if profile_name in ("high_precision", "tuned_balanced", "high_precision_plus", "high_precision_recall_boost", "high_precision_recall_strict", "high_precision_recall_balanced", "high_precision_recall_exploratory", "very_high_precision") else 0.85,
    }
    return kept, telemetry
