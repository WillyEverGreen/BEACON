"""Scan-mode orchestration integrating crawler discovery, parallel runner, and page auditing."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

import httpx

from app.audit.models import PageContext
from app.audit.failure_taxonomy import normalize_reason
from app.audit.parallel_runner import PageAuditor, SSEEmitter, run_site_audit
from app.crawlers.orchestrator import CrawlerOrchestrator
from app.config import AUDIT_PIPELINE_CONFIG, MAX_SCAN_GLOBAL_CAP, SCAN_MODE_CONFIG
from app.services.heuristics import HeuristicAnalyzer
from app.services.normalizer import normalize_all
from app.services.static_checks import StaticChecker


JourneySimulator = Callable[[list[str], str, PageContext], Awaitable[dict[str, Any]]]


_SITE_AUDIT_SEMAPHORE = asyncio.Semaphore(
    int(AUDIT_PIPELINE_CONFIG["parallel_runner"].get("max_concurrent_site_audits", 4))
)


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


def _normalize_scan_mode(scan_mode: str) -> str:
    mode = (scan_mode or "").lower()
    if mode not in {"fast", "deep", "max"}:
        raise ValueError(f"Unsupported scan_mode: {scan_mode}")
    return mode


def _mode_config(scan_mode: str) -> dict[str, Any]:
    return SCAN_MODE_CONFIG.get(scan_mode, SCAN_MODE_CONFIG["fast"])


def _mode_cap(scan_mode: str) -> int:
    mode_cfg = _mode_config(scan_mode)
    return min(int(mode_cfg["crawl_cap"]), int(MAX_SCAN_GLOBAL_CAP))


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
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
            response = await client.get(url)
        if response.status_code >= 400:
            return {"html": "", "hydration_status": "static_failed"}
        return {"html": response.text, "hydration_status": "static"}
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
            url=page_url,
        )
    except Exception:
        return [*list(static_issues or []), *list(heuristic_issues or [])]


async def _noop_async_engine(dom: str, page_url: str, page_context: PageContext) -> list[dict[str, Any]]:
    return []


async def _playwright_browser_factory() -> Any:
    if not _PLAYWRIGHT_AVAILABLE or async_playwright is None:
        raise RuntimeError("Playwright is unavailable for deep/max mode")

    driver = await async_playwright().start()
    browser = await driver.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-setuid-sandbox"],
    )
    return _ManagedPlaywrightBrowser(browser, driver)


async def _default_journey_simulator(urls: list[str], scan_mode: str, page_context: PageContext) -> dict[str, Any]:
    if scan_mode != "max":
        return {"enabled": False, "journeys": []}

    journey_cfg = _journey_config()
    deduped_urls = _dedupe_urls(urls)[: journey_cfg["max_candidate_urls"]]

    if not deduped_urls:
        return {
            "enabled": True,
            "bounded": True,
            "simulated_journeys": 0,
            "journeys": [],
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
                "bounded_steps": len(steps),
            }
        )

    simulated = sum(1 for journey in journeys if journey["steps"])
    return {
        "enabled": True,
        "bounded": True,
        "simulated_journeys": simulated,
        "journeys": journeys,
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
    mode = _normalize_scan_mode(scan_mode)
    mode_config = _mode_config(mode)
    cap = _mode_cap(mode)
    requested_pages = max(1, int(max_pages))
    requested_pages = min(requested_pages, int(mode_config["max_pages"]), int(MAX_SCAN_GLOBAL_CAP))
    effective_max_pages = min(requested_pages, cap)

    async with _SITE_AUDIT_SEMAPHORE:
        orchestrator = crawler_orchestrator or CrawlerOrchestrator()
        discovered_urls = await orchestrator.discover_urls(seed_url, mode, effective_max_pages)
        deduped_urls = _dedupe_urls(discovered_urls)
        if not deduped_urls:
            deduped_urls = [seed_url]
        urls_to_audit = deduped_urls[:effective_max_pages]

        context = page_context or PageContext()
        created_context = page_context is None
        _apply_mode_policy(mode, context)

        try:
            result = await run_site_audit(
                urls=urls_to_audit,
                scan_mode=mode,
                max_concurrent_pages=max(1, int(mode_config["concurrency"])),
                page_context=context,
                page_auditor=page_auditor,
                static_only_auditor=static_only_auditor,
                sse_emitter=sse_emitter,
                page_timeout_stage1_seconds=float(mode_config["stage1_timeout"]),
                page_timeout_stage2_seconds=float(mode_config["stage2_timeout"]),
                global_sla_seconds=float(mode_config["global_sla"]),
            )

            result["seed_url"] = seed_url
            result["scan_mode"] = mode
            result["pages_cap"] = cap
            result["pages_requested"] = requested_pages
            result["pages_discovered"] = len(deduped_urls)
            result["urls_audited"] = urls_to_audit
            result["engines_policy"] = _mode_engine_policy(mode)
            result["system_limits"] = {
                "max_concurrent_site_audits": int(
                    AUDIT_PIPELINE_CONFIG["parallel_runner"].get("max_concurrent_site_audits", 4)
                )
            }

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
                    }
                    result["degraded_mode"] = True
                    result["degraded_reason"] = normalize_reason(result.get("degraded_reason")) or "extraction_failure"
                    if isinstance(result.get("site_result"), dict):
                        result["site_result"]["degraded_mode"] = True
                        result["site_result"]["degraded_reason"] = (
                            normalize_reason(result["site_result"].get("degraded_reason")) or "extraction_failure"
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
                result["journey_simulation"] = {"enabled": False, "journeys": []}

            return result
        finally:
            if created_context:
                await context.close()
