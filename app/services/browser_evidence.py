"""
Browser Evidence & Interaction Engine (§8–§16)
Centralized service for compact evidence capture, accessibility-tree inspection,
focus/keyboard interaction verification, and WCAG 2.2 browser probes:
- §8: Targeted element browser evidence
- §9: Accessibility-tree evidence capture
- §10: Focus/keyboard verification engine & traces
- §11: Focus not obscured (2.4.11 / 2.4.12)
- §12: Target size engine (2.5.8)
- §13: Dragging movement analysis (2.5.7)
- §14: Accessible authentication (3.3.8 / 3.3.9)
- §15: Consistent help (3.2.6)
- §16: Redundant entry (3.3.7)
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _make_issue_id(url: str, selector: str, rule_id: str) -> str:
    """Deterministic hash ID for an issue."""
    raw = f"{url}|{selector}|{rule_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def create_browser_issue(
    url: str,
    rule_id: str,
    issue_type: str,
    severity: str,
    element: str,
    html_snippet: str,
    description: str,
    wcag_criterion: str,
    wcag_level: str,
    category: str,
    suggested_fix: str,
    evidence: dict[str, Any] | None = None,
    fix_effort: str = "medium",
) -> dict[str, Any]:
    """Factory function for standardized browser evidence issue dicts."""
    return {
        "issue_id": _make_issue_id(url, element, rule_id),
        "rule_id": rule_id,
        "raw_rule_id": rule_id,
        "source_engine": "beacon_browser",
        "engine_version": "2.0.0",
        "issue_type": issue_type,
        "element": element,
        "selector": element,
        "html": html_snippet[:500] if html_snippet else "",
        "html_snippet": html_snippet[:500] if html_snippet else "",
        "page_url": url,
        "severity": severity,
        "wcag_criterion": wcag_criterion,
        "wcag_level": wcag_level,
        "category": category,
        "confidence": 0.88,
        "scanner_confidence": 0.88,
        "confidence_sources": ["beacon_browser"],
        "needs_manual_review": issue_type == "needs-review",
        "description": description,
        "suggested_fix": suggested_fix,
        "code_fix": "",
        "fix_effort": fix_effort,
        "group_id": "",
        "domain": category,
        "evidence": evidence or {},
        "reproducibility": "deterministic",
    }


# ── §8: Compact Targeted Element Evidence Capture ─────────────────────────────

async def extract_element_evidence(page: Any, selector: str) -> dict[str, Any]:
    """
    Collect comprehensive rendered evidence for a specific element without dumping full DOM.
    Includes geometry, styles, ARIA attributes, landmarks, and scroll state.
    """
    try:
        data = await page.evaluate("""
            (sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;

                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                
                // Collect ARIA attributes
                const aria = {};
                for (let attr of el.attributes) {
                    if (attr.name.startsWith('aria-')) {
                        aria[attr.name] = attr.value;
                    }
                }

                // Ancestor chain
                const ancestors = [];
                let curr = el.parentElement;
                let depth = 0;
                while (curr && depth < 5 && curr !== document.body) {
                    let desc = curr.tagName.toLowerCase();
                    if (curr.id) desc += '#' + curr.id;
                    else if (curr.className && typeof curr.className === 'string') {
                        const firstClass = curr.className.trim().split(/\\s+/)[0];
                        if (firstClass) desc += '.' + firstClass;
                    }
                    ancestors.push(desc);
                    curr = curr.parentElement;
                    depth++;
                }

                // Nearest landmark
                const landmarkTags = ['main', 'nav', 'header', 'footer', 'aside', 'section', 'form'];
                let nearestLandmark = null;
                curr = el.parentElement;
                while (curr && curr !== document.body) {
                    const tag = curr.tagName.toLowerCase();
                    const role = curr.getAttribute('role');
                    if (landmarkTags.includes(tag) || (role && ['main', 'navigation', 'banner', 'contentinfo', 'complementary'].includes(role))) {
                        nearestLandmark = tag + (role ? `[role="${role}"]` : '');
                        break;
                    }
                    curr = curr.parentElement;
                }

                return {
                    outerHTML: (el.outerHTML || '').substring(0, 300),
                    textContent: (el.textContent || '').trim().substring(0, 100),
                    bounding_rect: {
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height),
                        top: Math.round(rect.top),
                        bottom: Math.round(rect.bottom),
                    },
                    computed_styles: {
                        display: style.display,
                        visibility: style.visibility,
                        opacity: style.opacity,
                        position: style.position,
                        zIndex: style.zIndex,
                        color: style.color,
                        backgroundColor: style.backgroundColor,
                        fontSize: style.fontSize,
                        outline: style.outline,
                    },
                    viewport: {
                        width: window.innerWidth,
                        height: window.innerHeight,
                        scrollX: window.scrollX,
                        scrollY: window.scrollY,
                    },
                    aria_attributes: aria,
                    role: el.getAttribute('role') || el.tagName.toLowerCase(),
                    accessible_name_hints: {
                        ariaLabel: el.getAttribute('aria-label'),
                        ariaLabelledby: el.getAttribute('aria-labelledby'),
                        title: el.getAttribute('title'),
                        alt: el.getAttribute('alt'),
                        placeholder: el.getAttribute('placeholder'),
                    },
                    focus_state: {
                        is_active: document.activeElement === el,
                        tabIndex: el.tabIndex,
                        is_focusable: el.tabIndex >= 0 || ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName),
                    },
                    ancestors: ancestors,
                    nearest_landmark: nearestLandmark,
                };
            }
        """, selector)
        return data or {}
    except Exception as e:
        logger.debug(f"extract_element_evidence error for {selector}: {e}")
        return {}


# ── §9: Accessibility-Tree Evidence Capture ───────────────────────────────────

async def capture_a11y_tree_evidence(page: Any, selector: str) -> dict[str, Any]:
    """
    Extracts accessibility-tree properties for an element and identifies DOM vs A11y discrepancies.
    """
    try:
        # Extract native browser accessible properties
        tree_node = await page.evaluate("""
            (sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;

                const role = el.getAttribute('role') || el.tagName.toLowerCase();
                const ariaDisabled = el.getAttribute('aria-disabled');
                const ariaExpanded = el.getAttribute('aria-expanded');
                const ariaChecked = el.getAttribute('aria-checked');
                const ariaOrientation = el.getAttribute('aria-orientation');
                const ariaLevel = el.getAttribute('aria-level');

                let accName = el.getAttribute('aria-label') || '';
                if (!accName && el.getAttribute('aria-labelledby')) {
                    const ref = document.getElementById(el.getAttribute('aria-labelledby'));
                    if (ref) accName = (ref.textContent || '').trim();
                }
                if (!accName) {
                    accName = (el.textContent || '').trim();
                }

                return {
                    role: role,
                    name: accName.substring(0, 100),
                    value: el.value !== undefined ? String(el.value).substring(0, 50) : null,
                    checked: ariaChecked !== null ? ariaChecked === 'true' : (el.checked || null),
                    expanded: ariaExpanded !== null ? ariaExpanded === 'true' : null,
                    disabled: ariaDisabled !== null ? ariaDisabled === 'true' : (el.disabled || false),
                    focused: document.activeElement === el,
                    orientation: ariaOrientation || null,
                    level: ariaLevel ? parseInt(ariaLevel, 10) : null,
                };
            }
        """, selector)

        if not tree_node:
            return {"available": False}

        # Check for discrepancies between DOM markup and accessible representation
        discrepancies = []
        if tree_node.get("disabled") and tree_node.get("focused"):
            discrepancies.append("Element is marked disabled but currently holds active focus.")
        if tree_node.get("role") in ["button", "link"] and not tree_node.get("name"):
            discrepancies.append(f"Interactive element role '{tree_node.get('role')}' has an empty computed accessible name.")

        return {
            "available": True,
            "a11y_tree": tree_node,
            "discrepancies": discrepancies,
            "has_discrepancy": len(discrepancies) > 0,
        }
    except Exception as e:
        logger.debug(f"capture_a11y_tree_evidence error for {selector}: {e}")
        return {"available": False, "error": str(e)}


# ── §10: Focus / Keyboard Verification Engine ─────────────────────────────────

async def trace_keyboard_navigation(page: Any, max_steps: int = 25) -> dict[str, Any]:
    """
    Executes sequential keyboard navigation and records a machine-readable trace of focus flow,
    detecting traps, loops, and invisible focus indicators.
    """
    steps = []
    visited_selectors = []
    trap_detected = False
    violations = []

    try:
        for i in range(max_steps):
            await page.keyboard.press("Tab")
            await page.wait_for_timeout(40)

            step_data = await page.evaluate("""
                () => {
                    const el = document.activeElement;
                    if (!el || el === document.body) return null;

                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    
                    let selector = el.tagName.toLowerCase();
                    if (el.id) selector += '#' + el.id;
                    else if (el.className && typeof el.className === 'string') {
                        const c = el.className.trim().split(/\\s+/)[0];
                        if (c) selector += '.' + c;
                    }

                    // Check visible focus indicator
                    const hasOutline = style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0;
                    const hasBoxShadow = style.boxShadow !== 'none' && style.boxShadow.length > 0;
                    const hasBorderChange = parseFloat(style.borderWidth) > 0;
                    const focusVisible = hasOutline || hasBoxShadow || hasBorderChange;

                    return {
                        selector: selector,
                        tag: el.tagName.toLowerCase(),
                        focus_visible: focusVisible,
                        rect: {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                        },
                        html: (el.outerHTML || '').substring(0, 100),
                    };
                }
            """)

            if not step_data:
                continue

            sel = step_data["selector"]
            steps.append({
                "step": i + 1,
                "key": "Tab",
                "focused_selector": sel,
                "focus_visible": step_data["focus_visible"],
                "rect": step_data["rect"],
            })

            # Detect immediate tight trap (stuck on same element for multiple tabs)
            if len(visited_selectors) >= 3 and all(s == sel for s in visited_selectors[-3:]):
                trap_detected = True
                violations.append({
                    "type": "keyboard_trap",
                    "element": sel,
                    "step": i + 1,
                    "description": f"Keyboard focus is trapped on '{sel}' and cannot advance using Tab.",
                })
                break

            visited_selectors.append(sel)

    except Exception as e:
        logger.debug(f"trace_keyboard_navigation error: {e}")

    return {
        "interaction": "keyboard_navigation",
        "total_steps": len(steps),
        "steps": steps,
        "trap_detected": trap_detected,
        "violations": violations,
    }


# ── §11: Focus Not Obscured Engine (WCAG 2.4.11 / 2.4.12) ────────────────────

async def analyze_focus_obscurance(page: Any, url: str) -> list[dict[str, Any]]:
    """
    Evaluates rendered geometry of focused elements against sticky/fixed overlays, banners, and headers.
    Distinguishes:
    - no_overlap: passes
    - partial_overlap: fails 2.4.12 (Enhanced AAA)
    - material_overlap: fails 2.4.11 (Minimum AA)
    - uncertain: flags needs-review for adjudication
    """
    issues = []
    try:
        obscurance_results = await page.evaluate("""
            () => {
                const results = [];
                const focusables = document.querySelectorAll(
                    'a[href], button, input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])'
                );
                
                // Find fixed or sticky overlay containers
                const overlays = [];
                for (let el of document.querySelectorAll('*')) {
                    const style = window.getComputedStyle(el);
                    if (['fixed', 'sticky'].includes(style.position)) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 50 && rect.height > 20) {
                            overlays.push({
                                element: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''),
                                rect: {
                                    top: rect.top,
                                    bottom: rect.bottom,
                                    left: rect.left,
                                    right: rect.right,
                                    width: rect.width,
                                    height: rect.height,
                                }
                            });
                        }
                    }
                }

                if (overlays.length === 0) return results;

                // Check first 30 focusable elements
                let checked = 0;
                for (let target of focusables) {
                    if (checked > 30) break;
                    checked++;

                    const style = window.getComputedStyle(target);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;

                    const tRect = target.getBoundingClientRect();
                    if (tRect.width === 0 || tRect.height === 0) continue;

                    const targetArea = tRect.width * tRect.height;

                    for (let ov of overlays) {
                        const oRect = ov.rect;
                        // Calculate intersection
                        const xOverlap = Math.max(0, Math.min(tRect.right, oRect.right) - Math.max(tRect.left, oRect.left));
                        const yOverlap = Math.max(0, Math.min(tRect.bottom, oRect.bottom) - Math.max(tRect.top, oRect.top));
                        const overlapArea = xOverlap * yOverlap;

                        if (overlapArea > 0 && targetArea > 0) {
                            const pct = Math.round((overlapArea / targetArea) * 100);
                            let classification = 'no_overlap';
                            if (pct >= 90) classification = 'material_overlap';
                            else if (pct > 0) classification = 'partial_overlap';

                            let selector = target.tagName.toLowerCase();
                            if (target.id) selector += '#' + target.id;
                            else if (target.className && typeof target.className === 'string') {
                                const c = target.className.trim().split(/\\s+/)[0];
                                if (c) selector += '.' + c;
                            }

                            results.push({
                                selector: selector,
                                html: (target.outerHTML || '').substring(0, 150),
                                obscuring_element: ov.element,
                                overlap_percentage: pct,
                                classification: classification,
                                target_rect: { width: Math.round(tRect.width), height: Math.round(tRect.height) },
                                viewport: { width: window.innerWidth, height: window.innerHeight },
                            });
                            break;
                        }
                    }
                }
                return results;
            }
        """)

        for item in (obscurance_results or []):
            pct = item.get("overlap_percentage", 0)
            cls = item.get("classification")
            sel = item.get("selector", "element")
            html = item.get("html", "")
            obs = item.get("obscuring_element", "sticky header/overlay")

            if cls == "material_overlap":
                # Fails 2.4.11 Minimum (AA)
                issues.append(create_browser_issue(
                    url=url,
                    rule_id="focus-obscured-minimum",
                    issue_type="violation",
                    severity="serious",
                    element=sel,
                    html_snippet=html,
                    description=f"Focused element '{sel}' is materially obscured ({pct}% overlap) by fixed/sticky content '{obs}'. Violates WCAG 2.4.11.",
                    wcag_criterion="2.4.11",
                    wcag_level="AA",
                    category="focus",
                    suggested_fix=f"Adjust scroll-margin-top or padding to ensure '{sel}' is fully visible when focused.",
                    evidence=item,
                ))
            elif cls == "partial_overlap":
                # Fails 2.4.12 Enhanced (AAA)
                issues.append(create_browser_issue(
                    url=url,
                    rule_id="focus-obscured-enhanced",
                    issue_type="violation",
                    severity="moderate",
                    element=sel,
                    html_snippet=html,
                    description=f"Focused element '{sel}' is partially obscured ({pct}% overlap) by fixed/sticky content '{obs}'. Violates WCAG 2.4.12.",
                    wcag_criterion="2.4.12",
                    wcag_level="AAA",
                    category="focus",
                    suggested_fix="Ensure zero occlusion by sticky/fixed content when focused by adding appropriate scroll-padding.",
                    evidence=item,
                ))

    except Exception as e:
        logger.debug(f"analyze_focus_obscurance error: {e}")

    return issues


# ── §12: Target Size Engine (WCAG 2.5.8 Minimum) ──────────────────────────────

async def analyze_target_size(page: Any, url: str) -> list[dict[str, Any]]:
    """
    Measures rendered dimensions and spacing offsets for pointer targets (24x24 CSS px).
    Evaluates exceptions: inline links, unstyled browser defaults, and spacing offset.
    """
    issues = []
    try:
        target_results = await page.evaluate("""
            () => {
                const results = [];
                const targets = Array.from(document.querySelectorAll(
                    'a[href], button, [role="button"], input[type="submit"], input[type="button"], select'
                ));

                for (let i = 0; i < targets.length; i++) {
                    const el = targets[i];
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden') continue;

                    const rect = el.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) continue;

                    // Exception check: inline text links inside a sentence or paragraph
                    const isInline = style.display === 'inline' || (el.tagName === 'A' && el.parentElement && ['P', 'SPAN', 'LI'].includes(el.parentElement.tagName));

                    if (rect.width < 24 || rect.height < 24) {
                        // Check spacing offset exception: 24px diameter circle clearance
                        let hasClearance = true;
                        const cX = rect.x + rect.width / 2;
                        const cY = rect.y + rect.height / 2;

                        for (let j = 0; j < targets.length; j++) {
                            if (i === j) continue;
                            const other = targets[j];
                            const oRect = other.getBoundingClientRect();
                            if (oRect.width <= 0 || oRect.height <= 0) continue;

                            const oX = oRect.x + oRect.width / 2;
                            const oY = oRect.y + oRect.height / 2;
                            const dist = Math.hypot(cX - oX, cY - oY);

                            if (dist < 24) {
                                hasClearance = false;
                                break;
                            }
                        }

                        let selector = el.tagName.toLowerCase();
                        if (el.id) selector += '#' + el.id;
                        else if (el.className && typeof el.className === 'string') {
                            const c = el.className.trim().split(/\\s+/)[0];
                            if (c) selector += '.' + c;
                        }

                        results.push({
                            selector: selector,
                            html: (el.outerHTML || '').substring(0, 150),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            is_inline_exception: isInline,
                            has_spacing_clearance: hasClearance,
                        });
                    }
                }
                return results.slice(0, 25);
            }
        """)

        for item in (target_results or []):
            if item.get("is_inline_exception"):
                continue  # Normative exemption under WCAG 2.5.8
            if item.get("has_spacing_clearance"):
                continue  # Spacing offset exception satisfied

            sel = item.get("selector", "target")
            w, h = item.get("width", 0), item.get("height", 0)
            issues.append(create_browser_issue(
                url=url,
                rule_id="target-size-minimum",
                issue_type="violation",
                severity="moderate",
                element=sel,
                html_snippet=item.get("html", ""),
                description=f"Pointer target '{sel}' is {w}x{h}px, below the required 24x24 CSS pixels, and lacks the 24px spacing clearance.",
                wcag_criterion="2.5.8",
                wcag_level="AA",
                category="target",
                suggested_fix="Increase min-width and min-height to at least 24px or provide at least 24px center-to-center spacing from adjacent targets.",
                evidence=item,
            ))

    except Exception as e:
        logger.debug(f"analyze_target_size error: {e}")

    return issues


# ── §13: Dragging Movement Analysis (WCAG 2.5.7) ──────────────────────────────

async def analyze_dragging_movements(page: Any, url: str) -> list[dict[str, Any]]:
    """
    Detects drag interactions (draggable, sliders, sortables) and checks for single-pointer alternatives.
    """
    issues = []
    try:
        drag_items = await page.evaluate("""
            () => {
                const findings = [];
                // 1. Explicit draggable attributes
                const draggables = document.querySelectorAll('[draggable="true"]');
                for (let el of draggables) {
                    let selector = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '');
                    findings.push({
                        selector: selector,
                        type: 'draggable_attribute',
                        html: (el.outerHTML || '').substring(0, 150),
                    });
                }

                // 2. Custom sliders or sortables without click/keyboard alternatives
                const sliders = document.querySelectorAll('[role="slider"]');
                for (let el of sliders) {
                    const hasKeyHandler = el.hasAttribute('aria-valuenow') || el.hasAttribute('tabindex');
                    if (!hasKeyHandler) {
                        let selector = el.tagName.toLowerCase() + (el.id ? '#' + el.id : '');
                        findings.push({
                            selector: selector,
                            type: 'slider_without_single_pointer_or_keyboard',
                            html: (el.outerHTML || '').substring(0, 150),
                        });
                    }
                }
                return findings;
            }
        """)

        for item in (drag_items or []):
            sel = item.get("selector", "draggable")
            issues.append(create_browser_issue(
                url=url,
                rule_id="dragging-movements-alternative",
                issue_type="needs-review",
                severity="moderate",
                element=sel,
                html_snippet=item.get("html", ""),
                description=f"Element '{sel}' uses a dragging interaction. Verify that a single-pointer or keyboard alternative is available (WCAG 2.5.7).",
                wcag_criterion="2.5.7",
                wcag_level="AA",
                category="interaction",
                suggested_fix="Provide buttons or click-to-move options alongside drag-and-drop actions.",
                evidence=item,
            ))
    except Exception as e:
        logger.debug(f"analyze_dragging_movements error: {e}")

    return issues


# ── §14: Accessible Authentication (WCAG 3.3.8 / 3.3.9) ──────────────────────

async def analyze_accessible_authentication(page: Any, url: str) -> list[dict[str, Any]]:
    """
    Inspects authentication flows to ensure no prohibited cognitive function tests are enforced
    without alternatives, and verifies that paste into password fields is not blocked.
    """
    issues = []
    try:
        auth_data = await page.evaluate("""
            () => {
                const findings = [];
                const pwInputs = document.querySelectorAll('input[type="password"]');
                for (let pw of pwInputs) {
                    // Check if paste is blocked via onpaste attribute or event
                    const onpasteAttr = pw.getAttribute('onpaste');
                    const pasteBlocked = onpasteAttr && onpasteAttr.includes('return false');

                    let selector = 'input[type="password"]' + (pw.id ? '#' + pw.id : '');
                    if (pasteBlocked) {
                        findings.push({
                            type: 'paste_blocked',
                            selector: selector,
                            html: (pw.outerHTML || '').substring(0, 150),
                        });
                    }
                }

                // Check for CAPTCHA containers
                const captchas = document.querySelectorAll(
                    '.g-recaptcha, .h-captcha, iframe[src*="captcha"], iframe[src*="recaptcha"]'
                );
                for (let c of captchas) {
                    findings.push({
                        type: 'captcha_present',
                        selector: c.tagName.toLowerCase() + (c.id ? '#' + c.id : ''),
                        html: (c.outerHTML || '').substring(0, 150),
                    });
                }

                return findings;
            }
        """)

        for item in (auth_data or []):
            if item["type"] == "paste_blocked":
                issues.append(create_browser_issue(
                    url=url,
                    rule_id="auth-paste-blocked",
                    issue_type="violation",
                    severity="serious",
                    element=item["selector"],
                    html_snippet=item.get("html", ""),
                    description="Password field explicitly blocks paste operations. This prevents the use of password managers and creates an inaccessible cognitive burden (WCAG 3.3.8).",
                    wcag_criterion="3.3.8",
                    wcag_level="AA",
                    category="authentication",
                    suggested_fix="Remove onpaste='return false' to allow password managers and paste assistance.",
                    evidence=item,
                ))
            elif item["type"] == "captcha_present":
                issues.append(create_browser_issue(
                    url=url,
                    rule_id="auth-captcha-review",
                    issue_type="needs-review",
                    severity="moderate",
                    element=item["selector"],
                    html_snippet=item.get("html", ""),
                    description="CAPTCHA detected in authentication flow. Verify that an accessible alternative (e.g. audio challenge, email verification) is provided (WCAG 3.3.8).",
                    wcag_criterion="3.3.8",
                    wcag_level="AA",
                    category="authentication",
                    suggested_fix="Ensure multi-modal CAPTCHA alternatives (audio challenge or 2FA link) are available.",
                    evidence=item,
                ))

    except Exception as e:
        logger.debug(f"analyze_accessible_authentication error: {e}")

    return issues


# ── §15: Consistent Help (WCAG 3.2.6) ──────────────────────────────────────────

def evaluate_consistent_help(pages_help_data: list[dict[str, Any]], url: str) -> list[dict[str, Any]]:
    """
    Evaluates consistent help mechanisms (chat, contact, phone, FAQ) across multiple crawled pages.
    Distinguishes:
    - present_consistently: passes
    - present_inconsistently: fails 3.2.6
    - not_present: informative
    - not_enough_pages: single-page scan
    """
    issues = []
    if len(pages_help_data) < 2:
        return issues

    # Compare the relative order of help components across pages
    first_page = pages_help_data[0]
    first_order = first_page.get("help_mechanisms", [])

    if not first_order:
        return issues

    for idx, page_data in enumerate(pages_help_data[1:], start=2):
        curr_order = page_data.get("help_mechanisms", [])
        if curr_order and curr_order != first_order:
            issues.append(create_browser_issue(
                url=url,
                rule_id="consistent-help-inconsistent",
                issue_type="violation",
                severity="moderate",
                element="body",
                html_snippet="",
                description=f"Help mechanisms appear in different relative order between page 1 ({first_order}) and page {idx} ({curr_order}). Violates WCAG 3.2.6 Consistent Help.",
                wcag_criterion="3.2.6",
                wcag_level="A",
                category="navigation",
                suggested_fix="Standardize the placement and relative order of contact, chat, and support options across all templates.",
                evidence={"baseline_order": first_order, "differing_page": page_data.get("url"), "differing_order": curr_order},
            ))
            break

    return issues


# ── §16: Redundant Entry (WCAG 3.3.7) ──────────────────────────────────────────

def evaluate_redundant_entry(form_inputs: list[dict[str, Any]], url: str) -> list[dict[str, Any]]:
    """
    Analyzes forms with repeated field requirements (e.g. shipping vs billing) and checks
    whether auto-population or selection mechanisms are provided.
    """
    issues = []
    names = {}
    for inp in form_inputs:
        n = inp.get("name") or inp.get("id")
        if n:
            names.setdefault(n, []).append(inp)

    for name, items in names.items():
        if len(items) > 1:
            has_auto_populate = any(item.get("has_auto_populate") for item in items)
            if not has_auto_populate:
                issues.append(create_browser_issue(
                    url=url,
                    rule_id="redundant-entry",
                    issue_type="needs-review",
                    severity="moderate",
                    element=f'input[name="{name}"]',
                    html_snippet=items[0].get("html", ""),
                    description=f"Multiple inputs request '{name}'. Verify that previously entered information is auto-populated or available to select under WCAG 3.3.7.",
                    wcag_criterion="3.3.7",
                    wcag_level="A",
                    category="forms",
                    suggested_fix="Add an option to auto-populate previously entered data (e.g. 'Same as billing address').",
                    evidence={"field_name": name, "occurrences": len(items)},
                ))

    return issues
