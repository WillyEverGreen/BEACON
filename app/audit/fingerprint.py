"""Stable fingerprint helpers for selectors and issue deduplication."""

from __future__ import annotations

import re

_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _looks_dynamic_token(token: str) -> bool:
    lowered = (token or "").strip().lower()
    if not lowered:
        return False

    if _UUID_PATTERN.match(lowered):
        return True

    if re.match(r"^(css|sc|jss|jsx|emotion)-[a-z0-9]{6,}$", lowered):
        return True

    if re.match(r"^[a-f0-9]{10,}$", lowered):
        return True

    if len(lowered) >= 10 and re.search(r"[a-z]", lowered) and re.search(r"\d", lowered):
        return True

    if lowered.endswith("-"):
        return True

    return False


def _normalize_attr_selector(match: re.Match[str]) -> str:
    attr_name = match.group(1).lower()
    raw_value = (match.group(2) or "").strip().strip('"\'')

    if attr_name in {"id", "class"} and _looks_dynamic_token(raw_value):
        return f"[{attr_name}=__dynamic__]"

    return f"[{attr_name}={raw_value.lower()}]"


def stable_selector_fingerprint(selector: str) -> str:
    """Normalize selector syntax so fingerprints are resilient to unstable tokens."""
    raw = (selector or "").strip().lower()
    if not raw:
        return ""

    # Pre-strip Tailwind JIT escaped brackets (e.g. -\\[...\\] or -\\[...)
    raw = re.sub(r"\\[^\s.#>+~]*\[[^\]]*\]", "", raw)
    raw = re.sub(r"\\[^\s.#>+~]*", "", raw)

    normalized = re.sub(r":nth-(?:child|of-type)\(\s*\d+\s*\)", "", raw)
    normalized = re.sub(r"\[(id|class)=['\"]?([^'\"\]]+)['\"]?\]", _normalize_attr_selector, normalized)

    normalized = re.sub(
        r"#([a-z0-9_-]+)",
        lambda m: "#__stable_id__" if _looks_dynamic_token(m.group(1)) else f"#{m.group(1)}",
        normalized,
    )

    normalized = re.sub(
        r"\.([a-z0-9_-]+)",
        lambda m: "" if _looks_dynamic_token(m.group(1)) else f".{m.group(1)}",
        normalized,
    )

    normalized = re.sub(r"\s*([>+~])\s*", r" \1 ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    normalized = re.sub(r"\s+\.", " .", normalized)
    normalized = re.sub(r"\s+#", " #", normalized)

    return normalized
