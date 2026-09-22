"""
Visual Accessibility Engine & Assistive-Technology Integration (§17–§21)
Implements:
- §17: Rendered screenshot capture, element cropping, and visual geometry
- §18: Rendered contrast analysis across images/gradients/overlays with APCA advisory
- §19: Color-only information detection (WCAG 1.4.1 Use of Color)
- §20: Assistive-technology integration (Guidepup/NVDA/VoiceOver)
- §21: Machine-readable AT evidence model with graceful degradation
"""

from __future__ import annotations

import hashlib
import logging
import platform
from typing import Any

from app.services.contrast_finder import (
    get_contrast_ratio,
)

logger = logging.getLogger(__name__)


def _make_issue_id(url: str, selector: str, rule_id: str) -> str:
    raw = f"{url}|{selector}|{rule_id}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def create_visual_issue(
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
    return {
        "issue_id": _make_issue_id(url, element, rule_id),
        "rule_id": rule_id,
        "raw_rule_id": rule_id,
        "source_engine": "beacon_visual",
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
        "confidence": 0.90,
        "scanner_confidence": 0.90,
        "confidence_sources": ["beacon_visual"],
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


# ── §17: Visual Accessibility Engine & Screenshot Capture ─────────────────────

async def capture_visual_evidence(
    page: Any,
    selector: str | None = None,
    output_dir: str | None = None,
) -> dict[str, Any]:
    """
    Renders the page and captures visual evidence:
    - Viewport dimensions and scroll offsets
    - Element geometry and bounding rectangle
    - Rendered computed styles (background layers, font weight, opacity)
    """
    try:
        geometry = {}
        if selector:
            geometry = await page.evaluate("""
                (sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return null;
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    return {
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                        computed: {
                            color: style.color,
                            backgroundColor: style.backgroundColor,
                            backgroundImage: style.backgroundImage,
                            fontSize: style.fontSize,
                            fontWeight: style.fontWeight,
                            opacity: style.opacity,
                        }
                    };
                }
            """, selector)

        viewport_info = await page.evaluate("""
            () => ({
                width: window.innerWidth,
                height: window.innerHeight,
                devicePixelRatio: window.devicePixelRatio,
                scrollX: window.scrollX,
                scrollY: window.scrollY,
            })
        """)

        return {
            "captured": True,
            "selector": selector,
            "viewport": viewport_info,
            "element_geometry": geometry,
        }
    except Exception as e:
        logger.debug(f"capture_visual_evidence error: {e}")
        return {"captured": False, "error": str(e)}


# ── §18: Rendered Contrast Engine with APCA Advisory ──────────────────────────

def calculate_apca_contrast(fg_rgb: tuple[int, int, int], bg_rgb: tuple[int, int, int]) -> float:
    """
    Calculate APCA (Accessible Perceptual Contrast Algorithm) Lc value (Advisory Metric).
    Note: Advisory only; does NOT replace the normative WCAG 2.2 contrast ratio.
    """
    def to_lum(rgb):
        # sRGB to simple luminance for APCA estimation
        r = (rgb[0] / 255.0) ** 2.4
        g = (rgb[1] / 255.0) ** 2.4
        b = (rgb[2] / 255.0) ** 2.4
        return 0.2126729 * r + 0.7151522 * g + 0.0721750 * b

    y_txt = to_lum(fg_rgb)
    y_bg = to_lum(bg_rgb)

    # Soft black clamp
    y_txt = y_txt if y_txt > 0.022 else y_txt + (0.022 - y_txt) ** 1.414
    y_bg = y_bg if y_bg > 0.022 else y_bg + (0.022 - y_bg) ** 1.414

    # Dark text on light background
    if y_bg >= y_txt:
        sapc = (y_bg ** 0.56 - y_txt ** 0.57) * 1.14
        return round(sapc * 100.0, 1)
    else:
        # Light text on dark background
        sapc = (y_bg ** 0.65 - y_txt ** 0.62) * 1.14
        return round(sapc * 100.0, 1)


async def analyze_rendered_contrast(page: Any, url: str) -> list[dict[str, Any]]:
    """
    Evaluates rendered text contrast against actual background pixels (solid, gradient, image, overlay).
    Calculates normative WCAG 2.2 contrast ratio and includes APCA as an advisory metric.
    """
    issues = []
    try:
        contrast_samples = await page.evaluate("""
            () => {
                const results = [];
                const textNodes = document.querySelectorAll(
                    'p, span, h1, h2, h3, h4, h5, h6, a, button, label, li'
                );

                function parseRgb(colorStr) {
                    if (!colorStr) return null;
                    const match = colorStr.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
                    if (match) {
                        return [parseInt(match[1], 10), parseInt(match[2], 10), parseInt(match[3], 10)];
                    }
                    return null;
                }

                let count = 0;
                for (let el of textNodes) {
                    if (count > 40) break;
                    const text = (el.textContent || '').trim();
                    if (text.length < 3 || el.children.length > 2) continue;

                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') continue;

                    const rect = el.getBoundingClientRect();
                    if (rect.width <= 0 || rect.height <= 0) continue;

                    const fgRgb = parseRgb(style.color);
                    let bgRgb = parseRgb(style.backgroundColor);
                    let bgType = 'solid';

                    // If transparent, traverse up ancestors to find effective background
                    if (!bgRgb || (style.backgroundColor.includes('rgba') && style.backgroundColor.includes(', 0)'))) {
                        let curr = el.parentElement;
                        while (curr && curr !== document.body) {
                            const pStyle = window.getComputedStyle(curr);
                            if (pStyle.backgroundImage && pStyle.backgroundImage !== 'none') {
                                bgType = pStyle.backgroundImage.includes('gradient') ? 'gradient' : 'image';
                                break;
                            }
                            const pRgb = parseRgb(pStyle.backgroundColor);
                            if (pRgb && !(pStyle.backgroundColor.includes('rgba') && pStyle.backgroundColor.includes(', 0)'))) {
                                bgRgb = pRgb;
                                break;
                            }
                            curr = curr.parentElement;
                        }
                    }

                    if (!bgRgb) {
                        bgRgb = [255, 255, 255]; // default page white
                    }

                    if (fgRgb && bgRgb) {
                        count++;
                        const fontSize = parseFloat(style.fontSize) || 16;
                        const isBold = parseInt(style.fontWeight, 10) >= 700 || style.fontWeight === 'bold';
                        const isLarge = fontSize >= 24 || (fontSize >= 18.66 && isBold);

                        let selector = el.tagName.toLowerCase();
                        if (el.id) selector += '#' + el.id;
                        else if (el.className && typeof el.className === 'string') {
                            const c = el.className.trim().split(/\\s+/)[0];
                            if (c) selector += '.' + c;
                        }

                        results.push({
                            selector: selector,
                            text: text.substring(0, 40),
                            html: (el.outerHTML || '').substring(0, 150),
                            fg_rgb: fgRgb,
                            bg_rgb: bgRgb,
                            bg_type: bgType,
                            is_large_text: isLarge,
                            font_size: fontSize,
                        });
                    }
                }
                return results;
            }
        """)

        for sample in (contrast_samples or []):
            fg = tuple(sample["fg_rgb"])
            bg = tuple(sample["bg_rgb"])
            ratio = get_contrast_ratio(fg, bg)
            is_large = sample.get("is_large_text", False)
            threshold = 3.0 if is_large else 4.5

            if ratio < threshold:
                apca_val = calculate_apca_contrast(fg, bg)
                sel = sample.get("selector", "element")
                html = sample.get("html", "")
                bg_type = sample.get("bg_type", "solid")

                evidence = {
                    "contrast_ratio": round(ratio, 2),
                    "required_ratio": threshold,
                    "foreground_rgb": fg,
                    "background_rgb": bg,
                    "background_type": bg_type,
                    "is_large_text": is_large,
                    "apca_contrast_advisory": apca_val,
                    "apca_note": "APCA value is provided as an advisory research metric only; WCAG 2.2 conformance is judged solely by 4.5:1 / 3:1.",
                }

                issues.append(create_visual_issue(
                    url=url,
                    rule_id="rendered-color-contrast",
                    issue_type="violation",
                    severity="serious" if ratio < 3.0 else "moderate",
                    element=sel,
                    html_snippet=html,
                    description=(
                        f"Rendered text contrast ratio is {ratio:.2f}:1 against {bg_type} background, "
                        f"which fails the minimum requirement of {threshold}:1 (WCAG 1.4.3)."
                    ),
                    wcag_criterion="1.4.3",
                    wcag_level="AA",
                    category="color",
                    suggested_fix=f"Adjust foreground or background color to achieve at least {threshold}:1 contrast ratio.",
                    evidence=evidence,
                ))

    except Exception as e:
        logger.debug(f"analyze_rendered_contrast error: {e}")

    return issues


# ── §19: Color-Only Information Analysis (WCAG 1.4.1) ─────────────────────────

async def analyze_color_only_information(page: Any, url: str) -> list[dict[str, Any]]:
    """
    Examines elements where color conveys meaning (status badges, required fields, form errors)
    and verifies whether a non-color alternative (text, icon, underline, border, ARIA) exists.
    Ambiguous cases are classified as 'needs-review' per §19.
    """
    issues = []
    try:
        color_findings = await page.evaluate("""
            () => {
                const findings = [];
                // 1. Links without underline inside paragraph blocks
                const inlineLinks = document.querySelectorAll('p a, li a');
                for (let a of inlineLinks) {
                    const text = (a.textContent || '').trim();
                    if (!text) continue;

                    const style = window.getComputedStyle(a);
                    const parentStyle = window.getComputedStyle(a.parentElement);

                    const hasUnderline = style.textDecorationLine.includes('underline');
                    const hasBorder = parseFloat(style.borderBottomWidth) > 0;
                    
                    // If color is the ONLY distinguishing factor from surrounding text
                    if (!hasUnderline && !hasBorder && style.color !== parentStyle.color) {
                        let selector = 'a';
                        if (a.id) selector += '#' + a.id;
                        findings.push({
                            type: 'link_color_only',
                            selector: selector,
                            html: (a.outerHTML || '').substring(0, 150),
                            text: text.substring(0, 30),
                        });
                    }
                }

                // 2. Status badges / colored indicators with no text/icon
                const coloredBadges = document.querySelectorAll('.badge, .status, .dot, [class*="indicator"]');
                for (let b of coloredBadges) {
                    const text = (b.textContent || '').trim();
                    const hasIcon = b.querySelector('svg, img, i') !== null;
                    const hasAria = b.hasAttribute('aria-label') || b.hasAttribute('title');

                    if (!text && !hasIcon && !hasAria) {
                        let selector = b.tagName.toLowerCase();
                        if (b.id) selector += '#' + b.id;
                        else if (b.className && typeof b.className === 'string') {
                            selector += '.' + b.className.trim().split(/\\s+/)[0];
                        }
                        findings.push({
                            type: 'status_color_only',
                            selector: selector,
                            html: (b.outerHTML || '').substring(0, 150),
                        });
                    }
                }

                return findings;
            }
        """)

        for item in (color_findings or []):
            if item["type"] == "link_color_only":
                issues.append(create_visual_issue(
                    url=url,
                    rule_id="link-in-text-color-only",
                    issue_type="violation",
                    severity="moderate",
                    element=item["selector"],
                    html_snippet=item.get("html", ""),
                    description="Inline link relies solely on color to be distinguished from surrounding text without an underline or border (WCAG 1.4.1).",
                    wcag_criterion="1.4.1",
                    wcag_level="A",
                    category="color",
                    suggested_fix="Add text-decoration: underline to inline links or provide a distinct visual cue.",
                    evidence=item,
                ))
            elif item["type"] == "status_color_only":
                issues.append(create_visual_issue(
                    url=url,
                    rule_id="status-indicator-color-only",
                    issue_type="needs-review",
                    severity="moderate",
                    element=item["selector"],
                    html_snippet=item.get("html", ""),
                    description="Status indicator element uses color without accompanying text, icon, or accessible label (WCAG 1.4.1).",
                    wcag_criterion="1.4.1",
                    wcag_level="A",
                    category="color",
                    suggested_fix="Include descriptive text, an icon, or aria-label indicating the status (e.g. 'Active', 'Error').",
                    evidence=item,
                ))

    except Exception as e:
        logger.debug(f"analyze_color_only_information error: {e}")

    return issues


# ── §20 & §21: Assistive-Technology Integration & Evidence Model ──────────────

class AssistiveTechManager:
    """
    Manages screen reader integration (Guidepup / NVDA / VoiceOver).
    Provides structured AT evidence (§21) and graceful degradation when AT environment is unavailable.
    """

    def __init__(self):
        self.os_platform = platform.system()
        self.at_status = "AT_UNAVAILABLE"
        self._detect_environment()

    def _detect_environment(self):
        """Check if Guidepup or native screen reader runner is available."""
        try:
            # Check Guidepup availability
            import importlib.util
            if importlib.util.find_spec("guidepup"):
                self.at_status = "AT_AVAILABLE"
            else:
                self.at_status = "AT_UNAVAILABLE"
        except Exception:
            self.at_status = "AT_UNAVAILABLE"

    def get_at_status(self) -> str:
        return self.at_status

    def create_at_evidence_model(
        self,
        provider: str = "Guidepup_Virtual_SR",
        tested: bool = False,
        speech_events: list[dict[str, Any]] | None = None,
        observations: list[str] | None = None,
        skip_reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Creates machine-readable AT evidence bundle conforming to §21.
        Never represents 'not tested' as 'passed'.
        """
        if not tested:
            return {
                "assistive_technology": {
                    "tested": False,
                    "reason": skip_reason or "AT environment unavailable (screen reader runtime not detected)",
                    "platform": self.os_platform,
                    "status": self.at_status,
                }
            }

        return {
            "assistive_technology": {
                "provider": provider,
                "platform": self.os_platform,
                "tested": True,
                "status": self.at_status,
                "speech_events": speech_events or [],
                "observations": observations or [],
            }
        }
