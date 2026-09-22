"""
Accessibility Statement Draft Generator (§68).

Generates official accessibility statements following W3C, UK PSBAR, and EU EAA models.
Strict Rule (§68):
- Never automatically claims full conformance when unresolved violations or review gaps remain.
- Explicitly lists known non-accessible content and limitations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def generate_accessibility_statement(
    scan_data: dict[str, Any],
    *,
    organization_name: str = "[Organization Name]",
    contact_email: str = "accessibility@example.com",
    contact_phone: str | None = None,
    enforcement_body: str | None = None,
    profile_name: str = "W3C WCAG 2.2 Level AA",
) -> str:
    """
    Generates a draft Accessibility Statement based on verified audit findings (§68).
    """
    target_url = scan_data.get("url") or scan_data.get("seed_url") or "https://example.com"
    findings = scan_data.get("issues") or scan_data.get("results") or []
    
    verified_violations = [f for f in findings if str(f.get("verdict") or "fail").lower() == "fail"]
    review_queue = [f for f in findings if str(f.get("verdict") or "fail").lower() == "needs_review"]

    assessment_date = datetime.now(timezone.utc).strftime("%d %B %Y")

    # Determine conformance status (§68)
    if len(verified_violations) == 0 and len(review_queue) == 0:
        conformance_status = "fully compliant"
        conformance_explanation = f"{organization_name} is fully compliant with the {profile_name} standard."
    elif len(verified_violations) > 0 and len(review_queue) == 0:
        conformance_status = "partially compliant"
        conformance_explanation = (
            f"{organization_name} is partially compliant with the {profile_name} standard, "
            f"due to the non-compliances listed below."
        )
    else:
        conformance_status = "partially compliant with manual review pending"
        conformance_explanation = (
            f"{organization_name} is partially compliant with the {profile_name} standard. "
            f"Certain content areas remain subject to ongoing human specialist evaluation."
        )

    # Build known issues list
    known_issues_lines = []
    for f in verified_violations[:15]:
        rule = f.get("rule_id", "issue")
        sc = f.get("wcag_criterion", "WCAG")
        desc = f.get("description", "Accessibility violation.")
        known_issues_lines.append(f"- **{sc} ({rule}):** {desc}")

    non_accessible_section = "\n".join(known_issues_lines) if known_issues_lines else "- No automated failures detected."

    statement_md = f"""# Accessibility Statement for {organization_name}

**Website:** [{target_url}]({target_url})  
**Date of Statement:** {assessment_date}  

{organization_name} is committed to ensuring digital accessibility for people with disabilities. We are continually improving the user experience for everyone and applying the relevant accessibility standards.

---

## 1. Compliance Status

This website is **{conformance_status}** with the **{profile_name}** technical standard.
{conformance_explanation}

---

## 2. Non-Accessible Content

The content listed below is non-compliant with accessibility standards for the following reasons:

{non_accessible_section}

---

## 3. Disproportionate Burden & Limitations

While we strive for comprehensive accessibility, certain complex dynamic components and third-party embeds are undergoing accessibility remediation or require disproportionate effort under applicable statutory frameworks.

---

## 4. Assessment and Testing Methodology

This statement was prepared on **{assessment_date}** using the **BEACON Accessibility Intelligence Platform**.  
Testing methodology combines multi-engine automated scanning (axe-core, static DOM analysis, browser probes) and AI-assisted adjudication, cross-referenced against the W3C WCAG 2.2 criteria.

---

## 5. Feedback and Contact Information

We welcome your feedback on the accessibility of this website. If you encounter accessibility barriers, please let us know:
- **Email:** [{contact_email}](mailto:{contact_email})
{f"- **Phone:** {contact_phone}" if contact_phone else ""}

We aim to respond to accessibility feedback within 5 business days.

---

## 6. Enforcement Procedure

If you are not satisfied with our response to your feedback, you may escalate your concern to the relevant supervisory body:
- **Enforcement Authority:** {enforcement_body or "Equality and Human Rights Commission (EHRC) / Relevant National Regulator"}

---

> **Notice:** *This document is a technical assessment draft generated automatically by BEACON. It does not constitute formal legal certification or legal representation.*
"""

    return statement_md
