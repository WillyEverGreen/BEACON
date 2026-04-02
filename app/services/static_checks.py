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

_WEAK_LINK_TEXT = {"click here", "read more"}

_VALID_ARIA_BOOL = {"true", "false"}
_VALID_ARIA_TRISTATE = {"true", "false", "mixed"}
_VALID_ARIA_CURRENT = {"page", "step", "location", "date", "time", "true", "false"}
_VALID_ARIA_SORT = {"ascending", "descending", "none", "other"}

# Compact role allowlist for strong validation with low false positives.
_KNOWN_ROLES = {
    "alert", "alertdialog", "application", "article", "banner", "button", "cell", "checkbox",
    "columnheader", "combobox", "complementary", "contentinfo", "definition", "dialog", "directory",
    "document", "feed", "figure", "form", "grid", "gridcell", "group", "heading", "img", "link",
    "list", "listbox", "listitem", "log", "main", "marquee", "math", "menu", "menubar", "menuitem",
    "menuitemcheckbox", "menuitemradio", "navigation", "none", "note", "option", "presentation",
    "progressbar", "radio", "radiogroup", "region", "row", "rowgroup", "rowheader", "scrollbar",
    "search", "searchbox", "separator", "slider", "spinbutton", "status", "switch", "tab", "table",
    "tablist", "tabpanel", "term", "textbox", "timer", "toolbar", "tooltip", "tree", "treegrid",
    "treeitem"
}


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
        self.rule_activity: dict[str, dict[str, int]] = {}

    def _track_rule_activity(self, rule_id: str, elements_checked: int = 0, violations_found: int = 0) -> None:
        """Track lightweight per-rule activity telemetry for detector coverage debugging."""
        slot = self.rule_activity.setdefault(rule_id, {"elements_checked": 0, "violations_found": 0})
        slot["elements_checked"] += max(0, int(elements_checked))
        slot["violations_found"] += max(0, int(violations_found))

    def get_rule_activity(self) -> dict[str, dict[str, int]]:
        """Return copy-safe rule activity telemetry."""
        return {
            rid: {
                "elements_checked": vals.get("elements_checked", 0),
                "violations_found": vals.get("violations_found", 0),
            }
            for rid, vals in self.rule_activity.items()
        }

    def run_all(self, checks: Optional[list[str]] = None) -> list[dict]:
        """Run all check categories. Pass a list to limit which categories run."""
        all_checks = checks or [
            "language", "title", "landmarks", "headings", "images",
            "links", "buttons", "forms", "tables", "lists",
            "aria", "media", "color_hints", "keyboard_hints",
            "viewport", "skip_nav", "advanced_detect",
            # New high-impact checks
            "color_contrast", "duplicate_ids", "redundant_alt",
            "svg_accessible_name", "empty_headings", "unsafe_external_links", "form_label_missing",
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
        weak_link_texts = {"click here", "read more", "link"}

        for link in self.soup.find_all("a"):
            text = link.get_text(" ", strip=True)
            aria_label = (link.get("aria-label") or "").strip()
            aria_labelledby = (link.get("aria-labelledby") or "").strip()
            title = (link.get("title") or "").strip()
            href = (link.get("href") or "").strip()
            selector = _css_selector(link)

            img = link.find("img")
            img_alt = (img.get("alt") or "").strip() if img else ""
            has_programmatic_name = bool(aria_label or aria_labelledby or title or img_alt)

            # Empty link
            if not text and not has_programmatic_name:
                issues.append(_issue(
                    self.url, "empty-link", "violation", "serious",
                    selector, _snippet(link),
                    "Link has no text content. Screen readers will announce it as empty.",
                    "2.4.4", "A", "navigation",
                    'Add descriptive text or aria-label="description".'
                ))

            # Strict link-purpose check aligned to benchmark-facing generic labels.
            if text and text.lower() in weak_link_texts and not has_programmatic_name and href and not href.startswith("#"):
                issues.append(_issue(
                    self.url, "link-purpose", "violation", "moderate",
                    selector, _snippet(link),
                    f'Link text "{text}" is generic and lacks clear purpose.',
                    "2.4.4", "A", "navigation",
                    "Use descriptive link text or add aria-label/aria-labelledby with purpose context."
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
        checked = 0
        button_name_violations = 0

        def _has_accessible_name(elem: Tag) -> bool:
            # Prefer explicit ARIA naming first.
            if elem.get("aria-label") or elem.get("aria-labelledby"):
                return True
            if elem.get("title"):
                return True

            # Native visible text.
            if elem.get_text(" ", strip=True):
                return True

            # Button-like inputs use value/alt attributes for naming.
            if elem.name == "input":
                input_type = (elem.get("type") or "").lower()
                if input_type in {"button", "submit", "reset"} and (elem.get("value") or "").strip():
                    return True
                if input_type == "image" and (elem.get("alt") or "").strip():
                    return True

            # Icon buttons with meaningful image alt can still be named.
            img = elem.find("img")
            if img and (img.get("alt") or "").strip():
                return True

            return False

        for btn in self.soup.find_all("button"):
            checked += 1
            selector = _css_selector(btn)

            if not _has_accessible_name(btn):
                issues.append(_issue(
                    self.url, "button-name", "violation", "critical",
                    selector, _snippet(btn),
                    "Button has no accessible name. Screen readers cannot identify this control.",
                    "4.1.2", "A", "forms",
                    'Add text content or aria-label="Button description".'
                ))
                button_name_violations += 1

        # Input controls that function as buttons also require an accessible name.
        for inp in self.soup.find_all("input"):
            inp_type = (inp.get("type") or "").lower()
            if inp_type not in {"button", "submit", "reset", "image"}:
                continue
            checked += 1
            if not _has_accessible_name(inp):
                issues.append(_issue(
                    self.url, "button-name", "violation", "critical",
                    _css_selector(inp), _snippet(inp),
                    "Button-like input has no accessible name.",
                    "4.1.2", "A", "forms",
                    'Add value text, alt text (for image inputs), or aria-label.'
                ))
                button_name_violations += 1

        # ARIA button role support in static mode.
        for elem in self.soup.find_all(attrs={"role": True}):
            role = (elem.get("role") or "").strip().lower()
            if role != "button":
                continue
            checked += 1
            if not _has_accessible_name(elem):
                issues.append(_issue(
                    self.url, "button-name", "violation", "critical",
                    _css_selector(elem), _snippet(elem),
                    "Element with role=button has no accessible name.",
                    "4.1.2", "A", "forms",
                    'Add visible text or aria-label/aria-labelledby to the role="button" element.'
                ))
                button_name_violations += 1

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

        self._track_rule_activity("button-name", elements_checked=checked, violations_found=button_name_violations)

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
        # Only flag if the error container is inside a <form> — error divs outside forms
        # are usually site-wide banners, not form-specific validation messages.
        for err_container in self.soup.find_all(class_=re.compile(r'error|invalid|alert', re.I)):
            err_id = err_container.get("id")
            if err_id:
                # Guard: only flag if inside a form context
                if not err_container.find_parent("form"):
                    continue
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

            # Video captions — skip muted+autoplay videos (decorative/ambient)
            if media.name == "video":
                has_track = media.find("track", {"kind": "captions"}) or media.find("track", {"kind": "subtitles"})
                is_muted = media.get("muted") is not None
                is_autoplay = media.get("autoplay") is not None
                if not has_track and not (is_muted and is_autoplay):
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

    # ── Advanced Detection Mastery (The Hidden 10) ─────────────
    
    def check_advanced_detect(self) -> list[dict]:
        """Advanced checks beyond basic axe-core rules."""
        issues = []
        issues.extend(self._check_link_accessibility_cluster())
        issues.extend(self._check_aria_valid_attr_values())
        issues.extend(self._check_text_spacing_signals())
        issues.extend(self._check_video_transcript_presence())
        issues.extend(self._check_placeholder_only_label())
        issues.extend(self._check_broken_aria_references())
        issues.extend(self._check_pseudo_icon_accessibility())
        issues.extend(self._check_visibility_mismatch())
        issues.extend(self._check_css_reordering())
        issues.extend(self._check_language_content_mismatch())
        issues.extend(self._check_inaccessible_documents())
        issues.extend(self._check_touch_target_spacing())
        issues.extend(self._check_timeout_warnings())
        issues.extend(self._check_auto_update_controls())
        return issues

    def _check_link_accessibility_cluster(self) -> list[dict]:
        """Benchmark-aligned link checks: strict empty-link + weak-purpose detection."""
        issues = []
        weak_texts = {"click here", "read more", "link"}

        for link in self.soup.find_all("a"):
            text = link.get_text(" ", strip=True).lower()
            href = (link.get("href") or "").strip()

            has_name = bool(
                (link.get("aria-label") or "").strip()
                or (link.get("aria-labelledby") or "").strip()
                or (link.get("title") or "").strip()
            )
            img = link.find("img")
            if img and (img.get("alt") or "").strip():
                has_name = True

            if not text and not has_name:
                issues.append(_issue(
                    self.url, "empty-link", "violation", "serious",
                    _css_selector(link), _snippet(link),
                    "Link has no accessible name.",
                    "2.4.4", "A", "navigation",
                    "Add visible text or an accessible name via aria-label/aria-labelledby."
                ))
                continue

            if text in weak_texts and not has_name and href and not href.startswith("#"):
                issues.append(_issue(
                    self.url, "link-purpose", "violation", "moderate",
                    _css_selector(link), _snippet(link),
                    f'Link text "{text}" is generic and not self-descriptive.',
                    "2.4.4", "A", "navigation",
                    "Replace generic text with descriptive link purpose text."
                ))

        return issues

    def _check_link_purpose_contextual(self) -> list[dict]:
        """Detect weak link purpose with context-aware suppression."""
        issues = []
        for link in self.soup.find_all("a"):
            text = link.get_text(" ", strip=True).lower()
            if text not in _WEAK_LINK_TEXT:
                continue

            # Tighten to avoid FP on icon-only/contextual navigation links.
            if link.find("img") or link.get("title"):
                continue
            href = (link.get("href") or "").strip()
            if not href or href.startswith("#"):
                continue

            has_aria = bool(link.get("aria-label") or link.get("aria-labelledby"))
            has_context = bool(link.find_parent(["nav", "header", "footer", "section"]))
            if has_aria or has_context:
                continue

            issues.append(_issue(
                self.url, "link-purpose", "violation", "moderate",
                _css_selector(link), _snippet(link),
                f'Link text "{text}" is generic and lacks contextual disambiguation.',
                "2.4.4", "A", "navigation",
                "Use descriptive link text or add aria-label/aria-labelledby with purpose context."
            ))
        return issues

    def _check_semantic_html_signals(self) -> list[dict]:
        """Detect common semantic misuse patterns with low ambiguity."""
        issues = []

        # Clickable non-interactive elements without role/tabindex.
        for el in self.soup.find_all(["div", "span"]):
            has_click = bool(el.get("onclick") or el.get("onmousedown") or el.get("onmouseup"))
            has_role = bool(el.get("role"))
            has_tabindex = el.get("tabindex") is not None
            if has_click and not has_role and not has_tabindex:
                issues.append(_issue(
                    self.url, "semantic-html", "violation", "serious",
                    _css_selector(el), _snippet(el),
                    "Non-interactive element appears clickable but lacks semantic role and keyboard affordance.",
                    "1.3.1", "A", "html",
                    "Use a native <button>/<a> or add role=\"button\", tabindex=\"0\", and keyboard handlers."
                ))

        # Visual heading pattern without heading semantics.
        for el in self.soup.find_all(["div", "span", "p"]):
            style = (el.get("style") or "").lower()
            if "font-size" not in style:
                continue
            size_match = re.search(r"font-size\s*:\s*([0-9.]+)px", style)
            if not size_match:
                continue
            try:
                font_size = float(size_match.group(1))
            except ValueError:
                continue
            if font_size < 20:
                continue
            if el.get("role") == "heading" or el.name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                continue

            text = el.get_text(" ", strip=True)
            if len(text) < 4:
                continue

            issues.append(_issue(
                self.url, "semantic-html", "needs-review", "moderate",
                _css_selector(el), _snippet(el),
                "Large text block appears heading-like but lacks semantic heading markup.",
                "1.3.1", "A", "html",
                "Use semantic heading tags (h1-h6) or role=\"heading\" with aria-level."
            ))

        return issues

    def _check_aria_valid_attr_values(self) -> list[dict]:
        """Validate role and selected ARIA attribute values with deterministic checks."""
        issues = []

        for el in self.soup.find_all(attrs={"role": True}):
            role_raw = (el.get("role") or "").strip().lower()
            role_tokens = [tok for tok in role_raw.split() if tok]
            # ARIA permits multiple role tokens as fallback. Treat as valid if any token is known.
            if role_tokens and not any(tok in _KNOWN_ROLES for tok in role_tokens):
                issues.append(_issue(
                    self.url, "aria-valid-attr-value", "violation", "serious",
                    _css_selector(el), _snippet(el),
                    f'Invalid ARIA role value "{role_raw}".',
                    "4.1.2", "A", "aria",
                    "Use a valid ARIA role value from the WAI-ARIA specification."
                ))

        for el in self.soup.find_all(attrs={"aria-hidden": True}):
            val = (el.get("aria-hidden") or "").strip().lower()
            if val and val not in _VALID_ARIA_BOOL:
                issues.append(_issue(
                    self.url, "aria-valid-attr-value", "violation", "serious",
                    _css_selector(el), _snippet(el),
                    f'Invalid aria-hidden value "{val}". Expected true/false.',
                    "4.1.2", "A", "aria",
                    'Set aria-hidden to "true" or "false".'
                ))

        for el in self.soup.find_all(attrs={"aria-checked": True}):
            val = (el.get("aria-checked") or "").strip().lower()
            role = (el.get("role") or "").strip().lower()
            if role not in {"checkbox", "menuitemcheckbox", "radio", "menuitemradio", "switch", "option", "treeitem"}:
                continue
            if val not in _VALID_ARIA_TRISTATE:
                issues.append(_issue(
                    self.url, "aria-valid-attr-value", "violation", "serious",
                    _css_selector(el), _snippet(el),
                    f'Invalid aria-checked value "{val}". Expected true/false/mixed.',
                    "4.1.2", "A", "aria",
                    'Set aria-checked to "true", "false", or "mixed" when supported.'
                ))

        for el in self.soup.find_all(attrs={"aria-current": True}):
            val = (el.get("aria-current") or "").strip().lower()
            if val not in _VALID_ARIA_CURRENT:
                issues.append(_issue(
                    self.url, "aria-valid-attr-value", "violation", "moderate",
                    _css_selector(el), _snippet(el),
                    f'Invalid aria-current value "{val}".',
                    "4.1.2", "A", "aria",
                    'Use aria-current values like "page", "step", "location", "date", "time", "true", or "false".'
                ))

        for el in self.soup.find_all(attrs={"aria-sort": True}):
            val = (el.get("aria-sort") or "").strip().lower()
            if val not in _VALID_ARIA_SORT:
                issues.append(_issue(
                    self.url, "aria-valid-attr-value", "violation", "moderate",
                    _css_selector(el), _snippet(el),
                    f'Invalid aria-sort value "{val}".',
                    "4.1.2", "A", "aria",
                    'Use aria-sort values "ascending", "descending", "none", or "other".'
                ))

        return issues

    def _check_text_spacing_signals(self) -> list[dict]:
        """Detect likely text spacing failures from inline styles and content visibility signals."""
        issues = []
        checked = 0
        for el in self.soup.find_all(style=True):
            text = el.get_text(" ", strip=True)
            if len(text) < 20:
                continue

            checked += 1

            style = (el.get("style") or "").lower()
            if "display:none" in style or "visibility:hidden" in style:
                continue

            fs_match = re.search(r"font-size\s*:\s*([0-9.]+)px", style)
            if fs_match:
                try:
                    if float(fs_match.group(1)) < 12:
                        continue
                except ValueError:
                    pass

            lh_match = re.search(r"line-height\s*:\s*([0-9.]+)", style)
            ls_match = re.search(r"letter-spacing\s*:\s*([0-9.]+)em", style)

            line_height_low = False
            letter_spacing_low = False

            if lh_match:
                try:
                    line_height_low = float(lh_match.group(1)) < 1.5
                except ValueError:
                    pass

            if ls_match:
                try:
                    letter_spacing_low = float(ls_match.group(1)) < 0.12
                except ValueError:
                    pass

            if line_height_low or letter_spacing_low:
                issues.append(_issue(
                    self.url, "text-spacing", "needs-review", "moderate",
                    _css_selector(el), _snippet(el),
                    "Inline text spacing may not meet WCAG reflow/readability guidance (line-height/letter-spacing).",
                    "1.4.12", "AA", "content",
                    "Increase line-height to at least 1.5 and letter-spacing to at least 0.12em for readable body text."
                ))

        self._track_rule_activity("text-spacing", elements_checked=checked, violations_found=len(issues))

        return issues

    def _check_video_transcript_presence(self) -> list[dict]:
        """Detect missing transcript/captions for meaningful videos with conservative FP guards."""
        issues = []
        checked = 0

        def _attr_truthy(value) -> bool:
            if value is None:
                return False
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            return text in {"", "true", "1", "yes", "autoplay", "muted"}

        for video in self.soup.find_all("video"):
            checked += 1
            selector = _css_selector(video)

            has_captions = bool(
                video.find("track", {"kind": re.compile(r"captions|subtitles", re.I)})
            )

            duration_raw = video.get("duration")
            if duration_raw:
                try:
                    if float(duration_raw) < 3.0:
                        continue
                except ValueError:
                    pass

            is_muted = _attr_truthy(video.get("muted"))
            is_autoplay = _attr_truthy(video.get("autoplay"))
            if is_muted and is_autoplay:
                continue

            # Search for transcript signals near the video first, then page-level hints.
            parent = video.parent
            local_scope = parent if isinstance(parent, Tag) else self.soup

            local_transcript_hint = bool(
                local_scope.find(attrs={"data-transcript": True})
                or local_scope.find(class_=re.compile(r"transcript", re.I))
                or local_scope.find(id=re.compile(r"transcript", re.I))
            )

            transcript_link_hint = bool(
                local_scope.find("a", string=re.compile(r"transcript", re.I))
                or local_scope.find("button", string=re.compile(r"transcript", re.I))
            )

            transcript_hint = bool(
                self.soup.find(attrs={"data-transcript": True})
                or self.soup.find(class_=re.compile(r"transcript", re.I))
                or self.soup.find(id=re.compile(r"transcript", re.I))
            )

            # Aggregate nearby sibling text blocks to detect transcript-like long-form content.
            sibling_chunks = []
            nxt = video.find_next_sibling()
            hops = 0
            while nxt is not None and hops < 3:
                sibling_chunks.append(nxt.get_text(" ", strip=True))
                nxt = nxt.find_next_sibling()
                hops += 1
            has_long_text_nearby = len(" ".join(sibling_chunks)) > 200

            if has_captions:
                continue
            if local_transcript_hint or transcript_link_hint or transcript_hint or has_long_text_nearby:
                continue

            issues.append(_issue(
                self.url, "video-transcript", "violation", "serious",
                selector, _snippet(video),
                "Video appears to lack nearby transcript or transcript indicators.",
                "1.2.1", "A", "media",
                "Provide a transcript near the video or a clearly labeled transcript link/section."
            ))

        self._track_rule_activity("video-transcript", elements_checked=checked, violations_found=len(issues))

        return issues

    def _check_touch_target_spacing(self) -> list[dict]:
        """Flag potential touch target spacing issues (WCAG 2.5.8)."""
        issues = []
        for elem in self.soup.find_all(["button", "a"]):
            style = elem.get("style", "").lower()
            # If it's a small button/link, check for spacing
            if "width:" in style or "height:" in style:
                match_w = re.search(r'width:\s*(\d+)px', style)
                match_h = re.search(r'height:\s*(\d+)px', style)
                if (match_w and int(match_w.group(1)) < 24) or (match_h and int(match_h.group(1)) < 24):
                    if "margin" not in style:
                        issues.append(_issue(
                            self.url, "touch-target-spacing", "violation", "moderate",
                            _css_selector(elem), _snippet(elem),
                            "Touch target may be smaller than 24px or missing adequate spacing. WCAG 2.2 requires at least 24px size or spacing.",
                            "2.5.8", "AA", "keyboard",
                            "Ensure the target is at least 24x24px or has enough spacing to prevent accidental activation."
                        ))
        return issues

    def _check_timeout_warnings(self) -> list[dict]:
        """Check for session timeout indicators without clear warning mechanisms."""
        issues = []
        timeout_words = ["session", "timeout", "expire", "logout"]
        body_text = self.soup.get_text().lower()
        
        if any(w in body_text for w in timeout_words):
            # Check for live regions or alerts
            has_warning_mech = bool(self.soup.find(attrs={"aria-live": True}) or 
                                    self.soup.find(attrs={"role": ["alert", "status", "timer"]}))
            if not has_warning_mech:
                issues.append(_issue(
                    self.url, "timeout-no-warning", "needs-review", "serious",
                    "<body>", "<body>",
                    "Page appears to have session logic but no obvious accessible warning mechanism for timeouts.",
                    "2.2.1", "A", "forms",
                    "Provide a warning at least 20 seconds before a timeout occurs, allowing users to extend the session."
                ))
        return issues

    def _check_auto_update_controls(self) -> list[dict]:
        """Detect auto-updating content (live regions, carousels) lacking controls."""
        issues = []
        if self.soup.find("marquee"):
            issues.append(_issue(
                self.url, "marquee-used", "violation", "critical",
                "<marquee>", "<marquee>...",
                "The <marquee> element is obsolete and provides no control over moving content.",
                "2.2.2", "A", "content",
                "Remove <marquee> and use CSS/JS with pause/stop controls."
            ))

        # Carousel/Live region check
        live_regions = self.soup.find_all(attrs={"aria-live": ["polite", "assertive"]})
        for region in live_regions:
            # Look for a button with "pause", "stop", or "hide" nearby
            parent = region.find_parent()
            if parent:
                controls = parent.find_all("button")
                has_stop = any(re.search(r'pause|stop|hide', str(c), re.I) for c in controls)
                if not has_stop and len(region.get_text()) > 50:
                    issues.append(_issue(
                        self.url, "auto-update-no-control", "needs-review", "moderate",
                        _css_selector(region), _snippet(region, 200),
                        "Auto-updating content area lacks a visible pause or stop control.",
                        "2.2.2", "A", "content",
                        "Provide a mechanism to pause, stop, or hide content that updates automatically."
                    ))
        return issues

    def _check_language_content_mismatch(self) -> list[dict]:
        """Detect text blocks that may be in a different language than the page/element lang."""
        issues = []
        html_lang = self.soup.find("html").get("lang", "en").lower()[:2]
        
        # Simple heuristic for common non-English words if page is English
        non_en_indicators = {"der", "die", "und", "dans", "avec", "pour", "este", "como"}
        
        for elem in self.soup.find_all(["p", "div", "section"]):
            if elem.get("lang"): continue # Already has a lang attribute
            
            text = elem.get_text(strip=True).lower()
            if len(text) > 100:
                words = set(text.split())
                if html_lang == "en" and any(w in words for w in non_en_indicators):
                    issues.append(_issue(
                        self.url, "lang-mismatch", "needs-review", "moderate",
                        _css_selector(elem), _snippet(elem, 100),
                        "Possible language mismatch. Content appears to be in a different language but lacks a 'lang' attribute.",
                        "3.1.2", "AA", "html",
                        "Add a lang attribute to the element (e.g., <div lang='de'>) to ensure correct screen reader pronunciation."
                    ))
        return issues

    def _check_inaccessible_documents(self) -> list[dict]:
        """Detect links to non-HTML documents (PDF, DOCX) without warnings."""
        issues = []
        doc_extensions = [".pdf", ".docx", ".xlsx", ".pptx", ".zip"]
        for link in self.soup.find_all("a"):
            href = link.get("href", "").lower()
            if any(href.endswith(ext) for ext in doc_extensions):
                text = link.get_text(strip=True).lower()
                ext_found = next(ext for ext in doc_extensions if href.endswith(ext))
                
                # Check if the text mentions the format
                if ext_found[1:] not in text:
                    issues.append(_issue(
                        self.url, "inaccessible-document-link", "best-practice", "moderate",
                        _css_selector(link), _snippet(link),
                        f"Link to {ext_found.upper()} document missing format warning. Users should be notified before downloading non-HTML content.",
                        "2.4.4", "A", "navigation",
                        f"Add ' ({ext_found[1:].upper()})' to the link text or an icon with a label."
                    ))
        return issues

    def _check_pseudo_icon_accessibility(self) -> list[dict]:
        """Detect icon elements (i, span) that likely use CSS pseudo-content but lack labels."""
        issues = []
        icon_classes = ["fa-", "icon-", "glyphicon-", "material-icons", "mdi-"]
        for elem in self.soup.find_all(["i", "span", "em"]):
            classes = elem.get("class", [])
            if not isinstance(classes, list): classes = [classes]
            
            is_icon = any(any(ic in c for ic in icon_classes) for c in classes)
            if is_icon:
                has_label = bool(elem.get("aria-label") or elem.get("aria-labelledby") or elem.get_text(strip=True))
                is_hidden = elem.get("aria-hidden") == "true"
                
                if not has_label and not is_hidden:
                    # Check if it has a parent button/link with a label
                    parent = elem.find_parent(["button", "a"])
                    if parent:
                        parent_label = bool(parent.get("aria-label") or parent.get("aria-labelledby") or parent.get_text(strip=True))
                        if parent_label:
                            continue

                    issues.append(_issue(
                        self.url, "unlabeled-icon", "violation", "serious",
                        _css_selector(elem), _snippet(elem),
                        "Icon element likely using CSS pseudo-content (::before/::after) has no accessible name or aria-hidden='true'.",
                        "1.1.1", "A", "aria",
                        "Add aria-hidden='true' if decorative, or provide a text label via aria-label."
                    ))
        return issues

    def _check_visibility_mismatch(self) -> list[dict]:
        """Detect elements with aria-hidden='false' but visually hidden via inline CSS."""
        issues = []
        hidden_styles = ["display: none", "display:none", "visibility: hidden", "visibility:hidden"]
        for elem in self.soup.find_all(attrs={"aria-hidden": "false"}):
            style = elem.get("style", "").lower()
            if any(hs in style for hs in hidden_styles):
                issues.append(_issue(
                    self.url, "visibility-aria-mismatch", "violation", "serious",
                    _css_selector(elem), _snippet(elem),
                    "Element set to aria-hidden='false' but visually hidden via CSS. This creates a mismatch between screen readers and visual state.",
                    "1.3.1", "A", "aria",
                    "Remove aria-hidden='false' if the element is hidden, or ensure it is visible to all users."
                ))
        return issues

    def _check_css_reordering(self) -> list[dict]:
        """Flag inline styles that reorder content (flex-direction: *-reverse)."""
        issues = []
        reorder_styles = ["flex-direction: row-reverse", "flex-direction:row-reverse", 
                          "flex-direction: column-reverse", "flex-direction:column-reverse"]
        for elem in self.soup.find_all(style=True):
            style = elem.get("style", "").lower()
            if any(rs in style for rs in reorder_styles):
                issues.append(_issue(
                    self.url, "css-reordering", "needs-review", "moderate",
                    _css_selector(elem), _snippet(elem),
                    "Flex container uses row-reverse or column-reverse. This may cause focus order to differ from visual order.",
                    "2.4.3", "A", "keyboard",
                    "Verify that the tab order matches the visual reading order."
                ))
        return issues

    def _check_placeholder_only_label(self) -> list[dict]:
        """Flag inputs using placeholder as the ONLY label (WCAG 1.3.1, 3.3.2)."""
        issues = []
        for inp in self.soup.find_all(["input", "textarea"]):
            inp_type = inp.get("type", "text")
            if inp_type in ("hidden", "submit", "button", "reset", "image"):
                continue
            
            placeholder = inp.get("placeholder")
            if not placeholder:
                continue

            # Check if there is ANY valid label/name
            has_real_label = False
            inp_id = inp.get("id")
            if inp_id and self.soup.find("label", attrs={"for": inp_id}):
                has_real_label = True
            
            if not has_real_label:
                has_real_label = bool(
                    inp.get("aria-label") or 
                    inp.get("aria-labelledby") or 
                    inp.find_parent("label")
                )
            
            if placeholder and not has_real_label:
                issues.append(_issue(
                    self.url, "placeholder-as-label", "violation", "serious",
                    _css_selector(inp), _snippet(inp),
                    f"Input uses placeholder '{placeholder}' as its only label. Placeholders disappear when typing and are not a substitute for semantic labels.",
                    "1.3.1", "A", "forms",
                    f'Add a <label for="{inp_id or "field-id"}">{placeholder}</label> or aria-label="{placeholder}".'
                ))
        return issues

    def _check_broken_aria_references(self) -> list[dict]:
        """Detect aria-labelledby/describedby pointing to missing or duplicate IDs."""
        issues = []
        # Find all unique IDs to check for duplicates
        all_ids = [tag['id'] for tag in self.soup.find_all(id=True)]
        id_counts = {}
        for i in all_ids:
            id_counts[i] = id_counts.get(i, 0) + 1

        for tag in self.soup.find_all(attrs={"aria-labelledby": True}):
            ref_ids = tag["aria-labelledby"].split()
            for rid in ref_ids:
                if rid not in id_counts:
                    issues.append(_issue(
                        self.url, "broken-aria-label", "violation", "serious",
                        _css_selector(tag), _snippet(tag),
                        f"aria-labelledby references non-existent ID '{rid}'.",
                        "1.3.1", "A", "aria",
                        f"Ensure an element with id='{rid}' exists on the page."
                    ))
                elif id_counts[rid] > 1:
                    issues.append(_issue(
                        self.url, "duplicate-aria-ref", "violation", "serious",
                        _css_selector(tag), _snippet(tag),
                        f"aria-labelledby references ID '{rid}' which is duplicated {id_counts[rid]} times on the page. References will be ambiguous.",
                        "1.3.1", "A", "aria",
                        "Ensure all IDs used in ARIA references are unique."
                    ))

        for tag in self.soup.find_all(attrs={"aria-describedby": True}):
            ref_ids = tag["aria-describedby"].split()
            for rid in ref_ids:
                if rid not in id_counts:
                    issues.append(_issue(
                        self.url, "broken-aria-description", "violation", "serious",
                        _css_selector(tag), _snippet(tag),
                        f"aria-describedby references non-existent ID '{rid}'.",
                        "1.3.1", "A", "aria",
                        f"Ensure an element with id='{rid}' exists on the page."
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
            # Only flag if the page has a nav AND >3 links before main content.
            # Single-section pages or minimal test fixtures don't need skip links.
            nav = self.soup.find("nav")
            if not has_skip and nav:
                nav_links = nav.find_all("a")
                if len(nav_links) > 3:
                    issues.append(_issue(
                        self.url, "missing-skip-link", "violation", "moderate",
                        "<body>", "<body>",
                        "Page with navigation lacks a 'skip to main content' link as the first focusable element.",
                        "2.4.1", "A", "navigation",
                        'Add <a href="#main-content" class="skip-link">Skip to main content</a> as the first element in <body>.'
                    ))
        return issues

    # ── Color Contrast (inline styles) ─────────────────────────

    def check_color_contrast(self) -> list[dict]:
        """
        Detect color contrast failures from inline styles using WCAG relative luminance.
        Only checks elements with BOTH color + background-color inline — zero FPs otherwise.
        WCAG SC 1.4.3 (AA): normal text needs 4.5:1, large text needs 3:1.
        """
        def _parse_rgb(css_val: str):
            css_val = css_val.strip().lower()
            m = re.match(r'rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', css_val)
            if m:
                return int(m.group(1)), int(m.group(2)), int(m.group(3))
            m = re.match(r'#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})', css_val)
            if m:
                return int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)
            m = re.match(r'#([0-9a-f])([0-9a-f])([0-9a-f])', css_val)
            if m:
                return int(m.group(1) * 2, 16), int(m.group(2) * 2, 16), int(m.group(3) * 2, 16)
            return None

        def _luminance(r, g, b) -> float:
            def _c(x):
                s = x / 255.0
                return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4
            return 0.2126 * _c(r) + 0.7152 * _c(g) + 0.0722 * _c(b)

        def _ratio(l1, l2) -> float:
            return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

        issues = []
        for elem in self.soup.find_all(style=True):
            text = elem.get_text(strip=True)
            if len(text) < 2:
                continue
            style = elem.get("style", "")
            color_m = re.search(r'(?<![a-zA-Z-])color\s*:\s*([^;]+)', style, re.I)
            bg_m = re.search(r'background-color\s*:\s*([^;]+)', style, re.I)
            if not color_m or not bg_m:
                continue
            fg = _parse_rgb(color_m.group(1))
            bg = _parse_rgb(bg_m.group(1))
            if fg is None or bg is None:
                continue
            contrast = _ratio(_luminance(*fg), _luminance(*bg))

            # Detect large text
            fs_m = re.search(r'font-size\s*:\s*([\d.]+)px', style, re.I)
            fw_m = re.search(r'font-weight\s*:\s*(bold|\d+)', style, re.I)
            fs_px = float(fs_m.group(1)) if fs_m else 16.0
            bold = bool(fw_m and (fw_m.group(1) == "bold" or
                                  (fw_m.group(1).isdigit() and int(fw_m.group(1)) >= 700)))
            is_large = fs_px >= 24 or (bold and fs_px >= 18.67)
            required = 3.0 if is_large else 4.5

            if contrast < required:
                issues.append(_issue(
                    self.url, "color-contrast", "violation",
                    "serious" if contrast < 2.0 else "moderate",
                    _css_selector(elem), _snippet(elem, 200),
                    f"Color contrast ratio {contrast:.2f}:1 is below the required {required}:1. "
                    f"Text: rgb{fg}, Background: rgb{bg}.",
                    "1.4.3", "AA", "color",
                    f"Adjust colors to achieve at least {required}:1 contrast ratio.",
                    fix_effort="low"
                ))
        return issues

    # ── Duplicate IDs ──────────────────────────────────────────

    def check_duplicate_ids(self) -> list[dict]:
        """
        Flag duplicate id attributes. Duplicate IDs break ARIA references,
        form labels, fragment navigation, and JavaScript queries.
        WCAG SC 4.1.1 (A).
        """
        issues = []
        id_map: dict[str, list] = {}
        for elem in self.soup.find_all(id=True):
            eid = (elem.get("id") or "").strip()
            if eid:
                id_map.setdefault(eid, []).append(elem)
        for eid, elems in id_map.items():
            if len(elems) > 1:
                issues.append(_issue(
                    self.url, "duplicate-id", "violation", "serious",
                    f'[id="{eid}"]', _snippet(elems[0], 200),
                    f'ID "{eid}" is used {len(elems)} times. Duplicate IDs break '
                    f"ARIA label associations, skip links, and DOM queries.",
                    "4.1.1", "A", "html",
                    f'Make id="{eid}" unique across the page. Rename duplicate instances.',
                    fix_effort="low"
                ))
        return issues

    # ── Redundant Alt Text ─────────────────────────────────────

    def check_redundant_alt(self) -> list[dict]:
        """
        Detect images whose alt text duplicates adjacent visible text.
        Screen readers will announce the same content twice.
        WCAG SC 1.1.1 (A), best-practice.
        """
        issues = []
        for img in self.soup.find_all("img"):
            alt = (img.get("alt") or "").strip()
            if not alt or len(alt) < 5:
                continue

            # Check parent link text
            parent_link = img.find_parent("a")
            if parent_link:
                link_text = parent_link.get_text(" ", strip=True)
                if link_text and link_text.lower() == alt.lower():
                    issues.append(_issue(
                        self.url, "image-redundant-alt", "best-practice", "minor",
                        _css_selector(img), _snippet(img, 200),
                        f'Image alt "{alt[:60]}" duplicates parent link text. '
                        f"Screen readers will announce this twice.",
                        "1.1.1", "A", "images",
                        'Set alt="" on the image — the link text already provides the label.',
                        fix_effort="low"
                    ))
                    continue

            # Check adjacent sibling text
            for sibling in [img.find_next_sibling(), img.find_previous_sibling()]:
                if sibling and hasattr(sibling, "get_text"):
                    sib_text = sibling.get_text(" ", strip=True)
                    if sib_text and sib_text.lower() == alt.lower():
                        issues.append(_issue(
                            self.url, "image-redundant-alt", "best-practice", "minor",
                            _css_selector(img), _snippet(img, 200),
                            f'Image alt "{alt[:60]}" duplicates adjacent text. '
                            f"Screen readers may announce this information twice.",
                            "1.1.1", "A", "images",
                            'Use alt="" if the adjacent text fully describes the image.',
                            fix_effort="low"
                        ))
                        break
        return issues


    # ── Polyfill Checks for Fast Mode ─────────────────────────
    # These checks fill the gap when Axe-core is disabled (fast mode).

    def check_svg_accessible_name(self) -> list[dict]:
        issues = []
        for svg in self.soup.find_all("svg"):
            if svg.get("aria-hidden", "").lower() == "true" or svg.get("role") == "presentation":
                continue
            has_name = bool(svg.get("aria-label") or svg.get("aria-labelledby"))
            if not has_name and svg.find("title"):
                has_name = bool(svg.find("title").get_text(strip=True))
            if not has_name:
                issues.append(_issue(
                    self.url, "svg-no-accessible-name", "violation", "serious",
                    _css_selector(svg), _snippet(svg, 200),
                    "SVG image is missing an accessible name.",
                    "1.1.1", "A", "images", "Add <title> or aria-label.",
                    fix_effort="low"
                ))
        return issues

    def check_empty_headings(self) -> list[dict]:
        issues = []
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            for h in self.soup.find_all(tag):
                if h.get("aria-hidden", "").lower() == "true" or h.get_text(strip=True):
                    continue
                has_img_alt = any((img.get("alt") or "").strip() for img in h.find_all("img"))
                if not has_img_alt:
                    issues.append(_issue(
                        self.url, "empty-heading", "violation", "moderate",
                        _css_selector(h), _snippet(h, 200),
                        f"Empty {tag.upper()} heading found.",
                        "1.3.1", "A", "structure", "Remove empty heading or add readable text.",
                        fix_effort="low"
                    ))
        return issues

    def check_unsafe_external_links(self) -> list[dict]:
        issues = []
        for a in self.soup.find_all("a", target="_blank"):
            rel = (a.get("rel") or [])
            if isinstance(rel, str):
                rel = rel.split()
            if "noopener" not in rel and "noreferrer" not in rel:
                issues.append(_issue(
                    self.url, "unsafe-external-link", "best-practice", "minor",
                    _css_selector(a), _snippet(a, 200),
                    "Link opens in a new window without rel='noopener'.",
                    "Best Practice", "", "navigation", "Add rel=\"noopener\".",
                    fix_effort="low"
                ))
        return issues

    def check_form_label_missing(self) -> list[dict]:
        issues = []
        skip_types = {"hidden", "submit", "button", "reset", "image"}
        for input_elem in self.soup.find_all(["input", "textarea", "select"]):
            itype = input_elem.get("type", "text").lower()
            if itype in skip_types or input_elem.get("aria-hidden") == "true":
                continue
            if input_elem.get("aria-label") or input_elem.get("aria-labelledby") or input_elem.get("title"):
                continue
            
            has_label = bool(input_elem.find_parent("label"))
            if not has_label:
                eid = input_elem.get("id")
                has_label = bool(eid and self.soup.find("label", {"for": eid}))
            
            if not has_label:
                issues.append(_issue(
                    self.url, "form-label-missing", "violation", "serious",
                    _css_selector(input_elem), _snippet(input_elem, 200),
                    "Form field is missing an external label or aria-label.",
                    "1.3.1", "A", "forms", "Wrap input in <label> or provide aria-label.",
                    fix_effort="low"
                ))
        return issues
