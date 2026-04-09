"""Phase 6 crawl execution orchestrator for multi-page site intelligence."""

from __future__ import annotations

import asyncio
from collections import deque
import inspect
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

import app.config as app_config
from app.audit.failure_taxonomy import classify_failure_reason, normalize_reason
from app.crawlers.crawler import CrawlQueueEntry, CrawlSession
from app.crawlers.page_selector import LiveDOMLinkExtractor, SelectedLink, select_links_for_enqueue
from app.crawlers.site_aggregator import aggregate_site_issues
from app.crawlers.site_scorer import compute_site_score
from app.observability.telemetry import record_operational_event

logger = logging.getLogger(__name__)


AuditCallable = Callable[..., Awaitable[dict[str, Any]]]
EventRecorder = Callable[[str, dict[str, Any]], Any]
SiteCrawlResult = dict[str, Any]


@dataclass(slots=True)
class CrawlConfig:
    max_pages: int
    max_depth: int
    timeout_per_page_s: int
    concurrency: int
    await_enrichment: bool
    scan_mode: str = "deep"
    global_timeout_s: int | None = None
    failure_rate_reduce_threshold: float = 0.30
    failure_rate_stop_threshold: float = 0.30
    avg_page_time_reduce_threshold_s: float | None = None
    adaptive_budget_reduce_ratio: float = 0.40
    min_pages_before_adaptive_budget: int = 3
    low_information_window: int = 3
    low_information_gain_threshold: float = 0.05
    min_pages_before_info_gain_stop: int = 4
    standard_page_skip_budget_threshold: int = 1

    @classmethod
    def from_runtime_defaults(cls) -> "CrawlConfig":
        return cls(
            max_pages=int(app_config.CRAWL_MAX_PAGES_PER_SITE),
            max_depth=int(app_config.CRAWL_MAX_DEPTH),
            timeout_per_page_s=int(app_config.CRAWL_TIMEOUT_PER_PAGE_S),
            concurrency=int(app_config.CRAWL_CONCURRENCY),
            await_enrichment=False,
            scan_mode="deep",
        )

    def normalized(self) -> "CrawlConfig":
        scan_mode = _normalize_scan_mode(self.scan_mode)
        _, timeout_max = _timeout_bounds_for_mode(scan_mode)
        timeout_per_page_s = int(self.timeout_per_page_s)
        if timeout_per_page_s <= 0:
            timeout_min, timeout_max_default = _timeout_bounds_for_mode(scan_mode)
            timeout_per_page_s = (timeout_min + timeout_max_default) // 2
        timeout_per_page_s = max(1, min(timeout_per_page_s, timeout_max))

        adaptive_threshold = self.avg_page_time_reduce_threshold_s
        if adaptive_threshold is None:
            adaptive_threshold = float(timeout_per_page_s * 0.85)

        max_pages = max(1, int(self.max_pages))
        max_depth = max(0, int(self.max_depth))
        if scan_mode == "deep":
            # Phase 6.2: hard-cap deep crawl breadth/depth for reliability promotion.
            max_pages = min(max_pages, 25)
            max_depth = min(max_depth, 3)

        global_timeout_s = self.global_timeout_s
        if global_timeout_s is None:
            global_timeout_s = int(max(30, min(300, max_pages * timeout_per_page_s)))

        max_allowed_concurrency = 3 if scan_mode == "deep" else 2

        return CrawlConfig(
            max_pages=max_pages,
            max_depth=max_depth,
            timeout_per_page_s=timeout_per_page_s,
            concurrency=max(1, min(int(self.concurrency), max_allowed_concurrency)),
            await_enrichment=bool(self.await_enrichment),
            scan_mode=scan_mode,
            global_timeout_s=max(20, int(global_timeout_s)),
            failure_rate_reduce_threshold=min(max(float(self.failure_rate_reduce_threshold), 0.05), 0.90),
            failure_rate_stop_threshold=min(max(float(self.failure_rate_stop_threshold), 0.10), 0.95),
            avg_page_time_reduce_threshold_s=max(4.0, float(adaptive_threshold)),
            adaptive_budget_reduce_ratio=min(max(float(self.adaptive_budget_reduce_ratio), 0.30), 0.50),
            min_pages_before_adaptive_budget=max(1, int(self.min_pages_before_adaptive_budget)),
            low_information_window=max(2, int(self.low_information_window)),
            low_information_gain_threshold=min(max(float(self.low_information_gain_threshold), 0.01), 0.20),
            min_pages_before_info_gain_stop=max(3, int(self.min_pages_before_info_gain_stop)),
            standard_page_skip_budget_threshold=max(1, int(self.standard_page_skip_budget_threshold)),
        )


@dataclass(slots=True)
class _ProcessedPage:
    entry: CrawlQueueEntry
    page_result: dict[str, Any]
    selected_links: list[SelectedLink]
    skipped_links: list[dict[str, str]]


class SiteCrawlOrchestrator:
    """Deterministic BFS crawl orchestrator with bounded audit and aggregation."""

    def __init__(
        self,
        *,
        audit_callable: Optional[AuditCallable] = None,
        link_extractor: Optional[LiveDOMLinkExtractor] = None,
        event_recorder: EventRecorder = record_operational_event,
    ) -> None:
        self._audit_callable = audit_callable or _default_audit_callable
        self._link_extractor = link_extractor
        self._event_recorder = event_recorder

    async def crawl_site(self, seed_url: str, config: CrawlConfig) -> SiteCrawlResult:
        cfg = config.normalized()
        session = CrawlSession()
        link_extractor = self._link_extractor or LiveDOMLinkExtractor()
        created_extractor = self._link_extractor is None

        start_time = time.perf_counter()
        crawl_deadline = start_time + float(cfg.global_timeout_s or 0)
        crawl_timestamp = _utc_now_iso()

        pages_crawled = 0
        pages_failed = 0
        pages_skipped_due_to_failure = 0
        pages_skipped_low_value = 0
        consecutive_failures = 0
        effective_max_pages = cfg.max_pages
        effective_concurrency = max(1, int(cfg.concurrency))
        budget_reduction_events = 0
        early_stop_reason: str | None = None

        page_results: list[dict[str, Any]] = []
        page_durations: list[float] = []
        unique_issue_keys: set[str] = set()
        recent_unique_issue_additions: deque[int] = deque(maxlen=cfg.low_information_window)

        seed_enqueued, seed_dedup_key = session.enqueue(
            fetch_url=seed_url,
            depth=0,
            page_type="homepage",
            page_weight=1.0,
        )
        if not seed_enqueued:
            raise ValueError(f"Invalid seed_url for crawl: {seed_url}")

        await self._emit_event(
            "crawl_started",
            {
                "site_url": seed_url,
                "max_pages": effective_max_pages,
                "max_depth": cfg.max_depth,
                "timeout_per_page_s": cfg.timeout_per_page_s,
                "global_timeout_s": cfg.global_timeout_s,
                "scan_mode": cfg.scan_mode,
                "timestamp": crawl_timestamp,
                "seed_fetch_url": seed_url,
                "seed_dedup_key": seed_dedup_key,
            },
        )

        if created_extractor:
            await link_extractor.start()

        try:
            while session.has_pending and pages_crawled < effective_max_pages:
                if time.perf_counter() >= crawl_deadline:
                    early_stop_reason = "global_timeout"
                    break

                failure_rate = _safe_ratio(pages_failed, pages_crawled)
                if pages_crawled >= 2 and failure_rate >= cfg.failure_rate_stop_threshold:
                    early_stop_reason = "failure_threshold"
                    break

                if failure_rate > cfg.failure_rate_reduce_threshold and effective_concurrency > 1:
                    effective_concurrency = max(1, effective_concurrency - 1)
                    await self._emit_event(
                        "crawl_concurrency_adjusted",
                        {
                            "site_url": seed_url,
                            "concurrency": effective_concurrency,
                            "reason": "failure_spike",
                            "failure_rate": round(failure_rate, 6),
                        },
                    )

                if consecutive_failures >= 3:
                    early_stop_reason = "failure_threshold"
                    break

                batch, skipped_depth_entries = self._dequeue_batch(
                    session=session,
                    cfg=cfg,
                    pages_crawled=pages_crawled,
                    max_pages_limit=effective_max_pages,
                    effective_concurrency=effective_concurrency,
                )

                for skipped_entry in skipped_depth_entries:
                    await self._emit_event(
                        "page_skipped",
                        {
                            "site_url": seed_url,
                            "url": skipped_entry.fetch_url,
                            "dedup_key": skipped_entry.dedup_key,
                            "skip_reason": "depth_exceeded",
                        },
                    )

                if not batch:
                    if skipped_depth_entries:
                        continue
                    break

                processed_batch = await asyncio.gather(
                    *[
                        self._process_entry(
                            entry=entry,
                            seed_url=seed_url,
                            timeout_per_page_s=_timeout_for_page_type(
                                page_type=entry.page_type,
                                scan_mode=cfg.scan_mode,
                                fallback_timeout_s=cfg.timeout_per_page_s,
                            ),
                            scan_mode=cfg.scan_mode,
                            await_enrichment=cfg.await_enrichment,
                            link_extractor=link_extractor,
                        )
                        for entry in batch
                    ]
                )

                for processed in processed_batch:
                    entry = processed.entry
                    page_results.append(processed.page_result)
                    pages_crawled += 1

                    audit_status = str(processed.page_result.get("audit_status") or "error")
                    page_duration_s = float(processed.page_result.get("audit_duration_s") or 0.0)
                    page_durations.append(page_duration_s)

                    if audit_status == "success":
                        new_unique_issues = _count_new_unique_issues(processed.page_result, unique_issue_keys)
                        recent_unique_issue_additions.append(new_unique_issues)
                    else:
                        new_unique_issues = 0
                        recent_unique_issue_additions.append(0)

                    if audit_status == "success":
                        consecutive_failures = 0
                    else:
                        pages_failed += 1
                        consecutive_failures += 1

                    failure_rate = _safe_ratio(pages_failed, pages_crawled)
                    avg_page_time = _safe_mean(page_durations)

                    await self._emit_event(
                        "page_crawled",
                        {
                            "site_url": seed_url,
                            "url": entry.fetch_url,
                            "fetch_url": entry.fetch_url,
                            "dedup_key": entry.dedup_key,
                            "depth": entry.depth,
                            "page_type": entry.page_type,
                            "audit_status": processed.page_result.get("audit_status"),
                            "failure_reason": processed.page_result.get("failure_reason"),
                            "issues_count": len(processed.page_result.get("issues") or []),
                            "new_unique_issues": new_unique_issues,
                            "score": processed.page_result.get("score"),
                            "duration_s": processed.page_result.get("audit_duration_s"),
                            "failure_rate": round(failure_rate, 6),
                            "avg_page_time": round(avg_page_time, 6),
                        },
                    )

                    for skipped in processed.skipped_links:
                        reason = str(skipped.get("reason") or "exclusion_rule")
                        if reason == "exclusion_rule":
                            session.pages_skipped_exclusion += 1
                        if reason.startswith("low_value"):
                            pages_skipped_low_value += 1

                        await self._emit_event(
                            "page_skipped",
                            {
                                "site_url": seed_url,
                                "url": str(skipped.get("url") or ""),
                                "skip_reason": reason,
                            },
                        )

                    if audit_status != "success":
                        pages_skipped_due_to_failure += len(processed.selected_links)
                        for link in processed.selected_links:
                            await self._emit_event(
                                "page_skipped",
                                {
                                    "site_url": seed_url,
                                    "url": link.fetch_url,
                                    "dedup_key": link.dedup_key,
                                    "skip_reason": "parent_page_failed",
                                },
                            )
                    else:
                        for link in processed.selected_links:
                            remaining_budget = max(0, effective_max_pages - pages_crawled)
                            if (
                                link.page_type == "standard"
                                and remaining_budget <= cfg.standard_page_skip_budget_threshold
                            ):
                                pages_skipped_low_value += 1
                                await self._emit_event(
                                    "page_skipped",
                                    {
                                        "site_url": seed_url,
                                        "url": link.fetch_url,
                                        "dedup_key": link.dedup_key,
                                        "skip_reason": "low_priority_budget_guard",
                                    },
                                )
                                continue

                            enqueued, dedup_key = session.enqueue(
                                fetch_url=link.fetch_url,
                                depth=entry.depth + 1,
                                page_type=link.page_type,
                                page_weight=link.page_weight,
                            )
                            if not enqueued:
                                await self._emit_event(
                                    "page_skipped",
                                    {
                                        "site_url": seed_url,
                                        "url": link.fetch_url,
                                        "dedup_key": dedup_key,
                                        "skip_reason": "dedup",
                                    },
                                )

                    if pages_crawled >= cfg.min_pages_before_adaptive_budget:
                        failure_rate = _safe_ratio(pages_failed, pages_crawled)
                        avg_page_time = _safe_mean(page_durations)
                        if (
                            failure_rate > cfg.failure_rate_reduce_threshold
                            or avg_page_time > float(cfg.avg_page_time_reduce_threshold_s or 0.0)
                        ):
                            remaining_budget = max(0, effective_max_pages - pages_crawled)
                            if remaining_budget > 1:
                                retained_budget = max(
                                    1,
                                    int(round(remaining_budget * (1.0 - cfg.adaptive_budget_reduce_ratio))),
                                )
                                updated_limit = pages_crawled + retained_budget
                                if updated_limit < effective_max_pages:
                                    effective_max_pages = updated_limit
                                    budget_reduction_events += 1
                                    await self._emit_event(
                                        "crawl_budget_reduced",
                                        {
                                            "site_url": seed_url,
                                            "effective_max_pages": effective_max_pages,
                                            "failure_rate": round(failure_rate, 6),
                                            "avg_page_time": round(avg_page_time, 6),
                                        },
                                    )

                    if (
                        pages_crawled >= cfg.min_pages_before_info_gain_stop
                        and len(recent_unique_issue_additions) == cfg.low_information_window
                    ):
                        recent_added = sum(recent_unique_issue_additions)
                        total_unique = len(unique_issue_keys)
                        information_gain = recent_added / float(max(1, total_unique))
                        if information_gain < cfg.low_information_gain_threshold:
                            early_stop_reason = "low_information_gain"
                            break

                    if pages_crawled >= effective_max_pages:
                        break

                    if time.perf_counter() >= crawl_deadline:
                        early_stop_reason = "global_timeout"
                        break

                    failure_rate = _safe_ratio(pages_failed, pages_crawled)
                    if pages_crawled >= 2 and failure_rate >= cfg.failure_rate_stop_threshold:
                        early_stop_reason = "failure_threshold"
                        break

                if pages_crawled >= effective_max_pages:
                    if early_stop_reason is None:
                        early_stop_reason = (
                            "max_pages_reached"
                            if effective_max_pages == cfg.max_pages
                            else "adaptive_budget_reached"
                        )
                    break

                if consecutive_failures >= 3:
                    early_stop_reason = "failure_threshold"
                    break

            successful_page_results = [
                page
                for page in page_results
                if str(page.get("audit_status") or "") == "success"
            ]

            aggregation = aggregate_site_issues(successful_page_results)
            site_score = compute_site_score(successful_page_results, aggregation["aggregated_issues"])

            await self._emit_event(
                "aggregation_completed",
                {
                    "site_url": seed_url,
                    "total_issues_before_dedup": aggregation["total_issues_before_dedup"],
                    "total_issues_after_dedup": aggregation["total_issues_after_dedup"],
                    "aggregated_issue_count": len(aggregation["aggregated_issues"]),
                    "top_priority_issue_type": (
                        aggregation["top_priorities"][0].get("issue_type")
                        if aggregation["top_priorities"]
                        else ""
                    ),
                },
            )

            crawl_duration_s = round(time.perf_counter() - start_time, 3)
            dedup_efficiency = _safe_ratio(
                session.pages_skipped_dedup,
                pages_crawled + session.pages_skipped_dedup,
            )
            failure_rate = _safe_ratio(pages_failed, pages_crawled)
            avg_page_time = _safe_mean(page_durations)

            crawl_status = _derive_crawl_status(
                early_stop_reason=early_stop_reason,
                pages_failed=pages_failed,
                queue_remaining=session.has_pending,
            )

            result: SiteCrawlResult = {
                "site_url": seed_url,
                "crawl_timestamp": crawl_timestamp,
                "crawl_status": crawl_status,
                "site_score": site_score,
                "pages_audited": pages_crawled,
                "pages_failed": pages_failed,
                "page_summaries": [
                    {
                        "url": str(page.get("fetch_url") or page.get("url") or ""),
                        "page_type": str(page.get("page_type") or "standard"),
                        "page_weight": float(page.get("page_weight") or 0.7),
                        "audit_scan_mode": str(page.get("audit_scan_mode") or "deep"),
                        "score": page.get("score"),
                        "issues_count": len(page.get("issues") or []),
                        "audit_status": str(page.get("audit_status") or "error"),
                        "failure_reason": page.get("failure_reason"),
                        "spa_detected": bool(page.get("spa_detected", False)),
                    }
                    for page in page_results
                ],
                "aggregated_issues": aggregation["aggregated_issues"],
                "top_priorities": aggregation["top_priorities"],
                "recommendations": aggregation["recommendations"],
                "crawl_meta": {
                    "max_pages_config": cfg.max_pages,
                    "effective_max_pages": effective_max_pages,
                    "max_depth_config": cfg.max_depth,
                    "timeout_per_page_s": cfg.timeout_per_page_s,
                    "global_timeout_s": cfg.global_timeout_s,
                    "scan_mode": cfg.scan_mode,
                    "concurrency": effective_concurrency,
                    "budget_reduction_events": budget_reduction_events,
                    "pages_skipped_dedup": session.pages_skipped_dedup,
                    "pages_skipped_depth": session.pages_skipped_depth,
                    "pages_skipped_exclusion": session.pages_skipped_exclusion,
                    "pages_skipped_due_to_failure": pages_skipped_due_to_failure,
                    "pages_skipped_low_value": pages_skipped_low_value,
                    "failure_rate": round(failure_rate, 6),
                    "avg_page_time": round(avg_page_time, 6),
                    "crawl_duration_s": crawl_duration_s,
                    "early_stop_reason": early_stop_reason,
                },
            }

            await self._emit_event(
                "crawl_completed",
                {
                    "site_url": seed_url,
                    "crawl_status": crawl_status,
                    "pages_crawled": pages_crawled,
                    "pages_failed": pages_failed,
                    "pages_skipped_dedup": session.pages_skipped_dedup,
                    "pages_skipped_due_to_failure": pages_skipped_due_to_failure,
                    "pages_skipped_low_value": pages_skipped_low_value,
                    "dedup_efficiency": round(dedup_efficiency, 6),
                    "failure_rate": round(failure_rate, 6),
                    "avg_page_time": round(avg_page_time, 6),
                    "site_score": site_score,
                    "crawl_duration_s": crawl_duration_s,
                    "early_stop_reason": early_stop_reason,
                },
            )

            return result
        finally:
            if created_extractor:
                await link_extractor.close()

    def _dequeue_batch(
        self,
        *,
        session: CrawlSession,
        cfg: CrawlConfig,
        pages_crawled: int,
        max_pages_limit: int,
        effective_concurrency: int,
    ) -> tuple[list[CrawlQueueEntry], list[CrawlQueueEntry]]:
        skipped_depth_entries: list[CrawlQueueEntry] = []

        entry = session.dequeue_prioritized()
        while entry is not None and entry.depth > cfg.max_depth:
            session.pages_skipped_depth += 1
            skipped_depth_entries.append(entry)
            entry = session.dequeue_prioritized()

        if entry is None:
            return [], skipped_depth_entries

        batch = [entry]
        if effective_concurrency <= 1:
            return batch, skipped_depth_entries

        while (
            len(batch) < effective_concurrency
            and session.has_pending
            and pages_crawled + len(batch) < max_pages_limit
        ):
            next_entry = session.dequeue_prioritized()
            if next_entry is None:
                break
            if next_entry.depth > cfg.max_depth:
                session.pages_skipped_depth += 1
                skipped_depth_entries.append(next_entry)
                continue
            batch.append(next_entry)

        return batch, skipped_depth_entries

    async def _process_entry(
        self,
        *,
        entry: CrawlQueueEntry,
        seed_url: str,
        timeout_per_page_s: int,
        scan_mode: str,
        await_enrichment: bool,
        link_extractor: LiveDOMLinkExtractor,
    ) -> _ProcessedPage:
        started = time.perf_counter()

        audit_status = "success"
        failure_reason: str | None = None
        issues: list[dict[str, Any]] = []
        score: float | None = None
        spa_detected = False

        try:
            audit_scan_mode = _scan_mode_for_page_type(entry.page_type, scan_mode)
            audit_result = await asyncio.wait_for(
                self._audit_callable(
                    url=entry.fetch_url,
                    scan_mode=audit_scan_mode,
                    max_pages=1,
                    await_enrichment=await_enrichment,
                ),
                timeout=max(1, int(timeout_per_page_s)),
            )
            audit_status, failure_reason = _classify_audit_result(audit_result)

            if audit_status == "success":
                issues = list(audit_result.get("issues") or [])
                raw_score = audit_result.get("overall_score", audit_result.get("score"))
                score = float(raw_score) if isinstance(raw_score, (int, float)) else None

            spa_detected = bool(audit_result.get("is_spa") or audit_result.get("spa_framework"))
        except asyncio.TimeoutError:
            audit_status = "timeout"
            failure_reason = "timeout_exceeded"
        except Exception as exc:
            audit_status, failure_reason = _classify_exception(exc)

        duration_s = round(time.perf_counter() - started, 3)

        selected_links: list[SelectedLink] = []
        skipped_links: list[dict[str, str]] = []
        if audit_status == "success":
            try:
                raw_links = await link_extractor.extract_links(entry.fetch_url, timeout_per_page_s)
                selected_links, skipped_links = select_links_for_enqueue(
                    raw_links,
                    current_fetch_url=entry.fetch_url,
                    seed_url=seed_url,
                    next_depth=entry.depth + 1,
                )
            except Exception as exc:
                logger.debug("Link extraction failed for %s: %s", entry.fetch_url, exc)

        page_result = {
            "url": entry.dedup_key,
            "fetch_url": entry.fetch_url,
            "dedup_key": entry.dedup_key,
            "depth": entry.depth,
            "page_type": entry.page_type,
            "page_weight": entry.page_weight,
            "audit_scan_mode": _scan_mode_for_page_type(entry.page_type, scan_mode),
            "audit_status": audit_status,
            "failure_reason": failure_reason,
            "issues": issues,
            "score": score,
            "spa_detected": spa_detected,
            "audit_duration_s": duration_s,
        }

        return _ProcessedPage(
            entry=entry,
            page_result=page_result,
            selected_links=selected_links,
            skipped_links=skipped_links,
        )

    async def _emit_event(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            maybe = self._event_recorder(event_type, payload)
            if inspect.isawaitable(maybe):
                await maybe
        except Exception as exc:
            logger.debug("Telemetry emission failed for %s: %s", event_type, exc)


async def crawl_site(seed_url: str, config: CrawlConfig) -> SiteCrawlResult:
    """Entry point required by the Phase 6 contract."""
    orchestrator = SiteCrawlOrchestrator()
    return await orchestrator.crawl_site(seed_url, config)


async def _default_audit_callable(**kwargs: Any) -> dict[str, Any]:
    from app.services.audit_runner import run_audit

    return await run_audit(**kwargs)


def _classify_exception(exc: Exception) -> tuple[str, str]:
    reason = normalize_reason(classify_failure_reason(exc)) or "network_error"
    detail = str(exc or "").strip()
    lowered = detail.lower()

    if reason == "render_timeout" or "timeout" in lowered:
        return "timeout", "timeout_exceeded"

    if reason == "blocked_request" or any(token in lowered for token in ("403", "401", "forbidden", "blocked", "csp", "auth wall")):
        return "blocked", f"blocked:{reason}"

    if any(token in lowered for token in ("navigation", "page.goto", "execution context", "target page")):
        return "error", f"navigation_error:{detail[:120]}"

    return "error", f"navigation_error:{reason}"


def _classify_audit_result(audit_result: dict[str, Any]) -> tuple[str, str | None]:
    if not isinstance(audit_result, dict):
        return "error", "navigation_error:invalid_audit_payload"

    degraded_mode = bool(audit_result.get("degraded_mode", False))
    runtime_passed = bool((audit_result.get("quality_gates") or {}).get("runtime_passed", True))
    explicit_reason = audit_result.get("degraded_reason") or audit_result.get("degradation_reason")

    if explicit_reason:
        degraded_reason = normalize_reason(explicit_reason)
    elif degraded_mode or not runtime_passed:
        degraded_reason = normalize_reason(classify_failure_reason(audit_result.get("summary")))
    else:
        degraded_reason = ""

    if not runtime_passed and not degraded_reason:
        degraded_reason = "render_timeout"

    if not degraded_mode and not degraded_reason:
        return "success", None

    if degraded_reason in {"render_timeout"}:
        return "timeout", "timeout_exceeded"

    if degraded_reason in {"blocked_request"}:
        return "blocked", f"blocked:{degraded_reason}"

    if degraded_reason in {"dns_failure", "network_error", "dom_parse_error", "extraction_failure"}:
        return "error", f"navigation_error:{degraded_reason}"

    return "error", f"navigation_error:{degraded_reason or 'unknown'}"


def _normalize_scan_mode(scan_mode: str) -> str:
    lowered = str(scan_mode or "deep").strip().lower()
    if lowered in {"fast", "standard", "deep"}:
        return lowered
    if lowered in {"max", "minimal"}:
        return "deep" if lowered == "max" else "fast"
    return "deep"


def _timeout_bounds_for_mode(scan_mode: str) -> tuple[int, int]:
    mode = _normalize_scan_mode(scan_mode)
    if mode == "fast":
        return 8, 10
    if mode == "standard":
        return 12, 15
    return 15, 15


def _timeout_for_page_type(*, page_type: str, scan_mode: str, fallback_timeout_s: int) -> int:
    lowered_page_type = str(page_type or "").strip().lower()

    if lowered_page_type in {"homepage", "interaction"}:
        timeout_min, timeout_max = _timeout_bounds_for_mode("deep")
    elif lowered_page_type == "nav":
        timeout_min, timeout_max = _timeout_bounds_for_mode("standard")
    else:
        timeout_min, timeout_max = _timeout_bounds_for_mode("fast")

    if _normalize_scan_mode(scan_mode) == "fast" and lowered_page_type in {"homepage", "interaction", "nav"}:
        timeout_min, timeout_max = _timeout_bounds_for_mode("standard")

    raw_timeout = int(fallback_timeout_s or 0)
    if raw_timeout <= 0:
        raw_timeout = (timeout_min + timeout_max) // 2
    return max(1, min(raw_timeout, timeout_max))


def _scan_mode_for_page_type(page_type: str, crawl_scan_mode: str) -> str:
    mode = _normalize_scan_mode(crawl_scan_mode)
    lowered_page_type = str(page_type or "").strip().lower()

    if mode == "fast":
        return "fast"

    if lowered_page_type in {"homepage", "interaction"}:
        return "deep"
    return "fast"


def _count_new_unique_issues(page_result: dict[str, Any], seen_issue_keys: set[str]) -> int:
    fresh_count = 0
    for issue in list(page_result.get("issues") or []):
        key = _issue_identity_key(issue)
        if key in seen_issue_keys:
            continue
        seen_issue_keys.add(key)
        fresh_count += 1
    return fresh_count


def _issue_identity_key(issue: dict[str, Any]) -> str:
    issue_type = str(issue.get("issue_type") or issue.get("rule_id") or "unknown")
    wcag = str(issue.get("wcag_criterion") or "")
    selector = str(issue.get("selector") or issue.get("element") or issue.get("target") or "")
    role = str(issue.get("element_role") or issue.get("element_type") or "")
    return "|".join([issue_type, wcag, selector.strip(), role.strip()])


def _safe_ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def _safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _derive_crawl_status(*, early_stop_reason: str | None, pages_failed: int, queue_remaining: bool) -> str:
    if early_stop_reason in {"failure_threshold", "global_timeout"}:
        return "aborted"

    if early_stop_reason == "low_information_gain":
        return "partial" if pages_failed > 0 else "completed"

    if pages_failed > 0:
        return "partial"

    if queue_remaining:
        return "partial"

    return "completed"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
