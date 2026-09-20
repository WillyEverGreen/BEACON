"""Adapter for normalizing BEACON native heuristics and rule checks into canonical Findings."""

from __future__ import annotations

from typing import Any, Dict, Optional

from app.audit.adapters.base import BaseAuditAdapter
from app.audit.fingerprint import stable_selector_fingerprint
from app.models.contracts import Finding


class HeuristicsAdapter(BaseAuditAdapter):
    """Adapter for BEACON's internal rule and heuristic engine."""

    def __init__(self, rule_version: str = "2.1.0") -> None:
        super().__init__(name="beacon_heuristics", engine_version="2.1.0", rule_version=rule_version)

    def normalize(self, raw_issue: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Finding:
        """Convert a BEACON native issue dictionary into a canonical Finding."""
        rule_id = str(raw_issue.get("rule_id") or raw_issue.get("issue_type") or "heuristic-rule")
        severity = str(raw_issue.get("severity") or "moderate").lower()
        wcag_sc = str(raw_issue.get("wcag_criterion") or "")
        wcag_level = str(raw_issue.get("wcag_level") or "AA").upper()

        selector = str(raw_issue.get("selector") or "body")
        selector_fp = stable_selector_fingerprint(selector)
        html_snippet = str(raw_issue.get("html_snippet") or raw_issue.get("element_html") or "")
        message = str(raw_issue.get("message") or raw_issue.get("description") or "")

        finding_id = self.generate_finding_id(rule_id, selector)
        confidence = float(raw_issue.get("confidence") or 0.80)

        evidence = {
            "source_type": raw_issue.get("source_type", "heuristic"),
            "details": raw_issue.get("details") or {},
            "contrast_ratio": raw_issue.get("contrast_ratio"),
            "expected_contrast": raw_issue.get("expected_contrast"),
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
            selector=selector,
            selector_fingerprint=selector_fp,
            html_snippet=html_snippet,
            message=message,
            evidence=evidence,
            confidence=confidence,
            agreement_count=1,
            participating_engines=[self.name],
        )
