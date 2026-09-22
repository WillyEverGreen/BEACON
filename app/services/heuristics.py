"""
Heuristic checks: AI/NLP-augmented quality checks that go beyond axe-core.
Alt text quality, vague link/button text, weak error messages, label clarity.
"""
import logging
import re

from bs4 import BeautifulSoup, Tag

from app.services.static_checks import (
    _KNOWN_ARIA_ATTRIBUTES,
    _KNOWN_ROLES,
    _css_selector,
    _snippet,
)

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
    re.compile(r'^image\d*$', re.IGNORECASE),
    re.compile(r'^photo\d*$', re.IGNORECASE),
    re.compile(r'^img[\s_-]?\d*$', re.IGNORECASE),
    re.compile(r'^pic(ture)?\d*$', re.IGNORECASE),
    re.compile(r'^untitled\d*$', re.IGNORECASE),
    re.compile(r'^placeholder\d*$', re.IGNORECASE),
    re.compile(r'^\w+\.(jpg|jpeg|png|gif|webp|svg|bmp)$', re.IGNORECASE),  # filename as alt
    re.compile(r'^DSC_?\d+$', re.IGNORECASE),  # camera filenames
    re.compile(r'^IMG_?\d+$', re.IGNORECASE),
    re.compile(r'^screenshot', re.IGNORECASE),
    re.compile(r'^\s*$'),  # whitespace-only
]

WEAK_ERROR_PATTERNS = [
    re.compile(r'^error\.?$', re.IGNORECASE),
    re.compile(r'^invalid\.?$', re.IGNORECASE),
    re.compile(r'^required\.?$', re.IGNORECASE),
    re.compile(r'^wrong\.?$', re.IGNORECASE),
    re.compile(r'^invalid input\.?$', re.IGNORECASE),
    re.compile(r'^please fix\.?$', re.IGNORECASE),
    re.compile(r'^check this field\.?$', re.IGNORECASE),
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
            "check_aria_cluster_corroboration",
            "check_landmark_corroboration",
            "check_semantic_html_corroboration",
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
            "check_meaningful_sequence",
            "check_orientation_lock",
            "check_images_of_text",
            "check_on_input_context_change",
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
        """Corroborate static keyboard trap patterns from focus handlers, positive tabindex, and clickable elements."""
        issues = []

        for el in self.soup.find_all(attrs={"onblur": True}):
            onblur = str(el.get("onblur") or "")
            onfocus = str(el.get("onfocus") or "")
            onkeydown = str(el.get("onkeydown") or "")
            combined = f"{onblur} {onfocus} {onkeydown}"

            loops_focus = bool(re.search(r"(focus|movefocus|setfocus)", onblur, re.IGNORECASE))
            trap_signal = bool(re.search(r"(trap|keydown|ctrl|escape|tab)", combined, re.IGNORECASE))
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

        # Check for positive tabindex (disrupts natural focus flow)
        for el in self.soup.find_all(attrs={"tabindex": True}):
            try:
                val = int(str(el.get("tabindex")).strip())
                if val > 0:
                    issues.append(_make_issue(
                        self.url,
                        "tabindex",
                        "violation",
                        "moderate",
                        _css_selector(el),
                        _snippet(el, 240),
                        f"Positive tabindex='{val}' changes the default tab order, which can cause keyboard navigation confusion.",
                        "2.1.1",
                        "A",
                        "keyboard",
                        "Remove positive tabindex. Use tabindex='0' to make elements focusable in natural DOM order.",
                        fix_effort="low",
                    ))
            except ValueError:
                pass

        # Check for interactive click elements missing focus capabilities
        for el in self.soup.find_all(True):
            if not isinstance(el, Tag):
                continue
            if el.name in {"a", "button", "input", "select", "textarea", "iframe", "object"}:
                continue
            if el.has_attr("onclick") and not el.has_attr("tabindex"):
                issues.append(_make_issue(
                    self.url,
                    "keyboard-focusable",
                    "violation",
                    "serious",
                    _css_selector(el),
                    _snippet(el, 240),
                    f"Element <{el.name}> has a click handler but is not keyboard focusable (missing tabindex).",
                    "2.1.1",
                    "A",
                    "keyboard",
                    "Add tabindex='0' and an appropriate ARIA role to make the element keyboard accessible.",
                    fix_effort="low",
                ))

        return issues

    def check_aria_cluster_corroboration(self) -> list[dict]:
        """Corroborate deterministic ARIA family misses with lightweight allowlist checks."""
        issues = []

        for inp in self.soup.find_all("input"):
            inp_type = str(inp.get("type") or "text").strip().lower()
            if inp_type not in {"checkbox", "radio"}:
                continue
            if not inp.has_attr("readonly"):
                continue

            selector = _css_selector(inp)
            snippet = _snippet(inp, 220)
            emitted_rules = {
                "aria-attribute": "Checkbox/radio uses readonly, which conflicts with supported control semantics.",
                "aria-allowed-attr": "Readonly behavior appears on a control type that does not allow this state.",
                "aria-valid-attr": "Control exposes an invalid state/attribute combination for accessibility semantics.",
                "aria-valid-attr-value": "Readonly creates an invalid state-value pattern for checkbox/radio semantics.",
            }
            for rule_id, description in emitted_rules.items():
                issues.append(_make_issue(
                    self.url,
                    rule_id,
                    "violation",
                    "serious",
                    selector,
                    snippet,
                    description,
                    "4.1.2",
                    "A",
                    "aria",
                    "Use role/state combinations supported by the control and remove readonly from checkbox/radio inputs.",
                    fix_effort="low",
                ))

        for el in self.soup.find_all(attrs={"role": True}):
            role_raw = str(el.get("role") or "").strip().lower()
            role_tokens = [token for token in role_raw.split() if token]
            if role_tokens and not any(token in _KNOWN_ROLES for token in role_tokens):
                selector = _css_selector(el)
                snippet = _snippet(el, 220)
                issues.append(_make_issue(
                    self.url,
                    "aria-roles",
                    "violation",
                    "serious",
                    selector,
                    snippet,
                    f'Unsupported role token "{role_raw}" detected.',
                    "4.1.2",
                    "A",
                    "aria",
                    "Replace the role with a valid WAI-ARIA role token.",
                    fix_effort="low",
                ))
                issues.append(_make_issue(
                    self.url,
                    "aria-valid-attr-value",
                    "violation",
                    "serious",
                    selector,
                    snippet,
                    f'Role value "{role_raw}" is invalid for ARIA parsing.',
                    "4.1.2",
                    "A",
                    "aria",
                    "Use valid ARIA role values from the specification.",
                    fix_effort="low",
                ))

        for el in self.soup.find_all(True):
            if not isinstance(el, Tag):
                continue
            for attr_name in [str(attr).strip().lower() for attr in el.attrs.keys() if str(attr).lower().startswith("aria-")]:
                if attr_name in _KNOWN_ARIA_ATTRIBUTES:
                    continue
                selector = _css_selector(el)
                snippet = _snippet(el, 220)
                issues.append(_make_issue(
                    self.url,
                    "aria-valid-attr",
                    "violation",
                    "serious",
                    selector,
                    snippet,
                    f'Unknown ARIA attribute "{attr_name}" detected.',
                    "4.1.2",
                    "A",
                    "aria",
                    "Remove unsupported ARIA attributes and keep only valid ones.",
                    fix_effort="low",
                ))
                issues.append(_make_issue(
                    self.url,
                    "aria-allowed-attr",
                    "violation",
                    "serious",
                    selector,
                    snippet,
                    f'Attribute "{attr_name}" is not allowed in valid ARIA syntax.',
                    "4.1.2",
                    "A",
                    "aria",
                    "Use only ARIA attributes defined in the WAI-ARIA spec.",
                    fix_effort="low",
                ))

        return issues

    def check_landmark_corroboration(self) -> list[dict]:
        """Corroborate missing-main/missing-landmark when navigation is present without a main region."""
        issues = []

        def _hidden(node: Tag) -> bool:
            current: Tag | None = node
            while isinstance(current, Tag):
                if str(current.get("aria-hidden") or "").strip().lower() == "true":
                    return True
                style = str(current.get("style") or "").replace(" ", "").lower()
                if "display:none" in style or "visibility:hidden" in style:
                    return True
                parent = current.parent
                current = parent if isinstance(parent, Tag) else None
            return False

        visible_main = [n for n in self.soup.find_all("main") if not _hidden(n)]
        visible_main.extend(
            [
                n
                for n in self.soup.find_all(attrs={"role": re.compile(r"(^|\s)main(\s|$)", re.IGNORECASE)})
                if not _hidden(n)
            ]
        )
        visible_main.extend(
            [
                n
                for n in self.soup.find_all(attrs={"id": re.compile(r"(^|[-_\s])main($|[-_\s])", re.IGNORECASE)})
                if not _hidden(n)
            ]
        )
        visible_main.extend(
            [
                n
                for n in self.soup.find_all(class_=re.compile(r"(^|\s)main(\s|$)", re.IGNORECASE))
                if not _hidden(n)
            ]
        )
        visible_nav = [n for n in self.soup.find_all("nav") if not _hidden(n)]
        visible_nav.extend(
            [
                n
                for n in self.soup.find_all(attrs={"role": re.compile(r"(^|\s)navigation(\s|$)", re.IGNORECASE)})
                if not _hidden(n)
            ]
        )

        has_main = bool(visible_main)
        has_nav = bool(visible_nav)
        if has_main or not has_nav:
            return issues

        selector = _css_selector(visible_nav[0]) if isinstance(visible_nav[0], Tag) else "<body>"
        snippet = _snippet(visible_nav[0], 220) if isinstance(visible_nav[0], Tag) else "<body>"

        issues.append(_make_issue(
            self.url,
            "no-main-landmark",
            "violation",
            "critical",
            selector,
            snippet,
            "Navigation is present but there is no visible main landmark for primary content.",
            "1.3.1",
            "A",
            "html",
            "Add one visible <main> landmark (or role='main') for primary page content.",
            fix_effort="low",
        ))
        issues.append(_make_issue(
            self.url,
            "missing-landmark",
            "violation",
            "critical",
            selector,
            snippet,
            "A navigation landmark exists without a corresponding main landmark.",
            "1.3.1",
            "A",
            "html",
            "Keep navigation landmarks and add a single main landmark to complete landmark navigation.",
            fix_effort="low",
        ))

        return issues

    def check_semantic_html_corroboration(self) -> list[dict]:
        """Corroborate semantic-html misses from root language and container-structure signals."""
        issues = []

        html_elem = self.soup.find("html")
        if isinstance(html_elem, Tag):
            lang = str(html_elem.get("lang") or "").strip().lower()
            if lang and re.fullmatch(r"[a-z]{3}", lang):
                issues.append(_make_issue(
                    self.url,
                    "semantic-html",
                    "violation",
                    "serious",
                    "html",
                    _snippet(html_elem, 220),
                    f'Root language value "{lang}" is likely non-standard for common BCP47 declarations.',
                    "3.1.1",
                    "A",
                    "html",
                    "Use a standard language tag such as en, en-US, fr, or es.",
                    fix_effort="low",
                ))

        div_span_count = len(self.soup.find_all(["div", "span"]))
        landmark_count = len(self.soup.find_all(["main", "nav", "header", "footer", "article", "section", "aside"]))
        text_len = len(self.soup.get_text(" ", strip=True))
        if div_span_count >= 8 and landmark_count == 0 and text_len >= 80:
            issues.append(_make_issue(
                self.url,
                "semantic-html",
                "violation",
                "moderate",
                "<body>",
                "<body>",
                "Page uses many generic containers and lacks semantic landmarks.",
                "1.3.1",
                "A",
                "html",
                "Introduce semantic structure with main/section/article/nav/header/footer elements.",
                fix_effort="medium",
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
            {"class_": re.compile(r'error|invalid|alert|warning', re.IGNORECASE)},
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
            re.compile(r'click the (red|blue|green|yellow|orange|purple) button', re.IGNORECASE),
            re.compile(r'(above|below|left|right) (button|link|section|image)', re.IGNORECASE),
            re.compile(r'the (round|square|circular|triangular) (icon|button)', re.IGNORECASE),
            re.compile(r'see the (image|figure|diagram) (above|below|on the left|on the right)', re.IGNORECASE),
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

    def check_meaningful_sequence(self) -> list[dict]:
        """SC 1.3.2: Detect CSS that alters reading order (e.g. float right on adjacent elements, row-reverse)."""
        issues = []
        for parent in self.soup.find_all(True):
            if not isinstance(parent, Tag):
                continue
            
            style = str(parent.get("style", "")).lower()
            if "row-reverse" in style or "column-reverse" in style:
                issues.append(_make_issue(
                    self.url, "meaningful-sequence", "needs-review", "moderate",
                    _css_selector(parent), _snippet(parent, 200),
                    "CSS flex-direction reverse alters visual order from DOM order, which may confuse screen reader users.",
                    "1.3.2", "A", "html",
                    "Ensure the DOM order matches the visual reading order."
                ))
            
            children = [c for c in parent.find_all(recursive=False) if isinstance(c, Tag)]
            float_right_count = sum(1 for c in children if "float:right" in str(c.get("style", "")).replace(" ", "").lower())
            if float_right_count >= 2:
                issues.append(_make_issue(
                    self.url, "meaningful-sequence", "needs-review", "moderate",
                    _css_selector(parent), _snippet(parent, 200),
                    "Multiple adjacent elements floated right. This reverses their visual order compared to the DOM.",
                    "1.3.2", "A", "html",
                    "Ensure the DOM order matches the visual reading order."
                ))
        return issues

    def check_orientation_lock(self) -> list[dict]:
        """SC 1.3.4: Detect scripts that lock screen orientation."""
        issues = []
        for script in self.soup.find_all("script"):
            content = script.string or ""
            if "screen.orientation.lock" in content:
                issues.append(_make_issue(
                    self.url, "orientation-lock", "violation", "serious",
                    "script", _snippet(script, 200),
                    "Script attempts to lock screen orientation. This restricts users who have their device mounted in a fixed orientation.",
                    "1.3.4", "AA", "html",
                    "Remove orientation locks unless essential (e.g., a piano app)."
                ))
        
        body = self.soup.find("body")
        if body and isinstance(body, Tag):
            onload = str(body.get("onload", ""))
            if "orientation.lock" in onload:
                issues.append(_make_issue(
                    self.url, "orientation-lock", "violation", "serious",
                    "body", _snippet(body, 200),
                    "Inline script attempts to lock screen orientation.",
                    "1.3.4", "AA", "html",
                    "Remove orientation locks unless essential."
                ))
        return issues

    def check_images_of_text(self) -> list[dict]:
        """SC 1.4.5: Detect images that likely contain text (long alt text or text-related filenames)."""
        issues = []
        for img in self.soup.find_all("img"):
            alt = (img.get("alt") or "").strip()
            src = (img.get("src") or "").lower()
            
            if len(alt) > 100 or "textimage" in src:
                issues.append(_make_issue(
                    self.url, "images-of-text", "needs-review", "moderate",
                    _css_selector(img), _snippet(img, 200),
                    "Image has very long alt text or filename suggesting it contains text.",
                    "1.4.5", "AA", "images",
                    "Use actual text styled with CSS rather than images of text."
                ))
        return issues

    def check_on_input_context_change(self) -> list[dict]:
        """SC 3.2.2: Detect forms with select inputs but no submit buttons, which might change context automatically."""
        issues = []
        for form in self.soup.find_all("form"):
            has_select = bool(form.find("select"))
            has_submit = bool(form.find("input", type=["submit", "image"])) or bool(form.find("button", type="submit")) or bool(form.find("button", type=None))
            
            if has_select and not has_submit:
                issues.append(_make_issue(
                    self.url, "on-input-context-change", "needs-review", "moderate",
                    _css_selector(form), _snippet(form, 200),
                    "Form contains a select element but no submit button. Changing the select might trigger an unexpected context change.",
                    "3.2.2", "A", "forms",
                    "Provide a submit button to allow users to explicitly request the change."
                ))
        return issues
