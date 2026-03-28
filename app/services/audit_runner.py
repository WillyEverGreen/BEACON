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
import logging
import time
from typing import Optional

import httpx

from app.config import QUALITY_GATES, SEVERITY_WEIGHTS
from app.services.static_checks import StaticChecker
from app.services.heuristics import HeuristicAnalyzer
from app.services.normalizer import normalize_all
from app.services.dedup_engine import deduplicate
from app.services.confidence import apply_confidence_rules
from app.services.grouper import group_issues
from app.services.report import generate_markdown_report
from app.services.cognitive_checks import CognitiveAnalyzer

logger = logging.getLogger(__name__)


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


async def run_audit(url: str, scan_mode: str = "fast", checks: Optional[list[str]] = None) -> dict:
    """
    Run the full accessibility audit pipeline.
    
    Fast mode: httpx fetch → static checks + heuristics → normalize → dedup → confidence → group → report
    Deep mode: Playwright render → static + heuristics + browser probes + axe-core → full pipeline + cognitive
    """
    start_time = time.time()
    engines_used = []
    
    # Determine timeout based on mode
    max_runtime = QUALITY_GATES["runtime"]["fast_max_seconds"] if scan_mode == "fast" else QUALITY_GATES["runtime"]["deep_max_seconds"]
    
    html = None
    static_issues = []
    heuristic_issues = []
    browser_issues = []
    axe_violations = []
    cognitive_scores = None

    # ── Step 1: Fetch / Render page ────────────────────────────
    if scan_mode == "deep":
        # Try Playwright for deep scan
        try:
            from app.services.browser_probes import BrowserProber, _PLAYWRIGHT_AVAILABLE
            if _PLAYWRIGHT_AVAILABLE:
                prober = BrowserProber(url, timeout=30000)
                browser_issues, rendered_html = await prober.run_all()
                if rendered_html:
                    html = rendered_html
                    engines_used.append("browser-probe")
                    logger.info(f"Deep scan: Playwright rendered page, {len(browser_issues)} browser probe issues")
            else:
                logger.info("Playwright not available — falling back to httpx for deep scan")
        except Exception as e:
            logger.warning(f"Playwright probing failed: {e}")

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

    # ── Step 2: Run check engines ──────────────────────────────
    
    # Static checks (always run)
    try:
        checker = StaticChecker(html, url)
        static_issues = checker.run_all(checks)
        engines_used.append("static")
        logger.info(f"Static checks: {len(static_issues)} issues")
    except Exception as e:
        logger.error(f"Static checks failed: {e}")

    # Heuristic checks (always run)
    try:
        heuristic_analyzer = HeuristicAnalyzer(html, url)
        heuristic_issues = heuristic_analyzer.run_all()
        engines_used.append("heuristic")
        logger.info(f"Heuristic checks: {len(heuristic_issues)} issues")
    except Exception as e:
        logger.error(f"Heuristic checks failed: {e}")

    # axe-core (deep mode only, requires Playwright)
    if scan_mode == "deep":
        try:
            from app.services.browser_probes import _PLAYWRIGHT_AVAILABLE
            if _PLAYWRIGHT_AVAILABLE:
                from playwright.async_api import async_playwright
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    try:
                        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                        axe_violations = await _run_axe_core_via_playwright(page)
                        if axe_violations:
                            engines_used.append("axe-core")
                            logger.info(f"axe-core: {len(axe_violations)} violations")
                    except Exception as e:
                        logger.warning(f"axe-core page load failed: {e}")
                    finally:
                        await browser.close()
        except Exception as e:
            logger.warning(f"axe-core execution failed: {e}")

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
    scored_issues = apply_confidence_rules(deduped_issues)
    
    # ── Step 4: Cognitive checks (deep mode only) ──────────────
    if scan_mode == "deep":
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

    # ── Step 5: Group issues ──────────────────────────────────
    groups = group_issues(scored_issues)
    
    # ── Step 6: Calculate score ────────────────────────────────
    total_penalty = sum(
        SEVERITY_WEIGHTS.get(i.get("severity", "minor"), 1) 
        for i in scored_issues 
        if not i.get("needs_manual_review") or i.get("confidence", 0) >= 0.4
    )
    score = max(0, min(100, 100 - total_penalty))
    
    # ── Step 7: Generate report ────────────────────────────────
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
        "engines_used": engines_used,
        "total_before_dedup": len(all_issues),
        "total_after_dedup": len(deduped_issues),
    }
    
    if len(all_issues) > 0:
        dup_rate = (len(all_issues) - len(deduped_issues)) / len(all_issues)
        quality_gates["duplicate_rate"] = round(dup_rate, 3)
        quality_gates["duplicate_rate_passed"] = dup_rate <= QUALITY_GATES["duplicate_rate_max"]
    
    if scan_time > max_runtime:
        logger.warning(f"⚠️ Runtime {scan_time:.1f}s exceeds {max_runtime}s limit")

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
    summary_parts.append(f"Engines: {', '.join(engines_used)}")
    summary_parts.append(f"Time: {scan_time:.1f}s")
    summary = " | ".join(summary_parts)

    return {
        "url": url,
        "scan_mode": scan_mode,
        "total_issues": len(scored_issues),
        "issues": scored_issues,
        "groups": groups,
        "score": score,
        "cognitive_scores": cognitive_scores,
        "summary": summary,
        "markdown_report": markdown_report,
        "scan_time_seconds": round(scan_time, 2),
        "engines_used": engines_used,
        "quality_gates": quality_gates,
    }
