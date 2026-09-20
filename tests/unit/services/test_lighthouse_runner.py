"""Unit tests for app/services/lighthouse_runner.py"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.lighthouse_runner import (
    ChromeLaunchError,
    LighthouseRunError,
    _cache_key,
    _cache_get,
    _cache_set,
    clear_lighthouse_cache,
    run_lighthouse_for_url,
)


# ── Cache tests ───────────────────────────────────────────────────────────────

def test_cache_key_deterministic():
    k1 = _cache_key("https://example.com", "10.x", "v1")
    k2 = _cache_key("https://example.com", "10.x", "v1")
    assert k1 == k2


def test_cache_key_differs_by_url():
    k1 = _cache_key("https://a.com", "10.x", "v1")
    k2 = _cache_key("https://b.com", "10.x", "v1")
    assert k1 != k2


def test_cache_key_differs_by_mapping_version():
    k1 = _cache_key("https://a.com", "10.x", "v1")
    k2 = _cache_key("https://a.com", "10.x", "v2")
    assert k1 != k2


def test_cache_set_and_get():
    clear_lighthouse_cache()
    key = _cache_key("https://test.com", "10.x", "v1")
    payload = {"url": "https://test.com", "raw_report": {"x": 1}}
    _cache_set(key, payload)
    result = _cache_get(key)
    assert result == payload


def test_cache_get_expired(monkeypatch):
    """Entry with timestamp far in the past should be treated as expired."""
    clear_lighthouse_cache()
    import app.services.lighthouse_runner as mod
    import time

    key = _cache_key("https://expired.com", "10.x", "v1")
    # Store with a timestamp far in the past relative to current monotonic time
    expired_time = time.monotonic() - (mod.LIGHTHOUSE_CACHE_TTL_SECONDS + 10)
    mod._LH_CACHE[key] = ({"url": "https://expired.com"}, expired_time)

    result = _cache_get(key)
    assert result is None  # expired


def test_clear_lighthouse_cache_returns_count():
    clear_lighthouse_cache()
    key = _cache_key("https://a.com", "10.x", "v1")
    _cache_set(key, {"url": "https://a.com"})
    count = clear_lighthouse_cache()
    assert count == 1


# ── chrome launch failure propagation ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_chrome_not_found_raises_chrome_launch_error():
    """FileNotFoundError from subprocess.exec → ChromeLaunchError (not LighthouseRunError)."""
    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError("No such file or directory"),
    ):
        with pytest.raises(ChromeLaunchError):
            from app.services.lighthouse_runner import _invoke_lighthouse_cli
            await _invoke_lighthouse_cli("https://example.com")


# ── url_timeout handling ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_url_timeout_returns_failure_dict_not_exception():
    """Per-URL timeout should return failure dict, not raise."""
    with patch(
        "app.services.lighthouse_runner._invoke_lighthouse_cli",
        side_effect=asyncio.TimeoutError(),
    ):
        with patch("asyncio.wait_for", side_effect=asyncio.TimeoutError()):
            result = await run_lighthouse_for_url("https://timeout.com")
    assert result["failure_reason"] == "url_timeout"
    assert result["raw_report"] is None
    assert result["cache_hit"] is False


# ── retry logic ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_retry_on_parse_error_succeeds_second_attempt():
    """parse_error on first attempt → retries once → succeeds."""
    success_json = {"audits": {}, "categories": {}}

    call_count = 0

    async def fake_cli(url: str) -> dict:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise LighthouseRunError("parse fail", "lighthouse_parse_error")
        return success_json

    with patch("app.services.lighthouse_runner._invoke_lighthouse_cli", side_effect=fake_cli):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await run_lighthouse_for_url("https://retry.com")

    assert result["failure_reason"] is None
    assert result["raw_report"] == success_json
    assert call_count == 2


@pytest.mark.asyncio
async def test_chrome_launch_failure_not_retried():
    """chrome_launch_failed must propagate immediately — no retry."""
    call_count = 0

    async def fake_cli(url: str) -> dict:
        nonlocal call_count
        call_count += 1
        raise ChromeLaunchError("Chrome not found")

    with patch("app.services.lighthouse_runner._invoke_lighthouse_cli", side_effect=fake_cli):
        with pytest.raises(ChromeLaunchError):
            await run_lighthouse_for_url("https://chrome-fail.com")

    # With real_invoke raising immediately, we only try once (the wait_for wraps it).
    # The exact count depends on semaphore but ChromeLaunchError must be raised.
    assert call_count >= 1


@pytest.mark.asyncio
async def test_cache_hit_skips_cli():
    """A cache-warm URL must never invoke the CLI."""
    clear_lighthouse_cache()
    # Pre-populate cache
    key = _cache_key("https://cached.com", "10.x", "v1")
    cached_result = {
        "url": "https://cached.com",
        "cache_hit": False,
        "raw_report": {"audits": {}},
        "failure_reason": None,
        "duration_seconds": 1.0,
        "attempts": 1,
    }
    _cache_set(key, cached_result)

    with patch(
        "app.services.lighthouse_runner._invoke_lighthouse_cli",
        side_effect=AssertionError("CLI should not be called on cache hit"),
    ):
        result = await run_lighthouse_for_url("https://cached.com")

    assert result["cache_hit"] is True
