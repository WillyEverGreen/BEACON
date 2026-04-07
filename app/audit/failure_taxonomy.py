"""Shared failure reason taxonomy and helpers for resilient audit flows."""

from __future__ import annotations

from typing import Any

STANDARD_DEGRADED_REASONS = {
    "dom_parse_error",
    "render_timeout",
    "extraction_failure",
    "network_error",
    "dns_failure",
    "blocked_request",
}


def classify_failure_reason(exc: Exception | str | None) -> str:
    """Map arbitrary exception text to one of the standard degraded reason codes."""
    text = str(exc or "").strip().lower()
    if not text:
        return "extraction_failure"

    blocked_tokens = (
        "access denied",
        "forbidden",
        "captcha",
        "security check",
        "are you a robot",
        "bot protection",
        "blocked by client",
        "blocked request",
        "cloudflare",
        "status code 403",
        "status code 429",
        "http status 403",
        "http status 429",
    )
    if any(token in text for token in blocked_tokens):
        return "blocked_request"

    dns_tokens = (
        "dns",
        "getaddrinfo",
        "name not resolved",
        "name resolution",
        "temporary failure in name resolution",
        "nodename nor servname",
        "nxdomain",
        "eai_again",
        "servfail",
    )
    if any(token in text for token in dns_tokens):
        return "dns_failure"

    timeout_tokens = (
        "timeout",
        "timed out",
        "navigation timeout",
        "target closed",
    )
    if any(token in text for token in timeout_tokens):
        return "render_timeout"

    network_tokens = (
        "econn",
        "connection reset",
        "connection aborted",
        "connection refused",
        "remote protocol error",
        "server disconnected",
        "connection",
        "net::",
        "transient",
        "http_status_5",
        "http status 5",
        "503",
        "504",
        "proxy",
        "certificate",
        "ssl",
        "tls",
        "socket",
        "network",
        "unreachable",
    )
    if any(token in text for token in network_tokens):
        return "network_error"

    parse_tokens = (
        "parse",
        "parser",
        "beautifulsoup",
        "lxml",
        "dom",
        "html",
        "malformed",
    )
    if any(token in text for token in parse_tokens):
        return "dom_parse_error"

    extraction_tokens = (
        "content",
        "snapshot",
        "evaluate",
        "selector",
        "execution context",
        "detached",
        "frame",
        "script",
    )
    if any(token in text for token in extraction_tokens):
        return "extraction_failure"

    return "extraction_failure"


def normalize_reason(reason: Any) -> str:
    """Normalize legacy or unknown reason strings into the standard taxonomy."""
    text = str(reason or "").strip().lower()
    if not text:
        return ""

    legacy_map = {
        "browser_timeout": "render_timeout",
        "script_failure": "extraction_failure",
        "unknown": "extraction_failure",
        "dns_error": "dns_failure",
        "name_resolution_failed": "dns_failure",
        "blocked": "blocked_request",
        "access_denied": "blocked_request",
        "cloudflare_block": "blocked_request",
    }
    if text in legacy_map:
        return legacy_map[text]
    if text in STANDARD_DEGRADED_REASONS:
        return text

    return classify_failure_reason(text)


def reason_message(reason_code: str, detail: str | None = None) -> str:
    """Return user-readable message for a standard degraded reason."""
    normalized = normalize_reason(reason_code) or "extraction_failure"
    messages = {
        "dom_parse_error": "Rendered DOM could not be parsed reliably; scan continued with partial extraction.",
        "render_timeout": "Rendering exceeded timeout budget; scan continued from the latest available DOM snapshot.",
        "extraction_failure": "DOM extraction encountered runtime failures; scan continued with partial coverage.",
        "network_error": "Network fetch or navigation failed; scan continued with fallback content where available.",
        "dns_failure": "DNS resolution failed while fetching the target page; scan continued with fallback content where available.",
        "blocked_request": "Target site blocked automated requests; scan continued with fallback content where available.",
    }
    base = messages.get(normalized, messages["extraction_failure"])
    if detail:
        return f"{base} ({detail})"
    return base
