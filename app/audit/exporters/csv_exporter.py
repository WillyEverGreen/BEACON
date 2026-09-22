"""
Enterprise CSV Exporter for Accessibility Audit Findings (§66).

Produces tabular CSV with:
Finding ID, Rule ID, WCAG Criterion, WCAG Level, Severity, Verdict, Confidence, Selector, Description, Suggested Fix, Persona Lenses, Regulatory Mappings
"""

from __future__ import annotations

import csv
import io
from typing import Any


def export_to_csv(findings: list[dict[str, Any]], target_url: str = "") -> str:
    """Exports findings list to CSV string (§66)."""
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

    headers = [
        "Finding ID",
        "Rule ID",
        "WCAG Criterion",
        "WCAG Level",
        "Severity",
        "Verdict",
        "Confidence",
        "Selector",
        "Description",
        "Suggested Fix",
        "Persona Lenses",
        "Regulatory Mappings",
        "URL",
    ]
    writer.writerow(headers)

    for item in findings:
        f_id = item.get("id") or item.get("finding_id") or ""
        rule = item.get("rule_id") or item.get("rule") or ""
        crit = item.get("wcag_criterion") or item.get("wcag", {}).get("criterion") or ""
        lvl = item.get("wcag_level") or item.get("wcag", {}).get("level") or "AA"
        sev = (item.get("severity") or "moderate").upper()
        
        verdict = str(item.get("verdict") or item.get("verification", {}).get("verdict") or "FAIL").upper()
        conf = item.get("confidence") or item.get("verification", {}).get("confidence") or 0.85

        sel = item.get("selector") or item.get("location", {}).get("selector") or ""
        desc = item.get("description") or item.get("message") or ""
        fix = item.get("suggested_fix") or item.get("remediation", {}).get("fix") or ""

        # Personas
        personas = item.get("persona_lenses") or item.get("personas") or []
        p_str = "; ".join(p.get("name", p.get("id", "")) for p in personas) if isinstance(personas, list) else ""

        # Regulatory mappings
        regs = item.get("profiles") or item.get("regulatory_mappings") or {}
        r_str = "; ".join(f"{k}: {v}" for k, v in regs.items()) if isinstance(regs, dict) else ""

        url = item.get("url") or target_url

        writer.writerow([
            f_id,
            rule,
            crit,
            lvl,
            sev,
            verdict,
            f"{float(conf):.2f}",
            sel,
            desc.replace("\n", " "),
            fix.replace("\n", " "),
            p_str,
            r_str,
            url,
        ])

    return output.getvalue()
