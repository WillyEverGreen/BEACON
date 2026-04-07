"""Data models for page-level and site-level audit orchestration."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, field
from typing import Any, Awaitable, Callable, Optional


StateProvider = Callable[[str, str, "PageContext"], Awaitable[dict[str, Any] | str]]
StaticEngine = Callable[[str, str], list[dict[str, Any]]]
InteractiveEngine = Callable[[str, str, "PageContext"], Awaitable[list[dict[str, Any]]]]
AxeEngine = Callable[[str, str, "PageContext"], Awaitable[list[dict[str, Any]]]]
CognitiveEngine = Callable[[str, str, "PageContext"], Awaitable[list[dict[str, Any]]]]
BrowserFactory = Callable[[], Awaitable[Any]]


@dataclass
class PageContext:
    """Shared resources reused across page audits in one site-audit run."""

    playwright_driver: Any = None
    playwright_browser: Any = None
    owns_browser: bool = False
    browser_factory: Optional[BrowserFactory] = None

    bm25_index: Any = None
    llm_semaphore: Optional[asyncio.Semaphore] = None
    cache: dict[str, Any] = field(default_factory=dict)

    state_provider: Optional[StateProvider] = None
    static_engine: Optional[StaticEngine] = None
    interactive_engine: Optional[InteractiveEngine] = None
    axe_engine: Optional[AxeEngine] = None
    cognitive_engine: Optional[CognitiveEngine] = None

    async def close(self) -> None:
        """Close browser resources created by this context."""
        if self.playwright_browser is not None and self.owns_browser:
            close_browser = getattr(self.playwright_browser, "close", None)
            if callable(close_browser):
                close_result = close_browser()
                if hasattr(close_result, "__await__"):
                    await close_result
            self.playwright_browser = None

        if self.playwright_driver is not None and self.owns_browser:
            stop_driver = getattr(self.playwright_driver, "stop", None)
            if callable(stop_driver):
                stop_result = stop_driver()
                if hasattr(stop_result, "__await__"):
                    await stop_result
            self.playwright_driver = None


@dataclass(slots=True)
class PageStateMeta:
    state: str
    duration_ms: int
    dom_hash: str
    issues_count: int
    duplicate_state: bool = False


@dataclass(slots=True)
class PageAuditResult:
    url: str
    score: float
    issues: list[dict[str, Any]]
    engine_timings: dict[str, float]
    degraded_mode: bool = False
    degraded_reason: str = ""
    skipped_engines: list[str] = field(default_factory=list)
    hydration_status: str = "unknown"
    enrichment_status: str = "pending"
    states_meta: list[dict[str, Any]] = field(default_factory=list)
    page_dom: str = ""


@dataclass(slots=True)
class SiteAuditResult:
    scan_mode: str
    site_score: float
    worst_page_score: float
    worst_page: dict[str, Any]
    best_page: dict[str, Any]
    pages_audited: int
    pages_discovered: int
    issues: list[dict[str, Any]]
    priority_ranking: list[dict[str, Any]]
    executive_summary: dict[str, Any]



def state_meta_to_dict(meta: PageStateMeta) -> dict[str, Any]:
    return asdict(meta)
