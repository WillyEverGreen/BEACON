"""Parallel page audit runner with timeout fallback, SLA guardrails, and SSE events."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import asdict
from typing import Any

from app.audit.failure_taxonomy import (
    classify_failure_reason,
    normalize_failure,
    normalize_reason,
)
from app.audit.models import PageAuditResult, PageContext
from app.audit.page_auditor import audit_page
from app.audit.site_aggregator import aggregate_site_results
from app.config import AUDIT_PIPELINE_CONFIG

logger = logging.getLogger(__name__)


PageAuditor = Callable[[str, str, PageContext], Awaitable[PageAuditResult]]
SSEEmitter = Callable[[dict[str, Any]], Awaitable[None] | None]


def _runner_config() -> dict[str, Any]:
    return AUDIT_PIPELINE_CONFIG["parallel_runner"]


def _mode_value(mapping: dict[str, Any], scan_mode: str) -> Any:
    mode_key = (scan_mode or "").lower()
    if mode_key not in mapping:
        mode_key = "fast"
    return mapping[mode_key]


async def _emit_event(event: dict[str, Any], events: list[dict[str, Any]], emitter: SSEEmitter | None) -> None:
    events.append(dict(event))
    if emitter is None:
        return

    maybe_awaitable = emitter(event)
    if hasattr(maybe_awaitable, "__await__"):
        await maybe_awaitable


def _minimal_failed_result(url: str, reason: str) -> PageAuditResult:
    return PageAuditResult(
        url=url,
        score=0.0,
        issues=[],
        engine_timings={},
        degraded_mode=True,
        degraded_reason=normalize_failure(reason).value,
        skipped_engines=["static", "interactive"],
        hydration_status="failed",
        enrichment_status="failed",
        states_meta=[],
        page_dom="",
    )


def _classify_degraded_reason(exc: Exception | str | None) -> str:
    return classify_failure_reason(exc)


def _clone_context_for_static(page_context: PageContext) -> PageContext:
    return PageContext(
        playwright_driver=page_context.playwright_driver,
        playwright_browser=page_context.playwright_browser,
        owns_browser=page_context.owns_browser,
        browser_factory=page_context.browser_factory,
        bm25_index=page_context.bm25_index,
        llm_semaphore=page_context.llm_semaphore,
        cache=page_context.cache,
        state_provider=page_context.state_provider,
        static_engine=page_context.static_engine,
        interactive_engine=None,
        axe_engine=None,
        cognitive_engine=None,
    )


async def _default_static_only_auditor(url: str, scan_mode: str, page_context: PageContext) -> PageAuditResult:
    static_context = _clone_context_for_static(page_context)
    return await audit_page(url, "fast", static_context)


async def _audit_with_two_stage_fallback(
    url: str,
    scan_mode: str,
    page_context: PageContext,
    page_auditor: PageAuditor,
    static_only_auditor: PageAuditor,
    page_timeout_stage1_seconds: float,
    page_timeout_stage2_seconds: float,
) -> PageAuditResult:
    stage1_reason = "unknown"
    try:
        return await asyncio.wait_for(
            page_auditor(url, scan_mode, page_context),
            timeout=page_timeout_stage1_seconds,
        )
    except Exception as exc:
        stage1_reason = _classify_degraded_reason(exc)
        try:
            degraded = await asyncio.wait_for(
                static_only_auditor(url, "fast", page_context),
                timeout=page_timeout_stage2_seconds,
            )
            degraded.degraded_mode = True
            if not getattr(degraded, "degraded_reason", ""):
                degraded.degraded_reason = normalize_failure(stage1_reason).value
            else:
                degraded.degraded_reason = normalize_failure(normalize_reason(degraded.degraded_reason) or stage1_reason).value
            skipped = set(degraded.skipped_engines)
            skipped.update(["interactive", "browser", "axe", "cognitive"])
            degraded.skipped_engines = sorted(skipped)
            return degraded
        except Exception as fallback_exc:
            fallback_reason = _classify_degraded_reason(fallback_exc)
            if stage1_reason == "render_timeout":
                return _minimal_failed_result(url, "render_timeout")
            return _minimal_failed_result(url, fallback_reason)


async def run_site_audit(
    urls: list[str],
    scan_mode: str,
    max_concurrent_pages: int | None = None,
    *,
    page_context: PageContext | None = None,
    page_auditor: PageAuditor | None = None,
    static_only_auditor: PageAuditor | None = None,
    sse_emitter: SSEEmitter | None = None,
    partial_summary_every_pages: int | None = None,
    page_timeout_stage1_seconds: float | None = None,
    page_timeout_stage2_seconds: float | None = None,
    global_sla_seconds: float | None = None,
) -> dict[str, Any]:
    """Run page audits in parallel with bounded concurrency and SLA truncation support."""
    cfg = _runner_config()

    mode_concurrency_limit = int(_mode_value(cfg["concurrency_by_mode"], scan_mode))
    concurrency = int(
        max_concurrent_pages
        if max_concurrent_pages is not None
        else mode_concurrency_limit
    )
    concurrency = max(1, min(concurrency, mode_concurrency_limit))

    stage1_timeout = float(
        page_timeout_stage1_seconds
        if page_timeout_stage1_seconds is not None
        else _mode_value(cfg["page_timeout_stage1_seconds"], scan_mode)
    )
    stage2_timeout = float(
        page_timeout_stage2_seconds
        if page_timeout_stage2_seconds is not None
        else _mode_value(cfg["page_timeout_stage2_seconds"], scan_mode)
    )
    global_sla = float(
        global_sla_seconds
        if global_sla_seconds is not None
        else _mode_value(cfg["global_sla_seconds"], scan_mode)
    )

    partial_every = int(
        partial_summary_every_pages
        if partial_summary_every_pages is not None
        else int(cfg["partial_summary_every_pages"])
    )
    partial_every = max(1, partial_every)
    event_buffer_max = int(cfg.get("event_buffer_max", 1000))
    event_buffer_max = max(10, event_buffer_max)

    context = page_context or PageContext()
    created_context = page_context is None
    run_page_auditor = page_auditor or audit_page
    run_static_only = static_only_auditor or _default_static_only_auditor

    semaphore = asyncio.Semaphore(max(1, concurrency))
    pages_total = len(urls)
    pages_completed = 0

    completed_results: list[PageAuditResult] = []
    events: deque[dict[str, Any]] = deque(maxlen=event_buffer_max)
    lock = asyncio.Lock()
    sla_truncated = False
    event_sequence = 0
    in_flight = 0
    max_in_flight = 0

    queue_maxsize = max(10, concurrency * 4)
    queue: asyncio.Queue[object] = asyncio.Queue(maxsize=queue_maxsize)
    _STOP = object()

    async def _emit_ordered_event(event: dict[str, Any]) -> None:
        nonlocal event_sequence
        event_sequence += 1
        payload = dict(event)
        payload["sequence"] = event_sequence
        await _emit_event(payload, events, sse_emitter)

    async def _record_completion(result: PageAuditResult) -> None:
        nonlocal pages_completed
        completed_results.append(result)
        pages_completed += 1

        await _emit_ordered_event(
            {
                "type": "page_complete",
                "url": result.url,
                "score": result.score,
                "issues_found": len(result.issues),
                "degraded_mode": result.degraded_mode,
                "degraded_reason": normalize_failure(getattr(result, "degraded_reason", "")).value if getattr(result, "degraded_reason", "") else "",
                "pages_done": pages_completed,
                "pages_total": pages_total,
            }
        )

        if pages_completed % partial_every != 0:
            return

        partial_site = aggregate_site_results(completed_results, scan_mode)
        top_issue = ""
        if partial_site.priority_ranking:
            top_issue = str(partial_site.priority_ranking[0].get("rule_id", ""))

        await _emit_ordered_event(
            {
                "type": "partial_summary",
                "pages_completed": pages_completed,
                "pages_total": pages_total,
                "current_score": partial_site.site_score,
                "top_issue": top_issue,
                "sla_truncated": False,
            }
        )

    async def _producer() -> None:
        for url in urls:
            await queue.put(url)
        for _ in range(concurrency):
            await queue.put(_STOP)

    async def _worker() -> None:
        nonlocal in_flight, max_in_flight

        while True:
            item = await queue.get()
            if item is _STOP:
                queue.task_done()
                break

            url = str(item)

            async with lock:
                in_flight += 1
                max_in_flight = max(max_in_flight, in_flight)

            try:
                async with semaphore:
                    result = await _audit_with_two_stage_fallback(
                        url=url,
                        scan_mode=scan_mode,
                        page_context=context,
                        page_auditor=run_page_auditor,
                        static_only_auditor=run_static_only,
                        page_timeout_stage1_seconds=stage1_timeout,
                        page_timeout_stage2_seconds=stage2_timeout,
                    )
            finally:
                async with lock:
                    in_flight = max(0, in_flight - 1)

            async with lock:
                await _record_completion(result)

            queue.task_done()

    async def _run_pipeline() -> None:
        producer_task = asyncio.create_task(_producer())
        worker_tasks = [asyncio.create_task(_worker()) for _ in range(concurrency)]
        try:
            await producer_task
            await queue.join()
            await asyncio.gather(*worker_tasks)
        except asyncio.CancelledError:
            producer_task.cancel()
            for task in worker_tasks:
                task.cancel()
            await asyncio.gather(producer_task, *worker_tasks, return_exceptions=True)
            raise
        except Exception:
            producer_task.cancel()
            for task in worker_tasks:
                task.cancel()
            await asyncio.gather(producer_task, *worker_tasks, return_exceptions=True)
            raise

    pipeline_task = asyncio.create_task(_run_pipeline())
    try:
        await asyncio.wait_for(pipeline_task, timeout=global_sla)
    except asyncio.TimeoutError:
        sla_truncated = True
        pipeline_task.cancel()
        await asyncio.gather(pipeline_task, return_exceptions=True)

        partial_site = aggregate_site_results(completed_results, scan_mode)
        top_issue = ""
        if partial_site.priority_ranking:
            top_issue = str(partial_site.priority_ranking[0].get("rule_id", ""))

        async with lock:
            await _emit_ordered_event(
            {
                "type": "partial_summary",
                "pages_completed": pages_completed,
                "pages_total": pages_total,
                "current_score": partial_site.site_score,
                "top_issue": top_issue,
                "sla_truncated": True,
            },
        )
    except Exception:
        pipeline_task.cancel()
        await asyncio.gather(pipeline_task, return_exceptions=True)
        raise

    site_result = aggregate_site_results(completed_results, scan_mode)
    degraded_pages = sum(1 for row in completed_results if row.degraded_mode)
    degraded_mode = degraded_pages > 0 or sla_truncated

    site_result_payload = asdict(site_result)
    site_result_payload["pages_audited"] = pages_completed
    site_result_payload["pages_discovered"] = pages_total
    site_result_payload["degraded_mode"] = degraded_mode
    site_result_payload["degraded_pages"] = degraded_pages
    site_result_payload["sla_truncated"] = sla_truncated

    degraded_reason_counts: dict[str, int] = {}
    for row in completed_results:
        if not row.degraded_mode:
            continue
        reason = (getattr(row, "degraded_reason", "") or "unknown").strip() or "unknown"
        degraded_reason_counts[reason] = degraded_reason_counts.get(reason, 0) + 1

    top_degraded_causes = [
        {"reason": reason, "count": count}
        for reason, count in sorted(degraded_reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:5]
    site_result_payload["top_degraded_causes"] = top_degraded_causes

    if pages_completed > 0:
        if int(site_result_payload.get("pages_audited") or 0) <= 0:
            logger.error("Invariant violation: site_result.pages_audited <= 0. Repairing with pages_completed.")
            site_result_payload["pages_audited"] = pages_completed

        if site_result_payload.get("issues") is None:
            logger.error("Invariant violation: site_result.issues is None. Repairing to empty list.")
            site_result_payload["issues"] = []

        score_value = float(site_result_payload.get("site_score") or 0.0)
        if score_value <= 0.0:
            logger.error("Invariant violation: site_result.site_score <= 0. Applying safe fallback.")
            if site_result_payload.get("issues"):
                fallback_score = max(15.0, round(sum(max(row.score, 15.0) for row in completed_results) / pages_completed, 1))
            else:
                fallback_score = 95.0
            site_result_payload["site_score"] = fallback_score

    if isinstance(site_result_payload.get("executive_summary"), dict):
        site_result_payload["executive_summary"]["pages_audited"] = pages_completed
        site_result_payload["executive_summary"]["pages_discovered"] = pages_total
        site_result_payload["executive_summary"]["degraded_mode"] = degraded_mode
        site_result_payload["executive_summary"]["sla_truncated"] = sla_truncated

    final_payload = {
        "scan_mode": scan_mode,
        "pages_total": pages_total,
        "pages_completed": pages_completed,
        "sla_truncated": sla_truncated,
        "degraded_mode": degraded_mode,
        "degraded_pages": degraded_pages,
        "top_degraded_causes": top_degraded_causes,
        "results": [asdict(result) for result in completed_results],
        "site_result": site_result_payload,
        "events": list(events),
        "runner_stats": {
            "worker_count": concurrency,
            "queue_maxsize": queue_maxsize,
            "max_in_flight": max_in_flight,
            "event_buffer_max": event_buffer_max,
        },
    }

    if created_context:
        await context.close()

    return final_payload
