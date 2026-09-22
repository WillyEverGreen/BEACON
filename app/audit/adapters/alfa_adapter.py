"""Adapter for normalizing Siteimprove Alfa (W3C ACT reference implementation) results."""

from __future__ import annotations

from typing import Any

from app.audit.adapters.base import BaseAuditAdapter
from app.audit.fingerprint import stable_selector_fingerprint
from app.models.contracts import Finding

# Well-known mapping of Alfa (sia-r*) rules to ACT Rules and WCAG Criteria
ALFA_ACT_MAP: dict[str, dict[str, str]] = {
    "sia-r1": {"act": "23a2a8", "wcag": "1.1.1", "level": "A", "desc": "Image has alternative text"},
    "sia-r2": {"act": "b5c3f8", "wcag": "3.1.1", "level": "A", "desc": "HTML element has lang attribute"},
    "sia-r3": {"act": "bf051a", "wcag": "3.1.1", "level": "A", "desc": "HTML lang attribute is valid"},
    "sia-r4": {"act": "bc659a", "wcag": "2.1.1", "level": "A", "desc": "Scrollable region is focusable"},
    "sia-r8": {"act": "e69583", "wcag": "1.4.4", "level": "AA", "desc": "Text cannot be zoomed"},
    "sia-r10": {"act": "73f2c2", "wcag": "1.3.5", "level": "AA", "desc": "Autocomplete attribute is valid"},
    "sia-r12": {"act": "c487ae", "wcag": "4.1.2", "level": "A", "desc": "Link has accessible name"},
    "sia-r14": {"act": "b4f0c3", "wcag": "1.2.2", "level": "A", "desc": "Video element has captions"},
    "sia-r16": {"act": "e086e5", "wcag": "4.1.2", "level": "A", "desc": "Input element has accessible name"},
    "sia-r20": {"act": "cae760", "wcag": "1.4.1", "level": "A", "desc": "Color is not used as only visual means"},
    "sia-r28": {"act": "afb423", "wcag": "1.4.3", "level": "AA", "desc": "Text contrast ratio meets minimum"},
    "sia-r39": {"act": "9eb3f6", "wcag": "1.4.3", "level": "AA", "desc": "Text in image contrast meets minimum"},
    "sia-r41": {"act": "3680e9", "wcag": "2.4.2", "level": "A", "desc": "Page title element exists"},
    "sia-r69": {"act": "97a4e1", "wcag": "1.4.3", "level": "AA", "desc": "Text contrast ratio for large text"},
    "sia-r83": {"act": "59796f", "wcag": "1.4.3", "level": "AA", "desc": "Contrast ratio of text"},
}


class AlfaAdapter(BaseAuditAdapter):
    """Adapter for Siteimprove Alfa (ACT Rule engine)."""

    def __init__(self, engine_version: str = "0.87.0", rule_version: str = "0.87.0") -> None:
        super().__init__(name="alfa", engine_version=engine_version, rule_version=rule_version)

    def normalize(self, raw_issue: dict[str, Any], context: dict[str, Any] | None = None) -> Finding:
        """Convert a Siteimprove Alfa outcome into a canonical Finding."""
        rule_id = str(raw_issue.get("rule") or raw_issue.get("ruleId") or raw_issue.get("rule_id") or "sia-r0")
        outcome = str(raw_issue.get("outcome") or raw_issue.get("verdict") or "failed").lower()

        # Lookup ACT mapping
        meta = ALFA_ACT_MAP.get(rule_id.lower(), {})
        act_rule_id = raw_issue.get("actRuleId") or raw_issue.get("act_rule_id") or meta.get("act")
        wcag_criterion = raw_issue.get("wcag_criterion") or meta.get("wcag", "")
        wcag_level = raw_issue.get("wcag_level") or meta.get("level", "AA")

        # Map outcome to severity
        if outcome in ("failed", "fail"):
            severity = raw_issue.get("severity") or ("critical" if wcag_level == "A" else "serious")
        elif outcome in ("canttell", "inapplicable"):
            severity = "moderate"
        else:
            severity = "minor"

        target = raw_issue.get("target") or raw_issue.get("selector") or "body"
        if isinstance(target, dict):
            selector = target.get("selector") or target.get("path") or "body"
            html_snippet = target.get("html") or ""
        else:
            selector = str(target)
            html_snippet = str(raw_issue.get("html") or raw_issue.get("html_snippet") or "")

        selector_fp = stable_selector_fingerprint(str(selector))
        message = str(raw_issue.get("message") or meta.get("desc") or f"Alfa ACT rule {rule_id} violated")

        finding_id = self.generate_finding_id(rule_id, str(selector))

        evidence = {
            "alfa_rule": rule_id,
            "outcome": outcome,
            "act_rule_id": act_rule_id,
            "details": raw_issue.get("details", {}),
        }

        # Alfa is an authoritative W3C ACT implementation -> high default confidence
        confidence = 0.95 if outcome in ("failed", "fail") else 0.70

        return Finding(
            id=finding_id,
            rule_id=rule_id,
            engine=self.name,
            engine_version=self.engine_version,
            rule_version=self.rule_version,
            beacon_version=self.beacon_version,
            wcag_criterion=wcag_criterion,
            wcag_level=wcag_level,
            severity=severity,
            selector=str(selector),
            selector_fingerprint=selector_fp,
            html_snippet=html_snippet,
            message=message,
            evidence=evidence,
            confidence=confidence,
            agreement_count=1,
            participating_engines=[self.name],
            act_rule_id=act_rule_id,
            act_adjudicated=True,
        )
