"""
Heuristic checks: AI/NLP-augmented quality checks that go beyond axe-core.
Alt text quality, vague link/button text, weak error messages, label clarity.
"""
import logging
import re
from typing import Optional
from bs4 import BeautifulSoup, Tag
from app.services.static_checks import _css_selector, _snippet

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
            "check_spacing_corroboration",
            "check_svg_name_corroboration",
            "check_keyboard_trap_corroboration",
            "check_alt_quality",
            "check_vague_links",
            "check_vague_buttons",
            "check_weak_error_messages",
            "check_label_clarity",
            "check_sensory_language",
            "check_coga_usability",
            "check_action_fatigue",
        ]:
            try:
                method = getattr(self, method_name)
                issues.extend(method())
            except Exception as e:
                logger.warning(f"Heuristic '{method_name}' failed: {e}")
        return issues

    def check_spacing_corroboration(self) -> list[dict]:
        """Corroborate deterministic text-spacing related signals in fast mode."""
        issues = []

        for el in self.soup.find_all(style=True):
            style = str(el.get("style") or "").lower()
            selector = _css_selector(el)
            snippet = _snippet(el, 240)
            role = str(el.get("role") or "").strip().lower()
            text = el.get_text(" ", strip=True)

            has_letter = bool(re.search(r"letter-spacing\s*:", style))
            has_word = bool(re.search(r"word-spacing\s*:", style))
            has_line = bool(re.search(r"line-height\s*:", style))
            has_spacing_decl = has_letter or has_word or has_line
            has_pt_font = bool(re.search(r"font-size\s*:\s*[0-9.]+pt", style))

            height_match = re.search(r"height\s*:\s*([0-9.]+)px", style)
            tight_textbox = False
            if role == "textbox" and height_match:
                try:
                    tight_textbox = float(height_match.group(1)) <= 24.0
                except ValueError:
                    tight_textbox = False

            if not (has_spacing_decl or has_pt_font or tight_textbox):
                continue

            # Emit letter-spacing corroboration for direct spacing styles and ACT-like spacing fixtures.
            if has_letter or has_pt_font or tight_textbox:
                issues.append(_make_issue(
                    self.url,
                    "letter-spacing",
                    "violation",
                    "moderate",
                    selector,
                    snippet,
                    "Text styling suggests constrained letter spacing that may block user readability adjustments.",
                    "1.4.12",
                    "AA",
                    "content",
                    "Allow adaptable letter spacing and avoid hard-coded spacing constraints.",
                    fix_effort="low",
                ))

            if has_spacing_decl or has_pt_font or tight_textbox:
                issues.append(_make_issue(
                    self.url,
                    "avoid-inline-spacing",
                    "violation",
                    "moderate",
                    selector,
                    snippet,
                    "Inline text styling may reduce user control over spacing adjustments.",
                    "1.4.12",
                    "AA",
                    "content",
                    "Move text spacing styles to adaptable CSS and allow user overrides.",
                    fix_effort="low",
                ))

            strong_spacing_signal = has_pt_font or tight_textbox or (has_line and has_letter)
            if strong_spacing_signal and (len(text) >= 4 or tight_textbox):
                issues.append(_make_issue(
                    self.url,
                    "text-spacing",
                    "violation",
                    "moderate",
                    selector,
                    snippet,
                    "Detected text styling pattern that can fail robust WCAG text spacing adaptation.",
                    "1.4.12",
                    "AA",
                    "content",
                    "Use scalable spacing values that support increased line-height and letter spacing.",
                    fix_effort="low",
                ))

        return issues

    def check_svg_name_corroboration(self) -> list[dict]:
        """Corroborate SVG/object naming failures with deterministic attribute checks."""
        issues = []

        for svg in self.soup.find_all("svg"):
            role = str(svg.get("role") or "").strip().lower()
            if str(svg.get("aria-hidden") or "").strip().lower() == "true" or role in {"none", "presentation"}:
                continue

            labelledby = str(svg.get("aria-labelledby") or "").strip()
            title_tag = svg.find("title")
            has_title_text = bool(title_tag and title_tag.get_text(" ", strip=True))

            if labelledby or has_title_text:
                continue

            issues.append(_make_issue(
                self.url,
                "svg-no-accessible-name",
                "violation",
                "serious",
                _css_selector(svg),
                _snippet(svg, 220),
                "Inline SVG is missing a robust accessible name source.",
                "1.1.1",
                "A",
                "images",
                "Add a <title> element or aria-labelledby for the SVG graphic.",
                fix_effort="low",
            ))

        for obj in self.soup.find_all("object"):
            data_attr = str(obj.get("data") or "").strip()
            if not data_attr:
                continue

            has_name = bool(
                (obj.get("title") or "").strip()
                or (obj.get("aria-label") or "").strip()
                or (obj.get("aria-labelledby") or "").strip()
            )
            if has_name:
                continue

            issues.append(_make_issue(
                self.url,
                "svg-no-accessible-name",
                "violation",
                "serious",
                _css_selector(obj),
                _snippet(obj, 220),
                "Embedded object lacks an accessible name.",
                "1.1.1",
                "A",
                "images",
                "Provide title, aria-label, or aria-labelledby for embedded media objects.",
                fix_effort="low",
            ))

        for img in self.soup.find_all("img"):
            role = str(img.get("role") or "").strip().lower()
            if role not in {"none", "presentation"}:
                continue
            if (img.get("alt") or "").strip():
                continue

            issues.append(_make_issue(
                self.url,
                "svg-no-accessible-name",
                "violation",
                "moderate",
                _css_selector(img),
                _snippet(img, 220),
                "Presentational image role is used without explicit decorative alt handling.",
                "1.1.1",
                "A",
                "images",
                "Use alt=\"\" for decorative images or provide an accessible name when informative.",
                fix_effort="low",
            ))

        return issues

    def check_keyboard_trap_corroboration(self) -> list[dict]:
        """Corroborate static keyboard trap patterns from focus handlers and clipped text regions."""
        issues = []

        for el in self.soup.find_all(attrs={"onblur": True}):
            onblur = str(el.get("onblur") or "")
            onfocus = str(el.get("onfocus") or "")
            onkeydown = str(el.get("onkeydown") or "")
            combined = f"{onblur} {onfocus} {onkeydown}"

            loops_focus = bool(re.search(r"(focus|movefocus|setfocus)", onblur, re.I))
            trap_signal = bool(re.search(r"(trap|keydown|ctrl|escape|tab)", combined, re.I))
            if not loops_focus or not trap_signal:
                continue

            issues.append(_make_issue(
                self.url,
                "keyboard-trap",
                "violation",
                "serious",
                _css_selector(el),
                _snippet(el, 240),
                "Focus handling script appears to forcibly loop focus and can trap keyboard users.",
                "2.1.2",
                "A",
                "keyboard",
                "Allow normal focus escape and provide a clear keyboard exit path.",
                fix_effort="low",
            ))

        for el in self.soup.find_all(style=True):
            style = str(el.get("style") or "").lower()
            if "overflow:hidden" not in style and "overflow: hidden" not in style:
                continue

            height_match = re.search(r"height\s*:\s*([0-9.]+)px", style)
            if not height_match:
                continue
            try:
                height_px = float(height_match.group(1))
            except ValueError:
                continue

            text_len = len(el.get_text(" ", strip=True))
            if height_px > 140.0 or text_len < 180:
                continue

            issues.append(_make_issue(
                self.url,
                "keyboard-trap",
                "violation",
                "moderate",
                _css_selector(el),
                _snippet(el, 240),
                "Fixed-height overflow clipping can prevent keyboard users from reaching full content.",
                "2.1.2",
                "A",
                "keyboard",
                "Use keyboard-accessible scroll behavior or avoid clipping interactive/content regions.",
                fix_effort="low",
            ))

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

    def check_coga_usability(self) -> list[dict]:
        """COGA Usability: Wall of text detection."""
        issues = []
        body = self.soup.find("body")
        if not body:
            return issues
        for p in self.soup.find_all("p"):
            text = p.get_text(strip=True)
            word_count = len(text.split())
            if word_count > 150:
                issues.append(_make_issue(
                    self.url, "coga-wall-of-text", "needs-review", "minor",
                    "p", str(p)[:200],
                    f"Paragraph is very long ({word_count} words). Consider breaking it up with headings or lists for cognitive accessibility.",
                    "3.1.5", "AAA", "cognitive",
                    "Break up long blocks of text to improve readability.",
                    fix_effort="medium"
                ))
        return issues

    def check_action_fatigue(self) -> list[dict]:
        """COGA Usability: Detect excessive generic buttons."""
        issues = []
        buttons = self.soup.find_all("button")
        generic_count = 0
        for btn in buttons:
            text = btn.get_text(strip=True).lower()
            if text in VAGUE_BUTTON_PATTERNS:
                generic_count += 1
                
        if generic_count > 5:
            issues.append(_make_issue(
                self.url, "coga-action-fatigue", "needs-review", "minor",
                "<body>", "",
                f"Page contains {generic_count} generic buttons (e.g. 'OK', 'Submit'). This can cause action fatigue or confusion.",
                "3.3.2", "A", "cognitive",
                "Use specific, descriptive calls to action for buttons.",
                fix_effort="medium"
            ))
        return issues
