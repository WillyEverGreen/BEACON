"""
Content filter module — removes noise and low-quality chunks from the pipeline.

Uses a two-stage approach:
1. Whitelist: Chunks from trusted silos (wcag, aria, coga, axe, toolkit) pass automatically
2. Quality check: Other chunks must contain accessibility-relevant terms
   and must not match known noise patterns (changelogs, copyright, etc.)
"""
import re

# ── Accessibility term whitelist ──────────────────────────────
# Chunks must contain at least one of these terms to be considered relevant
REQUIRED_TERMS: list[str] = [
    "success criterion", "wcag", "aria", "accessibility",
    "role=", "alt=", "aria-label", "screen reader",
    "keyboard", "focus", "contrast", "cognitive",
    "perceivable", "operable", "understandable", "robust",
    "technique", "failure", "sufficient", "advisory",
    "axe", "violation", "impact", "heading", "landmark",
    "caption", "transcript", "skip navigation", "tab order",
    "target size", "color alone", "reflow", "zoom", "lang attribute",
    "autocomplete", "fieldset", "legend", "aria-live", "aria-expanded",
    "aria-describedby", "prefers-reduced-motion", "focus visible"
]

# ── Noise patterns ────────────────────────────────────────────
# Chunks matching these patterns are discarded
NOISE_PATTERNS: list[str] = [
    r"^\s*(changelog|release notes|version \d)",
    r"copyright \d{4}",
    r"subscribe to our newsletter",
    r"^\s*menu\s*$",
    r"^\s*skip to (main )?content\s*$",
]

# ── Trusted source silos ──────────────────────────────────────
SAFE_SILOS: set[str] = {"wcag", "aria", "coga", "axe", "toolkit"}

# ── Minimum word count ────────────────────────────────────────
MIN_WORD_COUNT: int = 20


def passes_filter(chunk: dict) -> bool:
    """
    Determine if a chunk should be kept in the pipeline.
    
    Args:
        chunk: Dict with 'text' and optional 'silo' keys
    
    Returns:
        True if the chunk should be kept, False to discard
    """
    # Trusted silos always pass
    if chunk.get("silo") in SAFE_SILOS:
        return True

    text: str = chunk["text"].lower()

    # Reject noise patterns
    for pat in NOISE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return False

    # Reject very short content
    if len(text.split()) < MIN_WORD_COUNT:
        return False

    # Must contain at least one accessibility-relevant term
    return any(term in text for term in REQUIRED_TERMS)
