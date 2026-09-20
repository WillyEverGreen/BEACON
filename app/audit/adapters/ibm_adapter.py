"""Adapter for normalizing IBM Equal Access Accessibility Checker violations."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.audit.adapters.base import BaseAuditAdapter
from app.audit.fingerprint import stable_selector_fingerprint
from app.models.contracts import Finding


class IBMAdapter(BaseAuditAdapter):
    """Adapter for IBM Equal Access engine."""

    def __init__(self, engine_version: str = "3.1.60", rule_version: str = "3.1.60") -> None:
        super().__init__(name="ibm_equal_access", engine_version=engine_version, rule_version=rule_version)

    def normalize(self, raw_issue: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Finding:
        """Convert an IBM Equal Access report item into a canonical Finding."""
        rule_id = str(raw_issue.get("ruleId") or raw_issue.get("rule_id") or "ibm-rule")
        level = str(raw_issue.get("value") or raw_issue.get("level") or "violation").lower()
        severity = self._map_ibm_level_to_severity(level)

        # IBM outputs path / xpath / snippet
        path = raw_issue.get("path") or {}
        selector = path.get("dom") or raw_issue.get("selector") or "body"
        selector_fp = stable_selector_fingerprint(str(selector))

        html_snippet = str(raw_issue.get("snippet") or raw_issue.get("html") or "")
        message = str(raw_issue.get("message") or "")

        wcag_sc = ""
        wcag_level = "AA"
        # IBM rules often carry WCAG mapping in 'toolkit' or 'wcag' metadata
        toolkit_info = raw_issue.get("toolkit") or {}
        if "num" in toolkit_info:
            wcag_sc = str(toolkit_info["num"])

        finding_id = self.generate_finding_id(rule_id, str(selector))

        evidence = {
            "ibm_rule_id": rule_id,
            "bounds": raw_issue.get("bounds"),
            "category": raw_issue.get("category"),
            "reason_id": raw_issue.get("reasonId"),
        }

        return Finding(
            id=finding_id,
            rule_id=rule_id,
            engine=self.name,
            engine_version=self.engine_version,
            rule_version=self.rule_version,
            beacon_version=self.beacon_version,
            wcag_criterion=wcag_sc,
            wcag_level=wcag_level,
            severity=severity,
            selector=str(selector),
            selector_fingerprint=selector_fp,
            html_snippet=html_snippet,
            message=message,
            evidence=evidence,
            confidence=0.88,
            agreement_count=1,
            participating_engines=[self.name],
        )

    @staticmethod
    def _map_ibm_level_to_severity(level: str) -> str:
        mapping = {
            "violation": "serious",
            "potentialviolation": "moderate",
            "recommendation": "minor",
            "manual": "moderate",
        }
        return mapping.get(level, "moderate")
