"""
EARL (Evaluation and Report Language) 1.0 Report Generator.
Standardized JSON-LD format for accessibility audit assertions.
Reference: https://www.w3.org/WAI/standards-guidelines/earl/
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def generate_earl_report(
    url: str, 
    issues: List[Dict[str, Any]], 
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate an EARL 1.0 JSON-LD report from audit findings.
    
    :param url: The URL of the page audited.
    :param issues: List of normalized issue dictionaries.
    :param metadata: Audit metadata (engines used, timing, etc.)
    :return: A dictionary representing the EARL JSON-LD graph.
    """
    now = datetime.now(timezone.utc).isoformat()
    report_id = f"urn:beacon:report:{uuid.uuid4().hex[:12]}"
    
    # Define the EARL context
    report = {
        "@context": {
            "earl": "http://www.w3.org/ns/earl#",
            "dct": "http://purl.org/dc/terms/",
            "doap": "http://usefulinc.com/ns/doap#",
            "ptr": "http://www.w3.org/2009/pointers#",
            "@vocab": "http://www.w3.org/ns/earl#"
        },
        "@graph": []
    }

    # 1. Assertor: The BEACON Engine
    assertor = {
        "@id": "https://github.com/advdi/BEACON",
        "@type": ["Software", "Assertor"],
        "doap:name": "BEACON Accessibility Intelligence Engine",
        "doap:release": "v3.0.0",
        "doap:description": "Multi-engine automated accessibility auditor."
    }
    report["@graph"].append(assertor)

    # 2. Test Subject: The Page
    subject = {
        "@id": url,
        "@type": ["TestSubject", "WebPage"],
        "dct:title": f"Audit of {url}",
        "dct:source": url
    }
    report["@graph"].append(subject)

    # 3. Assertions: The Findings
    for issue in issues:
        assertion_id = f"{report_id}:assertion:{issue.get('issue_id', uuid.uuid4().hex[:8])}"
        
        # Map severity to EARL outcome
        severity = str(issue.get("severity", "moderate")).lower()
        outcome = "earl:failed" if severity in ("critical", "serious", "moderate") else "earl:cannotTell"
        
        assertion = {
            "@id": assertion_id,
            "@type": "Assertion",
            "assertedBy": assertor["@id"],
            "subject": subject["@id"],
            "test": {
                "@type": "TestCase",
                "dct:title": issue.get("rule_id", "Unknown Rule"),
                "dct:description": issue.get("description", ""),
                "testRequirement": {
                    "@id": f"https://www.w3.org/TR/WCAG22/#{(issue.get('wcag_criterion', '1.1.1').replace('.', '-'))}",
                    "dct:title": f"WCAG 2.2 SC {issue.get('wcag_criterion', '1.1.1')}"
                }
            },
            "result": {
                "@type": "TestResult",
                "outcome": outcome,
                "dct:description": issue.get("suggested_fix", ""),
                "dct:date": now,
                "info": {
                    "severity": severity,
                    "confidence": issue.get("confidence", 0.0),
                    "element": issue.get("element", ""),
                    "snippet": issue.get("html_snippet", "")
                }
            },
            "mode": "earl:automatic"
        }
        
        # Add pointer if element location is specific
        if issue.get("element") and issue.get("element") != "<body>":
            assertion["result"]["pointer"] = {
                "@type": "ptr:CSSSelectorPointer",
                "ptr:expression": issue.get("element")
            }
            
        report["@graph"].append(assertion)

    return report
