"""
Fix Validator: Re-runs the static checker against proposed code fixes
to validate they actually resolve the flagged issue before storing to cache.
"""
import logging
from typing import Optional
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def validate_fix(original_html_snippet: str, proposed_fix: str, rule_id: str) -> dict:
    """
    Validate a proposed code fix by checking if it resolves the original issue.
    
    Returns:
        {
            "valid": bool,
            "reason": str,
            "confidence": float  # 0.0 - 1.0
        }
    """
    if not proposed_fix or not proposed_fix.strip():
        return {"valid": False, "reason": "Empty fix provided", "confidence": 0.0}

    try:
        # Parse both the original and proposed fix
        original_soup = BeautifulSoup(original_html_snippet, "html.parser")
        fix_soup = BeautifulSoup(proposed_fix, "html.parser")
    except Exception as e:
        return {"valid": False, "reason": f"Parse error: {e}", "confidence": 0.0}

    # Run rule-specific validators
    validator = _VALIDATORS.get(rule_id)
    if validator:
        return validator(original_soup, fix_soup, original_html_snippet, proposed_fix)

    # Fallback: generic structural validation
    return _generic_validate(original_soup, fix_soup, original_html_snippet, proposed_fix)


def _generic_validate(original_soup, fix_soup, original_html: str, fix_html: str) -> dict:
    """Generic validator: ensures the fix changed something and didn't break structure."""
    # Check that *something* changed
    if original_html.strip() == fix_html.strip():
        return {"valid": False, "reason": "Fix is identical to original", "confidence": 0.0}

    # Check it's still valid HTML (has at least one element)
    if not fix_soup.find():
        return {"valid": False, "reason": "Fix produced no HTML elements", "confidence": 0.0}

    return {"valid": True, "reason": "Structural change detected (generic check)", "confidence": 0.6}


# ── Rule-Specific Validators ──────────────────────────────────

def _validate_image_alt(orig, fix, orig_html, fix_html) -> dict:
    """Validate that images now have alt attributes."""
    fix_imgs = fix.find_all("img")
    if not fix_imgs:
        return {"valid": True, "reason": "Image removed (valid remediation)", "confidence": 0.7}

    for img in fix_imgs:
        alt = img.get("alt")
        if alt is None:
            return {"valid": False, "reason": "Image still missing alt attribute", "confidence": 0.0}
        if alt == "":
            # Empty alt is valid for decorative images
            continue
    return {"valid": True, "reason": "All images have alt attributes", "confidence": 0.95}


def _validate_color_contrast(orig, fix, orig_html, fix_html) -> dict:
    """Check that color/background-color CSS was modified."""
    has_color_change = ("color:" in fix_html.lower() and 
                        fix_html.lower() != orig_html.lower())
    if has_color_change:
        return {"valid": True, "reason": "Color properties modified", "confidence": 0.7}
    return {"valid": False, "reason": "No color changes detected in fix", "confidence": 0.2}


def _validate_form_label(orig, fix, orig_html, fix_html) -> dict:
    """Validate that form elements now have associated labels."""
    inputs = fix.find_all(["input", "select", "textarea"])
    for inp in inputs:
        input_id = inp.get("id")
        aria_label = inp.get("aria-label")
        aria_labelledby = inp.get("aria-labelledby")
        
        if aria_label or aria_labelledby:
            continue
        
        if input_id:
            label = fix.find("label", {"for": input_id})
            if label:
                continue
        
        # Check for wrapping label
        parent_label = inp.find_parent("label")
        if parent_label:
            continue
            
        return {"valid": False, "reason": f"Input still lacks label association", "confidence": 0.1}

    return {"valid": True, "reason": "All inputs have label associations", "confidence": 0.9}


def _validate_heading_order(orig, fix, orig_html, fix_html) -> dict:
    """Validate heading hierarchy."""
    headings = fix.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    if not headings:
        return {"valid": False, "reason": "No headings found in fix", "confidence": 0.2}
    
    levels = [int(h.name[1]) for h in headings]
    for i in range(1, len(levels)):
        if levels[i] > levels[i-1] + 1:
            return {"valid": False, "reason": f"Heading skip: h{levels[i-1]} → h{levels[i]}", "confidence": 0.1}
    
    return {"valid": True, "reason": "Heading hierarchy is correct", "confidence": 0.9}


def _validate_link_purpose(orig, fix, orig_html, fix_html) -> dict:
    """Validate that links have discernible text."""
    links = fix.find_all("a")
    for link in links:
        text = link.get_text(strip=True)
        aria_label = link.get("aria-label")
        if not text and not aria_label:
            return {"valid": False, "reason": "Link still has no discernible text", "confidence": 0.0}
        if text and text.lower() in ("click here", "here", "read more", "more", "link"):
            return {"valid": False, "reason": f"Link text '{text}' is still non-descriptive", "confidence": 0.2}
    return {"valid": True, "reason": "All links have descriptive text", "confidence": 0.85}


def _validate_aria_roles(orig, fix, orig_html, fix_html) -> dict:
    """Validate ARIA usage."""
    elements_with_role = fix.find_all(attrs={"role": True})
    valid_roles = {
        "alert", "alertdialog", "application", "article", "banner", "button",
        "cell", "checkbox", "columnheader", "combobox", "complementary",
        "contentinfo", "definition", "dialog", "directory", "document",
        "feed", "figure", "form", "grid", "gridcell", "group", "heading",
        "img", "link", "list", "listbox", "listitem", "log", "main",
        "marquee", "math", "menu", "menubar", "menuitem", "menuitemcheckbox",
        "menuitemradio", "navigation", "none", "note", "option", "presentation",
        "progressbar", "radio", "radiogroup", "region", "row", "rowgroup",
        "rowheader", "scrollbar", "search", "searchbox", "separator",
        "slider", "spinbutton", "status", "switch", "tab", "table",
        "tablist", "tabpanel", "term", "textbox", "timer", "toolbar",
        "tooltip", "tree", "treegrid", "treeitem",
    }
    for el in elements_with_role:
        role = el.get("role", "").strip().lower()
        if role and role not in valid_roles:
            return {"valid": False, "reason": f"Invalid ARIA role: '{role}'", "confidence": 0.1}
    return {"valid": True, "reason": "ARIA roles are valid", "confidence": 0.85}


_VALIDATORS = {
    "image-alt": _validate_image_alt,
    "color-contrast": _validate_color_contrast,
    "label": _validate_form_label,
    "form-label-missing": _validate_form_label,
    "heading-order": _validate_heading_order,
    "empty-heading": _validate_heading_order,
    "link-name": _validate_link_purpose,
    "link-purpose": _validate_link_purpose,
    "aria-roles": _validate_aria_roles,
    "aria-valid-attr-value": _validate_aria_roles,
}
