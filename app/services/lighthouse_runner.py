"""
app/services/lighthouse_runner.py

Single responsibility: take a URL, invoke the Lighthouse CLI via subprocess,
return raw parsed JSON. No mapping, no merging, no business logic.

Also manages:
  - Per-URL timeout (LIGHTHOUSE_PER_URL_TIMEOUT_SECONDS)
  - Controlled concurrency via asyncio.Semaphore (LIGHTHOUSE_MAX_CONCURRENT_RUNS)
  - In-process result cache with TTL (LIGHTHOUSE_CACHE_TTL_SECONDS)
  - 1 retry for network_unreachable and lighthouse_parse_error only
  - Chrome launch failure detection → batch abort signal (ChromeLaunchError)

All operational constants come from app.config. Nothing is hardcoded here.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from typing import Any

from app.config import (
    LIGHTHOUSE_CACHE_TTL_SECONDS,
    LIGHTHOUSE_MAX_CONCURRENT_RUNS,
    LIGHTHOUSE_PER_URL_TIMEOUT_SECONDS,
    LIGHTHOUSE_RETRY_COUNT,
    LIGHTHOUSE_RETRY_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)

# ── Concurrency semaphore ──────────────────────────────────────────────────────
# Prevents more than 2 simultaneous Chrome instances (OOM protection on lean VPS).
_LH_SEMAPHORE = asyncio.Semaphore(LIGHTHOUSE_MAX_CONCURRENT_RUNS)

# ── In-process result cache ────────────────────────────────────────────────────
# Key: hash(url + lighthouse_version + mapping_version)
# Value: (result_dict, stored_at_timestamp)
_LH_CACHE: dict[str, tuple[dict[str, Any], float]] = {}


class ChromeLaunchError(RuntimeError):
    """Raised when Chromium fails to start. Signals batch abort — do not retry."""


class LighthouseRunError(Exception):
    """Raised for per-URL failures that may be retried (parse errors, network)."""

    def __init__(self, message: str, failure_reason: str) -> None:
        super().__init__(message)
        self.failure_reason = failure_reason


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _cache_key(url: str, lighthouse_version: str, mapping_version: str) -> str:
    """Compute deterministic cache key. Includes mapping_version so stale entries
    are auto-invalidated when the mapping file is bumped."""
    raw = f"{url}|{lighthouse_version}|{mapping_version}"
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()


def _cache_get(key: str) -> dict[str, Any] | None:
    """Return cached result if it exists and is within TTL. None otherwise."""
    entry = _LH_CACHE.get(key)
    if entry is None:
        return None
    result, stored_at = entry
    if (time.monotonic() - stored_at) > LIGHTHOUSE_CACHE_TTL_SECONDS:
        _LH_CACHE.pop(key, None)
        return None
    return result


def _cache_set(key: str, result: dict[str, Any]) -> None:
    _LH_CACHE[key] = (result, time.monotonic())


def clear_lighthouse_cache() -> int:
    """Clear the full in-process Lighthouse cache. Returns number of entries removed."""
    count = len(_LH_CACHE)
    _LH_CACHE.clear()
    return count


# ── Core runner ───────────────────────────────────────────────────────────────

async def _invoke_lighthouse_cli(url: str) -> dict[str, Any]:
    """Run the Lighthouse CLI against a single URL and return parsed JSON output.

    Raises:
        ChromeLaunchError: If Chromium cannot start (batch abort signal).
        LighthouseRunError: For parse errors or network failures (per-URL, may retry).
        asyncio.TimeoutError: If per-URL timeout is exceeded (caller handles).
    """
    import os
    cmd_name = "lighthouse.cmd" if os.name == "nt" else "lighthouse"
    cmd = [
        cmd_name,
        url,
        "--output=json",
        "--quiet",
        "--chrome-flags=--headless --no-sandbox --disable-gpu",
        "--only-categories=performance,accessibility,seo,best-practices",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        raise ChromeLaunchError(
            "Lighthouse CLI not found. Ensure 'npm install -g lighthouse' has been run."
        )
    except OSError as exc:
        raise ChromeLaunchError(f"Failed to launch Lighthouse process: {exc}") from exc

    stdout, stderr = await proc.communicate()

    # Detect Chrome/Chromium launch failure from stderr output.
    stderr_text = (stderr or b"").decode("utf-8", errors="ignore")
    if proc.returncode != 0:
        stderr_lower = stderr_text.lower()
        is_chrome_failure = any(
            token in stderr_lower
            for token in (
                "chrome not found",
                "chromium not found",
                "cannot find chrome",
                "failed to launch",
                "chrome_not_found",
                "chromium_not_found",
                "no chrome",
            )
        )
        if is_chrome_failure:
            raise ChromeLaunchError(
                f"Chrome/Chromium launch failed. returncode={proc.returncode}. "
                f"stderr={stderr_text[:300]}"
            )

        # Non-zero exit without chrome failure → parse/network error, may retry.
        raise LighthouseRunError(
            f"Lighthouse CLI exited {proc.returncode}. stderr={stderr_text[:300]}",
            failure_reason="lighthouse_parse_error",
        )

    raw = (stdout or b"").decode("utf-8", errors="ignore").strip()
    if not raw:
        raise LighthouseRunError(
            "Lighthouse produced empty stdout output.",
            failure_reason="lighthouse_parse_error",
        )

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LighthouseRunError(
            f"Failed to parse Lighthouse JSON output: {exc}",
            failure_reason="lighthouse_parse_error",
        ) from exc


async def run_lighthouse_for_url(
    url: str,
    *,
    lighthouse_version: str = "10.x",
    mapping_version: str = "v1",
) -> dict[str, Any]:
    """Run Lighthouse for one URL. Cache-aware, timeout-bounded, retry-capable.

    Returns a dict with keys:
        url, cache_hit, raw_report (the full Lighthouse JSON or None on failure),
        failure_reason (None on success), duration_seconds.

    Raises:
        ChromeLaunchError: If Chrome cannot start — caller should abort the batch.

    Per-URL failures (network_unreachable, lighthouse_parse_error) are caught
    here after retries and returned as failure_reason in the result dict.
    """
    key = _cache_key(url, lighthouse_version, mapping_version)
    cached = _cache_get(key)
    if cached is not None:
        logger.debug("lighthouse_runner cache_hit url=%s", url)
        return {**cached, "cache_hit": True}

    # Retryable failure reasons — Chrome launch failure is NOT retryable.
    retryable = {"network_unreachable", "lighthouse_parse_error"}

    last_failure_reason: str = "unknown"
    attempts = 0
    max_attempts = 1 + max(0, int(LIGHTHOUSE_RETRY_COUNT))

    while attempts < max_attempts:
        attempts += 1
        t0 = time.monotonic()
        try:
            async with _LH_SEMAPHORE:
                raw_report = await asyncio.wait_for(
                    _invoke_lighthouse_cli(url),
                    timeout=float(LIGHTHOUSE_PER_URL_TIMEOUT_SECONDS),
                )

            duration = round(time.monotonic() - t0, 2)
            result = {
                "url": url,
                "cache_hit": False,
                "raw_report": raw_report,
                "failure_reason": None,
                "duration_seconds": duration,
                "attempts": attempts,
            }
            _cache_set(key, result)
            logger.info(
                "lighthouse_runner success url=%s duration=%.1fs attempt=%d",
                url, duration, attempts,
            )
            return result

        except asyncio.TimeoutError:
            duration = round(time.monotonic() - t0, 2)
            logger.warning(
                "lighthouse_runner url_timeout url=%s timeout=%ds attempt=%d",
                url, LIGHTHOUSE_PER_URL_TIMEOUT_SECONDS, attempts,
            )
            # url_timeout is NOT retryable — already consumed the full timeout budget.
            return {
                "url": url,
                "cache_hit": False,
                "raw_report": None,
                "failure_reason": "url_timeout",
                "duration_seconds": duration,
                "attempts": attempts,
            }

        except ChromeLaunchError:
            # Infrastructure failure — propagate immediately, caller aborts batch.
            raise

        except LighthouseRunError as exc:
            duration = round(time.monotonic() - t0, 2)
            last_failure_reason = exc.failure_reason

            if last_failure_reason in retryable and attempts < max_attempts:
                logger.warning(
                    "lighthouse_runner retrying url=%s reason=%s attempt=%d delay=%ds",
                    url, last_failure_reason, attempts, LIGHTHOUSE_RETRY_DELAY_SECONDS,
                )
                await asyncio.sleep(LIGHTHOUSE_RETRY_DELAY_SECONDS)
                continue

            logger.warning(
                "lighthouse_runner failure url=%s reason=%s attempt=%d",
                url, last_failure_reason, attempts,
            )
            return {
                "url": url,
                "cache_hit": False,
                "raw_report": None,
                "failure_reason": last_failure_reason,
                "duration_seconds": duration,
                "attempts": attempts,
            }

        except Exception as exc:
            duration = round(time.monotonic() - t0, 2)
            logger.error(
                "lighthouse_runner unexpected_error url=%s error=%s attempt=%d",
                url, exc, attempts,
            )
            return {
                "url": url,
                "cache_hit": False,
                "raw_report": None,
                "failure_reason": "lighthouse_parse_error",
                "duration_seconds": duration,
                "attempts": attempts,
            }

    # Exhausted all attempts.
    return {
        "url": url,
        "cache_hit": False,
        "raw_report": None,
        "failure_reason": last_failure_reason,
        "duration_seconds": 0.0,
        "attempts": attempts,
    }
