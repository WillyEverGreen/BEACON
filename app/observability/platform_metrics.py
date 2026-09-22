"""
Platform Observability & Production Reliability Metrics (§56, §57).

Tracks structured platform metrics:
- Counts: pages crawled, pages audited, scanner findings, adjudicated findings,
  suppressed findings, verified findings, review findings, root-cause clusters,
  retrieval misses, LLM failures, sandbox failures, browser probe failures, AT tests, visual tests.
- Latencies: crawl, DOM, scan, AI, visual, remediation, total (P50 and P95 percentiles).
- Production reliability circuit breakers and partial audit recovery helpers (§57).
"""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_LOCK = threading.RLock()


@dataclass
class PlatformMetricsStore:
    """Stores structured observability counters and latency measurements."""
    # Counters
    pages_crawled: int = 0
    pages_audited: int = 0
    scanner_findings: int = 0
    adjudicated_findings: int = 0
    suppressed_findings: int = 0
    verified_findings: int = 0
    review_findings: int = 0
    root_cause_clusters: int = 0
    retrieval_misses: int = 0
    llm_failures: int = 0
    sandbox_failures: int = 0
    browser_probe_failures: int = 0
    at_tests_run: int = 0
    visual_tests_run: int = 0

    # Latencies in milliseconds
    latencies: dict[str, list[float]] = field(default_factory=lambda: {
        "crawl": [],
        "dom": [],
        "scan": [],
        "ai": [],
        "visual": [],
        "remediation": [],
        "total": [],
    })

    def record_counter(self, metric_name: str, count: int = 1) -> None:
        """Increments a structured metric counter."""
        with _LOCK:
            if hasattr(self, metric_name):
                setattr(self, metric_name, getattr(self, metric_name) + count)

    def record_latency(self, stage: str, duration_ms: float) -> None:
        """Records a stage latency measurement."""
        with _LOCK:
            if stage in self.latencies:
                self.latencies[stage].append(max(0.0, float(duration_ms)))
                # Keep sliding window of 2000 measurements per stage
                if len(self.latencies[stage]) > 2000:
                    self.latencies[stage].pop(0)

    def compute_percentiles(self, stage: str) -> dict[str, float]:
        """Calculates P50 and P95 latency percentiles for a stage."""
        with _LOCK:
            values = self.latencies.get(stage, [])
            if not values:
                return {"p50": 0.0, "p95": 0.0, "count": 0}

            ordered = sorted(values)
            n = len(ordered)

            def get_p(p: float) -> float:
                if n == 1:
                    return ordered[0]
                rank = (n - 1) * p
                lower = math.floor(rank)
                upper = math.ceil(rank)
                if lower == upper:
                    return ordered[int(rank)]
                weight = rank - lower
                return ordered[lower] + (ordered[upper] - ordered[lower]) * weight

            return {
                "p50": round(get_p(0.50), 2),
                "p95": round(get_p(0.95), 2),
                "count": n,
            }

    def get_metrics_snapshot(self) -> dict[str, Any]:
        """Returns a complete structured snapshot of platform observability (§56)."""
        with _LOCK:
            latency_summary = {
                stage: self.compute_percentiles(stage)
                for stage in self.latencies.keys()
            }

            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "counters": {
                    "pages_crawled": self.pages_crawled,
                    "pages_audited": self.pages_audited,
                    "scanner_findings": self.scanner_findings,
                    "adjudicated_findings": self.adjudicated_findings,
                    "suppressed_findings": self.suppressed_findings,
                    "verified_findings": self.verified_findings,
                    "review_findings": self.review_findings,
                    "root_cause_clusters": self.root_cause_clusters,
                    "retrieval_misses": self.retrieval_misses,
                    "llm_failures": self.llm_failures,
                    "sandbox_failures": self.sandbox_failures,
                    "browser_probe_failures": self.browser_probe_failures,
                    "at_tests_run": self.at_tests_run,
                    "visual_tests_run": self.visual_tests_run,
                },
                "latencies_ms": latency_summary,
            }


# Singleton platform metrics instance
platform_metrics = PlatformMetricsStore()


# ── §57: Production Reliability Helpers ───────────────────────────────────────

class CircuitBreakerOpen(Exception):
    """Raised when an external service is temporarily tripped."""


class CircuitBreaker:
    """Guards external services (LLM, browser probes) with failure thresholds (§57)."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout_s: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def record_success(self) -> None:
        with _LOCK:
            self.failure_count = 0
            self.state = "CLOSED"

    def record_failure(self) -> None:
        import time
        with _LOCK:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = "OPEN"

    def can_execute(self) -> bool:
        import time
        with _LOCK:
            if self.state == "CLOSED":
                return True
            if self.state == "OPEN":
                now = time.time()
                if self.last_failure_time and (now - self.last_failure_time) >= self.recovery_timeout_s:
                    self.state = "HALF_OPEN"
                    return True
                return False
            return True  # HALF_OPEN allows a trial
