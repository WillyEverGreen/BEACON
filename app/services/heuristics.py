"""
Heuristic checks: AI/NLP-augmented quality checks that go beyond axe-core.
Alt text quality, vague link/button text, weak error messages, label clarity.
"""
import logging
import re
from typing import Optional
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


# ── Patterns for vague/generic text ─────────────────────────────

VAGUE_LINK_PATTERNS = {
    "click here", "read more", "more", "here", "link", "learn more",
    "details", "click", "this", "go", "see more", "view more",
    "continue", "continue reading", "find out more", "see details",
}

VAGUE_BUTTON_PATTERNS = {
    "submit", "go", "ok", "click", "press", "button", "send",
    "done", "next", "back", "yes", "no",
}

GENERIC_ALT_PATTERNS = [
    re.compile(r'^image\d*$', re.I),
    re.compile(r'^photo\d*$', re.I),
    re.compile(r'^img[\s_-]?\d*$', re.I),
    re.compile(r'^pic(ture)?\d*$', re.I),
    re.compile(r'^untitled\d*$', re.I),
    re.compile(r'^placeholder\d*$', re.I),
    re.compile(r'^\w+\.(jpg|jpeg|png|gif|webp|svg|bmp)$', re.I),  # filename as alt
    re.compile(r'^DSC_?\d+$', re.I),  # camera filenames
    re.compile(r'^IMG_?\d+$', re.I),
    re.compile(r'^screenshot', re.I),
    re.compile(r'^\s*$'),  # whitespace-only
]

WEAK_ERROR_PATTERNS = [
    re.compile(r'^error\.?$', re.I),
    re.compile(r'^invalid\.?$', re.I),
    re.compile(r'^required\.?$', re.I),
    re.compile(r'^wrong\.?$', re.I),
    re.compile(r'^invalid input\.?$', re.I),
    re.compile(r'^please fix\.?$', re.I),
    re.compile(r'^check this field\.?$', re.I),
]


def _make_issue(url, rule_id, issue_type, severity, element, html_snippet,
                description, wcag_criterion, wcag_level, category,
                suggested_fix, fix_effort="medium"):
    import hashlib
    issue_id = hashlib.sha256(f"{url}|{element}|{rule_id}".encode()).hexdigest()[:16]
    return {
        "issue_id": issue_id,
        "rule_id": rule_id,
        "issue_type": issue_type,
        "element": element,
        "html_snippet": html_snippet[:500],
        "page_url": url,
        "severity": severity,
        "wcag_criterion": wcag_criterion,
        "wcag_level": wcag_level,
        "category": category,
        "confidence": 0.5,  # Heuristic checks have lower base confidence
        "confidence_sources": ["heuristic"],
        "needs_manual_review": True,
        "description": description,
        "suggested_fix": suggested_fix,
        "code_fix": "",
        "fix_effort": fix_effort,
        "group_id": "",
        "domain": "",
        "evidence": {},
        "reproducibility": "",
    }


class HeuristicAnalyzer:
    """AI/NLP-augmented heuristic checks for accessibility quality."""

    def __init__(self, html: str, url: str):
        self.soup = BeautifulSoup(html, "lxml")
        self.url = url

    def run_all(self) -> list[dict]:
        """Run all heuristic checks."""
        issues = []
        for method_name in [
            "check_alt_quality",
            "check_vague_links",
            "check_vague_buttons",
            "check_weak_error_messages",
            "check_label_clarity",
            "check_sensory_language",
        ]:
            try:
                method = getattr(self, method_name)
                issues.extend(method())
            except Exception as e:
                logger.warning(f"Heuristic '{method_name}' failed: {e}")
        return issues

    def check_alt_quality(self) -> list[dict]:
        """Check for poor-quality alt text (generic, filename-based, etc.)."""
        issues = []
        for img in self.soup.find_all("img"):
            alt = img.get("alt")
            if alt is None or alt == "":
                continue  # Handled by static checks

            alt_stripped = alt.strip()
            src = img.get("src", "")

            # Check against generic patterns
            for pattern in GENERIC_ALT_PATTERNS:
                if pattern.match(alt_stripped):
                    selector = img.name
                    if img.get("id"):
                        selector += f"#{img['id']}"

                    issues.append(_make_issue(
                        self.url, "alt-quality", "needs-review", "moderate",
                        selector, str(img)[:500],
                        f'Alt text "{alt_stripped}" appears generic or auto-generated. Provide meaningful description.',
                        "1.1.1", "A", "images",
                        "Write alt text describing the image content and purpose, not just the filename."
                    ))
                    break

            # Alt same as src filename
            if alt_stripped and src:
                src_filename = src.split("/")[-1].split("?")[0]
                if alt_stripped.lower() == src_filename.lower():
                    issues.append(_make_issue(
                        self.url, "alt-is-filename", "needs-review", "moderate",
                        img.name, str(img)[:500],
                        f'Alt text is the filename "{alt_stripped}". Provide descriptive alt text.',
                        "1.1.1", "A", "images",
                        "Describe the content and function of the image, not its filename."
                    ))

            # Excessively long alt text (> 150 chars suggests it should be longdesc)
            if len(alt_stripped) > 150:
                issues.append(_make_issue(
                    self.url, "alt-too-long", "needs-review", "minor",
                    img.name, str(img)[:500],
                    f"Alt text is {len(alt_stripped)} characters. Consider using a shorter alt with a long description.",
                    "1.1.1", "A", "images",
                    "Keep alt concise. For complex images, use a short alt and provide detail in surrounding text."
                ))

        return issues

    def check_vague_links(self) -> list[dict]:
        """Detect links with vague or non-descriptive text."""
        issues = []
        for link in self.soup.find_all("a"):
            text = link.get_text(strip=True).lower()
            if text in VAGUE_LINK_PATTERNS:
                # Already caught by static checks but with higher confidence NLP context
                continue  # Let static handle exact matches

            # Partial matches and context analysis
            if text and len(text) < 4 and text not in ("faq", "api", "rss", "pdf"):
                issues.append(_make_issue(
                    self.url, "short-link-text", "needs-review", "minor",
                    "a", str(link)[:500],
                    f'Link text "{text}" is very short and may not be descriptive enough.',
                    "2.4.4", "A", "navigation",
                    "Use descriptive link text that explains the link destination."
                ))

        return issues

    def check_vague_buttons(self) -> list[dict]:
        """Detect buttons with vague or unhelpful text."""
        issues = []
        for btn in self.soup.find_all("button"):
            text = btn.get_text(strip=True).lower()
            aria = btn.get("aria-label", "").lower()
            effective_text = aria or text

            if effective_text in VAGUE_BUTTON_PATTERNS:
                issues.append(_make_issue(
                    self.url, "vague-button-text", "needs-review", "moderate",
                    "button", str(btn)[:500],
                    f'Button text "{effective_text}" is vague. Users may not understand its purpose.',
                    "4.1.2", "A", "forms",
                    'Use specific text like "Submit application", "Save changes", "Delete item".'
                ))

        return issues

    def check_weak_error_messages(self) -> list[dict]:
        """Detect weak/generic error messages."""
        issues = []
        error_selectors = [
            {"class_": re.compile(r'error|invalid|alert|warning', re.I)},
            {"role": "alert"},
        ]
        for selector in error_selectors:
            for elem in self.soup.find_all(**selector):
                text = elem.get_text(strip=True)
                if not text:
                    continue
                for pattern in WEAK_ERROR_PATTERNS:
                    if pattern.match(text):
                        issues.append(_make_issue(
                            self.url, "weak-error-message", "needs-review", "moderate",
                            elem.name, str(elem)[:500],
                            f'Error message "{text}" is too generic. Users need specific guidance to fix the issue.',
                            "3.3.1", "A", "forms",
                            'Provide specific error messages like "Email address must include @" or "Password must be at least 8 characters".'
                        ))
                        break

        return issues

    def check_label_clarity(self) -> list[dict]:
        """Check if form labels are descriptive enough."""
        issues = []
        vague_labels = {"field", "input", "enter value", "type here", "data", "field1", "field2", "info"}

        for label in self.soup.find_all("label"):
            text = label.get_text(strip=True).lower()
            if text in vague_labels:
                issues.append(_make_issue(
                    self.url, "vague-label", "needs-review", "moderate",
                    "label", str(label)[:500],
                    f'Label text "{text}" is not descriptive. Users cannot understand what to enter.',
                    "2.4.6", "AA", "forms",
                    "Use specific labels: 'Email address', 'First name', 'Phone number'."
                ))

        return issues

    def check_sensory_language(self) -> list[dict]:
        """Check for instructions relying on sensory characteristics."""
        issues = []
        sensory_patterns = [
            re.compile(r'click the (red|blue|green|yellow|orange|purple) button', re.I),
            re.compile(r'(above|below|left|right) (button|link|section|image)', re.I),
            re.compile(r'the (round|square|circular|triangular) (icon|button)', re.I),
            re.compile(r'see the (image|figure|diagram) (above|below|on the left|on the right)', re.I),
        ]

        body = self.soup.find("body")
        if body:
            text = body.get_text()
            for pattern in sensory_patterns:
                matches = pattern.findall(text)
                if matches:
                    issues.append(_make_issue(
                        self.url, "sensory-language", "needs-review", "moderate",
                        "<body>", text[:200],
                        "Content may rely on sensory characteristics (shape, color, location) for instructions.",
                        "1.3.3", "A", "content",
                        "Supplement visual/spatial references with text labels or descriptions."
                    ))
                    break  # One warning per page

        return issues
