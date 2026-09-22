"""Adapter for normalizing Guidepup Screen Reader assertions and virtual SR traces."""

from __future__ import annotations

from typing import Any

from app.audit.adapters.base import BaseAuditAdapter
from app.audit.fingerprint import stable_selector_fingerprint
from app.models.contracts import Finding

GUIDEPUP_WCAG_MAP: dict[str, dict[str, str]] = {
    "dialog-announcement": {"wcag": "4.1.3", "level": "AA", "severity": "critical"},
    "dialog-focus-trap": {"wcag": "2.1.2", "level": "A", "severity": "critical"},
    "live-region-polite": {"wcag": "4.1.3", "level": "AA", "severity": "serious"},
    "live-region-assertive": {"wcag": "4.1.3", "level": "AA", "severity": "serious"},
    "menu-navigation": {"wcag": "2.1.1", "level": "A", "severity": "serious"},
    "disclosure-toggle": {"wcag": "4.1.2", "level": "A", "severity": "moderate"},
    "spoken-name-mismatch": {"wcag": "2.5.3", "level": "A", "severity": "serious"},
    "sr-unannounced-change": {"wcag": "4.1.3", "level": "AA", "severity": "serious"},
}


class GuidepupAdapter(BaseAuditAdapter):
    """Adapter for dynamic screen reader testing (Guidepup / Virtual Screen Reader)."""

    def __init__(self, engine_version: str = "0.14.0", rule_version: str = "1.0.0") -> None:
        super().__init__(name="guidepup_sr", engine_version=engine_version, rule_version=rule_version)

    def normalize(self, raw_issue: dict[str, Any], context: dict[str, Any] | None = None) -> Finding:
        """Convert a Guidepup speech trace assertion failure into a canonical Finding."""
        rule_id = str(raw_issue.get("rule_id") or raw_issue.get("test_id") or "sr-speech-assertion")
        target = str(raw_issue.get("target") or raw_issue.get("selector") or "body")
        selector_fp = stable_selector_fingerprint(target)

        # Lookup rule defaults
        rule_meta = GUIDEPUP_WCAG_MAP.get(rule_id, {})
        wcag_criterion = str(raw_issue.get("wcag_criterion") or rule_meta.get("wcag") or "4.1.3")
        wcag_level = str(raw_issue.get("wcag_level") or rule_meta.get("level") or "AA")
        severity = str(raw_issue.get("severity") or rule_meta.get("severity") or "serious")

        message = str(
            raw_issue.get("message")
            or f"Screen reader speech assertion '{rule_id}' failed on element '{target}'"
        )
        html_snippet = str(raw_issue.get("html") or raw_issue.get("html_snippet") or "")

        finding_id = self.generate_finding_id(rule_id, target)

        spoken_phrases: list[str] = raw_issue.get("spoken_phrases", [])
        missing_phrases: list[str] = raw_issue.get("missing_announcements", [])

        evidence = {
            "sr_engine": "guidepup_virtual_sr",
            "spoken_phrases": spoken_phrases,
            "missing_announcements": missing_phrases,
            "interaction_sequence": raw_issue.get("interaction_sequence", []),
        }

        # Dynamic screen reader failures are highly reliable empirical tests -> 0.92 confidence
        confidence = float(raw_issue.get("confidence", 0.92))

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
            selector=target,
            selector_fingerprint=selector_fp,
            html_snippet=html_snippet,
            message=message,
            evidence=evidence,
            confidence=confidence,
            agreement_count=1,
            participating_engines=[self.name],
            act_rule_id=raw_issue.get("act_rule_id"),
            act_adjudicated=False,
        )
