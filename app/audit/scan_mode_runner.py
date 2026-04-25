"""Scan-mode orchestration integrating crawler discovery, parallel runner, and page auditing."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Awaitable, Callable, Optional

from camoufox import AsyncNewBrowser
from curl_cffi import AsyncSession

from app.audit.models import PageAuditResult, PageContext
from app.audit.failure_taxonomy import normalize_failure
from app.audit.parallel_runner import PageAuditor, SSEEmitter, run_site_audit
from app.crawlers.common import http_get_with_backoff, normalize_scan_mode
from app.crawlers.orchestrator import CrawlerOrchestrator
from app.config import AUDIT_PIPELINE_CONFIG, resolve_max_pages, SCAN_MODES
from app.services.heuristics import HeuristicAnalyzer
from app.services.normalizer import normalize_all
from app.services.static_checks import StaticChecker


JourneySimulator = Callable[[list[str], str, PageContext], Awaitable[dict[str, Any]]]


_SITE_AUDIT_SEMAPHORE = asyncio.Semaphore(
    int(AUDIT_PIPELINE_CONFIG["parallel_runner"].get("max_concurrent_site_audits", 4))
)


def _lighthouse_eligible(scan_mode: str) -> bool:
    """Hard architectural gate: Lighthouse enrichment only runs in deep and max modes.

    This is not a feature flag. Never call Lighthouse code without passing this check.
    The eligible mode set is defined in app.config._LIGHTHOUSE_ELIGIBLE_MODES.
    """
    from app.config import _LIGHTHOUSE_ELIGIBLE_MODES
    return str(scan_mode).lower() in _LIGHTHOUSE_ELIGIBLE_MODES




_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright

    _PLAYWRIGHT_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    async_playwright = None  # type: ignore[assignment]


class _ManagedPlaywrightBrowser:
    def __init__(self, browser: Any, driver: Any) -> None:
        self._browser = browser
        self._driver = driver

    async def new_page(self) -> Any:
        return await self._browser.new_page()

    async def close(self) -> None:
        try:
            await self._browser.close()
        except Exception:
            pass
        stop_driver = getattr(self._driver, "stop", None)
        if callable(stop_driver):
            try:
                stop_result = stop_driver()
                if hasattr(stop_result, "__await__"):
                    await stop_result
            except Exception:
                pass


def _journey_config() -> dict[str, int]:
    cfg = AUDIT_PIPELINE_CONFIG.get("journey_simulation", {})
    return {
        "max_journeys": max(1, int(cfg.get("max_journeys", 3))),
        "max_steps_per_journey": max(1, int(cfg.get("max_steps_per_journey", 4))),
        "max_candidate_urls": max(10, int(cfg.get("max_candidate_urls", 200))),
    }


def _dedupe_urls(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for url in urls:
        key = (url or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    return deduped


async def _emit_optional_event(payload: dict[str, Any], emitter: Optional[SSEEmitter]) -> None:
    if emitter is None:
        return

    maybe_awaitable = emitter(payload)
    if hasattr(maybe_awaitable, "__await__"):
        await maybe_awaitable


async def _fast_state_provider(url: str, state: str, page_context: PageContext) -> dict[str, Any]:
    if state != "initial":
        return {"html": "", "hydration_status": "static"}

    try:
        async with AsyncSession(impersonate="chrome") as client:
            response = await http_get_with_backoff(url, client=client, max_retries=1, timeout_seconds=8.0)
        if int(response.status_code) >= 400:
            return {"html": "", "hydration_status": "static_failed"}
        return {"html": str(response.text or ""), "hydration_status": "static"}
    except Exception:
        return {"html": "", "hydration_status": "static_failed"}


def _default_static_engine(dom: str, page_url: str) -> list[dict[str, Any]]:
    """Run static + heuristic checks for site-orchestrated page audits."""
    if not isinstance(dom, str) or not dom.strip():
        return []

    static_issues: list[dict[str, Any]] = []
    heuristic_issues: list[dict[str, Any]] = []

    try:
        checker = StaticChecker(dom, page_url)
        static_issues = checker.run_all()
    except Exception:
        static_issues = []

    try:
        analyzer = HeuristicAnalyzer(dom, page_url)
        heuristic_issues = analyzer.run_all()
    except Exception:
        heuristic_issues = []

    try:
        return normalize_all(
            static_issues=static_issues,
            heuristic_issues=heuristic_issues,
            browser_issues=[],
            axe_issues=[],
            ibm_issues=[],
            url=page_url,
        )
    except Exception:
        return [*list(static_issues or []), *list(heuristic_issues or [])]


async def _noop_async_engine(dom: str, page_url: str, page_context: PageContext) -> list[dict[str, Any]]:
    return []


async def _full_engine_page_auditor(url: str, scan_mode: str, page_context: PageContext) -> PageAuditResult:
    """Run the full single-page audit pipeline for each discovered URL."""
    from app.services.audit_runner import run_audit

    run_id = ""
    if isinstance(page_context.cache, dict):
        run_id = str(page_context.cache.get("site_audit_run_id") or "")

    result = await run_audit(
        url=url,
        scan_mode=scan_mode,
        max_pages=1,
        enable_enrichment=False,
        use_cache=False,
        run_id=run_id or None,
    )

    scan_time_seconds = float(result.get("scan_time_seconds", 0.0) or 0.0)
    engine_timings: dict[str, float] = {}
    if scan_time_seconds > 0:
        engine_timings["total_ms"] = round(scan_time_seconds * 1000.0, 2)

    return PageAuditResult(
        url=str(result.get("url") or url),
        score=float(result.get("score", 0.0) or 0.0),
        issues=list(result.get("issues") or []),
        engine_timings=engine_timings,
        degraded_mode=bool(result.get("degraded_mode", False)),
        degraded_reason=normalize_failure(result.get("degraded_reason")).value if result.get("degraded_reason") else "",
        skipped_engines=list(result.get("skipped_components") or []),
        hydration_status=str(result.get("browser_probe_metadata", {}).get("hydration_status") or "unknown"),
        enrichment_status=str(result.get("enrichment_status") or "pending"),
        states_meta=[],
        page_dom="",
    )


async def _playwright_browser_factory() -> Any:
    if not _PLAYWRIGHT_AVAILABLE or async_playwright is None:
        raise RuntimeError("Playwright is unavailable for deep/max mode")

    driver = await async_playwright().start()
    browser = await AsyncNewBrowser(driver, headless=True)
    return _ManagedPlaywrightBrowser(browser, driver)


async def _default_journey_simulator(urls: list[str], scan_mode: str, page_context: PageContext) -> dict[str, Any]:
    if scan_mode != "max":
        return {"enabled": False, "journeys": [], "simulation_type": "url_planning"}

    journey_cfg = _journey_config()
    deduped_urls = _dedupe_urls(urls)[: journey_cfg["max_candidate_urls"]]

    if not deduped_urls:
        return {
            "enabled": True,
            "bounded": True,
            "simulated_journeys": 0,
            "journeys": [],
            "simulation_type": "url_planning",
            "max_journeys": journey_cfg["max_journeys"],
            "max_steps_per_journey": journey_cfg["max_steps_per_journey"],
            "early_exit": True,
            "early_exit_reasons": ["no_urls"],
        }

    def bounded_steps(steps: list[str]) -> list[str]:
        deduped = _dedupe_urls(steps)
        return deduped[: journey_cfg["max_steps_per_journey"]]

    lowered = [(url, url.lower()) for url in deduped_urls]

    def pick(*tokens: str) -> str:
        for original, lower in lowered:
            if any(token in lower for token in tokens):
                return original
        return ""

    homepage = deduped_urls[0] if deduped_urls else ""
    product = pick("/product", "/item", "/listing", "/shop")
    cart = pick("/cart", "/basket")
    checkout = pick("/checkout", "/payment", "/order")
    login = pick("/login", "/signin", "/auth")
    search = pick("/search", "/results")

    journey_specs = [
        ("checkout", [homepage, product, cart, checkout], checkout),
        ("login", [homepage, login], login),
        ("search", [homepage, search], search),
    ]

    journeys: list[dict[str, Any]] = []
    early_exit_reasons: list[str] = []

    for journey_name, raw_steps, expected_terminal in journey_specs[: journey_cfg["max_journeys"]]:
        steps = bounded_steps([step for step in raw_steps if step])
        if not steps:
            journeys.append(
                {
                    "name": journey_name,
                    "steps": [],
                    "completed": False,
                    "skipped": True,
                    "simulation_type": "url_planning",
                    "early_exit_reason": "missing_candidate_steps",
                }
            )
            early_exit_reasons.append(f"{journey_name}:missing_candidate_steps")
            continue

        completed = bool(expected_terminal and expected_terminal in steps)
        if expected_terminal and not completed:
            early_exit_reasons.append(f"{journey_name}:incomplete_path")

        journeys.append(
            {
                "name": journey_name,
                "steps": steps,
                "completed": completed,
                "skipped": False,
                "simulation_type": "url_planning",
                "bounded_steps": len(steps),
            }
        )

    simulated = sum(1 for journey in journeys if journey["steps"])
    return {
        "enabled": True,
        "bounded": True,
        "simulated_journeys": simulated,
        "journeys": journeys,
        "simulation_type": "url_planning",
        "max_journeys": journey_cfg["max_journeys"],
        "max_steps_per_journey": journey_cfg["max_steps_per_journey"],
        "candidate_urls_considered": len(deduped_urls),
        "early_exit": bool(early_exit_reasons),
        "early_exit_reasons": early_exit_reasons,
    }


def _mode_engine_policy(scan_mode: str) -> dict[str, bool]:
    return {
        "playwright": scan_mode in {"deep", "max"},
        "axe": scan_mode in {"deep", "max"},
        "cognitive": scan_mode == "max",
        "dom_crawler": scan_mode == "max",
        "journey_simulation": scan_mode == "max",
    }


def _apply_mode_policy(scan_mode: str, page_context: PageContext) -> None:
    if page_context.static_engine is None:
        page_context.static_engine = _default_static_engine

    if scan_mode == "fast":
        page_context.playwright_browser = None
        page_context.playwright_driver = None
        page_context.browser_factory = None
        page_context.interactive_engine = None
        page_context.axe_engine = None
        page_context.cognitive_engine = None
        if page_context.state_provider is None:
            page_context.state_provider = _fast_state_provider
        return

    if page_context.interactive_engine is None:
        page_context.interactive_engine = _noop_async_engine

    if page_context.axe_engine is None:
        page_context.axe_engine = _noop_async_engine

    if page_context.browser_factory is None and page_context.playwright_browser is None:
        page_context.browser_factory = _playwright_browser_factory

    if scan_mode == "deep":
        page_context.cognitive_engine = None
        return

    if page_context.cognitive_engine is None:
        page_context.cognitive_engine = _noop_async_engine


async def run_scan_mode_audit(
    seed_url: str,
    scan_mode: str,
    max_pages: int,
    *,
    crawler_orchestrator: Optional[CrawlerOrchestrator] = None,
    page_context: Optional[PageContext] = None,
    page_auditor: Optional[PageAuditor] = None,
    static_only_auditor: Optional[PageAuditor] = None,
    sse_emitter: Optional[SSEEmitter] = None,
    journey_simulator: Optional[JourneySimulator] = None,
) -> dict[str, Any]:
    """Execute full mode-specific site auditing from discovery through aggregation."""
    mode = normalize_scan_mode(scan_mode)
    requested_pages = max(1, int(max_pages))
    ceiling = resolve_max_pages(mode, has_sitemap=False)
    effective_max_pages = min(requested_pages, ceiling)
    mode_config = SCAN_MODES.get(mode, SCAN_MODES["fast"])

    async with _SITE_AUDIT_SEMAPHORE:
        orchestrator = crawler_orchestrator or CrawlerOrchestrator()
        discovered_urls = await orchestrator.discover_urls(seed_url, mode, effective_max_pages)
        deduped_urls = _dedupe_urls(discovered_urls)
        if not deduped_urls:
            deduped_urls = [seed_url]

        # ── Phase 20: Topology-guided URL selection ──────────────────────────
        # Run detect_topology on the full discovered set so the classification
        # uses maximum signal.  The returned crawl_urls list is already:
        #   • deduplicated          • template-diverse
        #   • pagination-filtered   • homepage-first
        # Fall back to the dumb slice if the detector fails.
        _topo_value: str | None = None
        _topo_templates: int | None = None
        _topo_discovered: int | None = None
        _topo_skipped: int | None = None
        try:
            from app.services.topology_detector import detect_topology as _topo_detect
            _topo_result = _topo_detect(deduped_urls)
            # Respect the effective_max_pages ceiling: even topology-guided lists
            # must not exceed what the caller requested.
            _topo_crawl = _topo_result.crawl_urls[:effective_max_pages]
            urls_to_audit = _topo_crawl if _topo_crawl else deduped_urls[:effective_max_pages]
            _topo_value = (
                _topo_result.topology.value
                if hasattr(_topo_result.topology, "value")
                else str(_topo_result.topology)
            )
            _topo_templates = _topo_result.templates_found
            _topo_discovered = _topo_result.total_discovered
            _topo_skipped = _topo_result.skipped_urls
        except Exception as _topo_err:
            import logging as _logging
            _logging.getLogger(__name__).warning(
                "topology detection failed in scan_mode_runner (fallback to slice): %s", _topo_err
            )
            urls_to_audit = deduped_urls[:effective_max_pages]

        context = page_context or PageContext()
        created_context = page_context is None
        if not isinstance(context.cache, dict):
            context.cache = {}
        site_audit_run_id = str(uuid.uuid4())
        context.cache["site_audit_run_id"] = site_audit_run_id

        try:
            from app.services.audit_runner import clear_domain_preflight_cache

            clear_domain_preflight_cache(site_audit_run_id)
        except Exception:
            pass

        _apply_mode_policy(mode, context)

        try:
            resolved_page_auditor = page_auditor
            if resolved_page_auditor is None and mode in {"deep", "max"}:
                resolved_page_auditor = _full_engine_page_auditor

            result = await run_site_audit(
                urls=urls_to_audit,
                scan_mode=mode,
                max_concurrent_pages=max(1, int(mode_config["concurrency"])),
                page_context=context,
                page_auditor=resolved_page_auditor,
                static_only_auditor=static_only_auditor,
                sse_emitter=sse_emitter,
                page_timeout_stage1_seconds=float(mode_config["stage1_timeout"]),
                page_timeout_stage2_seconds=float(mode_config["stage2_timeout"]),
                global_sla_seconds=float(mode_config["global_sla"]),
            )

            result["seed_url"] = seed_url
            result["scan_mode"] = mode
            result["pages_cap"] = effective_max_pages
            result["pages_requested"] = requested_pages
            result["pages_discovered"] = len(deduped_urls)
            result["urls_audited"] = urls_to_audit
            result["engines_policy"] = _mode_engine_policy(mode)
            result["system_limits"] = {
                "max_concurrent_site_audits": int(
                    AUDIT_PIPELINE_CONFIG["parallel_runner"].get("max_concurrent_site_audits", 4)
                )
            }
            # Phase 20: topology metadata propagated from URL-selection phase
            result["site_topology"] = _topo_value
            result["templates_found"] = _topo_templates
            result["urls_discovered"] = _topo_discovered
            result["urls_skipped"] = _topo_skipped

            if isinstance(result.get("site_result"), dict):
                result["site_result"]["pages_discovered"] = len(deduped_urls)
                if isinstance(result["site_result"].get("executive_summary"), dict):
                    result["site_result"]["executive_summary"]["pages_discovered"] = len(deduped_urls)

            if mode == "max":
                simulator = journey_simulator or _default_journey_simulator
                try:
                    journey_payload = await simulator(urls_to_audit, mode, context)
                except Exception:
                    journey_payload = {
                        "enabled": True,
                        "failed": True,
                        "simulated_journeys": 0,
                        "journeys": [],
                        "bounded": True,
                        "simulation_type": "url_planning",
                    }
                    result["degraded_mode"] = True
                    result["degraded_reason"] = normalize_failure(result.get("degraded_reason")).value
                    if isinstance(result.get("site_result"), dict):
                        result["site_result"]["degraded_mode"] = True
                        result["site_result"]["degraded_reason"] = (
                            normalize_failure(result["site_result"].get("degraded_reason")).value
                        )

                result["journey_simulation"] = journey_payload
                await _emit_optional_event(
                    {
                        "type": "journey_complete",
                        "scan_mode": mode,
                        "simulated_journeys": int(journey_payload.get("simulated_journeys", 0)),
                    },
                    sse_emitter,
                )
            else:
                result["journey_simulation"] = {
                    "enabled": False,
                    "journeys": [],
                    "simulation_type": "url_planning",
                }

            return result
        finally:
            try:
                from app.services.audit_runner import clear_domain_preflight_cache

                clear_domain_preflight_cache(site_audit_run_id)
            except Exception:
                pass
            if created_context:
                await context.close()
