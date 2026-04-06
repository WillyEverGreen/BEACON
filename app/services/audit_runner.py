"""
Audit runner: orchestrates the full multi-engine accessibility audit pipeline.

Pipeline:
1. Fetch/render page (httpx for Fast, Playwright for Deep)
2. Run static checks + heuristics + browser probes in parallel
3. Normalize → deduplicate → confidence score
4. Cognitive checks (Deep mode only)
5. Group → RAG remediation → merge
6. Generate report → output
"""
import asyncio
import hashlib
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import httpx

from app.config import QUALITY_GATES, SEVERITY_WEIGHTS, SCORING_CONFIG
from app.config import PRECISION_PROFILES
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

logger = logging.getLogger(__name__)

_browser_semaphore = asyncio.Semaphore(3)
_enrichment_tasks: dict[str, asyncio.Task] = {}
_enriched_results: dict[str, dict] = {}
_active_audits = 0
_MAX_CONCURRENT_AUDITS = 20

_RULE_QUALITY_POLICY_CACHE: dict[str, Any] | None = None


def _upgrade_cached_deep_result(result: dict, requested_mode: str) -> dict:
    """Backfill degradation metadata for older cached deep scans lacking browser evidence."""
    if requested_mode != "deep":
        return result

    engines_used = result.get("engines_used") or []
    has_browser_evidence = "browser-probe" in engines_used or "axe-core" in engines_used
    if has_browser_evidence:
        return result

    # If this was already marked degraded, keep it untouched.
    if result.get("degraded_mode") is True:
        return result

    result["degraded_mode"] = True
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


async def _fetch_html(url: str, timeout: float = 15.0) -> Optional[str]:
    """Fetch page HTML via httpx."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


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
    precision_profile: str = "balanced",
    enable_enrichment: bool = True,
    max_enrich_issues: int = 20,
    enable_cognitive: bool = True,
) -> dict:
    """
    Run the full accessibility audit pipeline.

    Scan modes:
    - ``minimal``: static-only + basic heuristics. Fastest path, most reliable.
      Skips browser, axe-core, cognitive, and RAG enrichment. (~1-3s)
    - ``fast``:    httpx fetch → static + heuristics. No browser/LLM. (~5-10s)
    - ``deep``:    Playwright render → all engines + cognitive + RAG. (~30-120s)
    """
    global _active_audits
    start_time = time.time()
    
    # ── Step 0a: Check URL Cache ───────────────────────────────
    url_hash = get_url_hash(url, scan_mode)
    cached_res = check_cache(url_hash)
    if cached_res:
        cached_res = _upgrade_cached_deep_result(cached_res, scan_mode)
        logger.info(f"Page Cache HIT (URL) for {url}")
        cached_res["cache_hit"] = True
        return cached_res

    degraded_mode = False
    skipped_components = []
    degradation_reason = None

    # ── Step 0b: Global Backpressure Guard ─────────────────────
    _active_audits += 1
    if _active_audits > _MAX_CONCURRENT_AUDITS:
        if scan_mode == "deep":
            logger.warning(f"⚠️ Backpressure active ({_active_audits} audits). Auto-degrading to fast mode.")
            scan_mode = "fast"
            degraded_mode = True
            skipped_components.extend(["browser_probes", "axe-core", "cognitive"])
            degradation_reason = "System under heavy load. Auto-degraded to fast mode."

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
        
        html = None
        static_issues = []
        static_rule_activity: dict[str, dict[str, int]] = {}
        heuristic_issues = []
        browser_issues = []
        axe_violations = []
        cognitive_scores = None

        # ── Step 1: Fetch / Render page ────────────────────────────
        browser_probe_metadata = {}
        
        if scan_mode == "deep":
            # Try Playwright for deep scan
            try:
                from app.services.browser_probes import BrowserProber, _PLAYWRIGHT_AVAILABLE
                if _PLAYWRIGHT_AVAILABLE:
                    prober = BrowserProber(url, timeout=30000, max_retries=2)
                    probe_result = await prober.run_all()
                    
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
                            logger.info(f"Deep scan: SPA detected ({spa_framework or 'generic'}), {len(browser_issues)} browser probe issues")
                        else:
                            logger.info(f"Deep scan: Playwright rendered page, {len(browser_issues)} browser probe issues")
                else:
                    logger.info("Playwright not available — falling back to httpx for deep scan")
                    degraded_mode = True
                    skipped_components.extend(["browser_probes", "axe-core"])
                    if not degradation_reason:
                        degradation_reason = "Playwright rendering engine is unavailable."
            except Exception as e:
                logger.warning(f"Playwright probing failed: {e}")
                degraded_mode = True
                skipped_components.extend(["browser_probes", "axe-core"])
                if not degradation_reason:
                    degradation_reason = f"Browser engine failed: {e}"

        # Fallback: fetch with httpx if no rendered HTML yet
        if not html:
            html = await _fetch_html(url, timeout=min(15.0, max_runtime))
        
        if not html:
            return {
                "url": url,
                "scan_mode": scan_mode,
                "total_issues": 0,
                "issues": [],
                "groups": [],
                "score": 0.0,
                "cognitive_scores": None,
                "summary": f"Failed to fetch URL: {url}",
                "markdown_report": "",
                "scan_time_seconds": time.time() - start_time,
                "engines_used": engines_used,
                "quality_gates": {},
            }

        # ── Step 1.5: Check Structure / DOM Cache ─────────────────
        dom_hash = get_dom_hash(clean_html_for_hash(html), scan_mode)
        cached_dom_res = check_cache(dom_hash)
        if cached_dom_res:
            cached_dom_res = _upgrade_cached_deep_result(cached_dom_res, scan_mode)
            logger.info(f"Page Cache HIT (DOM Hash) for {url}")
            cached_dom_res["cache_hit"] = True
            return cached_dom_res

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
            if scan_mode != "deep":
                return [], "axe-core", {"executed": False}
            try:
                from app.services.browser_probes import _PLAYWRIGHT_AVAILABLE
                if not _PLAYWRIGHT_AVAILABLE:
                    return [], "axe-core", {"executed": False}
                try:
                    # Circuit breaker & backpressure guard (25s max wait)
                    async with asyncio.timeout(25):
                        async with _browser_semaphore:
                            from playwright.async_api import async_playwright
                            async with async_playwright() as p:
                                browser = await p.chromium.launch(headless=True)
                                page = await browser.new_page()
                                try:
                                    await page.goto(url, timeout=20000, wait_until="domcontentloaded")
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
        if scan_mode == "deep":
            used_set = set(engines_used)
            if "browser-probe" not in used_set and "axe-core" not in used_set:
                degraded_mode = True
                skipped_components.extend(["browser_probes", "axe-core"])
                if not degradation_reason:
                    degradation_reason = (
                        "Deep scan requested, but browser engines did not execute. "
                        "Results are based on static HTML analysis only."
                    )
                logger.warning("Deep scan degraded to static-only path (no browser engines executed).")

        ttfi_ms = int((time.time() - start_time) * 1000)

        # ── Step 3: Normalize → Dedup → Confidence ────────────────
        all_issues = normalize_all(
            static_issues=static_issues,
            heuristic_issues=heuristic_issues,
            browser_issues=browser_issues,
            axe_issues=axe_violations,
            url=url,
        )
        
        # Deduplicate
        deduped_issues = deduplicate(all_issues)
        
        # Apply confidence scoring
        scored_issues = apply_confidence_rules(deduped_issues, html)
        
        # ── Step 4: Cognitive checks (deep mode only) ──────────────
        if scan_mode == "deep" and enable_cognitive:
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

        if enable_enrichment:
            enrichment_status = "pending"
            
            async def run_enrichment_task(aid: str, iss: list[dict], max_num: int):
                try:
                    # 60s absolute timeout for enrichment to prevent memory leaks
                    async with asyncio.timeout(60):
                        enriched = await enrich_issues(iss, max_issues=max_num)
                        _enriched_results[aid] = {"status": "complete", "issues": enriched}
                except TimeoutError:
                    logger.error(f"Enrichment task {aid} timed out.")
                    _enriched_results[aid] = {"status": "failed", "issues": iss}
                except Exception as e:
                    logger.error(f"Enrichment task {aid} failed: {e}")
                    _enriched_results[aid] = {"status": "failed", "issues": iss}

            # Fire and forget
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
            issues=scored_issues,  # Returning base unenriched issues immediately
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
            "cognitive_mode": "experimental" if enable_cognitive and scan_mode == "deep" else "off",
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
            "skipped_components": list(set(skipped_components)),
            "degradation_reason": degradation_reason,
            "cognitive_scores": cognitive_scores,
            "summary": summary,
            "markdown_report": markdown_report,
            "scan_time_seconds": round(scan_time, 2),
            "engines_used": engines_used,
            "quality_gates": quality_gates,
            "precision_profile": precision_profile,
            "precision_profile_telemetry": profile_telemetry,
            "rule_activity": static_rule_activity,
            "enrichment_status": enrichment_status,
            "audit_id": audit_id,
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

        return res

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
