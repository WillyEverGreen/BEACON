"""Unit tests for Phase 5 Guidepup Screen Reader Adapter and Runner."""

import pytest

from app.audit.adapters.guidepup_adapter import GuidepupAdapter
from app.audit.screen_reader_runner import ScreenReaderAuditRunner


def test_guidepup_adapter_normalization():
    adapter = GuidepupAdapter()
    raw_issue = {
        "rule_id": "dialog-announcement",
        "target": "dialog#modal",
        "wcag_criterion": "4.1.2",
        "wcag_level": "A",
        "severity": "critical",
        "html": "<dialog id='modal'>Close</dialog>",
        "spoken_phrases": ["dialog"],
        "missing_announcements": ["Accessible dialog title/name"],
        "confidence": 0.94,
    }
    finding = adapter.normalize(raw_issue)
    assert finding.engine == "guidepup_sr"
    assert finding.rule_id == "dialog-announcement"
    assert finding.wcag_criterion == "4.1.2"
    assert finding.severity == "critical"
    assert finding.selector == "dialog#modal"
    assert finding.confidence == 0.94
    assert finding.evidence["spoken_phrases"] == ["dialog"]
    assert finding.evidence["missing_announcements"] == ["Accessible dialog title/name"]


@pytest.mark.asyncio
async def test_screen_reader_audit_runner():
    runner = ScreenReaderAuditRunner()
    sample_html = """
    <html>
      <body>
        <!-- Missing label and not modal -->
        <dialog id="cookie-dialog">
          <p>Please accept our cookies</p>
          <button>OK</button>
        </dialog>

        <!-- Silenced alert -->
        <div id="status-bar" role="alert" aria-live="off">
          Error saving document!
        </div>

        <!-- Disclosure missing aria-controls -->
        <button id="toggle-faq" aria-expanded="false">FAQ</button>
      </body>
    </html>
    """
    findings = await runner.audit_page_interactions(sample_html)
    assert len(findings) >= 3

    rule_ids = {f.rule_id for f in findings}
    assert "dialog-announcement" in rule_ids
    assert "dialog-focus-trap" in rule_ids
    assert "live-region-assertive" in rule_ids
    assert "disclosure-toggle" in rule_ids
