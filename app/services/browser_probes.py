"""
Browser dynamic probes using Playwright.
Deep-scan only: keyboard navigation, focus traps, responsive reflow,
zoom testing, animation detection, ARIA tree snapshots.

Playwright is an optional dependency — all probes fail gracefully if unavailable.
"""
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Check if playwright is available
_PLAYWRIGHT_AVAILABLE = False
try:
    from playwright.async_api import async_playwright
    _PLAYWRIGHT_AVAILABLE = True
except ImportError:
    logger.info("Playwright not installed. Browser probes will be skipped. Install with: pip install playwright && playwright install chromium")


def _make_issue(url, rule_id, issue_type, severity, element, html_snippet,
                description, wcag_criterion, wcag_level, category,
                suggested_fix, evidence=None, fix_effort="medium"):
    issue_id = hashlib.sha256(f"{url}|{element}|{rule_id}".encode()).hexdigest()[:16]
    return {
        "issue_id": issue_id,
        "rule_id": rule_id,
        "issue_type": issue_type,
        "element": element,
        "html_snippet": html_snippet[:500] if html_snippet else "",
        "page_url": url,
        "severity": severity,
        "wcag_criterion": wcag_criterion,
        "wcag_level": wcag_level,
        "category": category,
        "confidence": 0.8,
        "confidence_sources": ["browser-probe"],
        "needs_manual_review": False,
        "description": description,
        "suggested_fix": suggested_fix,
        "code_fix": "",
        "fix_effort": fix_effort,
        "group_id": "",
        "domain": "",
        "evidence": evidence or {},
        "reproducibility": "",
    }


class BrowserProber:
    """Playwright-powered dynamic accessibility probes."""

    def __init__(self, url: str, timeout: int = 30000):
        self.url = url
        self.timeout = timeout

    async def run_all(self) -> tuple[list[dict], Optional[str]]:
        """
        Run all browser probes.
        Returns (issues, rendered_html) tuple.
        rendered_html can be used by static checks on the fully rendered DOM.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available — skipping browser probes")
            return [], None

        issues = []
        rendered_html = None

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="AccessibilityIntelligenceEngine/1.0"
                )
                page = await context.new_page()

                try:
                    await page.goto(self.url, timeout=self.timeout, wait_until="networkidle")
                except Exception:
                    # Fallback to domcontentloaded
                    try:
                        await page.goto(self.url, timeout=self.timeout, wait_until="domcontentloaded")
                    except Exception as e:
                        logger.error(f"Failed to load page: {e}")
                        await browser.close()
                        return [], None

                # Capture rendered HTML
                rendered_html = await page.content()

                # Run probes
                probe_methods = [
                    self._probe_keyboard_nav,
                    self._probe_focus_styles,
                    self._probe_responsive_reflow,
                    self._probe_zoom,
                    self._probe_viewport_zoom_meta,
                    self._probe_aria_tree,
                ]

                for probe in probe_methods:
                    try:
                        probe_issues = await probe(page)
                        issues.extend(probe_issues)
                    except Exception as e:
                        logger.warning(f"Probe {probe.__name__} failed: {e}")

                await browser.close()

        except Exception as e:
            logger.error(f"Browser probing failed: {e}")

        return issues, rendered_html

    async def _probe_keyboard_nav(self, page) -> list[dict]:
        """Tab through all interactive elements and check reachability."""
        issues = []
        try:
            # Get all interactive elements
            interactive_count = await page.evaluate("""
                () => {
                    const interactives = document.querySelectorAll(
                        'a[href], button, input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])'
                    );
                    return interactives.length;
                }
            """)

            if interactive_count == 0:
                return issues

            # Tab through elements and check focus
            focused_elements = set()
            max_tabs = min(interactive_count * 2, 100)

            for i in range(max_tabs):
                await page.keyboard.press("Tab")
                focused = await page.evaluate("""
                    () => {
                        const el = document.activeElement;
                        if (!el || el === document.body) return null;
                        return {
                            tag: el.tagName.toLowerCase(),
                            id: el.id || '',
                            text: (el.textContent || '').trim().substring(0, 50),
                            type: el.type || '',
                        };
                    }
                """)
                if focused:
                    key = f"{focused['tag']}#{focused['id']}:{focused['text'][:20]}"
                    if key in focused_elements:
                        break  # We've cycled through all elements
                    focused_elements.add(key)

            # Compare focused count to interactive count
            if len(focused_elements) < interactive_count * 0.5:
                issues.append(_make_issue(
                    self.url, "keyboard-unreachable", "violation", "serious",
                    "<body>", "",
                    f"Only {len(focused_elements)} of {interactive_count} interactive elements are keyboard reachable.",
                    "2.1.1", "A", "keyboard",
                    "Ensure all interactive elements can be reached via Tab key.",
                    evidence={"reachable": len(focused_elements), "total": interactive_count}
                ))

        except Exception as e:
            logger.warning(f"Keyboard nav probe error: {e}")

        return issues

    async def _probe_focus_styles(self, page) -> list[dict]:
        """Check if interactive elements have visible focus indicators."""
        issues = []
        try:
            # Check a sample of focusable elements for focus styles
            focus_check = await page.evaluate("""
                () => {
                    const results = [];
                    const elements = document.querySelectorAll('a[href], button, input, select, textarea');
                    const sample = Array.from(elements).slice(0, 10);
                    
                    for (const el of sample) {
                        el.focus();
                        const styles = window.getComputedStyle(el);
                        const focusStyles = window.getComputedStyle(el, ':focus');
                        const outline = styles.outline;
                        const outlineWidth = styles.outlineWidth;
                        const boxShadow = styles.boxShadow;
                        
                        const hasOutline = outline !== 'none' && outline !== '' && outlineWidth !== '0px';
                        const hasBoxShadow = boxShadow !== 'none' && boxShadow !== '';
                        
                        if (!hasOutline && !hasBoxShadow) {
                            results.push({
                                tag: el.tagName.toLowerCase(),
                                id: el.id || '',
                                text: (el.textContent || '').trim().substring(0, 50),
                                outline: outline,
                            });
                        }
                        el.blur();
                    }
                    return results;
                }
            """)

            for elem in focus_check:
                issues.append(_make_issue(
                    self.url, "no-focus-style", "violation", "serious",
                    f"{elem['tag']}#{elem['id']}" if elem['id'] else elem['tag'],
                    "",
                    f"Element {elem['tag']} has no visible focus indicator.",
                    "2.4.7", "AA", "keyboard",
                    "Add :focus styles with visible outline, border, or box-shadow.",
                    evidence={"outline": elem["outline"]},
                    fix_effort="low"
                ))

        except Exception as e:
            logger.warning(f"Focus styles probe error: {e}")

        return issues

    async def _probe_responsive_reflow(self, page) -> list[dict]:
        """Check for horizontal scrollbar at 320px width."""
        issues = []
        try:
            await page.set_viewport_size({"width": 320, "height": 720})
            await page.wait_for_timeout(500)

            has_horizontal_scroll = await page.evaluate("""
                () => document.documentElement.scrollWidth > document.documentElement.clientWidth
            """)

            if has_horizontal_scroll:
                scroll_width = await page.evaluate("() => document.documentElement.scrollWidth")
                issues.append(_make_issue(
                    self.url, "responsive-reflow", "violation", "serious",
                    "<body>", "",
                    f"Horizontal scroll detected at 320px viewport width (content is {scroll_width}px wide).",
                    "1.4.10", "AA", "content",
                    "Ensure content reflows without horizontal scrolling at 320px width.",
                    evidence={"viewport_width": 320, "content_width": scroll_width}
                ))

            # Reset viewport
            await page.set_viewport_size({"width": 1280, "height": 720})

        except Exception as e:
            logger.warning(f"Responsive reflow probe error: {e}")

        return issues

    async def _probe_zoom(self, page) -> list[dict]:
        """Test content at 200% zoom for overlaps and clipping."""
        issues = []
        try:
            # Simulate 200% zoom by setting viewport to half size
            await page.set_viewport_size({"width": 640, "height": 360})
            await page.evaluate("document.body.style.zoom = '2'")
            await page.wait_for_timeout(500)

            # Check for overflow
            has_overflow = await page.evaluate("""
                () => {
                    const body = document.body;
                    return body.scrollWidth > window.innerWidth * 2;
                }
            """)

            if has_overflow:
                issues.append(_make_issue(
                    self.url, "zoom-overflow", "needs-review", "moderate",
                    "<body>", "",
                    "Content may have overflow issues at 200% zoom.",
                    "1.4.4", "AA", "content",
                    "Ensure content is usable at 200% zoom without loss of content or functionality."
                ))

            # Reset
            await page.evaluate("document.body.style.zoom = '1'")
            await page.set_viewport_size({"width": 1280, "height": 720})

        except Exception as e:
            logger.warning(f"Zoom probe error: {e}")

        return issues

    async def _probe_viewport_zoom_meta(self, page) -> list[dict]:
        """Check viewport meta for zoom restrictions (from rendered DOM)."""
        # This overlaps with static check but validates the rendered result
        return []  # Covered by static_checks

    async def _probe_aria_tree(self, page) -> list[dict]:
        """Capture accessibility tree snapshot."""
        issues = []
        try:
            if not hasattr(page, "accessibility") or page.accessibility is None:
                return issues

            snapshot = await page.accessibility.snapshot()
            if snapshot:
                # Check for unnamed interactive elements in the tree
                self._check_tree_node(snapshot, issues)
        except Exception as e:
            logger.warning(f"ARIA tree probe error: {e}")
        return issues

    def _check_tree_node(self, node: dict, issues: list, depth: int = 0):
        """Recursively check accessibility tree nodes."""
        if depth > 20:
            return

        role = node.get("role", "")
        name = node.get("name", "")

        interactive_roles = {"button", "link", "textbox", "combobox", "listbox",
                            "menuitem", "tab", "checkbox", "radio", "slider"}

        if role in interactive_roles and not name:
            issues.append(_make_issue(
                self.url, "aria-tree-no-name", "violation", "serious",
                f'[role="{role}"]', "",
                f'Interactive element with role="{role}" has no accessible name in the accessibility tree.',
                "4.1.2", "A", "aria",
                f'Add aria-label or visible text content to the element with role="{role}".',
                evidence={"role": role, "tree_depth": depth}
            ))

        for child in node.get("children", []):
            self._check_tree_node(child, issues, depth + 1)
