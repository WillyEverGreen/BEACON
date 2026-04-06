"""
Browser dynamic probes using Playwright.
Deep-scan only: keyboard navigation, focus traps, responsive reflow,
zoom testing, animation detection, ARIA tree snapshots.

World-class features:
- Smart SPA detection (React, Angular, Vue, Next.js, Nuxt)
- Adaptive waiting for dynamic content
- Retry logic for complex sites with CSP/Cloudflare
- Progressive enhancement detection
- Shadow DOM traversal

Playwright is an optional dependency — all probes fail gracefully if unavailable.
"""
import asyncio
import hashlib
import logging
import re
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
    element_str = str(element) if element is not None else ""
    snippet_str = str(html_snippet) if html_snippet is not None else ""
    return {
        "issue_id": issue_id,
        "rule_id": rule_id,
        "issue_type": issue_type,
        "element": element_str,
        "html_snippet": snippet_str[:500] if snippet_str else "",
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
    """Playwright-powered dynamic accessibility probes with world-class SPA support."""

    # SPA framework detection patterns
    SPA_INDICATORS = {
        "react": [
            "__REACT_DEVTOOLS_GLOBAL_HOOK__",
            "_reactRootContainer",
            "__NEXT_DATA__",
            "data-reactroot",
        ],
        "angular": [
            "ng-version",
            "ng-app",
            "_ng_",
            "__ngContext__",
        ],
        "vue": [
            "__VUE__",
            "__vue__",
            "__NUXT__",
            "data-v-",
        ],
        "svelte": [
            "__svelte",
        ],
    }

    def __init__(self, url: str, timeout: int = 30000, max_retries: int = 2):
        self.url = url
        self.timeout = timeout
        self.max_retries = max_retries
        self.detected_framework: Optional[str] = None
        self.is_spa: bool = False

    async def _detect_spa_framework(self, page) -> Optional[str]:
        """Detect if the page is a SPA and identify the framework."""
        try:
            detection_result = await page.evaluate("""
                () => {
                    const result = { framework: null, is_spa: false, indicators: [] };
                    
                    // React detection
                    if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__ ||
                        document.querySelector('[data-reactroot]') ||
                        document.querySelector('#__next') ||
                        window.__NEXT_DATA__) {
                        result.framework = 'react';
                        result.is_spa = true;
                        result.indicators.push('react');
                    }
                    
                    // Angular detection
                    if (window.ng || document.querySelector('[ng-version]') ||
                        document.querySelector('[ng-app]') ||
                        document.querySelector('app-root')) {
                        result.framework = 'angular';
                        result.is_spa = true;
                        result.indicators.push('angular');
                    }
                    
                    // Vue detection
                    if (window.__VUE__ || window.__NUXT__ ||
                        document.querySelector('[data-v-]') ||
                        document.querySelector('#__nuxt')) {
                        result.framework = 'vue';
                        result.is_spa = true;
                        result.indicators.push('vue');
                    }
                    
                    // Svelte detection
                    if (window.__svelte || document.querySelector('[class*="svelte-"]')) {
                        result.framework = 'svelte';
                        result.is_spa = true;
                        result.indicators.push('svelte');
                    }
                    
                    // Generic SPA indicators
                    const hasHistoryAPI = typeof history.pushState === 'function';
                    const hasServiceWorker = 'serviceWorker' in navigator;
                    const hasMinimalHTML = document.body?.innerHTML?.includes('Loading') ||
                                          document.body?.children?.length <= 3;
                    
                    if (hasHistoryAPI && (hasServiceWorker || hasMinimalHTML)) {
                        result.is_spa = true;
                    }
                    
                    return result;
                }
            """)
            
            self.detected_framework = detection_result.get("framework")
            self.is_spa = detection_result.get("is_spa", False)
            
            if self.detected_framework:
                logger.info(f"Detected SPA framework: {self.detected_framework}")
            
            return self.detected_framework
            
        except Exception as e:
            logger.warning(f"SPA detection failed: {e}")
            return None

    async def _wait_for_spa_hydration(self, page, framework: Optional[str] = None) -> bool:
        """Wait for SPA framework to complete hydration/mounting."""
        try:
            # Framework-specific waiting strategies
            if framework == "react":
                # Wait for React to finish initial render
                await page.wait_for_function(
                    """
                    () => {
                        // Next.js specific
                        if (window.__NEXT_DATA__) return true;
                        // General React - look for mounted components
                        const root = document.querySelector('[data-reactroot]') ||
                                    document.querySelector('#root') ||
                                    document.querySelector('#app');
                        return root && root.children.length > 0;
                    }
                    """,
                    timeout=5000
                )
                
            elif framework == "angular":
                await page.wait_for_function(
                    """
                    () => {
                        const appRoot = document.querySelector('app-root');
                        return appRoot && appRoot.children.length > 0;
                    }
                    """,
                    timeout=5000
                )
                
            elif framework == "vue":
                await page.wait_for_function(
                    """
                    () => {
                        // Nuxt.js specific
                        if (window.__NUXT__ && window.__NUXT__.data) return true;
                        // General Vue
                        const app = document.querySelector('#app') || document.querySelector('#__nuxt');
                        return app && app.children.length > 0;
                    }
                    """,
                    timeout=5000
                )
            else:
                # Generic SPA waiting: wait for meaningful content
                await page.wait_for_function(
                    """
                    () => {
                        const body = document.body;
                        if (!body) return false;
                        // Wait for actual content beyond loading spinners
                        const text = body.innerText || '';
                        const hasContent = text.length > 100;
                        const noLoadingSpinner = !document.querySelector('.loading, .spinner, [class*="loading"]');
                        return hasContent && noLoadingSpinner;
                    }
                    """,
                    timeout=5000
                )
            
            logger.info(f"SPA hydration complete for {framework or 'generic SPA'}")
            return True
            
        except Exception as e:
            logger.warning(f"SPA hydration wait failed (continuing anyway): {e}")
            return False

    async def _navigate_with_retry(self, page, retry_count: int = 0) -> bool:
        """Navigate to URL with retry logic for CSP/Cloudflare/bot protection."""
        wait_strategies = ["networkidle", "domcontentloaded", "load", "commit"]
        
        for strategy in wait_strategies:
            try:
                await page.goto(
                    self.url,
                    timeout=self.timeout,
                    wait_until=strategy
                )
                
                # Check for bot protection pages
                is_blocked = await page.evaluate("""
                    () => {
                        const text = document.body?.innerText?.toLowerCase() || '';
                        const blockers = [
                            'checking your browser',
                            'please wait',
                            'access denied',
                            'captcha',
                            'are you a robot',
                            'security check',
                        ];
                        return blockers.some(b => text.includes(b));
                    }
                """)
                
                if is_blocked:
                    logger.warning(f"Bot protection detected, waiting...")
                    await asyncio.sleep(2)
                    # Try to wait for redirect
                    try:
                        await page.wait_for_load_state("networkidle", timeout=10000)
                    except:
                        pass
                
                return True
                
            except Exception as e:
                logger.warning(f"Navigation with {strategy} failed: {e}")
                continue
        
        # Retry logic
        if retry_count < self.max_retries:
            logger.info(f"Retrying navigation (attempt {retry_count + 2})")
            await asyncio.sleep(1)
            return await self._navigate_with_retry(page, retry_count + 1)
        
        return False

    async def run_all(self) -> tuple[list[dict], Optional[str], dict]:
        """
        Run all browser probes with world-class SPA support.
        
        Returns (issues, rendered_html, metadata) tuple.
        rendered_html can be used by static checks on the fully rendered DOM.
        metadata contains framework detection, timing, and probe execution info.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            logger.warning("Playwright not available — skipping browser probes")
            return [], None, {"error": "playwright_unavailable"}

        issues = []
        rendered_html = None
        metadata = {
            "spa_framework": None,
            "is_spa": False,
            "navigation_strategy": None,
            "hydration_waited": False,
            "probes_executed": [],
            "probes_failed": [],
            "shadow_dom_detected": False,
        }

        try:
            async with async_playwright() as p:
                # Launch with additional options for complex sites
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-web-security",  # Handle CSP issues
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-features=IsolateOrigins,site-per-process",
                    ]
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    bypass_csp=True,  # Bypass CSP for axe-core injection
                    java_script_enabled=True,
                )
                
                # Enable request interception for better debugging
                page = await context.new_page()
                page.set_default_timeout(self.timeout)

                # Navigate with retry logic
                nav_success = await self._navigate_with_retry(page)
                if not nav_success:
                    logger.error(f"Failed to load page after retries: {self.url}")
                    await browser.close()
                    return [], None, {"error": "navigation_failed"}
                
                metadata["navigation_strategy"] = "retry_with_fallback"

                # Detect SPA framework
                framework = await self._detect_spa_framework(page)
                metadata["spa_framework"] = framework
                metadata["is_spa"] = self.is_spa
                
                # Wait for SPA hydration if detected
                if self.is_spa:
                    hydration_success = await self._wait_for_spa_hydration(page, framework)
                    metadata["hydration_waited"] = hydration_success
                    
                    # Additional wait for lazy-loaded content
                    try:
                        await page.wait_for_load_state("networkidle", timeout=5000)
                    except:
                        pass

                # Check for Shadow DOM
                has_shadow_dom = await page.evaluate("""
                    () => {
                        const allElements = document.querySelectorAll('*');
                        for (const el of allElements) {
                            if (el.shadowRoot) return true;
                        }
                        return false;
                    }
                """)
                metadata["shadow_dom_detected"] = has_shadow_dom
                
                if has_shadow_dom:
                    logger.info("Shadow DOM detected — some probes may have limited coverage")

                # Capture rendered HTML (including shadow DOM content if possible)
                rendered_html = await page.content()
                
                # If Shadow DOM present, try to extract its content
                if has_shadow_dom:
                    try:
                        shadow_content = await page.evaluate("""
                            () => {
                                const extractShadow = (root) => {
                                    let html = '';
                                    const walk = (node) => {
                                        if (node.shadowRoot) {
                                            html += node.shadowRoot.innerHTML;
                                            node.shadowRoot.querySelectorAll('*').forEach(walk);
                                        }
                                    };
                                    root.querySelectorAll('*').forEach(walk);
                                    return html;
                                };
                                return extractShadow(document);
                            }
                        """)
                        if shadow_content:
                            # Append shadow content as a comment for static analysis
                            rendered_html += f"\n<!-- SHADOW_DOM_CONTENT:\n{shadow_content}\n-->"
                    except Exception as e:
                        logger.warning(f"Shadow DOM extraction failed: {e}")

                # Run probes
                probe_methods = [
                    self._probe_keyboard_nav,
                    self._probe_focus_styles,
                    self._probe_responsive_reflow,
                    self._probe_zoom,
                    self._probe_text_spacing_computed_style,
                    self._probe_viewport_zoom_meta,
                    self._probe_aria_tree,
                    self._probe_target_size,
                    self._probe_focus_obscurance,
                    self._probe_animation_motion,  # New: detect motion issues
                    self._probe_lazy_loading,      # New: detect lazy-load issues
                ]

                for probe in probe_methods:
                    probe_name = probe.__name__
                    try:
                        probe_issues = await probe(page)
                        issues.extend(probe_issues)
                        metadata["probes_executed"].append(probe_name)
                    except Exception as e:
                        logger.warning(f"Probe {probe_name} failed: {e}")
                        metadata["probes_failed"].append({"probe": probe_name, "error": str(e)[:100]})

                await browser.close()

        except Exception as e:
            logger.error(f"Browser probing failed: {e}")
            metadata["error"] = str(e)[:200]

        return issues, rendered_html, metadata

    @staticmethod
    async def validate_element_visibility(page, selectors: list[str]) -> dict[str, bool]:
        """
        Batch-check which CSS selectors are actually visible to the user.
        Returns a dict of {selector: is_visible}. Runs as a single JS call.
        Fail-open: if a selector can't be found or errors, assume visible.
        Timeout: hard cap at 2 seconds to avoid blocking the pipeline.
        """
        if not selectors or not page:
            return {}
        
        # Limit batch size to prevent JS execution timeouts
        batch = selectors[:500]
        
        try:
            import asyncio
            result = await asyncio.wait_for(
                page.evaluate("""
                    (selectors) => {
                        const result = {};
                        for (const sel of selectors) {
                            try {
                                const el = document.querySelector(sel);
                                if (!el) { result[sel] = false; continue; }
                                const style = window.getComputedStyle(el);
                                const rect = el.getBoundingClientRect();
                                result[sel] = (
                                    style.display !== 'none' &&
                                    style.visibility !== 'hidden' &&
                                    parseFloat(style.opacity || '1') > 0 &&
                                    rect.width > 0 && rect.height > 0
                                );
                            } catch (e) { result[sel] = true; }
                        }
                        return result;
                    }
                """, batch),
                timeout=2.0  # Hard 2s timeout
            )
            return result
        except Exception as e:
            logger.warning(f"Visibility validation failed (fail-open): {e}")
            # Fail open: assume everything is visible
            return {sel: True for sel in batch}

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
            await page.evaluate("() => { if (document.body) document.body.style.zoom = '2'; }")
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
            await page.evaluate("() => { if (document.body) document.body.style.zoom = '1'; }")
            await page.set_viewport_size({"width": 1280, "height": 720})

        except Exception as e:
            logger.warning(f"Zoom probe error: {e}")

        return issues

    async def _probe_text_spacing_computed_style(self, page) -> list[dict]:
        """Detect text-spacing issues using computed styles with conservative guards."""
        issues = []
        try:
            findings = await page.evaluate(
                """
                () => {
                    const results = [];
                    const selectors = 'p, li, td, th, blockquote, article p, section p, div, span';
                    const nodes = Array.from(document.querySelectorAll(selectors));

                    const weakSet = new Set();

                    const visible = (el, style) => {
                        if (!el) return false;
                        if (style.display === 'none' || style.visibility === 'hidden') return false;
                        if (parseFloat(style.opacity || '1') === 0) return false;
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0;
                    };

                    const makeSelector = (el) => {
                        const tag = (el.tagName || '').toLowerCase();
                        const id = el.id ? `#${el.id}` : '';
                        const cls = (el.className && typeof el.className === 'string')
                            ? '.' + el.className.trim().split(/\\s+/).slice(0, 2).join('.')
                            : '';
                        return `${tag}${id}${cls}`;
                    };

                    for (const el of nodes) {
                        if (!el || !el.tagName) continue;
                        if (el.closest('button, nav, input, select, textarea, [role="button"], [role="navigation"]')) {
                            continue;
                        }

                        const text = (el.innerText || '').trim();
                        if (text.length < 40) continue;

                        const style = window.getComputedStyle(el);
                        if (!visible(el, style)) continue;

                        const fontSize = parseFloat(style.fontSize || '0');
                        const lineHeight = parseFloat(style.lineHeight || '0');

                        // Ignore tiny UI text to reduce false positives.
                        if (!Number.isFinite(fontSize) || fontSize < 12) continue;
                        if (!Number.isFinite(lineHeight) || lineHeight <= 0) continue;

                        const lsRaw = style.letterSpacing || 'normal';
                        if (lsRaw === 'normal') continue;
                        const lsPx = parseFloat(lsRaw);
                        if (!Number.isFinite(lsPx)) continue;

                        const lineHeightRatio = lineHeight / fontSize;
                        const letterSpacingEm = lsPx / fontSize;

                        if (lineHeightRatio < 1.5 && letterSpacingEm < 0.12) {
                            const key = makeSelector(el) + '|' + text.slice(0, 40);
                            if (weakSet.has(key)) continue;
                            weakSet.add(key);

                            results.push({
                                selector: makeSelector(el),
                                snippet: (el.outerHTML || '').slice(0, 280),
                                fontSize,
                                lineHeight,
                                lineHeightRatio,
                                letterSpacingPx: lsPx,
                                letterSpacingEm,
                            });
                        }
                    }

                    return results.slice(0, 20);
                }
                """
            )

            for item in findings:
                issues.append(_make_issue(
                    self.url,
                    "text-spacing",
                    "violation",
                    "moderate",
                    item.get("selector", "<element>"),
                    item.get("snippet", ""),
                    "Computed style indicates insufficient text spacing for robust readability.",
                    "1.4.12",
                    "AA",
                    "content",
                    "Increase line-height to at least 1.5 and letter-spacing to at least 0.12em for visible body text.",
                    evidence={
                        "font_size_px": item.get("fontSize"),
                        "line_height_px": item.get("lineHeight"),
                        "line_height_ratio": item.get("lineHeightRatio"),
                        "letter_spacing_px": item.get("letterSpacingPx"),
                        "letter_spacing_em": item.get("letterSpacingEm"),
                    },
                    fix_effort="low",
                ))

        except Exception as e:
            logger.warning(f"Text spacing probe error: {e}")

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

    async def _probe_target_size(self, page) -> list[dict]:
        """WCAG 2.5.8 Target Size Minimum: Ensure interactive targets are at least 24x24px."""
        issues = []
        try:
            findings = await page.evaluate(
                """
                () => {
                    const results = [];
                    const interactives = document.querySelectorAll('a[href], button, [role="button"], input[type="submit"], input[type="button"]');
                    for (const el of Array.from(interactives)) {
                        const style = window.getComputedStyle(el);
                        if (style.display === 'none' || style.visibility === 'hidden') continue;
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            if (rect.width < 24 || rect.height < 24) {
                                results.push({
                                    tag: el.tagName.toLowerCase(),
                                    id: el.id ? '#' + el.id : '',
                                    text: (el.textContent || '').trim().substring(0, 30),
                                    html: (el.outerHTML || '').slice(0, 150),
                                    w: rect.width,
                                    h: rect.height
                                });
                            }
                        }
                    }
                    return results.slice(0, 20);
                }
                """
            )
            for item in findings:
                selector = item["tag"] + item["id"]
                issues.append(_make_issue(
                    self.url, "target-size-minimum", "violation", "moderate",
                    selector, item["html"],
                    f"Interactive element is too small ({item['w']}x{item['h']}px). Must be at least 24x24px.",
                    "2.5.8", "AA", "target",
                    "Increase the padding, min-width, and min-height of the target to at least 24px.",
                    evidence={"width": item["w"], "height": item["h"]}
                ))
        except Exception as e:
            logger.warning(f"Target size probe error: {e}")
        return issues

    async def _probe_focus_obscurance(self, page) -> list[dict]:
        """WCAG 2.4.11 Focus Obscured (Minimum): Ensure focused elements are not completely hidden by fixed/sticky content."""
        issues = []
        try:
            interactive_count = await page.evaluate(
                "() => document.querySelectorAll('a[href], button, input:not([type=\"hidden\"]), select, textarea, [tabindex]:not([tabindex=\"-1\"])').length"
            )
            if interactive_count == 0:
                return issues

            max_tabs = min(interactive_count * 2, 50)
            obscured_found = 0

            for i in range(max_tabs):
                await page.keyboard.press("Tab")
                await page.wait_for_timeout(50)
                
                obscured = await page.evaluate("""
                    () => {
                        const el = document.activeElement;
                        if (!el || el === document.body) return null;
                        
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return null;
                        
                        const cx = rect.left + rect.width / 2;
                        const cy = rect.top + rect.height / 2;
                        
                        if (cx < 0 || cy < 0 || cx > window.innerWidth || cy > window.innerHeight) {
                            return null;
                        }
                        
                        const topEl = document.elementFromPoint(cx, cy);
                        if (!topEl) return null;
                        
                        if (topEl !== el && !topEl.contains(el) && !el.contains(topEl)) {
                            const style = window.getComputedStyle(topEl);
                            if (style.position === 'fixed' || style.position === 'sticky') {
                                return {
                                    tag: el.tagName.toLowerCase(),
                                    id: el.id ? '#' + el.id : '',
                                    text: (el.textContent || '').trim().substring(0, 30),
                                    html: (el.outerHTML || '').slice(0, 150),
                                    obscuredBy: topEl.tagName.toLowerCase() + (topEl.id ? '#' + topEl.id : '') + '.' + topEl.className
                                };
                            }
                        }
                        return null;
                    }
                """)
                if obscured:
                    selector = obscured["tag"] + obscured["id"]
                    issues.append(_make_issue(
                        self.url, "focus-obscured", "violation", "serious",
                        selector, obscured["html"],
                        f"Focused element is hidden behind a sticky/fixed element ({obscured['obscuredBy']}).",
                        "2.4.11", "AA", "keyboard",
                        "Ensure scroll-padding-top is applied or sticky headers don't cover focused elements.",
                        evidence={"obscured_by": obscured["obscuredBy"]}
                    ))
                    obscured_found += 1
                    if obscured_found >= 5:
                        break
        except Exception as e:
            logger.warning(f"Focus obscurance probe error: {e}")
        return issues

    async def _probe_animation_motion(self, page) -> list[dict]:
        """WCAG 2.3.3 Animation from Interactions: Detect excessive motion that could cause vestibular issues."""
        issues = []
        try:
            motion_findings = await page.evaluate("""
                () => {
                    const findings = [];
                    const allElements = document.querySelectorAll('*');
                    
                    for (const el of allElements) {
                        const style = window.getComputedStyle(el);
                        const animation = style.animation || style.webkitAnimation;
                        const transition = style.transition || style.webkitTransition;
                        const transform = style.transform || style.webkitTransform;
                        
                        // Check for animations
                        if (animation && animation !== 'none' && animation.length > 10) {
                            // Check animation duration
                            const duration = style.animationDuration || '0s';
                            const durationMs = parseFloat(duration) * (duration.includes('ms') ? 1 : 1000);
                            
                            // Infinite animations or long animations are concerning
                            const isInfinite = style.animationIterationCount === 'infinite';
                            
                            if (isInfinite || durationMs > 5000) {
                                findings.push({
                                    type: 'animation',
                                    element: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''),
                                    html: (el.outerHTML || '').slice(0, 200),
                                    isInfinite: isInfinite,
                                    duration: durationMs
                                });
                            }
                        }
                        
                        // Check for autoplay media
                        if (el.tagName === 'VIDEO' || el.tagName === 'AUDIO') {
                            if (el.autoplay && !el.paused) {
                                findings.push({
                                    type: 'autoplay',
                                    element: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''),
                                    html: (el.outerHTML || '').slice(0, 200),
                                });
                            }
                        }
                    }
                    
                    // Check for CSS animations that are not user-triggered
                    const styleSheets = document.styleSheets;
                    let problematicKeyframes = 0;
                    
                    try {
                        for (const sheet of styleSheets) {
                            try {
                                const rules = sheet.cssRules || sheet.rules;
                                for (const rule of rules) {
                                    if (rule.type === CSSRule.KEYFRAMES_RULE) {
                                        problematicKeyframes++;
                                    }
                                }
                            } catch (e) { /* Cross-origin stylesheets */ }
                        }
                    } catch (e) {}
                    
                    // Check for prefers-reduced-motion support
                    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
                    
                    return {
                        findings: findings.slice(0, 10),
                        keyframeCount: problematicKeyframes,
                        prefersReducedMotion: prefersReducedMotion
                    };
                }
            """)
            
            for finding in motion_findings.get("findings", []):
                if finding["type"] == "animation":
                    issues.append(_make_issue(
                        self.url, "excessive-motion", "needs-review", "moderate",
                        finding["element"], finding["html"],
                        f"Potentially problematic animation detected {'(infinite loop)' if finding.get('isInfinite') else ''}. Users with vestibular disorders may be affected.",
                        "2.3.3", "AAA", "animation",
                        "Respect prefers-reduced-motion media query. Provide controls to pause/stop animations.",
                        evidence={"is_infinite": finding.get("isInfinite"), "duration_ms": finding.get("duration")}
                    ))
                elif finding["type"] == "autoplay":
                    issues.append(_make_issue(
                        self.url, "autoplay-media", "violation", "moderate",
                        finding["element"], finding["html"],
                        "Media element autoplays. This can be disorienting for users and violates WCAG.",
                        "1.4.2", "A", "media",
                        "Remove autoplay or provide immediate controls to pause.",
                    ))
                    
        except Exception as e:
            logger.warning(f"Animation/motion probe error: {e}")
        return issues

    async def _probe_lazy_loading(self, page) -> list[dict]:
        """Detect lazy-loaded content that may have accessibility issues."""
        issues = []
        try:
            # Scroll to bottom to trigger lazy loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)
            
            lazy_findings = await page.evaluate("""
                () => {
                    const findings = [];
                    
                    // Check for images with loading="lazy" that are missing alt
                    const lazyImages = document.querySelectorAll('img[loading="lazy"]');
                    for (const img of lazyImages) {
                        if (!img.hasAttribute('alt')) {
                            findings.push({
                                type: 'lazy-img-no-alt',
                                element: 'img' + (img.id ? '#' + img.id : ''),
                                html: (img.outerHTML || '').slice(0, 200),
                                src: img.src || img.dataset?.src || ''
                            });
                        }
                    }
                    
                    // Check for infinite scroll patterns without keyboard support
                    const hasInfiniteScroll = 
                        document.querySelector('[data-infinite-scroll]') ||
                        document.querySelector('.infinite-scroll') ||
                        document.querySelector('[class*="infinite"]');
                    
                    if (hasInfiniteScroll) {
                        findings.push({
                            type: 'infinite-scroll',
                            element: 'page',
                            html: ''
                        });
                    }
                    
                    // Check for skeleton loaders that might be announced incorrectly
                    const skeletons = document.querySelectorAll('[class*="skeleton"], [class*="loading"], [class*="placeholder"]');
                    const visibleSkeletons = Array.from(skeletons).filter(el => {
                        const style = window.getComputedStyle(el);
                        return style.display !== 'none' && style.visibility !== 'hidden';
                    });
                    
                    if (visibleSkeletons.length > 3) {
                        findings.push({
                            type: 'skeleton-loaders',
                            element: 'multiple',
                            count: visibleSkeletons.length
                        });
                    }
                    
                    return findings;
                }
            """)
            
            for finding in lazy_findings:
                if finding["type"] == "lazy-img-no-alt":
                    issues.append(_make_issue(
                        self.url, "lazy-img-missing-alt", "violation", "serious",
                        finding["element"], finding["html"],
                        "Lazy-loaded image is missing alt attribute.",
                        "1.1.1", "A", "images",
                        "Add alt attribute to all images, including lazy-loaded ones.",
                        evidence={"src": finding.get("src", "")[:100]}
                    ))
                elif finding["type"] == "infinite-scroll":
                    issues.append(_make_issue(
                        self.url, "infinite-scroll-accessibility", "needs-review", "moderate",
                        finding["element"], "",
                        "Infinite scroll detected. This pattern can cause navigation issues for keyboard and screen reader users.",
                        "2.4.1", "A", "navigation",
                        "Provide alternative navigation methods (pagination, 'Load More' button) and announce new content to screen readers.",
                    ))
                elif finding["type"] == "skeleton-loaders":
                    issues.append(_make_issue(
                        self.url, "skeleton-loading-state", "needs-review", "minor",
                        "multiple elements", "",
                        f"Multiple skeleton loaders detected ({finding['count']} elements). Ensure loading states are announced to screen readers.",
                        "4.1.3", "AA", "aria",
                        "Use aria-busy='true' on loading containers and announce when content is ready.",
                    ))
                    
            # Scroll back to top
            await page.evaluate("window.scrollTo(0, 0)")
            
        except Exception as e:
            logger.warning(f"Lazy loading probe error: {e}")
        return issues
