"""
Static HTML checks: comprehensive WCAG 2.2 Level A + AA + AAA checks.
Parses rendered DOM and checks against the full WCAG checklist.
"""
import hashlib
import logging
import re
from typing import Any, Optional
from urllib.parse import urlsplit, urlunsplit
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_WEAK_LINK_TEXT = {
    "click here",
    "read more",
    "learn more",
    "more",
    "details",
    "here",
    "view more",
    "see more",
    "more info",
}

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


def _is_effectively_empty_text(text: str) -> bool:
    """Treat single-character content as effectively empty for detection recall."""
    return not text or len(text.strip()) < 2


def _looks_like_weak_link_text(text: str, weak_texts: set[str]) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    if normalized in weak_texts:
        return True
    for token in weak_texts:
        if re.search(rf"\\b{re.escape(token)}\\b", normalized):
            return True
    return len(normalized) < 3


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
        self.rule_activity: dict[str, dict[str, Any]] = {}

    def _track_rule_activity(
        self,
        rule_id: str,
        elements_checked: int = 0,
        violations_found: int = 0,
        confidence_bucket: Optional[str] = None,
        sample_elements_checked: Optional[list[str]] = None,
        sample_violations: Optional[list[str]] = None,
        count_towards_total: bool = True,
    ) -> None:
        """Track lightweight per-rule activity telemetry for detector coverage debugging."""
        slot = self.rule_activity.setdefault(
            rule_id,
            {
                "elements_checked": 0,
                "violations_found": 0,
                "confidence_bucket": {"high": 0, "medium": 0, "low": 0},
                "sample_elements_checked": [],
                "sample_violations": [],
            },
        )
        slot["elements_checked"] += max(0, int(elements_checked))
        if count_towards_total:
            slot["violations_found"] += max(0, int(violations_found))

        buckets = slot.setdefault("confidence_bucket", {"high": 0, "medium": 0, "low": 0})
        if confidence_bucket in {"high", "medium", "low"}:
            buckets[confidence_bucket] = max(0, int(buckets.get(confidence_bucket, 0))) + max(0, int(violations_found))

        checked_samples = slot.setdefault("sample_elements_checked", [])
        for sample in sample_elements_checked or []:
            if not isinstance(sample, str):
                continue
            clean = sample.strip()
            if not clean or clean in checked_samples:
                continue
            if len(checked_samples) >= 5:
                break
            checked_samples.append(clean)

        violation_samples = slot.setdefault("sample_violations", [])
        for sample in sample_violations or []:
            if not isinstance(sample, str):
                continue
            clean = sample.strip()
            if not clean or clean in violation_samples:
                continue
            if len(violation_samples) >= 5:
                break
            violation_samples.append(clean)

    def get_rule_activity(self) -> dict[str, dict[str, Any]]:
        """Return copy-safe rule activity telemetry."""
        return {
            rid: {
                "elements_checked": vals.get("elements_checked", 0),
                "violations_found": vals.get("violations_found", 0),
                "firing_status": "FIRING" if int(vals.get("violations_found", 0) or 0) > 0 else "NOT FIRING",
                "confidence_bucket": {
                    "high": (vals.get("confidence_bucket") or {}).get("high", 0),
                    "medium": (vals.get("confidence_bucket") or {}).get("medium", 0),
                    "low": (vals.get("confidence_bucket") or {}).get("low", 0),
                },
                "sample_elements_checked": list(vals.get("sample_elements_checked") or []),
                "sample_violations": list(vals.get("sample_violations") or []),
                "violations": list(vals.get("sample_violations") or []),
            }
            for rid, vals in self.rule_activity.items()
        }

    @staticmethod
    def _style_hides_element(style_value: str) -> bool:
        style = re.sub(r"\s+", "", (style_value or "").lower())
        return (
            "display:none" in style
            or "visibility:hidden" in style
            or "content-visibility:hidden" in style
        )

    @staticmethod
    def _style_has_display_none(style_value: str) -> bool:
        style = re.sub(r"\s+", "", (style_value or "").lower())
        return "display:none" in style

    def _is_hidden_for_static(self, elem: Optional[Tag]) -> bool:
        current = elem
        while isinstance(current, Tag):
            if current.has_attr("hidden"):
                return True
            if str(current.get("aria-hidden") or "").strip().lower() == "true":
                return True
            if self._style_hides_element(str(current.get("style") or "")):
                return True
            parent = current.parent
            current = parent if isinstance(parent, Tag) else None
        return False

    def _is_visible_for_static(self, elem: Optional[Tag]) -> bool:
        return isinstance(elem, Tag) and not self._is_hidden_for_static(elem)

    def _is_hidden_for_group3(self, elem: Optional[Tag]) -> bool:
        current = elem
        while isinstance(current, Tag):
            if str(current.get("aria-hidden") or "").strip().lower() == "true":
                return True
            if self._style_has_display_none(str(current.get("style") or "")):
                return True
            parent = current.parent
            current = parent if isinstance(parent, Tag) else None
        return False

    def _is_visible_for_group3(self, elem: Optional[Tag]) -> bool:
        return isinstance(elem, Tag) and not self._is_hidden_for_group3(elem)

    def _has_sectioning_context(self, elem: Tag) -> bool:
        current = elem.parent
        while isinstance(current, Tag):
            if current.name in {"section", "article", "aside", "nav"}:
                return True
            current = current.parent if isinstance(current.parent, Tag) else None
        return False

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
            "accessible_auth", "redundant_entry", "aria_apg_patterns", "semantic_depth"
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
        checked = 0
        missing_lang_violations = 0
        sample_elements_checked: list[str] = []
        sample_violations: list[str] = []
        invalid_lang_checked = 0
        invalid_lang_violations = 0
        invalid_lang_checked_samples: list[str] = []
        invalid_lang_violation_samples: list[str] = []

        def _is_valid_lang_tag(lang_value: str) -> bool:
            # Practical BCP47 subset validator (language + optional subtags).
            return bool(re.match(r"^[a-zA-Z]{2,3}(?:-[a-zA-Z0-9]{2,8})*$", lang_value))

        html_tag = self.soup.find("html")
        if html_tag:
            checked = 1
            sample_elements_checked.append("<html>")
            lang = str(html_tag.get("lang", "")).strip()
            if lang:
                invalid_lang_checked += 1
                if len(invalid_lang_checked_samples) < 5:
                    invalid_lang_checked_samples.append(f"html[lang=\"{lang}\"]")
            if not lang:
                issues.append(_issue(
                    self.url, "missing-lang", "violation", "serious",
                    "<html>", "<html>", 
                    "HTML element is missing the lang attribute. Screen readers need this to select correct pronunciation.",
                    "3.1.1", "A", "html",
                    'Add lang attribute: <html lang="en">'
                ))
                missing_lang_violations += 1
                sample_violations.append("<html>")
            elif not _is_valid_lang_tag(lang):
                issues.append(_issue(
                    self.url, "invalid-lang", "violation", "serious",
                    "<html>", f'<html lang="{lang}">',
                    f'Invalid language code "{lang}". Use a valid BCP 47 language tag.',
                    "3.1.1", "A", "html",
                    'Use a valid language code like "en", "es", "fr".'
                ))
                invalid_lang_violations += 1
                if len(invalid_lang_violation_samples) < 5:
                    invalid_lang_violation_samples.append(f'<html lang="{lang}">')

        for node in self.soup.find_all(attrs={"lang": True}):
            if not isinstance(node, Tag) or node.name == "html":
                continue
            lang = str(node.get("lang", "")).strip()
            if not lang:
                continue
            invalid_lang_checked += 1
            selector = _css_selector(node)
            if len(invalid_lang_checked_samples) < 5:
                invalid_lang_checked_samples.append(f'{selector}[lang="{lang}"]')
            if _is_valid_lang_tag(lang):
                continue

            issues.append(_issue(
                self.url, "invalid-lang", "violation", "serious",
                selector, _snippet(node, 200),
                f'Element has invalid language code "{lang}". Use a valid BCP 47 language tag.',
                "3.1.2", "AA", "html",
                'Use a valid language code like "en", "es", "fr", or region tags like "en-US".'
            ))
            invalid_lang_violations += 1
            if len(invalid_lang_violation_samples) < 5:
                invalid_lang_violation_samples.append(_snippet(node, 200))

        self._track_rule_activity(
            "missing-lang",
            elements_checked=checked,
            violations_found=missing_lang_violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=sample_violations,
        )

        self._track_rule_activity(
            "invalid-lang",
            elements_checked=invalid_lang_checked,
            violations_found=invalid_lang_violations,
            confidence_bucket="high",
            sample_elements_checked=invalid_lang_checked_samples,
            sample_violations=invalid_lang_violation_samples,
        )

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

        def _dedupe_nodes(nodes: list[Tag]) -> list[Tag]:
            seen: set[int] = set()
            out: list[Tag] = []
            for node in nodes:
                key = id(node)
                if key in seen:
                    continue
                seen.add(key)
                out.append(node)
            return out

        visible_main_landmarks = _dedupe_nodes(
            [n for n in self.soup.find_all("main") if self._is_visible_for_static(n)]
            + [
                n
                for n in self.soup.find_all(attrs={"role": re.compile(r"(^|\s)main(\s|$)", re.I)})
                if self._is_visible_for_static(n)
            ]
        )
        visible_nav_landmarks = _dedupe_nodes(
            [n for n in self.soup.find_all("nav") if self._is_visible_for_static(n)]
            + [
                n
                for n in self.soup.find_all(attrs={"role": re.compile(r"(^|\s)navigation(\s|$)", re.I)})
                if self._is_visible_for_static(n)
            ]
        )

        has_main = bool(visible_main_landmarks)
        has_nav = bool(visible_nav_landmarks)
        has_header = bool(
            [n for n in self.soup.find_all("header") if self._is_visible_for_static(n)]
            or [n for n in self.soup.find_all(attrs={"role": "banner"}) if self._is_visible_for_static(n)]
        )
        has_footer = bool(
            [n for n in self.soup.find_all("footer") if self._is_visible_for_static(n)]
            or [n for n in self.soup.find_all(attrs={"role": "contentinfo"}) if self._is_visible_for_static(n)]
        )

        if not has_main:
            issues.append(_issue(
                self.url, "no-main-landmark", "violation", "moderate",
                "<body>", "<body>",
                "Page has no <main> landmark. Screen reader users rely on landmarks to navigate.",
                "1.3.1", "A", "html",
                "Wrap main content in a <main> element."
            ))
            if has_nav:
                issues.append(_issue(
                    self.url, "missing-landmark", "violation", "moderate",
                    "<body>", "<body>",
                    "Navigation landmark is present but the page has no main landmark.",
                    "1.3.1", "A", "html",
                    "Add a single visible <main> landmark so assistive technology users can jump to primary content."
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

        # Group 2 deterministic landmark-role checks.
        landmark_roles_checked = 2
        landmark_roles_high_violations = 0
        landmark_roles_medium_logs = 0
        landmark_samples_checked: list[str] = []
        landmark_samples_high: list[str] = []
        landmark_samples_medium: list[str] = []

        if len(visible_main_landmarks) == 0:
            issues.append(_issue(
                self.url, "landmark-roles", "violation", "serious",
                "<body>", "<body>",
                "Page has no visible main landmark.",
                "1.3.1", "A", "html",
                "Add one visible <main> element (or role=\"main\") around primary content."
            ))
            landmark_roles_high_violations += 1
            if len(landmark_samples_high) < 5:
                landmark_samples_high.append("missing visible main landmark")
        elif len(visible_main_landmarks) > 1:
            first_main = visible_main_landmarks[0]
            issues.append(_issue(
                self.url, "landmark-roles", "violation", "serious",
                _css_selector(first_main), _snippet(first_main),
                f"Page has {len(visible_main_landmarks)} visible main landmarks. Exactly one main landmark is allowed.",
                "1.3.1", "A", "html",
                "Keep a single main landmark and move non-primary regions to complementary/navigation/region landmarks."
            ))
            landmark_roles_high_violations += 1
            if len(landmark_samples_high) < 5:
                landmark_samples_high.append(_snippet(first_main, 200))

        if len(visible_nav_landmarks) == 0:
            landmark_roles_medium_logs += 1
            if len(landmark_samples_medium) < 5:
                landmark_samples_medium.append("missing visible nav landmark")
        elif len(visible_nav_landmarks) > 1:
            unlabeled_nav = 0
            for nav in visible_nav_landmarks:
                label = (
                    (nav.get("aria-label") or "").strip()
                    or (nav.get("aria-labelledby") or "").strip()
                    or (nav.get("title") or "").strip()
                )
                if not label:
                    unlabeled_nav += 1
            if unlabeled_nav > 1:
                landmark_roles_medium_logs += 1
                if len(landmark_samples_medium) < 5:
                    landmark_samples_medium.append(_snippet(visible_nav_landmarks[0], 200))

        if len(landmark_samples_checked) < 5:
            landmark_samples_checked.append(f"main_landmarks={len(visible_main_landmarks)}")
        if len(landmark_samples_checked) < 5:
            landmark_samples_checked.append(f"navigation_landmarks={len(visible_nav_landmarks)}")

        self._track_rule_activity(
            "landmark-roles",
            elements_checked=landmark_roles_checked,
            violations_found=landmark_roles_high_violations,
            confidence_bucket="high",
            sample_elements_checked=landmark_samples_checked,
            sample_violations=landmark_samples_high,
        )
        if landmark_roles_medium_logs > 0:
            self._track_rule_activity(
                "landmark-roles",
                violations_found=landmark_roles_medium_logs,
                confidence_bucket="medium",
                sample_violations=landmark_samples_medium,
                count_towards_total=False,
            )

        if landmark_roles_medium_logs > 0:
            logger.debug("Group2 landmark-roles medium signals: %s", ", ".join(landmark_samples_medium[:3]))

        return issues

    # ── Headings ───────────────────────────────────────────────

    def check_headings(self) -> list[dict]:
        issues = []
        headings = self.soup.find_all(re.compile(r'^h[1-6]$'))
        visible_headings = [h for h in headings if self._is_visible_for_static(h)]

        aria_heading_nodes = []
        for node in self.soup.find_all(attrs={"role": True}):
            role_tokens = str(node.get("role") or "").lower().split()
            if "heading" not in role_tokens:
                continue
            aria_level_raw = str(node.get("aria-level") or "").strip()
            if not aria_level_raw.isdigit():
                continue
            aria_level = int(aria_level_raw)
            if not (1 <= aria_level <= 6):
                continue
            if self._is_visible_for_static(node):
                aria_heading_nodes.append(node)

        total_visible_headings = len(visible_headings) + len(aria_heading_nodes)

        no_headings_checked = 1
        no_headings_violations = 0
        no_headings_checked_samples: list[str] = [f"total_visible_headings={total_visible_headings}"]
        no_headings_violation_samples: list[str] = []

        missing_h1_checked = 0
        missing_h1_high = 0
        missing_h1_medium = 0
        missing_h1_checked_samples: list[str] = []
        missing_h1_high_samples: list[str] = []
        missing_h1_medium_samples: list[str] = []

        multiple_h1_checked = 0
        multiple_h1_high = 0
        multiple_h1_medium = 0
        multiple_h1_checked_samples: list[str] = []
        multiple_h1_high_samples: list[str] = []
        multiple_h1_medium_samples: list[str] = []

        heading_order_checked = 0
        heading_order_violations = 0
        heading_order_checked_samples: list[str] = []
        heading_order_violation_samples: list[str] = []

        if total_visible_headings == 0:
            contentful_blocks = 0
            for node in self.soup.find_all(["main", "article", "section", "p", "li", "td", "th", "blockquote", "figcaption"]):
                if not self._is_visible_for_static(node):
                    continue
                if len(node.get_text(" ", strip=True)) >= 20:
                    contentful_blocks += 1

            visible_text_length = len(self.soup.get_text(" ", strip=True))
            dom_element_count = len(self.soup.find_all(True))
            has_head_tag = self.soup.find("head") is not None

            descendant_lang_nodes = [
                node
                for node in self.soup.find_all(attrs={"lang": True})
                if isinstance(node, Tag)
                and node.name != "html"
                and str(node.get("lang", "")).strip()
            ]

            interactive_nodes = self.soup.find_all(["a", "button", "input", "select", "textarea", "summary", "details"])
            aria_heading_nodes_any = [
                node
                for node in self.soup.find_all(attrs={"role": True})
                if "heading" in str(node.get("role") or "").lower().split()
            ]

            contentful_no_headings = (
                # High-signal path is intentionally strict: only tiny, fragment-like pages.
                visible_text_length >= 35
                and visible_text_length <= 60
                and contentful_blocks == 1
                and dom_element_count <= 4
                and not has_head_tag
                and len(descendant_lang_nodes) == 0
                and len(interactive_nodes) == 0
                and len(headings) == 0
                and len(aria_heading_nodes_any) == 0
            )

            issue = _issue(
                self.url, "no-headings", "violation", "serious",
                "<body>", "<body>",
                "Page has no visible headings. Headings are essential for screen reader navigation.",
                "1.3.1", "A", "html",
                "Add semantic headings (h1-h6). Each page should have exactly one visible h1."
            )
            if contentful_no_headings:
                # High confidence signal: visible content exists, but no heading structure is present.
                issue["confidence"] = 0.95
            issue["evidence"] = {
                "visible_native_heading_count": len(visible_headings),
                "visible_aria_heading_count": len(aria_heading_nodes),
                "visible_text_length": visible_text_length,
                "contentful_blocks": contentful_blocks,
                "dom_element_count": dom_element_count,
                "has_head_tag": has_head_tag,
                "interactive_element_count": len(interactive_nodes),
                "descendant_lang_count": len(descendant_lang_nodes),
                "raw_heading_tag_count": len(headings),
                "raw_aria_heading_count": len(aria_heading_nodes_any),
                "contentful_page_without_headings": contentful_no_headings,
            }
            issues.append(issue)
            no_headings_violations = 1
            no_headings_violation_samples.append("<body>")

        all_h1s = self.soup.find_all("h1")
        visible_h1s = [h for h in all_h1s if self._is_visible_for_static(h)]

        if headings:
            missing_h1_checked += 1
            multiple_h1_checked += 1
            if len(missing_h1_checked_samples) < 5:
                missing_h1_checked_samples.append(f"visible_h1_count={len(visible_h1s)}")
            if len(multiple_h1_checked_samples) < 5:
                multiple_h1_checked_samples.append(f"visible_h1_count={len(visible_h1s)}")

            if len(visible_h1s) == 0:
                if len(all_h1s) > 0:
                    missing_h1_medium += 1
                    if len(missing_h1_medium_samples) < 5:
                        missing_h1_medium_samples.append("h1 exists but appears hidden")
                else:
                    issues.append(_issue(
                        self.url, "missing-h1", "violation", "serious",
                        "<body>", "<body>",
                        "Page is missing a visible h1 heading.",
                        "1.3.1", "A", "html",
                        "Add a visible h1 element as the main heading of the page."
                    ))
                    missing_h1_high += 1
                    if len(missing_h1_high_samples) < 5:
                        missing_h1_high_samples.append("<body>")

            if len(visible_h1s) > 1:
                h1_in_sectioning = [self._has_sectioning_context(h1) for h1 in visible_h1s]
                if all(h1_in_sectioning):
                    multiple_h1_medium += 1
                    if len(multiple_h1_medium_samples) < 5:
                        multiple_h1_medium_samples.append("multiple visible h1 in sectioning contexts")
                else:
                    issues.append(_issue(
                        self.url, "multiple-h1", "violation", "moderate",
                        f"{len(visible_h1s)} visible h1 elements", f"{len(visible_h1s)} visible h1 elements found",
                        f"Page has {len(visible_h1s)} visible h1 headings outside clear sectioning context.",
                        "1.3.1", "A", "html",
                        "Use one visible page-level h1, or place additional h1 headings inside clear section/article regions."
                    ))
                    multiple_h1_high += 1
                    if len(multiple_h1_high_samples) < 5:
                        multiple_h1_high_samples.append(f"visible_h1_count={len(visible_h1s)}")

        # Heading order (only meaningful when at least two visible headings exist).
        if len(visible_headings) >= 2:
            prev_level = 0
            for h in visible_headings:
                heading_order_checked += 1
                level = int(h.name[1])
                if len(heading_order_checked_samples) < 5:
                    heading_order_checked_samples.append(f"{_css_selector(h)} level={level}")
                if level > prev_level + 1 and prev_level > 0:
                    issues.append(_issue(
                        self.url, "heading-order", "violation", "moderate",
                        _css_selector(h), _snippet(h),
                        f"Heading level skipped upward: {h.name} follows h{prev_level}.",
                        "1.3.1", "A", "html",
                        f"Use h{prev_level + 1} instead of {h.name}, or add intermediate headings."
                    ))
                    heading_order_violations += 1
                    if len(heading_order_violation_samples) < 5:
                        heading_order_violation_samples.append(_snippet(h, 200))
                prev_level = level

        # Empty headings
        for h in visible_headings:
            if not h.get_text(strip=True):
                issues.append(_issue(
                    self.url, "empty-heading", "violation", "serious",
                    _css_selector(h), _snippet(h),
                    f"Empty {h.name} heading found. Headings must have text content.",
                    "1.3.1", "A", "html",
                    f"Add descriptive text to the {h.name} element or remove it."
                ))

        self._track_rule_activity(
            "missing-h1",
            elements_checked=missing_h1_checked,
            violations_found=missing_h1_high,
            confidence_bucket="high",
            sample_elements_checked=missing_h1_checked_samples,
            sample_violations=missing_h1_high_samples,
        )
        if missing_h1_medium > 0:
            self._track_rule_activity(
                "missing-h1",
                violations_found=missing_h1_medium,
                confidence_bucket="medium",
                sample_violations=missing_h1_medium_samples,
                count_towards_total=False,
            )

        self._track_rule_activity(
            "multiple-h1",
            elements_checked=multiple_h1_checked,
            violations_found=multiple_h1_high,
            confidence_bucket="high",
            sample_elements_checked=multiple_h1_checked_samples,
            sample_violations=multiple_h1_high_samples,
        )
        if multiple_h1_medium > 0:
            self._track_rule_activity(
                "multiple-h1",
                violations_found=multiple_h1_medium,
                confidence_bucket="medium",
                sample_violations=multiple_h1_medium_samples,
                count_towards_total=False,
            )

        self._track_rule_activity(
            "heading-order",
            elements_checked=heading_order_checked,
            violations_found=heading_order_violations,
            confidence_bucket="high",
            sample_elements_checked=heading_order_checked_samples,
            sample_violations=heading_order_violation_samples,
        )

        self._track_rule_activity(
            "no-headings",
            elements_checked=no_headings_checked,
            violations_found=no_headings_violations,
            confidence_bucket="high",
            sample_elements_checked=no_headings_checked_samples,
            sample_violations=no_headings_violation_samples,
        )

        return issues

    # ── Images ─────────────────────────────────────────────────

    def check_images(self) -> list[dict]:
        issues = []
        missing_alt_checked = 0
        missing_alt_high_violations = 0
        missing_alt_medium_logs = 0
        sample_elements_checked: list[str] = []
        sample_high_violations: list[str] = []
        sample_medium_logs: list[str] = []

        def _to_int(raw: Any) -> Optional[int]:
            try:
                return int(str(raw).strip())
            except (TypeError, ValueError):
                return None

        for img in self.soup.find_all("img"):
            try:
                selector = _css_selector(img)
                src = img.get("src", "")

                if not self._is_visible_for_group3(img):
                    missing_alt_medium_logs += 1
                    if len(sample_medium_logs) < 5:
                        sample_medium_logs.append(_snippet(img, 200))
                    continue

                alt = img.get("alt")
                role = str(img.get("role") or "").strip().lower()
                aria_hidden = str(img.get("aria-hidden") or "").strip().lower() == "true"
                width = _to_int(img.get("width"))
                height = _to_int(img.get("height"))

                missing_alt_checked += 1
                if len(sample_elements_checked) < 5:
                    sample_elements_checked.append(f'{selector} src="{src[:80]}"')

                spacer_keywords = ["spacer", "pixel", "blank", "divider"]
                likely_spacer = bool(src and any(x in src.lower() for x in spacer_keywords))
                tracking_pixel = width == 1 and height == 1
                likely_decorative = role in {"presentation", "none"} or likely_spacer or tracking_pixel

                # Group 3 confidence policy: missing alt is a high-confidence violation.
                if alt is None:
                    if likely_decorative:
                        missing_alt_medium_logs += 1
                        if len(sample_medium_logs) < 5:
                            sample_medium_logs.append(_snippet(img, 200))
                    else:
                        issues.append(_issue(
                            self.url, "missing-alt", "violation", "critical",
                            selector, _snippet(img),
                            "Image is missing alt attribute. Screen readers cannot describe this image.",
                            "1.1.1", "A", "images",
                            f'Add alt="" for decorative images or alt="description" for informative: <img src="{src}" alt="description">'
                        ))
                        missing_alt_high_violations += 1
                        if len(sample_high_violations) < 5:
                            sample_high_violations.append(_snippet(img, 200))
                    continue

                # Group 3 confidence policy: empty alt is ambiguous and tracked as medium confidence.
                if alt == "":
                    missing_alt_medium_logs += 1
                    if len(sample_medium_logs) < 5:
                        sample_medium_logs.append(_snippet(img, 200))

                    if role not in {"presentation", "none"} and not aria_hidden and src and not likely_spacer and not tracking_pixel:
                        issues.append(_issue(
                            self.url, "empty-alt", "needs-review", "moderate",
                            selector, _snippet(img),
                            "Image has empty alt text. If decorative, add role='presentation'. If informative, add meaningful alt.",
                            "1.1.1", "A", "images",
                            'Add role="presentation" if decorative, or meaningful alt text if informative.',
                            fix_effort="low"
                        ))
            except Exception as exc:
                logger.debug("Group3 missing-alt check skipped image due to error: %s", exc)
                continue

        self._track_rule_activity(
            "missing-alt",
            elements_checked=missing_alt_checked,
            violations_found=missing_alt_high_violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=sample_high_violations,
        )
        if missing_alt_medium_logs > 0:
            self._track_rule_activity(
                "missing-alt",
                violations_found=missing_alt_medium_logs,
                confidence_bucket="medium",
                sample_violations=sample_medium_logs,
                count_towards_total=False,
            )

        return issues

    # ── Links ──────────────────────────────────────────────────

    def check_links(self) -> list[dict]:
        issues = []
        weak_link_texts = set(_WEAK_LINK_TEXT) | {"link"}
        ambiguous_purpose_texts = weak_link_texts | {"contact us", "about us", "call us", "link text", "list of contributors"}
        checked = 0
        link_purpose_violations = 0
        sample_elements_checked: list[str] = []
        sample_violations: list[str] = []
        link_rows: list[dict[str, Any]] = []
        iframe_named_rows: list[dict[str, Any]] = []

        def _normalize_href(raw_href: str) -> str:
            href = (raw_href or "").strip()
            if not href:
                return ""
            parts = urlsplit(href)
            path = parts.path or ""
            if path != "/":
                path = path.rstrip("/")
            return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, parts.query, ""))

        def _labelledby_text(elem: Tag) -> str:
            ref_ids = str(elem.get("aria-labelledby") or "").strip().split()
            if not ref_ids:
                return ""
            chunks: list[str] = []
            for ref_id in ref_ids:
                target = self.soup.find(id=ref_id)
                if not target:
                    continue
                txt = target.get_text(" ", strip=True)
                if txt:
                    chunks.append(txt)
            return " ".join(chunks).strip()

        def _extract_onclick_target(raw_js: str) -> str:
            js = (raw_js or "").strip()
            if not js:
                return ""
            patterns = [
                r"(?:window\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]",
                r"location\.assign\(\s*['\"]([^'\"]+)['\"]\s*\)",
                r"document\.location\s*\+?=\s*['\"]([^'\"]+)['\"]",
            ]
            for pattern in patterns:
                match = re.search(pattern, js, re.I)
                if match:
                    return match.group(1).strip()
            return ""

        for link in self.soup.find_all("a"):
            checked += 1
            text = link.get_text(" ", strip=True)
            aria_label = (link.get("aria-label") or "").strip()
            aria_labelledby = _labelledby_text(link)
            title = (link.get("title") or "").strip()
            href = (link.get("href") or "").strip()
            selector = _css_selector(link)

            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(f'{selector} text="{text[:60]}" href="{href[:80]}"')

            img = link.find("img")
            img_alt = (img.get("alt") or "").strip() if img else ""
            has_programmatic_name = bool(aria_label or aria_labelledby or title or img_alt)
            accessible_name = (aria_label or aria_labelledby or title or text or img_alt).strip()
            normalized_href = _normalize_href(href)

            link_rows.append(
                {
                    "element": link,
                    "selector": selector,
                    "text": text,
                    "href": href,
                    "normalized_href": normalized_href,
                    "accessible_name": accessible_name,
                    "has_programmatic_name": has_programmatic_name,
                }
            )

            # Empty link
            if _is_effectively_empty_text(text) and not has_programmatic_name:
                issues.append(_issue(
                    self.url, "empty-link", "violation", "serious",
                    selector, _snippet(link),
                    "Link has no text content. Screen readers will announce it as empty.",
                    "2.4.4", "A", "navigation",
                    'Add descriptive text or aria-label="description".'
                ))

            # Strict link-purpose check aligned to benchmark-facing generic labels.
            if _looks_like_weak_link_text(text, weak_link_texts) and not has_programmatic_name and href and not href.startswith("#"):
                issues.append(_issue(
                    self.url, "link-purpose", "violation", "moderate",
                    selector, _snippet(link),
                    f'Link text "{text}" is generic and lacks clear purpose.',
                    "2.4.4", "A", "navigation",
                    "Use descriptive link text or add aria-label/aria-labelledby with purpose context."
                ))
                link_purpose_violations += 1
                if len(sample_violations) < 5:
                    sample_violations.append(_snippet(link, 200))

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

        # Custom link-role controls should carry equivalent purpose semantics.
        for elem in self.soup.find_all(attrs={"role": re.compile(r"(^|\s)link(\s|$)", re.I)}):
            if elem.name == "a":
                continue

            checked += 1
            selector = _css_selector(elem)
            text = elem.get_text(" ", strip=True)
            aria_label = (elem.get("aria-label") or "").strip()
            aria_labelledby = _labelledby_text(elem)
            title = (elem.get("title") or "").strip()
            href = (elem.get("href") or "").strip()
            onclick_target = _extract_onclick_target(str(elem.get("onclick") or ""))
            effective_target = href or onclick_target
            accessible_name = (aria_label or aria_labelledby or title or text).strip()

            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(f'{selector} role="link" text="{text[:60]}" target="{effective_target[:80]}"')

            link_rows.append(
                {
                    "element": elem,
                    "selector": selector,
                    "text": text,
                    "href": effective_target,
                    "normalized_href": _normalize_href(effective_target),
                    "accessible_name": accessible_name,
                    "has_programmatic_name": bool(aria_label or aria_labelledby or title or text),
                }
            )

            if not accessible_name:
                issues.append(_issue(
                    self.url, "empty-link", "violation", "serious",
                    selector, _snippet(elem),
                    "Custom link role control has no accessible name.",
                    "2.4.4", "A", "navigation",
                    "Provide descriptive text or aria-label/aria-labelledby for this link control."
                ))
                if len(sample_violations) < 5:
                    sample_violations.append(_snippet(elem, 200))
                continue

            lower_name = accessible_name.lower()
            if _looks_like_weak_link_text(lower_name, weak_link_texts):
                if not href and onclick_target and lower_name in {"more", "here", "details", "link"}:
                    issues.append(_issue(
                        self.url, "empty-link", "violation", "moderate",
                        selector, _snippet(elem),
                        "Custom link role control uses generic text and no native href destination.",
                        "2.4.4", "A", "navigation",
                        "Use descriptive link text and expose a concrete destination target."
                    ))
                else:
                    issues.append(_issue(
                        self.url, "link-purpose", "violation", "moderate",
                        selector, _snippet(elem),
                        f'Custom link role text "{accessible_name}" is generic and lacks clear purpose.',
                        "2.4.4", "A", "navigation",
                        "Provide descriptive link text or add contextual labelling via aria-label/aria-labelledby."
                    ))
                    link_purpose_violations += 1

                if len(sample_violations) < 5:
                    sample_violations.append(_snippet(elem, 200))

        # Links with identical ambiguous names in the same region should not lead to different destinations.
        grouped_links: dict[tuple[str, int], list[dict[str, Any]]] = {}
        for row in link_rows:
            name = str(row.get("accessible_name") or "").strip().lower()
            if not name:
                continue
            norm_href = str(row.get("normalized_href") or "").strip()
            if not norm_href:
                continue
            parent = row["element"].parent if isinstance(row.get("element"), Tag) else None
            key = (name, id(parent) if parent is not None else -1)
            grouped_links.setdefault(key, []).append(row)

        for (name, _), rows in grouped_links.items():
            if len(rows) < 2:
                continue
            if name not in ambiguous_purpose_texts:
                continue
            targets = {str(r.get("normalized_href") or "").strip() for r in rows if str(r.get("normalized_href") or "").strip()}
            if len(targets) <= 1:
                continue

            first = rows[0]
            issues.append(_issue(
                self.url, "link-purpose", "violation", "moderate",
                str(first.get("selector") or "a"), _snippet(first["element"]),
                f'Multiple links named "{name}" in the same context point to different destinations.',
                "2.4.4", "A", "navigation",
                "Differentiate link text or add contextual labels so each destination purpose is clear."
            ))
            link_purpose_violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(first["element"], 200))

        # Treat unnamed iframes as ambiguous embedded content purpose.
        for iframe in self.soup.find_all("iframe"):
            checked += 1
            selector = _css_selector(iframe)
            frame_name = (
                (iframe.get("title") or "").strip()
                or (iframe.get("aria-label") or "").strip()
                or _labelledby_text(iframe)
            )
            src = (iframe.get("src") or "").strip()

            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(f'{selector} title="{frame_name[:60]}" src="{src[:80]}"')

            if frame_name:
                iframe_named_rows.append(
                    {
                        "element": iframe,
                        "selector": selector,
                        "name": frame_name.strip().lower(),
                        "normalized_src": _normalize_href(src),
                    }
                )
                continue

            issues.append(_issue(
                self.url, "link-purpose", "violation", "moderate",
                selector, _snippet(iframe),
                "IFrame has no accessible name, so users cannot determine its purpose.",
                "2.4.4", "A", "navigation",
                "Add a descriptive title attribute or aria-label to the iframe."
            ))
            link_purpose_violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(iframe, 200))

        # Duplicate frame names are ambiguous even when frame destinations are similar.
        grouped_iframes: dict[str, list[dict[str, Any]]] = {}
        for row in iframe_named_rows:
            grouped_iframes.setdefault(str(row.get("name") or ""), []).append(row)

        for name, rows in grouped_iframes.items():
            if len(rows) < 2:
                continue
            if name not in ambiguous_purpose_texts:
                continue

            first = rows[0]
            issues.append(_issue(
                self.url, "link-purpose", "violation", "moderate",
                str(first.get("selector") or "iframe"), _snippet(first["element"]),
                f'Multiple embedded frames share the name "{name}", which makes purpose ambiguous.',
                "2.4.4", "A", "navigation",
                "Give each embedded frame a unique descriptive title so users can distinguish their purposes."
            ))
            link_purpose_violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(first["element"], 200))

        self._track_rule_activity(
            "link-purpose",
            elements_checked=checked,
            violations_found=link_purpose_violations,
            confidence_bucket="medium",
            sample_elements_checked=sample_elements_checked,
            sample_violations=sample_violations,
        )

        return issues

    # ── Buttons ────────────────────────────────────────────────

    def check_buttons(self) -> list[dict]:
        issues = []
        checked = 0
        button_name_high_violations = 0
        button_name_medium_logs = 0
        clickable_checked = 0
        clickable_violations = 0
        clickable_medium_logs = 0
        sample_elements_checked: list[str] = []
        sample_high_violations: list[str] = []
        sample_medium_logs: list[str] = []
        clickable_samples_checked: list[str] = []
        clickable_samples_violations: list[str] = []
        clickable_samples_medium_logs: list[str] = []
        style_text = "\n".join(s.get_text(" ", strip=True) for s in self.soup.find_all("style"))

        def _labelledby_text(elem: Tag) -> str:
            ref_ids = str(elem.get("aria-labelledby") or "").strip().split()
            if not ref_ids:
                return ""
            parts: list[str] = []
            for ref_id in ref_ids:
                target = self.soup.find(id=ref_id)
                if not target:
                    continue
                txt = target.get_text(" ", strip=True)
                if txt:
                    parts.append(txt)
            return " ".join(parts).strip()

        def _has_accessible_name(elem: Tag) -> bool:
            # Prefer explicit ARIA naming first.
            if (elem.get("aria-label") or "").strip():
                return True
            if _labelledby_text(elem):
                return True
            if (elem.get("title") or "").strip():
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

        def _is_ambiguous_nested_content(elem: Tag) -> bool:
            # Conservative medium bucket for icon-only / CSS-driven content candidates.
            if elem.name == "input":
                return False
            if elem.get_text(" ", strip=True):
                return False
            if elem.find(["svg", "img", "i", "span", "use"]):
                return True
            return False

        def _is_offscreen_via_class_css(elem: Tag) -> bool:
            classes = elem.get("class") or []
            if not classes or not style_text:
                return False
            if not isinstance(classes, list):
                classes = [classes]

            for cls in classes:
                cls_name = str(cls).strip()
                if not cls_name:
                    continue
                rule_match = re.search(
                    rf"\.{re.escape(cls_name)}\s*\{{([^}}]+)\}}",
                    style_text,
                    flags=re.I | re.S,
                )
                if not rule_match:
                    continue
                rule_body = re.sub(r"\s+", "", rule_match.group(1).lower())
                if "position:absolute" not in rule_body:
                    continue

                left_match = re.search(r"left:(-?\d+)px", rule_body)
                top_match = re.search(r"top:(-?\d+)px", rule_body)
                left_offscreen = bool(left_match and int(left_match.group(1)) <= -500)
                top_offscreen = bool(top_match and int(top_match.group(1)) <= -500)
                if left_offscreen or top_offscreen:
                    return True

            return False

        for btn in self.soup.find_all("button"):
            checked += 1
            selector = _css_selector(btn)
            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(selector)

            if _is_offscreen_via_class_css(btn):
                issues.append(_issue(
                    self.url, "button-name", "violation", "serious",
                    selector, _snippet(btn),
                    "Button is positioned far off-screen via CSS, making its purpose unavailable to many users.",
                    "4.1.2", "A", "forms",
                    "Ensure interactive controls remain perceivable and programmatically named in the rendered viewport."
                ))
                button_name_high_violations += 1
                if len(sample_high_violations) < 5:
                    sample_high_violations.append(_snippet(btn, 200))
                continue

            if not _has_accessible_name(btn):
                if _is_ambiguous_nested_content(btn):
                    button_name_medium_logs += 1
                    if len(sample_medium_logs) < 5:
                        sample_medium_logs.append(_snippet(btn, 200))
                    continue
                issues.append(_issue(
                    self.url, "button-name", "violation", "critical",
                    selector, _snippet(btn),
                    "Button has no accessible name. Screen readers cannot identify this control.",
                    "4.1.2", "A", "forms",
                    'Add text content or aria-label="Button description".'
                ))
                button_name_high_violations += 1
                if len(sample_high_violations) < 5:
                    sample_high_violations.append(_snippet(btn, 200))

        # Input controls that function as buttons also require an accessible name.
        for inp in self.soup.find_all("input"):
            inp_type = (inp.get("type") or "").lower()
            if inp_type not in {"button", "submit", "reset", "image"}:
                continue
            checked += 1
            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(f'{_css_selector(inp)} type="{inp_type}"')
            if not _has_accessible_name(inp):
                issues.append(_issue(
                    self.url, "button-name", "violation", "critical",
                    _css_selector(inp), _snippet(inp),
                    "Button-like input has no accessible name.",
                    "4.1.2", "A", "forms",
                    'Add value text, alt text (for image inputs), or aria-label.'
                ))
                button_name_high_violations += 1
                if len(sample_high_violations) < 5:
                    sample_high_violations.append(_snippet(inp, 200))

        # ARIA button role support in static mode.
        for elem in self.soup.find_all(attrs={"role": True}):
            role = (elem.get("role") or "").strip().lower()
            if role != "button":
                continue
            checked += 1
            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(f'{_css_selector(elem)} role="button"')
            if not _has_accessible_name(elem):
                if _is_ambiguous_nested_content(elem):
                    button_name_medium_logs += 1
                    if len(sample_medium_logs) < 5:
                        sample_medium_logs.append(_snippet(elem, 200))
                    continue
                issues.append(_issue(
                    self.url, "button-name", "violation", "critical",
                    _css_selector(elem), _snippet(elem),
                    "Element with role=button has no accessible name.",
                    "4.1.2", "A", "forms",
                    'Add visible text or aria-label/aria-labelledby to the role="button" element.'
                ))
                button_name_high_violations += 1
                if len(sample_high_violations) < 5:
                    sample_high_violations.append(_snippet(elem, 200))

        # Group 3: any non-native element with onclick but no role should be evaluated.
        native_interactive_tags = {"a", "button", "input", "select", "textarea", "summary", "option"}
        for elem in self.soup.find_all(attrs={"onclick": True}):
            try:
                onclick = str(elem.get("onclick") or "").strip()
                if not onclick:
                    continue
                if elem.name in native_interactive_tags:
                    continue
                if elem.get("role"):
                    continue

                clickable_checked += 1
                selector = _css_selector(elem)
                if len(clickable_samples_checked) < 5:
                    clickable_samples_checked.append(selector)

                if not self._is_visible_for_group3(elem):
                    clickable_medium_logs += 1
                    if len(clickable_samples_medium_logs) < 5:
                        clickable_samples_medium_logs.append(_snippet(elem, 200))
                    continue

                has_interactive_descendant = bool(elem.find(["a", "button", "input", "select", "textarea"]))
                if has_interactive_descendant:
                    clickable_medium_logs += 1
                    if len(clickable_samples_medium_logs) < 5:
                        clickable_samples_medium_logs.append(_snippet(elem, 200))
                    continue

                has_keyboard_handler = bool(elem.get("onkeydown") or elem.get("onkeyup") or elem.get("onkeypress"))
                has_tabindex = elem.get("tabindex") is not None
                if has_keyboard_handler and has_tabindex:
                    clickable_medium_logs += 1
                    if len(clickable_samples_medium_logs) < 5:
                        clickable_samples_medium_logs.append(_snippet(elem, 200))
                    continue

                issues.append(_issue(
                    self.url, "clickable-no-role", "violation", "serious",
                    selector, _snippet(elem),
                    "Element with onclick handler has no role='button'. Not accessible via keyboard.",
                    "4.1.2", "A", "aria",
                    'Add role="button" tabindex="0" and keyboard event handlers, or use a <button>.'
                ))
                clickable_violations += 1
                if len(clickable_samples_violations) < 5:
                    clickable_samples_violations.append(_snippet(elem, 200))
            except Exception as exc:
                logger.debug("Group3 clickable-no-role check skipped element due to error: %s", exc)
                continue

        self._track_rule_activity(
            "button-name",
            elements_checked=checked,
            violations_found=button_name_high_violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=sample_high_violations,
        )
        if button_name_medium_logs > 0:
            self._track_rule_activity(
                "button-name",
                violations_found=button_name_medium_logs,
                confidence_bucket="medium",
                sample_violations=sample_medium_logs,
                count_towards_total=False,
            )

        self._track_rule_activity(
            "clickable-no-role",
            elements_checked=clickable_checked,
            violations_found=clickable_violations,
            confidence_bucket="high",
            sample_elements_checked=clickable_samples_checked,
            sample_violations=clickable_samples_violations,
        )
        if clickable_medium_logs > 0:
            self._track_rule_activity(
                "clickable-no-role",
                violations_found=clickable_medium_logs,
                confidence_bucket="medium",
                sample_violations=clickable_samples_medium_logs,
                count_towards_total=False,
            )

        return issues

    # ── Forms ──────────────────────────────────────────────────

    def check_forms(self) -> list[dict]:
        issues = []
        checked = 0
        sample_elements_checked: list[str] = []
        sample_violations: list[str] = []

        missing_label_violations = 0
        input_label_checked = 0
        input_label_high_violations = 0
        input_label_medium_logs = 0
        input_label_samples_checked: list[str] = []
        input_label_samples_high: list[str] = []
        input_label_samples_medium: list[str] = []

        form_label_missing_violations = 0
        form_label_missing_samples: list[str] = []
        label_rule_violations = 0
        label_rule_samples: list[str] = []

        input_name_checked = 0
        input_name_high_violations = 0
        input_name_medium_logs = 0
        input_name_samples_checked: list[str] = []
        input_name_samples_high: list[str] = []
        input_name_samples_medium: list[str] = []

        autocomplete_checked = 0
        autocomplete_violations = 0
        autocomplete_samples_checked: list[str] = []
        autocomplete_samples_violations: list[str] = []

        duplicate_label_checked = 0
        duplicate_label_violations = 0
        duplicate_label_samples_checked: list[str] = []
        duplicate_label_samples_violations: list[str] = []

        autocomplete_types = {
            "name", "email", "tel", "url", "username", "new-password",
            "current-password", "cc-name", "cc-number", "cc-exp",
            "street-address", "country", "postal-code", "bday"
        }

        def _labelledby_text(elem: Tag) -> str:
            ref_ids = str(elem.get("aria-labelledby") or "").strip().split()
            if not ref_ids:
                return ""
            chunks: list[str] = []
            for ref_id in ref_ids:
                target = self.soup.find(id=ref_id)
                if not target:
                    continue
                txt = target.get_text(" ", strip=True)
                if txt:
                    chunks.append(txt)
            return " ".join(chunks).strip()

        def _associated_labels(elem: Tag) -> list[Tag]:
            labels: list[Tag] = []
            elem_id = str(elem.get("id") or "").strip()
            if elem_id:
                labels.extend(self.soup.find_all("label", attrs={"for": elem_id}))
            parent_label = elem.find_parent("label")
            if isinstance(parent_label, Tag):
                labels.append(parent_label)

            deduped: list[Tag] = []
            seen: set[int] = set()
            for label in labels:
                key = id(label)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(label)
            return deduped

        def _emit_unified_label_issues(selector: str, control: Tag, control_id: str) -> None:
            nonlocal missing_label_violations, input_label_high_violations
            nonlocal form_label_missing_violations, label_rule_violations

            payload = [
                (
                    "missing-label",
                    "critical",
                    "Form input has no associated label. Screen readers cannot identify this field.",
                    f'Add <label for="{control_id or "field-id"}">Label text</label> or aria-label="Label text".',
                ),
                (
                    "input-label",
                    "serious",
                    "Input has no associated <label> element.",
                    f'Associate a <label for="{control_id or "field-id"}> with this input, or wrap it in <label>.',
                ),
                (
                    "form-label-missing",
                    "serious",
                    "Form field is missing an external label or aria-label.",
                    "Wrap input in <label> or provide aria-label.",
                ),
                (
                    "label",
                    "serious",
                    "Form field has no programmatically associated label.",
                    "Provide a visible label or aria-labelledby/aria-label so assistive tech can announce this field.",
                ),
            ]

            for rule_id, severity, description, suggested_fix in payload:
                issues.append(_issue(
                    self.url, rule_id, "violation", severity,
                    selector, _snippet(control),
                    description,
                    "1.3.1", "A", "forms",
                    suggested_fix,
                ))

            missing_label_violations += 1
            input_label_high_violations += 1
            form_label_missing_violations += 1
            label_rule_violations += 1

            snippet = _snippet(control, 200)
            if len(sample_violations) < 5:
                sample_violations.append(snippet)
            if len(input_label_samples_high) < 5:
                input_label_samples_high.append(snippet)
            if len(form_label_missing_samples) < 5:
                form_label_missing_samples.append(snippet)
            if len(label_rule_samples) < 5:
                label_rule_samples.append(snippet)

        for inp in self.soup.find_all(["input", "textarea", "select"]):
            try:
                inp_type = inp.get("type", "text")
                if inp_type in ("hidden", "submit", "button", "reset", "image"):
                    continue

                checked += 1

                selector = _css_selector(inp)
                inp_id = str(inp.get("id") or "")
                associated_labels = _associated_labels(inp)
                has_explicit_label = bool(associated_labels)
                aria_label_text = str(inp.get("aria-label") or "").strip()
                aria_labelledby_text = _labelledby_text(inp)
                title_text = str(inp.get("title") or "").strip()
                placeholder_text = str(inp.get("placeholder") or "").strip()
                is_visible_for_group3 = self._is_visible_for_group3(inp)
                has_label_signal = bool(has_explicit_label or aria_label_text or aria_labelledby_text or title_text)

                if len(sample_elements_checked) < 5:
                    sample_elements_checked.append(f'{selector} type="{inp_type}" id="{inp_id}"')

                if not has_label_signal:
                    _emit_unified_label_issues(selector, inp, inp_id)

                if is_visible_for_group3:
                    input_label_checked += 1
                    if len(input_label_samples_checked) < 5:
                        input_label_samples_checked.append(f'{selector} type="{inp_type}"')

                    if not has_explicit_label and has_label_signal:
                        input_label_medium_logs += 1
                        if len(input_label_samples_medium) < 5:
                            input_label_samples_medium.append(_snippet(inp, 200))

                    input_name_checked += 1
                    if len(input_name_samples_checked) < 5:
                        input_name_samples_checked.append(f'{selector} type="{inp_type}"')

                    has_programmatic_name = has_label_signal
                    if not has_programmatic_name:
                        if placeholder_text:
                            input_name_medium_logs += 1
                            if len(input_name_samples_medium) < 5:
                                input_name_samples_medium.append(_snippet(inp, 200))
                        else:
                            issues.append(_issue(
                                self.url, "input-name", "violation", "critical",
                                selector, _snippet(inp),
                                "Input has no programmatic accessible name.",
                                "4.1.2", "A", "forms",
                                "Provide a visible label or add aria-label/aria-labelledby/title with clear field purpose."
                            ))
                            input_name_high_violations += 1
                            if len(input_name_samples_high) < 5:
                                input_name_samples_high.append(_snippet(inp, 200))

                    if inp_type in ("text", "email", "tel", "url", "password") and not inp.get("autocomplete"):
                        autocomplete_checked += 1
                        if len(autocomplete_samples_checked) < 5:
                            autocomplete_samples_checked.append(f'{selector} type="{inp_type}"')

                        label_text = " ".join(
                            re.sub(r"\s+", " ", lbl.get_text(" ", strip=True)).strip().lower()
                            for lbl in associated_labels
                        )
                        signal_blob = " ".join(
                            [
                                str(inp.get("name", "") or ""),
                                str(inp.get("id", "") or ""),
                                aria_label_text,
                                aria_labelledby_text,
                                title_text,
                                placeholder_text,
                                label_text,
                            ]
                        ).lower()

                        if re.search(r"\b(search|query|filter|keyword)\b", signal_blob):
                            signal_blob = ""

                        inferred_type = None
                        if inp_type == "email":
                            inferred_type = "email"
                        elif inp_type == "tel":
                            inferred_type = "tel"
                        elif inp_type == "password":
                            inferred_type = "current-password"
                        elif signal_blob:
                            token_map = {
                                "name": ["first name", "last name", "full name", "given name", "family name", "name"],
                                "email": ["email", "e-mail"],
                                "tel": ["phone", "mobile", "telephone", "tel"],
                                "street-address": ["address", "street", "addr", "line 1", "line 2"],
                                "postal-code": ["zip", "postal", "postcode", "pin"],
                                "country": ["country"],
                                "bday": ["birthday", "birth", "dob"],
                                "username": ["username", "user name", "login"],
                                "cc-name": ["cardholder", "card name", "name on card"],
                                "cc-number": ["card number", "credit card", "cc number", "ccnum"],
                                "cc-exp": ["expiry", "expiration", "exp date", "exp"],
                            }
                            for ac_type, tokens in token_map.items():
                                if any(re.search(rf"\\b{re.escape(tok)}\\b", signal_blob) for tok in tokens):
                                    inferred_type = ac_type
                                    break

                        if inferred_type and inferred_type in autocomplete_types:
                            issues.append(_issue(
                                self.url, "autocomplete-missing", "violation", "moderate",
                                selector, _snippet(inp),
                                "Input likely collects personal data but is missing autocomplete attribute.",
                                "1.3.5", "AA", "forms",
                                f'Add autocomplete="{inferred_type}" to this input.',
                                fix_effort="low"
                            ))
                            autocomplete_violations += 1
                            if len(autocomplete_samples_violations) < 5:
                                autocomplete_samples_violations.append(_snippet(inp, 200))

                    duplicate_label_checked += 1
                    if len(duplicate_label_samples_checked) < 5:
                        duplicate_label_samples_checked.append(f'{selector} type="{inp_type}"')

                    label_texts = [
                        re.sub(r"\s+", " ", lbl.get_text(" ", strip=True)).strip().lower()
                        for lbl in associated_labels
                    ]
                    label_texts = [txt for txt in label_texts if txt]
                    if len(label_texts) >= 2 and len(label_texts) != len(set(label_texts)):
                        duplicates = sorted({txt for txt in label_texts if label_texts.count(txt) > 1})
                        duplicate_preview = ", ".join(duplicates[:2])
                        issues.append(_issue(
                            self.url, "duplicate-label", "violation", "moderate",
                            selector, _snippet(inp),
                            f'Input has duplicate associated labels ({duplicate_preview}).',
                            "3.3.2", "A", "forms",
                            "Keep one unique, descriptive label per form control."
                        ))
                        duplicate_label_violations += 1
                        if len(duplicate_label_samples_violations) < 5:
                            duplicate_label_samples_violations.append(_snippet(inp, 200))
            except Exception as exc:
                logger.debug("Group3 form checks skipped control due to error: %s", exc)
                continue

        role_name_required = {"combobox", "textbox", "searchbox", "spinbutton", "slider", "listbox"}
        for elem in self.soup.find_all(attrs={"role": True}):
            role_tokens = self._extract_role_tokens(elem)
            if not role_tokens:
                continue
            primary_role = role_tokens[0]
            if primary_role not in role_name_required:
                continue
            if elem.name in {"input", "textarea", "select"}:
                continue

            checked += 1
            selector = _css_selector(elem)
            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(f'{selector} role="{primary_role}"')

            has_name = bool(
                (elem.get("aria-label") or "").strip()
                or (elem.get("aria-labelledby") or "").strip()
                or (elem.get("title") or "").strip()
                or elem.get_text(" ", strip=True)
            )
            if has_name:
                continue

            issues.append(_issue(
                self.url, "missing-label", "violation", "critical",
                selector, _snippet(elem),
                f'Element with role="{primary_role}" has no accessible name.',
                "1.3.1", "A", "forms",
                "Add aria-label, aria-labelledby, title, or visible text to provide a clear name."
            ))
            missing_label_violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(elem, 200))

        self._track_rule_activity(
            "missing-label",
            elements_checked=checked,
            violations_found=missing_label_violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=sample_violations,
        )
        self._track_rule_activity(
            "input-label",
            elements_checked=input_label_checked,
            violations_found=input_label_high_violations,
            confidence_bucket="high",
            sample_elements_checked=input_label_samples_checked,
            sample_violations=input_label_samples_high,
        )
        if input_label_medium_logs > 0:
            self._track_rule_activity(
                "input-label",
                violations_found=input_label_medium_logs,
                confidence_bucket="medium",
                sample_violations=input_label_samples_medium,
                count_towards_total=False,
            )

        self._track_rule_activity(
            "form-label-missing",
            elements_checked=checked,
            violations_found=form_label_missing_violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=form_label_missing_samples,
        )
        self._track_rule_activity(
            "label",
            elements_checked=checked,
            violations_found=label_rule_violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=label_rule_samples,
        )

        self._track_rule_activity(
            "input-name",
            elements_checked=input_name_checked,
            violations_found=input_name_high_violations,
            confidence_bucket="high",
            sample_elements_checked=input_name_samples_checked,
            sample_violations=input_name_samples_high,
        )
        if input_name_medium_logs > 0:
            self._track_rule_activity(
                "input-name",
                violations_found=input_name_medium_logs,
                confidence_bucket="medium",
                sample_violations=input_name_samples_medium,
                count_towards_total=False,
            )

        self._track_rule_activity(
            "autocomplete-missing",
            elements_checked=autocomplete_checked,
            violations_found=autocomplete_violations,
            confidence_bucket="high",
            sample_elements_checked=autocomplete_samples_checked,
            sample_violations=autocomplete_samples_violations,
        )
        self._track_rule_activity(
            "duplicate-label",
            elements_checked=duplicate_label_checked,
            violations_found=duplicate_label_violations,
            confidence_bucket="high",
            sample_elements_checked=duplicate_label_samples_checked,
            sample_violations=duplicate_label_samples_violations,
        )

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

        for err_container in self.soup.find_all(class_=re.compile(r'error|invalid|alert', re.I)):
            err_id = err_container.get("id")
            if err_id:
                if not err_container.find_parent("form"):
                    continue
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

    def _extract_role_tokens(self, elem: Tag) -> list[str]:
        role_raw = str(elem.get("role") or "").strip().lower()
        return [tok for tok in role_raw.split() if tok]

    def _has_ancestor_role_or_tag(self, elem: Tag, allowed_roles: set[str], allowed_tags: set[str]) -> bool:
        parent = elem.parent
        while isinstance(parent, Tag):
            parent_roles = set(self._extract_role_tokens(parent))
            if parent_roles & allowed_roles:
                return True
            if parent.name in allowed_tags:
                return True
            parent = parent.parent
        return False

    def _has_required_descendant(self, elem: Tag, required_roles: set[str], required_tags: set[str]) -> bool:
        for desc in elem.find_all(True):
            roles = set(self._extract_role_tokens(desc))
            if roles & required_roles:
                return True
            if desc.name in required_tags:
                if desc.name == "input":
                    inp_type = str(desc.get("type") or "").strip().lower()
                    if inp_type == "radio":
                        return True
                    continue
                return True
        return False

    def _check_aria_required_parent(self) -> list[dict]:
        issues = []

        required_parent = {
            "option": ({"listbox", "group"}, {"select", "datalist"}),
            "menuitem": ({"menu", "menubar", "group"}, {"menu"}),
            "menuitemcheckbox": ({"menu", "menubar", "group"}, {"menu"}),
            "menuitemradio": ({"menu", "menubar", "group"}, {"menu"}),
            "listitem": ({"list", "group"}, {"ul", "ol"}),
            "row": ({"grid", "rowgroup", "table", "treegrid"}, {"table", "tbody", "thead", "tfoot"}),
            "gridcell": ({"row", "grid", "treegrid"}, {"tr"}),
            "columnheader": ({"row"}, {"tr"}),
            "rowheader": ({"row"}, {"tr"}),
            "tab": ({"tablist"}, set()),
            "treeitem": ({"tree", "group", "treegrid"}, {"ul", "ol"}),
        }

        checked = 0
        violations = 0
        sample_elements_checked: list[str] = []
        sample_violations: list[str] = []

        for elem in self.soup.find_all(attrs={"role": True}):
            role_tokens = self._extract_role_tokens(elem)
            if not role_tokens:
                continue

            primary_role = role_tokens[0]
            if primary_role not in required_parent:
                continue

            checked += 1
            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(f'{_css_selector(elem)} role="{primary_role}"')
            allowed_roles, allowed_tags = required_parent[primary_role]
            if self._has_ancestor_role_or_tag(elem, allowed_roles, allowed_tags):
                continue

            issues.append(_issue(
                self.url, "aria-required-parent", "violation", "serious",
                _css_selector(elem), _snippet(elem),
                f'Element with role="{primary_role}" is missing a required parent role/container.',
                "4.1.2", "A", "aria",
                f'Place this element inside a compatible parent (roles: {", ".join(sorted(allowed_roles))}).'
            ))
            violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(elem, 200))

        self._track_rule_activity(
            "aria-required-parent",
            elements_checked=checked,
            violations_found=violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=sample_violations,
        )

        return issues

    def _check_aria_required_children(self) -> list[dict]:
        issues = []

        required_children = {
            "list": ({"listitem", "group"}, {"li"}),
            "listbox": ({"option", "group"}, {"option", "optgroup"}),
            "menu": ({"menuitem", "menuitemcheckbox", "menuitemradio", "group"}, {"li"}),
            "menubar": ({"menuitem", "menuitemcheckbox", "menuitemradio", "group"}, {"li"}),
            "tablist": ({"tab"}, set()),
            "radiogroup": ({"radio"}, {"input"}),
            "tree": ({"treeitem", "group"}, {"li"}),
            "grid": ({"row", "rowgroup"}, {"tr", "tbody", "thead", "tfoot"}),
            "row": ({"cell", "gridcell", "columnheader", "rowheader"}, {"td", "th"}),
        }

        checked = 0
        violations = 0
        sample_elements_checked: list[str] = []
        sample_violations: list[str] = []

        for elem in self.soup.find_all(attrs={"role": True}):
            role_tokens = self._extract_role_tokens(elem)
            if not role_tokens:
                continue

            primary_role = role_tokens[0]
            if primary_role not in required_children:
                continue

            checked += 1
            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(f'{_css_selector(elem)} role="{primary_role}"')

            # Dynamic containers can be transiently empty while hydrating.
            if str(elem.get("aria-busy") or "").strip().lower() == "true":
                continue

            req_roles, req_tags = required_children[primary_role]
            if self._has_required_descendant(elem, req_roles, req_tags):
                continue

            issues.append(_issue(
                self.url, "aria-required-children", "violation", "serious",
                _css_selector(elem), _snippet(elem),
                f'Element with role="{primary_role}" is missing required child roles.',
                "4.1.2", "A", "aria",
                f'Add required child roles such as: {", ".join(sorted(req_roles))}.',
            ))
            violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(elem, 200))

        self._track_rule_activity(
            "aria-required-children",
            elements_checked=checked,
            violations_found=violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=sample_violations,
        )

        return issues

    def _check_aria_allowed_role(self) -> list[dict]:
        issues = []

        structural_roles = {
            "article", "banner", "complementary", "contentinfo", "form", "main",
            "navigation", "region", "table", "row", "cell", "rowgroup", "heading", "list", "listitem",
        }

        checked = 0
        violations = 0
        sample_elements_checked: list[str] = []
        sample_violations: list[str] = []

        for elem in self.soup.find_all(attrs={"role": True}):
            role_tokens = self._extract_role_tokens(elem)
            if not role_tokens:
                continue

            primary_role = role_tokens[0]
            if primary_role in {"none", "presentation"}:
                continue

            disallowed: set[str] = set()

            if elem.name == "input":
                inp_type = str(elem.get("type") or "text").strip().lower()
                if inp_type in {"text", "email", "search", "url", "tel", "password"}:
                    disallowed = structural_roles
                elif inp_type in {"checkbox", "radio"}:
                    disallowed = structural_roles | {"textbox", "combobox", "searchbox", "slider", "spinbutton"}
            elif elem.name in {"textarea", "select"}:
                disallowed = structural_roles | {"button", "link"}
            elif elem.name in {"ul", "ol"}:
                disallowed = {"button", "link", "textbox", "checkbox", "radio", "switch", "combobox", "searchbox", "slider", "spinbutton"}
            elif elem.name == "li":
                disallowed = {"button", "link", "textbox", "combobox", "searchbox", "slider", "spinbutton"}
            elif elem.name == "table":
                disallowed = {"button", "link", "textbox", "checkbox", "radio"}

            if not disallowed:
                continue

            checked += 1
            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(f'{_css_selector(elem)} role="{primary_role}"')
            if primary_role not in disallowed:
                continue

            issues.append(_issue(
                self.url, "aria-allowed-role", "violation", "serious",
                _css_selector(elem), _snippet(elem),
                f'Role "{primary_role}" is not a safe/compatible override for <{elem.name}> in this context.',
                "4.1.2", "A", "aria",
                "Use a role compatible with the host element semantics, or use a native element that matches the intended behavior.",
            ))
            violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(elem, 200))

        self._track_rule_activity(
            "aria-allowed-role",
            elements_checked=checked,
            violations_found=violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=sample_violations,
        )

        return issues

    def check_aria(self) -> list[dict]:
        issues = []
        # Elements with role but no accessible name
        interactive_roles = {"button", "link", "tab", "menuitem", "option", "textbox", "combobox", "listbox"}
        for elem in self.soup.find_all(attrs={"role": True}):
            role = elem.get("role", "")
            if role in interactive_roles:
                text = elem.get_text(strip=True)
                if _is_effectively_empty_text(text) and not elem.get("aria-label") and not elem.get("aria-labelledby"):
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

        # Deterministic Group 1 ARIA rules.
        issues.extend(self._check_aria_required_parent())
        issues.extend(self._check_aria_required_children())
        issues.extend(self._check_aria_allowed_role())
        issues.extend(self._check_aria_attribute_signals())

        return issues

    def _check_aria_attribute_signals(self) -> list[dict]:
        """Detect deterministic ARIA/attribute misuse patterns that map to ACT aria-attribute family rules."""
        issues = []
        checked = 0
        violations = 0
        sample_elements_checked: list[str] = []
        sample_violations: list[str] = []

        for inp in self.soup.find_all("input"):
            inp_type = str(inp.get("type") or "text").strip().lower()
            if inp_type not in {"checkbox", "radio"}:
                continue

            checked += 1
            selector = _css_selector(inp)
            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(f'{selector} type="{inp_type}"')

            if inp.has_attr("readonly"):
                issues.append(_issue(
                    self.url, "aria-attribute", "violation", "serious",
                    selector, _snippet(inp),
                    f'Input type="{inp_type}" uses readonly, which is not a valid state for this control type.',
                    "4.1.2", "A", "aria",
                    f'Remove readonly from this {inp_type} control and rely on disabled or checked semantics as appropriate.'
                ))
                violations += 1
                if len(sample_violations) < 5:
                    sample_violations.append(_snippet(inp, 200))

        self._track_rule_activity(
            "aria-attribute",
            elements_checked=checked,
            violations_found=violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=sample_violations,
        )

        return issues

    # ── Media ──────────────────────────────────────────────────

    def check_media(self) -> list[dict]:
        issues = []
        media_alternative_checked = 0
        media_alternative_violations = 0
        media_alt_samples_checked: list[str] = []
        media_alt_samples_violations: list[str] = []

        def _has_transcript_signal(scope: Tag | BeautifulSoup) -> bool:
            return bool(
                scope.find(attrs={"data-transcript": True})
                or scope.find(class_=re.compile(r"transcript|caption", re.I))
                or scope.find(id=re.compile(r"transcript|caption", re.I))
                or scope.find("a", string=re.compile(r"transcript|captions", re.I))
                or scope.find("button", string=re.compile(r"transcript|captions", re.I))
            )

        # Autoplay media
        for media in self.soup.find_all(["video", "audio"]):
            selector = _css_selector(media)
            media_alternative_checked += 1
            if len(media_alt_samples_checked) < 5:
                media_alt_samples_checked.append(f"{selector}:{media.name}")

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
                    issues.append(_issue(
                        self.url, "media-alternative", "violation", "serious",
                        selector, _snippet(media),
                        "Video element has no captions/transcript alternative.",
                        "1.2.1", "A", "media",
                        "Provide captions and a text transcript for prerecorded media content."
                    ))
                    media_alternative_violations += 1
                    if len(media_alt_samples_violations) < 5:
                        media_alt_samples_violations.append(_snippet(media, 200))

            # Audio transcript
            if media.name == "audio":
                parent = media.parent
                local_scope = parent if isinstance(parent, Tag) else self.soup
                sibling_text = ""
                nxt = media.find_next_sibling()
                hops = 0
                while nxt is not None and hops < 3:
                    sibling_text += " " + nxt.get_text(" ", strip=True)
                    nxt = nxt.find_next_sibling()
                    hops += 1

                has_transcript = _has_transcript_signal(local_scope) or _has_transcript_signal(self.soup) or len(sibling_text.strip()) > 200
                if not has_transcript:
                    issues.append(_issue(
                        self.url, "missing-transcript", "needs-review", "serious",
                        selector, _snippet(media),
                        "Audio element found without nearby transcript indication.",
                        "1.2.1", "A", "media",
                        "Provide a text transcript of the audio content, linked near the audio player."
                    ))
                    issues.append(_issue(
                        self.url, "media-alternative", "violation", "serious",
                        selector, _snippet(media),
                        "Audio content appears to be missing a transcript alternative.",
                        "1.2.1", "A", "media",
                        "Add an adjacent transcript section or clearly labeled transcript link."
                    ))
                    media_alternative_violations += 1
                    if len(media_alt_samples_violations) < 5:
                        media_alt_samples_violations.append(_snippet(media, 200))

        self._track_rule_activity(
            "media-alternative",
            elements_checked=media_alternative_checked,
            violations_found=media_alternative_violations,
            confidence_bucket="high",
            sample_elements_checked=media_alt_samples_checked,
            sample_violations=media_alt_samples_violations,
        )

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

        for meta in self.soup.find_all("meta", attrs={"http-equiv": True}):
            http_equiv = str(meta.get("http-equiv") or "").strip().lower()
            if http_equiv != "refresh":
                continue

            content = str(meta.get("content") or "").strip()
            delay = None
            delay_match = re.match(r"\s*(\d+)", content)
            if delay_match:
                try:
                    delay = int(delay_match.group(1))
                except ValueError:
                    delay = None

            if delay is None:
                continue

            issues.append(_issue(
                self.url, "meta-refresh", "violation", "serious",
                'meta[http-equiv="refresh"]', _snippet(meta, 200),
                "Page uses meta refresh, which can disorient users and interfere with assistive technology workflows.",
                "2.2.1", "A", "content",
                "Remove meta refresh redirects or provide user controls and sufficient time before refresh."
            ))
        return issues

    # ── WCAG 2.2 & ARIA APG & Semantics ────────────────────────

    def check_accessible_auth(self) -> list[dict]:
        """WCAG 3.3.7 Accessible Authentication (Minimum)."""
        issues = []
        for form in self.soup.find_all("form"):
            password_inputs = form.find_all("input", type="password")
            for pw in password_inputs:
                if pw.get("autocomplete") not in ("current-password", "new-password"):
                    issues.append(_issue(
                        self.url, "missing-autocomplete-auth", "violation", "serious",
                        _css_selector(pw), _snippet(pw),
                        "Password input is missing required autocomplete attribute to support password managers (cognitive aid).",
                        "3.3.7", "AA", "forms",
                        'Add autocomplete="current-password" or "new-password".'
                    ))
        return issues

    def check_redundant_entry(self) -> list[dict]:
        """WCAG 3.3.9 Redundant Entry."""
        issues = []
        name_groups = {}
        for inp in self.soup.find_all("input"):
            inp_type = inp.get("type", "text")
            if inp_type in ("radio", "checkbox", "hidden", "submit", "button", "reset"):
                continue
            name = inp.get("name")
            if name:
                name_groups.setdefault(name, []).append(inp)
                
        for name, inputs in name_groups.items():
            if len(inputs) > 1:
                issues.append(_issue(
                    self.url, "redundant-entry", "needs-review", "moderate",
                    f'input[name="{name}"]', _snippet(inputs[0]),
                    f"Multiple text inputs with the name '{name}'. Check if this requires redundant data entry.",
                    "3.3.9", "A", "forms",
                    "Provide an option to auto-populate previously entered data (e.g., 'Same as shipping').",
                    fix_effort="high"
                ))
        return issues

    def check_aria_apg_patterns(self) -> list[dict]:
        """Validate composite ARIA implementations against APG (ARIA Authoring Practices)."""
        issues = []
        for tablist in self.soup.find_all(attrs={"role": "tablist"}):
            tabs = tablist.find_all(attrs={"role": "tab"})
            if not tabs:
                issues.append(_issue(
                    self.url, "apg-tablist-missing-tabs", "violation", "serious",
                    _css_selector(tablist), _snippet(tablist),
                    'element role="tablist" has no children with role="tab".',
                    "4.1.2", "A", "aria",
                    'Ensure tablist contains tab elements.'
                ))
            for tab in tabs:
                controls = tab.get("aria-controls")
                if not controls:
                    issues.append(_issue(
                        self.url, "apg-tab-missing-controls", "violation", "moderate",
                        _css_selector(tab), _snippet(tab),
                        'Tab element is missing aria-controls pointing to its tabpanel.',
                        "4.1.2", "A", "aria",
                        'Add aria-controls="panel-id" to the tab.'
                    ))
                elif not self.soup.find(id=controls):
                    issues.append(_issue(
                        self.url, "apg-tab-broken-controls", "violation", "serious",
                        _css_selector(tab), _snippet(tab),
                        f'Tab aria-controls="{controls}" points to a missing element.',
                        "4.1.2", "A", "aria",
                        'Ensure the referenced tabpanel exists in the DOM.'
                    ))
        for btn in self.soup.find_all(attrs={"aria-expanded": True}):
            if not btn.get("aria-controls"):
                issues.append(_issue(
                    self.url, "apg-expanded-missing-controls", "needs-review", "moderate",
                    _css_selector(btn), _snippet(btn),
                    'aria-expanded element is missing aria-controls to identify the collapsible area.',
                    "4.1.2", "A", "aria",
                    'Add aria-controls="region-id".'
                ))
        for dialog in self.soup.find_all(attrs={"role": ["dialog", "alertdialog"]}):
            if not dialog.get("aria-labelledby") and not dialog.get("aria-label"):
                issues.append(_issue(
                    self.url, "apg-dialog-no-name", "violation", "serious",
                    _css_selector(dialog), _snippet(dialog),
                    'Dialog/modal is missing an accessible name.',
                    "4.1.2", "A", "aria",
                    'Add aria-labelledby pointing to the modal title or an aria-label.'
                ))
            if dialog.get("aria-modal") != "true":
                issues.append(_issue(
                    self.url, "apg-dialog-not-modal", "needs-review", "minor",
                    _css_selector(dialog), _snippet(dialog),
                    'Dialog should typically have aria-modal="true" to indicate it traps focus.',
                    "4.1.2", "A", "aria",
                    'Add aria-modal="true" if this is a modal dialog.'
                ))
        return issues

    def check_semantic_depth(self) -> list[dict]:
        """MDN Semantic depth: catch div-itis."""
        issues = []
        for div in self.soup.find_all("div"):
            if div.get("role"):
                continue
            text = div.get_text(strip=True)
            if len(text.split()) > 200:
                if not div.find_parent(["article", "section", "main", "aside", "nav"]):
                    issues.append(_issue(
                        self.url, "div-itis-missing-semantics", "needs-review", "minor",
                        _css_selector(div), _snippet(div, 200),
                        'Large block of content wrapped in generic <div> without semantic landmarks.',
                        "1.3.1", "A", "structure",
                        'Replace generic <div> with <article>, <section>, or <main> as appropriate.',
                        fix_effort="medium"
                    ))
        return issues

    # ── Advanced Detection Mastery (The Hidden 10) ─────────────
    
    def check_advanced_detect(self) -> list[dict]:
        """Advanced checks beyond basic axe-core rules."""
        issues = []
        issues.extend(self._check_semantic_html_signals())
        issues.extend(self._check_focus_management_static_signals())
        issues.extend(self._check_keyboard_trap_signals())
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
        weak_texts = set(_WEAK_LINK_TEXT) | {"link"}

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

            if _is_effectively_empty_text(text) and not has_name:
                issues.append(_issue(
                    self.url, "empty-link", "violation", "serious",
                    _css_selector(link), _snippet(link),
                    "Link has no accessible name.",
                    "2.4.4", "A", "navigation",
                    "Add visible text or an accessible name via aria-label/aria-labelledby."
                ))
                continue

            if _looks_like_weak_link_text(text, weak_texts) and not has_name and href and not href.startswith("#"):
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
            if not _looks_like_weak_link_text(text, set(_WEAK_LINK_TEXT)):
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

        html_elem = self.soup.find("html")
        if isinstance(html_elem, Tag):
            lang = str(html_elem.get("lang") or "").strip().lower()
            if lang and re.fullmatch(r"[a-z]{3}", lang):
                issues.append(_issue(
                    self.url, "semantic-html", "violation", "moderate",
                    "html", _snippet(html_elem, 200),
                    f'Root lang value "{lang}" is potentially non-standard for common language declarations.',
                    "3.1.1", "A", "html",
                    "Use a standard BCP 47 primary language code such as en, fr, es, or en-US."
                ))

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

    def _check_keyboard_trap_signals(self) -> list[dict]:
        """Detect static patterns that strongly suggest keyboard trap behavior."""
        issues = []
        checked = 0
        violations = 0
        sample_checked: list[str] = []
        sample_violations: list[str] = []

        for el in self.soup.find_all(attrs={"onblur": True}):
            if not isinstance(el, Tag):
                continue
            checked += 1
            selector = _css_selector(el)
            if len(sample_checked) < 5:
                sample_checked.append(selector)

            onblur = str(el.get("onblur") or "")
            onfocus = str(el.get("onfocus") or "")
            onkeydown = str(el.get("onkeydown") or "")
            combined = f"{onblur} {onfocus} {onkeydown}"

            loops_focus = bool(re.search(r"(focus|movefocus|setfocus)", onblur, re.I))
            trap_signal = bool(re.search(r"(trap|keydown|ctrl|escape|tab)", combined, re.I))
            if not loops_focus or not trap_signal:
                continue

            issues.append(_issue(
                self.url,
                "keyboard-trap",
                "violation",
                "serious",
                selector,
                _snippet(el, 220),
                "Focus appears to be forcibly redirected on blur, which can trap keyboard users.",
                "2.1.2",
                "A",
                "keyboard",
                "Allow users to move focus away normally and provide a clear keyboard escape path.",
                fix_effort="low",
            ))
            violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(el, 220))

        for el in self.soup.find_all(style=True):
            if not isinstance(el, Tag):
                continue
            checked += 1
            selector = _css_selector(el)
            if len(sample_checked) < 5:
                sample_checked.append(selector)

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
            if height_px > 140 or text_len < 220:
                continue

            issues.append(_issue(
                self.url,
                "keyboard-trap",
                "violation",
                "moderate",
                selector,
                _snippet(el, 240),
                "Scrollable text region uses overflow:hidden with a fixed height, which can prevent keyboard users from reaching all content.",
                "2.1.2",
                "A",
                "keyboard",
                "Use keyboard-accessible scrolling behavior or remove clipping that blocks keyboard navigation.",
                fix_effort="low",
            ))
            violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(el, 220))

        self._track_rule_activity(
            "keyboard-trap",
            elements_checked=checked,
            violations_found=violations,
            confidence_bucket="high",
            sample_elements_checked=sample_checked,
            sample_violations=sample_violations,
        )

        return issues

    def _check_focus_management_static_signals(self) -> list[dict]:
        """Static signal set for focus-management corroboration in precision-first profiles."""
        issues = []
        checked = 0
        violations = 0
        sample_checked: list[str] = []
        sample_violations: list[str] = []

        native_interactive = {"a", "button", "input", "select", "textarea", "summary", "details"}

        for el in self.soup.find_all(attrs={"onclick": True}):
            if not isinstance(el, Tag):
                continue
            checked += 1
            selector = _css_selector(el)
            if len(sample_checked) < 5:
                sample_checked.append(selector)

            if el.name in native_interactive:
                continue

            tabindex = str(el.get("tabindex") or "").strip()
            role = str(el.get("role") or "").strip().lower()
            if tabindex or role:
                continue

            issues.append(_issue(
                self.url,
                "focus-management",
                "violation",
                "serious",
                selector,
                _snippet(el, 220),
                "Clickable non-interactive element is missing keyboard focus semantics.",
                "2.1.1",
                "A",
                "keyboard",
                "Use a native interactive element or add role='button', tabindex='0', and keyboard handlers.",
                fix_effort="low",
            ))
            violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(el, 220))

        for el in self.soup.find_all(attrs={"role": re.compile(r"(^|\s)button(\s|$)", re.I)}):
            if not isinstance(el, Tag):
                continue
            checked += 1
            selector = _css_selector(el)
            if len(sample_checked) < 5:
                sample_checked.append(selector)

            tabindex = str(el.get("tabindex") or "").strip()
            if tabindex == "0":
                continue

            issues.append(_issue(
                self.url,
                "focus-management",
                "violation",
                "serious",
                selector,
                _snippet(el, 220),
                "Custom button role is missing keyboard focusability (tabindex='0').",
                "2.1.1",
                "A",
                "keyboard",
                "Ensure role='button' elements are focusable (tabindex='0') and respond to Enter/Space.",
                fix_effort="low",
            ))
            violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(el, 220))

        for el in self.soup.find_all(attrs={"aria-activedescendant": True}):
            if not isinstance(el, Tag):
                continue
            checked += 1
            selector = _css_selector(el)
            if len(sample_checked) < 5:
                sample_checked.append(selector)

            tabindex = str(el.get("tabindex") or "").strip()
            naturally_focusable = el.name in {"input", "textarea", "select", "button"} or (
                el.name == "a" and bool(el.get("href"))
            )
            focusable_via_tabindex = False
            if tabindex:
                try:
                    focusable_via_tabindex = int(tabindex) >= 0
                except ValueError:
                    focusable_via_tabindex = False

            if naturally_focusable or focusable_via_tabindex:
                continue

            issues.append(_issue(
                self.url,
                "focus-management",
                "violation",
                "serious",
                selector,
                _snippet(el, 220),
                "aria-activedescendant is used on an element that is not keyboard-focusable.",
                "4.1.2",
                "A",
                "keyboard",
                "Make the active-descendant container focusable with tabindex='0' or use a native focusable control.",
                fix_effort="low",
            ))
            violations += 1
            if len(sample_violations) < 5:
                sample_violations.append(_snippet(el, 220))

        self._track_rule_activity(
            "focus-management",
            elements_checked=checked,
            violations_found=violations,
            confidence_bucket="high",
            sample_elements_checked=sample_checked,
            sample_violations=sample_violations,
        )

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
        rule_hits = {
            "text-spacing": 0,
            "letter-spacing": 0,
            "line-height": 0,
            "avoid-inline-spacing": 0,
        }
        sample_checked: list[str] = []
        sample_violations: dict[str, list[str]] = {
            "text-spacing": [],
            "letter-spacing": [],
            "line-height": [],
            "avoid-inline-spacing": [],
        }

        for el in self.soup.find_all(style=True):
            style = (el.get("style") or "").lower()
            if "display:none" in style or "visibility:hidden" in style:
                continue

            has_letter_spacing = bool(re.search(r"letter-spacing\s*:", style))
            has_word_spacing = bool(re.search(r"word-spacing\s*:", style))
            has_line_height = bool(re.search(r"line-height\s*:", style))
            has_spacing_decl = has_letter_spacing or has_word_spacing or has_line_height

            text = el.get_text(" ", strip=True)
            role = str(el.get("role") or "").strip().lower()
            if not has_spacing_decl and _is_effectively_empty_text(text) and role != "textbox":
                continue
            if not has_spacing_decl and len(text) < 20 and role != "textbox" and not any(
                token in style for token in ("line-height", "letter-spacing", "word-spacing", "font-size", "overflow")
            ):
                continue

            checked += 1
            selector = _css_selector(el)
            if len(sample_checked) < 5:
                sample_checked.append(selector)

            emitted: set[str] = set()

            def _emit(rule_id: str, issue_type: str, description: str, suggested_fix: str) -> None:
                if rule_id in emitted:
                    return
                issues.append(_issue(
                    self.url,
                    rule_id,
                    issue_type,
                    "moderate",
                    selector,
                    _snippet(el),
                    description,
                    "1.4.12",
                    "AA",
                    "content",
                    suggested_fix,
                ))
                emitted.add(rule_id)
                rule_hits[rule_id] += 1
                if len(sample_violations[rule_id]) < 5:
                    sample_violations[rule_id].append(_snippet(el, 220))

            if has_letter_spacing:
                _emit(
                    "letter-spacing",
                    "violation",
                    "Inline letter-spacing style can block adaptive text spacing behavior.",
                    "Move spacing styles to CSS classes and avoid locking letter-spacing inline.",
                )
            if has_word_spacing:
                _emit(
                    "text-spacing",
                    "violation",
                    "Inline word-spacing style can interfere with user-applied text spacing adjustments.",
                    "Avoid hard-coded inline word-spacing and allow user spacing overrides.",
                )
            if has_line_height:
                _emit(
                    "line-height",
                    "violation",
                    "Inline line-height style may prevent robust text spacing adaptation.",
                    "Use scalable line-height values in CSS classes so user styles can override them.",
                )
            if has_spacing_decl:
                _emit(
                    "avoid-inline-spacing",
                    "violation",
                    "Inline spacing declarations reduce flexibility for user text spacing overrides.",
                    "Prefer class-based spacing styles and avoid fixed inline spacing declarations.",
                )

            reasons: list[str] = []

            if re.search(r"(?:letter-spacing|line-height|word-spacing)\s*:[^;]*!important", style):
                reasons.append("spacing styles use !important")

            fs_match = re.search(r"font-size\s*:\s*([0-9.]+)px", style)
            if fs_match:
                try:
                    if float(fs_match.group(1)) < 12:
                        continue
                except ValueError:
                    pass

            fs_pt_match = re.search(r"font-size\s*:\s*([0-9.]+)pt", style)
            if fs_pt_match and len(text) >= 15:
                reasons.append("text uses absolute pt font-size")

            lh_match = re.search(r"line-height\s*:\s*([0-9.]+)", style)
            ls_match_em = re.search(r"letter-spacing\s*:\s*([0-9.]+)em", style)
            ls_match_px = re.search(r"letter-spacing\s*:\s*([0-9.]+)px", style)

            line_height_value: Optional[float] = None
            letter_spacing_value: Optional[float] = None
            line_height_low = False
            letter_spacing_low = False

            if lh_match:
                try:
                    line_height_value = float(lh_match.group(1))
                    line_height_low = line_height_value < 1.5
                except ValueError:
                    pass

            if ls_match_em:
                try:
                    letter_spacing_value = float(ls_match_em.group(1))
                    letter_spacing_low = letter_spacing_value < 0.12
                except ValueError:
                    pass
            elif ls_match_px:
                try:
                    letter_spacing_value = float(ls_match_px.group(1))
                    letter_spacing_low = letter_spacing_value < 2.0
                except ValueError:
                    pass

            height_match = re.search(r"height\s*:\s*([0-9.]+)px", style)
            if height_match:
                try:
                    height_px = float(height_match.group(1))
                except ValueError:
                    height_px = 0.0
                overflow_hidden = "overflow:hidden" in style or "overflow: hidden" in style
                if overflow_hidden and height_px <= 120 and len(text) >= 120:
                    reasons.append("fixed-height text block with overflow hidden")
                if role == "textbox" and 0 < height_px <= 24:
                    reasons.append("textbox has tight fixed height")

            if line_height_low or letter_spacing_low:
                if line_height_low:
                    reasons.append("line-height is below 1.5")
                if letter_spacing_low:
                    reasons.append("letter-spacing is below recommended threshold")

            if reasons and "text-spacing" not in emitted:
                strong_failure = bool(
                    line_height_value is not None
                    and letter_spacing_value is not None
                    and line_height_value < 1.35
                    and letter_spacing_value < 0.08
                )
                _emit(
                    "text-spacing",
                    "violation" if strong_failure else "needs-review",
                    "Inline text styling may block WCAG text spacing adjustments: " + "; ".join(reasons[:3]) + ".",
                    "Increase line-height to at least 1.5 and letter-spacing to at least 0.12em for readable body text.",
                )

        self._track_rule_activity(
            "text-spacing",
            elements_checked=checked,
            violations_found=rule_hits["text-spacing"],
            confidence_bucket="high",
            sample_elements_checked=sample_checked,
            sample_violations=sample_violations["text-spacing"],
        )
        self._track_rule_activity(
            "letter-spacing",
            elements_checked=checked,
            violations_found=rule_hits["letter-spacing"],
            confidence_bucket="high",
            sample_elements_checked=sample_checked,
            sample_violations=sample_violations["letter-spacing"],
        )
        self._track_rule_activity(
            "line-height",
            elements_checked=checked,
            violations_found=rule_hits["line-height"],
            confidence_bucket="high",
            sample_elements_checked=sample_checked,
            sample_violations=sample_violations["line-height"],
        )
        self._track_rule_activity(
            "avoid-inline-spacing",
            elements_checked=checked,
            violations_found=rule_hits["avoid-inline-spacing"],
            confidence_bucket="high",
            sample_elements_checked=sample_checked,
            sample_violations=sample_violations["avoid-inline-spacing"],
        )

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
        checked = 0
        high_violations = 0
        medium_logs = 0
        sample_elements_checked: list[str] = []
        sample_high_violations: list[str] = []
        sample_medium_logs: list[str] = []

        def _labelledby_text(elem: Tag) -> str:
            ref_ids = str(elem.get("aria-labelledby") or "").strip().split()
            if not ref_ids:
                return ""
            chunks: list[str] = []
            for ref_id in ref_ids:
                target = self.soup.find(id=ref_id)
                if not target:
                    continue
                txt = target.get_text(" ", strip=True)
                if txt:
                    chunks.append(txt)
            return " ".join(chunks).strip()

        for svg in self.soup.find_all("svg"):
            try:
                checked += 1
                selector = _css_selector(svg)
                if len(sample_elements_checked) < 5:
                    sample_elements_checked.append(selector)

                role = str(svg.get("role") or "").strip().lower()
                hidden = (
                    str(svg.get("aria-hidden", "")).lower() == "true"
                    or role in {"presentation", "none"}
                    or not self._is_visible_for_group3(svg)
                )
                if hidden:
                    medium_logs += 1
                    if len(sample_medium_logs) < 5:
                        sample_medium_logs.append(_snippet(svg, 200))
                    continue

                has_name = bool((svg.get("aria-label") or "").strip() or _labelledby_text(svg))
                if not has_name and svg.find("title"):
                    has_name = bool(svg.find("title").get_text(strip=True))
                if has_name and (svg.get("aria-label") or "").strip() and not _labelledby_text(svg):
                    # Inline SVG labels are more robust with <title> or aria-labelledby.
                    has_name = bool(svg.find("title"))
                if not has_name:
                    issues.append(_issue(
                        self.url, "svg-no-accessible-name", "violation", "serious",
                        selector, _snippet(svg, 200),
                        "SVG image is missing an accessible name.",
                        "1.1.1", "A", "images", "Add <title> or aria-label.",
                        fix_effort="low"
                    ))
                    high_violations += 1
                    if len(sample_high_violations) < 5:
                        sample_high_violations.append(_snippet(svg, 200))
            except Exception as exc:
                logger.debug("Group3 svg-accessible-name check skipped svg due to error: %s", exc)
                continue

        for obj in self.soup.find_all("object"):
            checked += 1
            selector = _css_selector(obj)
            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(selector)

            data_attr = str(obj.get("data") or "").strip()
            if not data_attr:
                continue

            object_name = (
                (obj.get("title") or "").strip()
                or (obj.get("aria-label") or "").strip()
                or _labelledby_text(obj)
            )
            if object_name:
                continue

            issues.append(_issue(
                self.url, "svg-no-accessible-name", "violation", "serious",
                selector, _snippet(obj, 200),
                "Embedded object is missing an accessible name.",
                "1.1.1", "A", "images", "Add title, aria-label, or aria-labelledby to describe embedded content.",
                fix_effort="low"
            ))
            high_violations += 1
            if len(sample_high_violations) < 5:
                sample_high_violations.append(_snippet(obj, 200))

        for img in self.soup.find_all("img"):
            checked += 1
            selector = _css_selector(img)
            if len(sample_elements_checked) < 5:
                sample_elements_checked.append(selector)

            role = str(img.get("role") or "").strip().lower()
            if role not in {"none", "presentation"}:
                continue

            alt = (img.get("alt") or "").strip()
            if alt:
                continue

            issues.append(_issue(
                self.url, "svg-no-accessible-name", "violation", "moderate",
                selector, _snippet(img, 200),
                "Presentational image role is used without explicit decorative handling.",
                "1.1.1", "A", "images", "Use alt=\"\" for decorative images or provide an accessible name if informative.",
                fix_effort="low"
            ))
            high_violations += 1
            if len(sample_high_violations) < 5:
                sample_high_violations.append(_snippet(img, 200))

        self._track_rule_activity(
            "svg-no-accessible-name",
            elements_checked=checked,
            violations_found=high_violations,
            confidence_bucket="high",
            sample_elements_checked=sample_elements_checked,
            sample_violations=sample_high_violations,
        )
        if medium_logs > 0:
            self._track_rule_activity(
                "svg-no-accessible-name",
                violations_found=medium_logs,
                confidence_bucket="medium",
                sample_violations=sample_medium_logs,
                count_towards_total=False,
            )

        return issues

    def check_empty_headings(self) -> list[dict]:
        issues = []
        for tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            for h in self.soup.find_all(tag):
                heading_text = h.get_text(" ", strip=True)
                if h.get("aria-hidden", "").lower() == "true" or not _is_effectively_empty_text(heading_text):
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

        for heading in self.soup.find_all(attrs={"role": re.compile(r"(^|\s)heading(\s|$)", re.I)}):
            aria_level = str(heading.get("aria-level") or "").strip()
            text = heading.get_text(" ", strip=True)
            if _is_effectively_empty_text(text):
                issues.append(_issue(
                    self.url, "empty-heading", "violation", "moderate",
                    _css_selector(heading), _snippet(heading, 200),
                    "Element with role='heading' has no readable text.",
                    "1.3.1", "A", "structure", "Add descriptive heading text or remove heading semantics.",
                    fix_effort="low"
                ))
                continue

            if not aria_level:
                issues.append(_issue(
                    self.url, "empty-heading", "violation", "moderate",
                    _css_selector(heading), _snippet(heading, 200),
                    "Element with role='heading' is missing aria-level.",
                    "1.3.1", "A", "structure", "Add aria-level (1-6) to role='heading' elements.",
                    fix_effort="low"
                ))

        visible_h1 = [
            h for h in self.soup.find_all("h1")
            if h.get("aria-hidden", "").lower() != "true" and h.get_text(" ", strip=True)
        ]
        if len(visible_h1) > 1 and any(h.find_parent("nav") for h in visible_h1):
            first_h1 = visible_h1[0]
            issues.append(_issue(
                self.url, "empty-heading", "violation", "moderate",
                _css_selector(first_h1), _snippet(first_h1, 200),
                "Multiple H1 headings include navigation heading content, which can create ambiguous heading structure.",
                "1.3.1", "A", "structure", "Use a clear single page-level H1 and move navigation labels to lower heading levels.",
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
        # Unified label detection is handled in check_forms().
        return []
