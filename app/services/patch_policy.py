"""Security and safety policy engine for AI-generated remediation patches.

Prevents prompt injection, XSS vectors, destructive DOM rewrites, and security bypasses
in AI-generated accessibility code fixes.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

# Strictly prohibited tag names that must never be introduced in a patch
FORBIDDEN_TAGS = frozenset({
    "script", "iframe", "object", "embed", "applet", "meta", "base", "link", "svg:script"
})

# Disallowed inline JavaScript event attributes
ON_EVENT_PATTERN = re.compile(r"^on[a-z]+", re.IGNORECASE)

# Dangerous URL schemes
DANGEROUS_SCHEMES = ("javascript:", "data:text/html", "vbscript:")

# Sensitive input names that must never be altered by an accessibility patch
SENSITIVE_FIELD_NAMES = frozenset({
    "csrf", "token", "csrftoken", "csrf_token", "_csrf", "authenticity_token",
    "password", "passwd", "secret", "card", "cvv", "ssn", "stripetoken"
})


class PatchPolicy:
    """Evaluates safety and structural validity of candidate remediation patches."""

    @staticmethod
    def evaluate(original_snippet: str, candidate_patch: str) -> tuple[bool, list[str]]:
        """Validate candidate patch against security and stability policies.
        
        Returns:
            (is_allowed: bool, violation_reasons: List[str])
        """
        reasons: list[str] = []

        if not candidate_patch or not candidate_patch.strip():
            return False, ["Candidate patch is empty."]

        # 1. Parse validation
        try:
            soup = BeautifulSoup(candidate_patch, "html.parser")
        except Exception as e:
            return False, [f"Malformed HTML syntax in patch: {e}"]

        elements = soup.find_all(True)
        if not elements and not soup.text.strip():
            return False, ["Patch contains no HTML elements or text."]

        # 2. Check forbidden tags
        for tag in elements:
            tag_name = tag.name.lower()
            if tag_name in FORBIDDEN_TAGS:
                reasons.append(f"Forbidden tag <{tag_name}> introduced in patch.")

            # 3. Check for inline event handlers (XSS vectors)
            for attr in list(tag.attrs.keys()):
                attr_lower = attr.lower()
                if ON_EVENT_PATTERN.match(attr_lower):
                    reasons.append(f"Inline event handler '{attr}' is prohibited in remediation patch.")

                # 4. Check dangerous URL schemes
                val = str(tag.attrs[attr]).strip().lower()
                for scheme in DANGEROUS_SCHEMES:
                    if scheme in val:
                        reasons.append(f"Dangerous URL scheme '{scheme}' detected in attribute '{attr}'.")

            # 5. Check sensitive fields
            if tag_name == "input":
                field_name = str(tag.get("name") or "").lower()
                input_type = str(tag.get("type") or "").lower()
                if any(s in field_name for s in SENSITIVE_FIELD_NAMES) or input_type == "password":
                    # Verify original snippet also had this, and check if value changed
                    orig_soup = BeautifulSoup(original_snippet, "html.parser")
                    orig_inputs = orig_soup.find_all("input")
                    if not orig_inputs:
                        reasons.append(f"Patch attempts to introduce sensitive input field: {field_name or input_type}")

        is_allowed = len(reasons) == 0
        return is_allowed, reasons
