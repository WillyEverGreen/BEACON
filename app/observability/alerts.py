"""Alert evaluation and webhook dispatch for operational anomalies."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from curl_cffi import AsyncSession

from app.config import settings
from app.observability.telemetry import (
    get_alert_snapshot,
    get_llm_failure_count,
    record_llm_failure,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _post_alert(payload: dict[str, Any]) -> bool:
    webhook = str(getattr(settings, "alert_webhook_url", "") or "").strip()
    if not webhook:
        return False

    try:
        async with AsyncSession(impersonate="chrome", timeout=10.0) as client:
            response = await client.post(webhook, json=payload)
        return int(response.status_code) < 400
    except Exception as exc:
        logger.warning("Failed to send alert webhook: %s", exc)
        return False


async def evaluate_audit_alerts(event: dict[str, Any]) -> list[dict[str, Any]]:
    """Evaluate timeout/fallback/long-running thresholds and dispatch alerts."""
    triggered: list[dict[str, Any]] = []

    scan_seconds = float(event.get("scan_time_seconds") or 0.0)
    if scan_seconds > float(getattr(settings, "long_running_audit_seconds", 180.0)):
        triggered.append(
            {
                "type": "long_running_audit",
                "timestamp": _now_iso(),
                "threshold_seconds": float(getattr(settings, "long_running_audit_seconds", 180.0)),
                "scan_time_seconds": scan_seconds,
                "audit_id": event.get("audit_id", ""),
                "url": event.get("url", ""),
                "scan_mode": event.get("scan_mode", "fast"),
            }
        )

    snapshot = get_alert_snapshot()

    timeout_threshold = float(getattr(settings, "timeout_spike_threshold", 0.02))
    if snapshot["timeout_rate"] > timeout_threshold:
        triggered.append(
            {
                "type": "timeout_spike",
                "timestamp": _now_iso(),
                "threshold": timeout_threshold,
                "observed": snapshot["timeout_rate"],
            }
        )

    fallback_threshold = float(getattr(settings, "enrichment_fallback_spike_threshold", 0.10))
    if snapshot["enrichment_fallback_rate"] > fallback_threshold:
        triggered.append(
            {
                "type": "enrichment_fallback_spike",
                "timestamp": _now_iso(),
                "threshold": fallback_threshold,
                "observed": snapshot["enrichment_fallback_rate"],
            }
        )

    for payload in triggered:
        payload["source"] = "beacon"
        await _post_alert(payload)

    return triggered


async def trigger_test_alert() -> dict[str, Any]:
    """Send a manual test alert payload to validate webhook plumbing."""
    payload = {
        "type": "manual_test_alert",
        "timestamp": _now_iso(),
        "source": "beacon",
        "message": "Manual alert triggered by admin endpoint.",
    }
    sent = await _post_alert(payload)
    return {"sent": sent, "payload": payload}


def notify_llm_failure(reason: str) -> None:
    """Record an LLM failure and trigger burst alerts when threshold is exceeded."""
    record_llm_failure(reason)

    burst_window = int(getattr(settings, "llm_failure_burst_window_seconds", 300) or 300)
    burst_count = int(getattr(settings, "llm_failure_burst_count", 3) or 3)
    failures = get_llm_failure_count(burst_window)

    if failures < burst_count:
        return

    payload = {
        "type": "llm_failure_burst",
        "timestamp": _now_iso(),
        "source": "beacon",
        "threshold_count": burst_count,
        "window_seconds": burst_window,
        "observed": failures,
        "reason": str(reason or "unknown"),
    }

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_post_alert(payload))
    except RuntimeError:
        # No running loop (e.g. sync context); silently skip async webhook.
        pass
