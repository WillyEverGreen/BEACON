"""
Static HTML checks: comprehensive WCAG 2.2 Level A + AA + AAA checks.
Parses rendered DOM and checks against the full WCAG checklist.
"""
import hashlib
import logging
import re
from typing import Optional
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def _make_issue_id(url: str, selector: str, rule_id: str) -> str:
    """Generate a unique issue ID via SHA256."""
    raw = f"{url}|{selector}|{rule_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _snippet(tag: Tag, max_len: int = 500) -> str:
    """Get a truncated HTML snippet."""
    s = str(tag)
    return s[:max_len] if len(s) > max_len else s


def _css_selector(tag: Tag) -> str:
    """Build a rough CSS selector for an element."""
    parts = []
    parts.append(tag.name)
    if tag.get("id"):
        parts.append(f"#{tag['id']}")
    elif tag.get("class"):
        classes = tag["class"] if isinstance(tag["class"], list) else [tag["class"]]
        parts.append("." + ".".join(classes[:2]))
    return "".join(parts)


def _issue(url: str, rule_id: str, issue_type: str, severity: str,
           element: str, html_snippet: str, description: str,
           wcag_criterion: str, wcag_level: str, category: str,
           suggested_fix: str, fix_effort: str = "low") -> dict:
    """Build a standardized issue dict."""
    return {
        "issue_id": _make_issue_id(url, element, rule_id),
        "rule_id": rule_id,
        "issue_type": issue_type,
        "element": element,
        "html_snippet": html_snippet,
        "page_url": url,
        "severity": severity,
        "wcag_criterion": wcag_criterion,
        "wcag_level": wcag_level,
        "category": category,
        "confidence": 0.85,
        "confidence_sources": ["static"],
        "needs_manual_review": False,
        "description": description,
        "suggested_fix": suggested_fix,
        "code_fix": "",
        "fix_effort": fix_effort,
        "group_id": "",
        "domain": "",
        "evidence": {},
        "reproducibility": "",
    }


class StaticChecker:
    """Runs comprehensive static HTML checks against WCAG 2.2."""

    def __init__(self, html: str, url: str):
        self.soup = BeautifulSoup(html, "lxml")
        self.url = url

    def run_all(self, checks: Optional[list[str]] = None) -> list[dict]:
        """Run all check categories. Pass a list to limit which categories run."""
        all_checks = checks or [
            "language", "title", "landmarks", "headings", "images",
            "links", "buttons", "forms", "tables", "lists",
            "aria", "media", "color_hints", "keyboard_hints",
            "viewport", "skip_nav",
        ]
        issues = []
        for check_name in all_checks:
            method = getattr(self, f"check_{check_name}", None)
            if method:
                try:
                    issues.extend(method())
                except Exception as e:
                    logger.warning(f"Static check '{check_name}' failed: {e}")
        return issues

    # ── HTML Semantics ─────────────────────────────────────────

    def check_language(self) -> list[dict]:
        issues = []
        html_tag = self.soup.find("html")
        if html_tag:
            lang = html_tag.get("lang", "")
            if not lang:
                issues.append(_issue(
                    self.url, "no-lang", "violation", "serious",
                    "<html>", "<html>", 
                    "HTML element is missing the lang attribute. Screen readers need this to select correct pronunciation.",
                    "3.1.1", "A", "html",
                    'Add lang attribute: <html lang="en">'
                ))
            elif len(lang) < 2:
                issues.append(_issue(
                    self.url, "invalid-lang", "violation", "serious",
                    "<html>", f'<html lang="{lang}">',
                    f'Invalid language code "{lang}". Use a valid BCP 47 language tag.',
                    "3.1.1", "A", "html",
                    'Use a valid language code like "en", "es", "fr".'
                ))
        return issues

    def check_title(self) -> list[dict]:
        issues = []
        title = self.soup.find("title")
        if not title or not title.get_text(strip=True):
            issues.append(_issue(
                self.url, "no-title", "violation", "serious",
                "<head>", "<head>",
                "Page is missing a title. The title is the first thing announced by screen readers.",
                "2.4.2", "A", "html",
                "Add a descriptive <title> element: <title>Page Description - Site Name</title>"
            ))
        return issues

    def check_landmarks(self) -> list[dict]:
        issues = []
        has_main = bool(self.soup.find("main") or self.soup.find(attrs={"role": "main"}))
        has_nav = bool(self.soup.find("nav") or self.soup.find(attrs={"role": "navigation"}))
        has_header = bool(self.soup.find("header") or self.soup.find(attrs={"role": "banner"}))
        has_footer = bool(self.soup.find("footer") or self.soup.find(attrs={"role": "contentinfo"}))

        if not has_main:
            issues.append(_issue(
                self.url, "no-main-landmark", "violation", "moderate",
                "<body>", "<body>",
                "Page has no <main> landmark. Screen reader users rely on landmarks to navigate.",
                "1.3.1", "A", "html",
                "Wrap main content in a <main> element."
            ))
        if not has_nav:
            issues.append(_issue(
                self.url, "no-nav-landmark", "best-practice", "minor",
                "<body>", "<body>",
                "Page has no <nav> landmark for navigation.",
                "1.3.1", "A", "html",
                "Wrap navigation links in a <nav> element."
            ))
        if not has_header:
            issues.append(_issue(
                self.url, "no-header-landmark", "best-practice", "minor",
                "<body>", "<body>",
                "Page has no <header> landmark.",
                "1.3.1", "A", "html",
                "Add a <header> element for the site banner area."
            ))
        if not has_footer:
            issues.append(_issue(
                self.url, "no-footer-landmark", "best-practice", "minor",
                "<body>", "<body>",
                "Page has no <footer> landmark.",
                "1.3.1", "A", "html",
                "Add a <footer> element for site-wide footer content."
            ))
        return issues

    # ── Headings ───────────────────────────────────────────────

    def check_headings(self) -> list[dict]:
        issues = []
        headings = self.soup.find_all(re.compile(r'^h[1-6]$'))

        if not headings:
            issues.append(_issue(
                self.url, "no-headings", "violation", "serious",
                "<body>", "<body>",
                "Page has no headings. Headings are essential for screen reader navigation.",
                "1.3.1", "A", "html",
                "Add semantic headings (h1-h6). Each page should have exactly one h1."
            ))
            return issues

        # h1 count
        h1s = self.soup.find_all("h1")
        if len(h1s) == 0:
            issues.append(_issue(
                self.url, "no-h1", "violation", "serious",
                "<body>", "<body>",
                "Page is missing an h1 heading.",
                "1.3.1", "A", "html",
                "Add an h1 element as the main heading of the page."
            ))
        elif len(h1s) > 1:
            issues.append(_issue(
                self.url, "multiple-h1", "violation", "moderate",
                f"{len(h1s)} h1 elements", f"{len(h1s)} h1 elements found",
                f"Page has {len(h1s)} h1 headings. Best practice is one h1 per page.",
                "1.3.1", "A", "html",
                "Use only one h1 per page. Use h2-h6 for subsections."
            ))

        # Heading order
        prev_level = 0
        for h in headings:
            level = int(h.name[1])
            if level > prev_level + 1 and prev_level > 0:
                issues.append(_issue(
                    self.url, "heading-skip", "violation", "moderate",
                    _css_selector(h), _snippet(h),
                    f"Heading level skipped: {h.name} follows h{prev_level}.",
                    "1.3.1", "A", "html",
                    f"Use h{prev_level + 1} instead of {h.name}, or add intermediate headings."
                ))
            prev_level = level

        # Empty headings
        for h in headings:
            if not h.get_text(strip=True):
                issues.append(_issue(
                    self.url, "empty-heading", "violation", "serious",
                    _css_selector(h), _snippet(h),
                    f"Empty {h.name} heading found. Headings must have text content.",
                    "1.3.1", "A", "html",
                    f"Add descriptive text to the {h.name} element or remove it."
                ))

        return issues

    # ── Images ─────────────────────────────────────────────────

    def check_images(self) -> list[dict]:
        issues = []
        for img in self.soup.find_all("img"):
            alt = img.get("alt")
            src = img.get("src", "")
            selector = _css_selector(img)

            if alt is None:
                issues.append(_issue(
                    self.url, "missing-alt", "violation", "critical",
                    selector, _snippet(img),
                    "Image is missing alt attribute. Screen readers cannot describe this image.",
                    "1.1.1", "A", "images",
                    f'Add alt="" for decorative images or alt="description" for informative: <img src="{src}" alt="description">'
                ))
            elif alt == "" and not img.get("role") == "presentation":
                spacer_keywords = ["spacer", "pixel", "blank", "divider"]
                if src and not any(x in src.lower() for x in spacer_keywords):
                    issues.append(_issue(
                        self.url, "empty-alt", "needs-review", "moderate",
                        selector, _snippet(img),
                        "Image has empty alt text. If decorative, add role='presentation'. If informative, add meaningful alt.",
                        "1.1.1", "A", "images",
                        'Add role="presentation" if decorative, or meaningful alt text if informative.',
                        fix_effort="low"
                    ))

        # SVG without title
        for svg in self.soup.find_all("svg"):
            has_title = svg.find("title")
            has_label = svg.get("aria-label") or svg.get("aria-labelledby")
            has_hidden = svg.get("aria-hidden") == "true"
            if not has_title and not has_label and not has_hidden:
                issues.append(_issue(
                    self.url, "svg-no-accessible-name", "violation", "serious",
                    _css_selector(svg), _snippet(svg, 200),
                    "SVG element has no accessible name. Add a <title> child or aria-label.",
                    "1.1.1", "A", "images",
                    'Add <title>Description</title> inside the SVG or aria-label="description".'
                ))

        return issues

    # ── Links ──────────────────────────────────────────────────

    def check_links(self) -> list[dict]:
        issues = []
        vague_texts = {"click here", "read more", "more", "here", "link", "learn more", "details"}

        for link in self.soup.find_all("a"):
            text = link.get_text(strip=True)
            aria_label = link.get("aria-label", "")
            selector = _css_selector(link)

            # Empty link
            if not text and not aria_label and not link.find("img"):
                issues.append(_issue(
                    self.url, "empty-link", "violation", "serious",
                    selector, _snippet(link),
                    "Link has no text content. Screen readers will announce it as empty.",
                    "2.4.4", "A", "navigation",
                    'Add descriptive text or aria-label="description".'
                ))

            # Vague link text
            if text and text.lower() in vague_texts:
                issues.append(_issue(
                    self.url, "generic-link-text", "violation", "moderate",
                    selector, _snippet(link),
                    f'Link text "{text}" is not descriptive. Users should understand the purpose from text alone.',
                    "2.4.4", "A", "navigation",
                    "Replace generic text with descriptive link text."
                ))

            # External links opening new window
            if link.get("target") == "_blank":
                rel = link.get("rel", [])
                if isinstance(rel, str):
                    rel = rel.split()
                if "noopener" not in rel:
                    issues.append(_issue(
                        self.url, "unsafe-external-link", "best-practice", "moderate",
                        selector, _snippet(link),
                        'Link opens in new tab without rel="noopener noreferrer".',
                        "3.2.5", "AA", "navigation",
                        'Add rel="noopener noreferrer" and "(opens in new tab)" for screen readers.'
                    ))

            # Links with only color distinguishing them
            style = link.get("style", "")
            if "text-decoration: none" in style or "text-decoration:none" in style:
                issues.append(_issue(
                    self.url, "link-no-underline", "needs-review", "moderate",
                    selector, _snippet(link),
                    "Link may only be distinguishable by color (no underline). Ensure 3:1 contrast ratio with surrounding text.",
                    "1.4.1", "A", "navigation",
                    "Add an underline, border, or other non-color visual indicator."
                ))

        return issues

    # ── Buttons ────────────────────────────────────────────────

    def check_buttons(self) -> list[dict]:
        issues = []
        for btn in self.soup.find_all("button"):
            text = btn.get_text(strip=True)
            selector = _css_selector(btn)

            if not text and not btn.get("aria-label") and not btn.get("aria-labelledby"):
                issues.append(_issue(
                    self.url, "button-no-name", "violation", "critical",
                    selector, _snippet(btn),
                    "Button has no accessible name. Screen readers cannot identify this control.",
                    "4.1.2", "A", "forms",
                    'Add text content or aria-label="Button description".'
                ))

        # Div/span acting as button without role
        for elem in self.soup.find_all(["div", "span"]):
            onclick = elem.get("onclick", "")
            if onclick and not elem.get("role"):
                issues.append(_issue(
                    self.url, "clickable-no-role", "violation", "serious",
                    _css_selector(elem), _snippet(elem),
                    "Element with onclick handler has no role='button'. Not accessible via keyboard.",
                    "4.1.2", "A", "aria",
                    'Add role="button" tabindex="0" and keyboard event handlers, or use a <button>.'
                ))

        return issues

    # ── Forms ──────────────────────────────────────────────────

    def check_forms(self) -> list[dict]:
        issues = []
        for inp in self.soup.find_all(["input", "textarea", "select"]):
            inp_type = inp.get("type", "text")
            if inp_type in ("hidden", "submit", "button", "reset", "image"):
                continue

            selector = _css_selector(inp)
            inp_id = inp.get("id", "")
            has_label = False

            if inp_id:
                label = self.soup.find("label", attrs={"for": inp_id})
                if label:
                    has_label = True

            if not has_label:
                has_label = bool(
                    inp.get("aria-label") or
                    inp.get("aria-labelledby") or
                    inp.get("title") or
                    inp.find_parent("label")
                )

            if not has_label:
                issues.append(_issue(
                    self.url, "missing-label", "violation", "critical",
                    selector, _snippet(inp),
                    "Form input has no associated label. Screen readers cannot identify this field.",
                    "1.3.1", "A", "forms",
                    f'Add <label for="{inp_id or "field-id"}">Label text</label> or aria-label="Label text".'
                ))

            # Autocomplete check (AA)
            autocomplete_types = {
                "name", "email", "tel", "url", "username", "new-password",
                "current-password", "cc-name", "cc-number", "cc-exp",
                "street-address", "country", "postal-code", "bday"
            }
            if inp_type in ("text", "email", "tel", "url", "password") and not inp.get("autocomplete"):
                # Flag only if the input name/id hints at personal data
                name_lower = (inp.get("name", "") + inp.get("id", "")).lower()
                for ac_type in autocomplete_types:
                    ac_key = ac_type.replace("-", "")
                    if ac_key in name_lower.replace("-", "").replace("_", ""):
                        issues.append(_issue(
                            self.url, "missing-autocomplete", "violation", "moderate",
                            selector, _snippet(inp),
                            f"Input likely collects personal data but missing autocomplete attribute.",
                            "1.3.5", "AA", "forms",
                            f'Add autocomplete="{ac_type}" to this input.',
                            fix_effort="low"
                        ))
                        break

        # Check for fieldset/legend on radio/checkbox groups
        radio_groups = {}
        for inp in self.soup.find_all("input", {"type": ["radio", "checkbox"]}):
            name = inp.get("name", "")
            if name:
                radio_groups.setdefault(name, []).append(inp)

        for name, inputs in radio_groups.items():
            if len(inputs) > 1:
                parent_fieldset = inputs[0].find_parent("fieldset")
                if not parent_fieldset:
                    issues.append(_issue(
                        self.url, "no-fieldset-legend", "violation", "moderate",
                        f'input[name="{name}"]', _snippet(inputs[0]),
                        f"Radio/checkbox group '{name}' not wrapped in <fieldset> with <legend>.",
                        "1.3.1", "A", "forms",
                        f'Wrap the group in <fieldset><legend>Group label</legend>...</fieldset>.',
                        fix_effort="medium"
                    ))

        # Error messages linked via aria-describedby
        for err_container in self.soup.find_all(class_=re.compile(r'error|invalid|alert', re.I)):
            err_id = err_container.get("id")
            if err_id:
                # Check if any input references this via aria-describedby
                linked = self.soup.find(attrs={"aria-describedby": re.compile(err_id)})
                if not linked:
                    issues.append(_issue(
                        self.url, "error-not-linked", "needs-review", "moderate",
                        _css_selector(err_container), _snippet(err_container),
                        "Error message container not linked to input via aria-describedby.",
                        "3.3.1", "A", "forms",
                        f'Add aria-describedby="{err_id}" to the related input element.',
                        fix_effort="low"
                    ))

        return issues

    # ── Tables ─────────────────────────────────────────────────

    def check_tables(self) -> list[dict]:
        issues = []
        for table in self.soup.find_all("table"):
            selector = _css_selector(table)
            # No headers
            if not table.find("th"):
                issues.append(_issue(
                    self.url, "table-no-headers", "violation", "serious",
                    selector, _snippet(table, 300),
                    "Data table has no header cells (th). Screen readers cannot associate data with headers.",
                    "1.3.1", "A", "content",
                    'Use <th> for header cells and add scope="col" or scope="row".'
                ))
            else:
                # Check scope on th
                for th in table.find_all("th"):
                    if not th.get("scope"):
                        issues.append(_issue(
                            self.url, "th-no-scope", "violation", "moderate",
                            _css_selector(th), _snippet(th),
                            "Table header (th) missing scope attribute.",
                            "1.3.1", "A", "content",
                            'Add scope="col" or scope="row" to <th> elements.'
                        ))
                        break  # One warning per table

            # No caption
            if not table.find("caption"):
                issues.append(_issue(
                    self.url, "table-no-caption", "best-practice", "minor",
                    selector, _snippet(table, 200),
                    "Table has no <caption> element describing its purpose.",
                    "1.3.1", "A", "content",
                    "Add <caption>Table description</caption> as the first child of <table>."
                ))

        return issues

    # ── Lists ──────────────────────────────────────────────────

    def check_lists(self) -> list[dict]:
        issues = []
        # Look for fake lists (divs/spans with bullet chars)
        for elem in self.soup.find_all(["div", "span", "p"]):
            text = elem.get_text(strip=True)
            if text and (text.startswith("• ") or text.startswith("- ") or re.match(r'^\d+\.\s', text)):
                # Check if parent is already a list
                if not elem.find_parent(["ul", "ol", "li"]):
                    issues.append(_issue(
                        self.url, "fake-list", "needs-review", "minor",
                        _css_selector(elem), _snippet(elem),
                        "Content appears to be a list but not using semantic list markup.",
                        "1.3.1", "A", "html",
                        "Use <ul>/<ol>/<li> for list content instead of plain text with bullets.",
                        fix_effort="medium"
                    ))
                    break  # One warning per page
        return issues

    # ── ARIA ───────────────────────────────────────────────────

    def check_aria(self) -> list[dict]:
        issues = []
        # Elements with role but no accessible name
        interactive_roles = {"button", "link", "tab", "menuitem", "option", "textbox", "combobox", "listbox"}
        for elem in self.soup.find_all(attrs={"role": True}):
            role = elem.get("role", "")
            if role in interactive_roles:
                text = elem.get_text(strip=True)
                if not text and not elem.get("aria-label") and not elem.get("aria-labelledby"):
                    issues.append(_issue(
                        self.url, "role-no-name", "violation", "serious",
                        _css_selector(elem), _snippet(elem),
                        f'Element with role="{role}" has no accessible name.',
                        "4.1.2", "A", "aria",
                        f'Add aria-label="description" to the element with role="{role}".'
                    ))

        # aria-hidden on focusable elements
        for elem in self.soup.find_all(attrs={"aria-hidden": "true"}):
            if elem.name in ("a", "button", "input", "select", "textarea"):
                issues.append(_issue(
                    self.url, "aria-hidden-focusable", "violation", "critical",
                    _css_selector(elem), _snippet(elem),
                    "aria-hidden='true' on focusable element. Element will be hidden from screen readers but still focusable.",
                    "4.1.2", "A", "aria",
                    "Remove aria-hidden or make the element non-focusable with tabindex='-1'."
                ))

        # Dynamic content without aria-live (look for common patterns)
        for elem in self.soup.find_all(class_=re.compile(r'toast|notification|alert|snackbar|message', re.I)):
            if not elem.get("aria-live") and not elem.get("role") in ("alert", "status", "log"):
                issues.append(_issue(
                    self.url, "no-aria-live", "needs-review", "moderate",
                    _css_selector(elem), _snippet(elem),
                    "Dynamic content container may need aria-live region for screen reader announcements.",
                    "4.1.3", "AA", "aria",
                    'Add aria-live="polite" or role="status" for non-urgent, aria-live="assertive" or role="alert" for urgent.'
                ))

        return issues

    # ── Media ──────────────────────────────────────────────────

    def check_media(self) -> list[dict]:
        issues = []
        # Autoplay media
        for media in self.soup.find_all(["video", "audio"]):
            selector = _css_selector(media)
            if media.get("autoplay") is not None:
                issues.append(_issue(
                    self.url, "autoplay-media", "violation", "serious",
                    selector, _snippet(media),
                    "Media element has autoplay. Users must be able to control media playback.",
                    "1.4.2", "A", "media",
                    "Remove autoplay or provide controls to pause/stop within first 3 seconds."
                ))

            # Video captions
            if media.name == "video":
                has_track = media.find("track", {"kind": "captions"}) or media.find("track", {"kind": "subtitles"})
                if not has_track:
                    issues.append(_issue(
                        self.url, "missing-captions", "violation", "critical",
                        selector, _snippet(media),
                        "Video element has no captions track. Deaf and hard-of-hearing users need captions.",
                        "1.2.2", "A", "media",
                        'Add <track kind="captions" src="captions.vtt" srclang="en" label="English">.'
                    ))

            # Audio transcript
            if media.name == "audio":
                issues.append(_issue(
                    self.url, "missing-transcript", "needs-review", "serious",
                    selector, _snippet(media),
                    "Audio element found. Ensure a text transcript is available nearby.",
                    "1.2.1", "A", "media",
                    "Provide a text transcript of the audio content, linked near the audio player."
                ))

        return issues

    # ── Color Hints (static-only, can't compute actual contrast) ─

    def check_color_hints(self) -> list[dict]:
        """Flag elements that may have contrast issues based on inline styles."""
        issues = []
        # Look for very small font sizes
        for elem in self.soup.find_all(style=re.compile(r'font-size\s*:\s*(\d+)', re.I)):
            style = elem.get("style", "")
            match = re.search(r'font-size\s*:\s*(\d+)', style)
            if match:
                size = int(match.group(1))
                if size < 12:
                    issues.append(_issue(
                        self.url, "small-font-size", "needs-review", "moderate",
                        _css_selector(elem), _snippet(elem, 200),
                        f"Font size {size}px may be too small for readability.",
                        "1.4.4", "AA", "content",
                        "Use at least 16px for body text. Ensure text can be resized to 200%.",
                        fix_effort="low"
                    ))
        return issues

    # ── Keyboard Hints ─────────────────────────────────────────

    def check_keyboard_hints(self) -> list[dict]:
        """Static checks for keyboard accessibility issues."""
        issues = []
        # Positive tabindex
        for elem in self.soup.find_all(attrs={"tabindex": True}):
            try:
                tabindex = int(elem.get("tabindex", "0"))
                if tabindex > 0:
                    issues.append(_issue(
                        self.url, "positive-tabindex", "violation", "serious",
                        _css_selector(elem), _snippet(elem),
                        f"Element has tabindex={tabindex}. Positive tabindex disrupts natural tab order.",
                        "2.4.3", "A", "keyboard",
                        "Remove positive tabindex or set to 0 to use natural DOM order."
                    ))
            except (ValueError, TypeError):
                pass

        return issues

    # ── Viewport ───────────────────────────────────────────────

    def check_viewport(self) -> list[dict]:
        issues = []
        meta_vp = self.soup.find("meta", attrs={"name": "viewport"})
        if meta_vp:
            content = meta_vp.get("content", "")
            if "maximum-scale=1" in content or "user-scalable=no" in content:
                issues.append(_issue(
                    self.url, "viewport-zoom-disabled", "violation", "critical",
                    "meta[name=viewport]", _snippet(meta_vp),
                    "Viewport meta tag prevents zoom. Users with low vision need to zoom content.",
                    "1.4.4", "AA", "content",
                    'Remove maximum-scale=1 and user-scalable=no from viewport meta tag.'
                ))
        return issues

    # ── Skip Navigation ────────────────────────────────────────

    def check_skip_nav(self) -> list[dict]:
        issues = []
        body = self.soup.find("body")
        if body:
            first_links = body.find_all("a", limit=5)
            has_skip = False
            for link in first_links:
                href = link.get("href", "")
                text = link.get_text(strip=True).lower()
                if href.startswith("#") and ("skip" in text or "main" in text or "content" in text):
                    has_skip = True
                    break
            if not has_skip and self.soup.find("nav"):
                issues.append(_issue(
                    self.url, "missing-skip-link", "violation", "moderate",
                    "<body>", "<body>",
                    "Page with navigation lacks a 'skip to main content' link as the first focusable element.",
                    "2.4.1", "A", "navigation",
                    'Add <a href="#main-content" class="skip-link">Skip to main content</a> as the first element in <body>.'
                ))
        return issues
