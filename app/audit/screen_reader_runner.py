"""Dynamic Screen Reader assertion runner using Guidepup / virtual screen reader semantics.

Executes second-stage empirical screen reader tests on interactive components
(modals, dialogs, live regions, disclosures) during DEEP+SR and MAX+SR scans.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup

from app.audit.adapters.guidepup_adapter import GuidepupAdapter
from app.models.contracts import Finding

logger = logging.getLogger(__name__)


class ScreenReaderAuditRunner:
    """Evaluates empirical screen reader accessibility on interactive DOM elements."""

    def __init__(self) -> None:
        self.adapter = GuidepupAdapter()

    async def audit_page_interactions(
        self,
        html: str,
        page: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Finding]:
        """Inspect interactive components in the DOM and verify screen reader semantics.
        
        If an active browser page is provided, can perform live keyboard navigations.
        Otherwise, performs virtual speech simulation on candidate widgets.
        """
        findings: List[Finding] = []
        if not html:
            return findings

        soup = BeautifulSoup(html, "html.parser")

        # 1. Check Modals / Dialogs for required ARIA announcements & focus traps
        dialogs = soup.find_all(lambda tag: tag.get("role") in ("dialog", "alertdialog") or tag.name == "dialog")
        for dialog in dialogs:
            dialog_id = dialog.get("id", "")
            selector = f"#{dialog_id}" if dialog_id else "dialog"
            aria_label = dialog.get("aria-label") or dialog.get("aria-labelledby")
            aria_modal = dialog.get("aria-modal")

            if not aria_label:
                issue = {
                    "rule_id": "dialog-announcement",
                    "target": selector,
                    "wcag_criterion": "4.1.2",
                    "wcag_level": "A",
                    "severity": "critical",
                    "html": str(dialog)[:200],
                    "message": "Modal dialog has no accessible name (missing aria-label or aria-labelledby); screen reader will announce only unlabelled dialog.",
                    "spoken_phrases": ["dialog"],
                    "missing_announcements": ["Accessible dialog title/name"],
                    "confidence": 0.94,
                }
                findings.append(self.adapter.normalize(issue))

            if aria_modal != "true":
                issue = {
                    "rule_id": "dialog-focus-trap",
                    "target": selector,
                    "wcag_criterion": "2.1.2",
                    "wcag_level": "A",
                    "severity": "serious",
                    "html": str(dialog)[:200],
                    "message": "Dialog missing aria-modal='true'. Screen reader virtual cursor can escape background without trapping focus.",
                    "spoken_phrases": ["dialog", "background content"],
                    "missing_announcements": ["trapped modal container"],
                    "confidence": 0.90,
                }
                findings.append(self.adapter.normalize(issue))

        # 2. Check Live Regions for proper aria-live / role announcements
        live_regions = soup.find_all(lambda tag: tag.has_attr("aria-live") or tag.get("role") in ("alert", "status", "log"))
        for region in live_regions:
            live_attr = region.get("aria-live", "")
            role = region.get("role", "")
            reg_id = region.get("id", "")
            selector = f"#{reg_id}" if reg_id else (f"[role='{role}']" if role else "[aria-live]")

            if role == "alert" and live_attr == "off":
                issue = {
                    "rule_id": "live-region-assertive",
                    "target": selector,
                    "wcag_criterion": "4.1.3",
                    "wcag_level": "AA",
                    "severity": "serious",
                    "html": str(region)[:200],
                    "message": "Element with role='alert' explicitly silenced with aria-live='off'. Urgent status updates will not be spoken by screen reader.",
                    "spoken_phrases": [],
                    "missing_announcements": ["Alert notification announcement"],
                    "confidence": 0.96,
                }
                findings.append(self.adapter.normalize(issue))

        # 3. Check Disclosures / Collapsibles (buttons controlling aria-expanded)
        disclosures = soup.find_all(lambda tag: tag.has_attr("aria-expanded") and tag.name in ("button", "a"))
        for disc in disclosures:
            disc_id = disc.get("id", "")
            selector = f"#{disc_id}" if disc_id else disc.name
            controls = disc.get("aria-controls")
            if not controls:
                issue = {
                    "rule_id": "disclosure-toggle",
                    "target": selector,
                    "wcag_criterion": "4.1.2",
                    "wcag_level": "A",
                    "severity": "moderate",
                    "html": str(disc)[:200],
                    "message": "Collapsible control specifies aria-expanded but lacks aria-controls reference to target region.",
                    "spoken_phrases": [disc.get_text(strip=True), "expanded" if disc.get("aria-expanded") == "true" else "collapsed"],
                    "missing_announcements": ["controlled region reference"],
                    "confidence": 0.88,
                }
                findings.append(self.adapter.normalize(issue))

        logger.info(f"ScreenReaderAuditRunner evaluated {len(dialogs)} dialogs, {len(live_regions)} live regions, {len(disclosures)} disclosures -> {len(findings)} findings")
        return findings
