"""URL validation helpers with SSRF protections."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

_ALLOWED_SCHEMES = {"http", "https"}
_MAX_URL_LENGTH = 2048

_BLOCKED_RANGES = (
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("224.0.0.0/4"),
    ipaddress.ip_network("240.0.0.0/4"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)

_BLOCKED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "instance-data",
    "169.254.169.254",
}

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


class URLValidationError(ValueError):
    """Raised when a URL violates validation or SSRF rules."""


def sanitize_url(raw_url: str) -> str:
    """Trim and strip control characters from a URL string."""
    cleaned = "".join(ch for ch in str(raw_url or "").strip() if ord(ch) >= 32)
    return cleaned


def _resolved_ip_addresses(hostname: str) -> list[IPAddress]:
    addresses: list[IPAddress] = []
    seen: set[str] = set()

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise URLValidationError(f"Cannot resolve hostname: {hostname}") from exc

    for info in infos:
        addr = info[4][0]
        if addr in seen:
            continue
        seen.add(addr)
        try:
            addresses.append(ipaddress.ip_address(addr))
        except ValueError:
            continue

    if not addresses:
        raise URLValidationError(f"Cannot resolve hostname: {hostname}")

    return addresses


def _ip_is_blocked(ip: IPAddress) -> bool:
    if any(ip in network for network in _BLOCKED_RANGES):
        return True

    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_public_url(url: str) -> str:
    """Validate URL format and block private/internal destinations.

    Returns the sanitized URL when valid.
    """
    cleaned = sanitize_url(url)

    if not cleaned:
        raise URLValidationError("URL is required")
    if len(cleaned) > _MAX_URL_LENGTH:
        raise URLValidationError("URL exceeds maximum length")

    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise URLValidationError("Only http/https URLs are allowed")

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise URLValidationError("URL has no hostname")
    if hostname in _BLOCKED_HOSTNAMES:
        raise URLValidationError(f"Hostname {hostname} is blocked")
    if hostname.endswith(".internal") or hostname.endswith(".local"):
        raise URLValidationError("Internal hostnames are blocked")

    try:
        literal_ip = ipaddress.ip_address(hostname)
        addresses = [literal_ip]
    except ValueError:
        addresses = _resolved_ip_addresses(hostname)

    for resolved in addresses:
        if _ip_is_blocked(resolved):
            raise URLValidationError(f"IP {resolved} is blocked")

    return cleaned
