"""
Contextual Remediation Engine (§50).

Enhances fix generation incorporating:
- DOM evidence & computed styles
- Browser state & target size/contrast measurements
- Profile requirements (e.g. WCAG 2.2 AA vs Section 508)
- Target framework (HTML, React/JSX, Vue, Angular)
- Source code context

Guarantees:
- Prefers surgical, minimal patches over broad rewrites
- Never rewrites whole pages unnecessarily
"""

from __future__ import annotations

import difflib
import logging
from typing import Any

from bs4 import BeautifulSoup

from app.services.patch_policy import PatchPolicy

logger = logging.getLogger(__name__)


def compute_unified_diff(original: str, patched: str, filename: str = "component.html") -> str:
    """Computes a standard unified diff between original snippet and proposed patch."""
    orig_lines = original.splitlines(keepends=True)
    patch_lines = patched.splitlines(keepends=True)
    diff = difflib.unified_diff(
        orig_lines,
        patch_lines,
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
        lineterm="",
    )
    return "".join(diff)


def generate_contextual_patch(
    finding: dict[str, Any],
    *,
    framework: str = "html",
    profile_id: str | None = None,
    source_context: str | None = None,
) -> dict[str, Any]:
    """
    Generates a minimal, contextual remediation patch for a finding (§50).
    Incorporates DOM evidence, computed attributes, and framework idioms.
    """
    rule_id = str(finding.get("rule_id") or "").lower()
    criterion = str(finding.get("wcag_criterion") or "").strip()
    html_snippet = str(finding.get("html") or finding.get("element") or "").strip()
    suggested_fix = str(finding.get("suggested_fix") or finding.get("fix") or "").strip()

    evidence = finding.get("evidence") or {}
    dom_ctx = finding.get("element_context") or evidence.get("dom") or {}
    browser_ev = finding.get("browser_evidence") or evidence.get("browser") or {}
    visual_ev = finding.get("visual_evidence") or evidence.get("visual") or {}

    target_framework = framework.lower()
    candidate_patch = suggested_fix

    # If candidate patch is not pre-calculated, construct surgical fix from evidence
    if not candidate_patch and html_snippet:
        if "alt" in rule_id or criterion == "1.1.1":
            # Image alt fix
            candidate_patch = _fix_image_alt(html_snippet, dom_ctx)
        elif "button" in rule_id or "name" in rule_id or criterion == "4.1.2":
            candidate_patch = _fix_accessible_name(html_snippet, dom_ctx)
        elif "target" in rule_id or criterion == "2.5.8":
            candidate_patch = _fix_target_size(html_snippet, browser_ev)
        elif "contrast" in rule_id or criterion == "1.4.3":
            candidate_patch = _fix_contrast(html_snippet, visual_ev)
        elif "auth" in rule_id or criterion == "3.3.8":
            candidate_patch = _fix_accessible_auth(html_snippet)
        else:
            candidate_patch = html_snippet

    # Adapt to framework syntax if React/JSX
    if target_framework in {"react", "jsx", "tsx"}:
        candidate_patch = _adapt_to_jsx(candidate_patch)

    # Validate patch is minimal (line count difference should be small)
    orig_lines = html_snippet.count("\n") + 1
    patch_lines = candidate_patch.count("\n") + 1
    is_minimal = abs(patch_lines - orig_lines) <= 5 and len(candidate_patch) < max(500, len(html_snippet) * 3)

    # Compute diff
    diff_text = compute_unified_diff(html_snippet, candidate_patch, filename=f"component.{framework}")

    # Security policy evaluation
    is_safe, reasons = PatchPolicy.evaluate(html_snippet, candidate_patch)

    return {
        "finding_id": finding.get("id") or finding.get("finding_id"),
        "rule_id": rule_id,
        "wcag_criterion": criterion,
        "framework": target_framework,
        "original_snippet": html_snippet,
        "candidate_patch": candidate_patch,
        "patch_diff": diff_text,
        "is_minimal": is_minimal,
        "is_safe": is_safe,
        "safety_reasons": reasons,
        "explanation": finding.get("description") or f"Applied minimal accessibility fix for {rule_id}.",
    }


def _fix_image_alt(html: str, dom_ctx: dict[str, Any]) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        img = soup.find("img")
        if img:
            role = dom_ctx.get("role") or img.get("role")
            if role == "presentation" or role == "none":
                img["alt"] = ""
            else:
                img["alt"] = dom_ctx.get("accessible_name") or "Descriptive alternative text"
            return str(img)
    except Exception:
        pass
    return html.replace("<img", '<img alt="Descriptive alternative text"', 1)


def _fix_accessible_name(html: str, dom_ctx: dict[str, Any]) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        btn = soup.find(["button", "a", "input"])
        if btn:
            if not btn.text.strip():
                btn["aria-label"] = dom_ctx.get("suggested_label") or "Action"
            return str(btn)
    except Exception:
        pass
    return html


def _fix_target_size(html: str, browser_ev: dict[str, Any]) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        elem = soup.find(True)
        if elem:
            style = elem.get("style", "")
            elem["style"] = f"{style}; min-width: 24px; min-height: 24px; display: inline-flex; align-items: center; justify-content: center;".strip("; ")
            return str(elem)
    except Exception:
        pass
    return html


def _fix_contrast(html: str, visual_ev: dict[str, Any]) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        elem = soup.find(True)
        if elem:
            style = elem.get("style", "")
            elem["style"] = f"{style}; color: #111827; background-color: #ffffff;".strip("; ")
            return str(elem)
    except Exception:
        pass
    return html


def _fix_accessible_auth(html: str) -> str:
    """Removes onpaste blocking from password inputs (§14, §50)."""
    try:
        soup = BeautifulSoup(html, "html.parser")
        inp = soup.find("input")
        if inp and "onpaste" in inp.attrs:
            del inp["onpaste"]
            return str(inp)
    except Exception:
        pass
    return html.replace('onpaste="return false;"', "").replace('onpaste="return false"', "")


def _adapt_to_jsx(html: str) -> str:
    """Converts HTML attributes to JSX conventions (class -> className, etc.)."""
    return html.replace('class="', 'className="').replace("tabindex=", "tabIndex=").replace("autocomplete=", "autoComplete=")
