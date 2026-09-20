"""W3C EARL 1.0 (Evaluation and Report Language) JSON-LD Exporter.

Serializes canonical BEACON findings into standard W3C EARL 1.0 conformance assertions.
Reference: https://www.w3.org/WAI/standards-guidelines/earl/
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.models.contracts import Finding


EARL_CONTEXT = {
    "earl": "http://www.w3.org/ns/earl#",
    "dct": "http://purl.org/dc/terms/",
    "doap": "http://usefulinc.com/ns/doap#",
    "ptr": "http://www.w3.org/2009/pointers#",
    "@vocab": "http://www.w3.org/ns/earl#",
}


def export_to_earl(
    findings: List[Finding],
    target_url: str,
    tool_version: str = "2.1.0",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Export canonical Findings to W3C EARL 1.0 JSON-LD format."""
    now_iso = datetime.now(timezone.utc).isoformat()
    report_id = f"urn:beacon:report:{uuid.uuid4().hex[:12]}"

    graph: List[Dict[str, Any]] = []

    # 1. Assertor: BEACON Engine
    assertor_id = "https://github.com/WillyEverGreen/BEACON"
    graph.append({
        "@id": assertor_id,
        "@type": ["Software", "Assertor"],
        "doap:name": "BEACON Accessibility Intelligence Engine",
        "doap:release": tool_version,
        "doap:description": "Multi-engine automated accessibility auditor with ACT adjudication.",
    })

    # 2. Test Subject: The audited page
    subject_id = target_url
    graph.append({
        "@id": subject_id,
        "@type": ["TestSubject", "WebPage"],
        "dct:title": f"Audit of {target_url}",
        "dct:source": target_url,
        "dct:date": now_iso,
    })

    # 3. Assertions from Findings
    for f in findings:
        assertion_id = f"{report_id}:assertion:{f.id[:12]}"

        test_case_id = (
            f"https://www.w3.org/TR/WCAG21/#wcag{f.wcag_criterion.replace('.', '')}"
            if f.wcag_criterion
            else f"urn:beacon:rule:{f.rule_id}"
        )

        test_result: Dict[str, Any] = {
            "@type": "TestResult",
            "outcome": "earl:failed",
            "dct:description": f.message,
            "dct:date": f.timestamp or now_iso,
            "earl:info": {
                "severity": f.severity,
                "confidence": f.confidence,
                "agreement_count": f.agreement_count,
                "participating_engines": f.participating_engines,
                "act_rule_id": f.act_rule_id,
                "act_adjudicated": f.act_adjudicated,
                "wcag_level": f.wcag_level,
            },
        }

        if f.selector:
            test_result["pointer"] = {
                "@type": "ptr:CSSSelectorPointer",
                "ptr:expression": f.selector,
            }

        graph.append({
            "@id": assertion_id,
            "@type": "Assertion",
            "assertedBy": assertor_id,
            "subject": subject_id,
            "test": {
                "@id": test_case_id,
                "@type": "TestCase",
                "dct:title": f"WCAG {f.wcag_criterion}: {f.rule_id}" if f.wcag_criterion else f.rule_id,
            },
            "result": test_result,
            "mode": "earl:automatic",
        })

    return {
        "@context": EARL_CONTEXT,
        "@graph": graph,
    }
