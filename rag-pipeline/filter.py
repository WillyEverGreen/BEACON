# filter.py
import re

REQUIRED_TERMS = [
    "success criterion","wcag","aria","accessibility",
    "role=","alt=","aria-label","screen reader",
    "keyboard","focus","contrast","cognitive",
    "perceivable","operable","understandable","robust",
    "technique","failure","sufficient","advisory",
    "axe","violation","impact","heading","landmark",
    "caption","transcript","skip navigation","tab order",
    "target size","color alone","reflow","zoom","lang attribute",
    "autocomplete","fieldset","legend","aria-live","aria-expanded",
    "aria-describedby","prefers-reduced-motion","focus visible"
]

NOISE_PATTERNS = [
    r"^\s*(changelog|release notes|version \d)",
    r"copyright \d{4}",
    r"subscribe to our newsletter",
    r"^\s*menu\s*$",
    r"^\s*skip to (main )?content\s*$",
]

SAFE_SILOS = {"wcag", "aria", "coga", "axe", "toolkit"}

def passes_filter(chunk: dict) -> bool:
    if chunk.get("silo") in SAFE_SILOS:
        return True

    text = chunk["text"].lower()

    for pat in NOISE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return False

    if len(text.split()) < 20:
        return False

    return any(term in text for term in REQUIRED_TERMS)
