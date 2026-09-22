"""
Automatic vs Human Evidence Labeling System (§49).

Every evidence item must explicitly declare its provenance and epistemic status:
- OBSERVED: Directly measured from browser runtime, DOM geometry, computed styles
- INFERRED: Derived from heuristics, template propagation, or structural assumptions
- HEURISTIC: Pattern-matched by static inspection without browser execution
- RETRIEVED: Fetched from authoritative WCAG/ARIA standards or RAG knowledge base
- HUMAN_CONFIRMED: Validated by human accessibility specialist or reviewer
- NOT_TESTED: Modality or assistive tech was not run; must never be misrepresented as passing
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EvidenceStatus(str, Enum):
    OBSERVED = "observed"
    INFERRED = "inferred"
    HEURISTIC = "heuristic"
    RETRIEVED = "retrieved"
    HUMAN_CONFIRMED = "human_confirmed"
    NOT_TESTED = "not_tested"


def create_evidence_label(
    source: str,
    status: EvidenceStatus | str,
    *,
    confidence: float = 1.0,
    notes: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Creates a machine-readable evidence provenance record (§49)."""
    norm_status = status.value if isinstance(status, EvidenceStatus) else str(status).lower()
    return {
        "source": source,
        "status": norm_status,
        "confidence": round(float(confidence), 3),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes": notes or "",
        "details": details or {},
    }


def label_finding_evidence(finding: dict[str, Any]) -> dict[str, Any]:
    """
    Attaches explicit evidence provenance labels to all modalities of a finding (§49).
    Ensures untested modalities (such as screen reader or audio) are transparently labeled 'not_tested'.
    """
    enriched = dict(finding)
    evidence_labels: dict[str, dict[str, Any]] = {}

    # 1. DOM Context
    dom_ctx = finding.get("element_context") or finding.get("evidence", {}).get("dom")
    if dom_ctx:
        evidence_labels["dom"] = create_evidence_label(
            source="dom_analyzer",
            status=EvidenceStatus.OBSERVED,
            confidence=0.95,
            notes="Extracted from live DOM tree and computed node properties.",
        )
    else:
        evidence_labels["dom"] = create_evidence_label(
            source="dom_analyzer",
            status=EvidenceStatus.HEURISTIC,
            confidence=0.75,
            notes="Static HTML snippet only; live computed DOM context unavailable.",
        )

    # 2. Browser Evidence
    browser_ev = finding.get("browser_evidence") or finding.get("evidence", {}).get("browser")
    if browser_ev:
        evidence_labels["browser"] = create_evidence_label(
            source="playwright_runtime",
            status=EvidenceStatus.OBSERVED,
            confidence=0.95,
            notes="Measured in headless browser runtime (geometry, focus, or event handlers).",
        )
    else:
        evidence_labels["browser"] = create_evidence_label(
            source="browser_runtime",
            status=EvidenceStatus.NOT_TESTED,
            confidence=0.0,
            notes="Browser runtime probes not executed for this finding.",
        )

    # 3. Visual Evidence
    visual_ev = finding.get("visual_evidence") or finding.get("evidence", {}).get("visual")
    if visual_ev:
        evidence_labels["visual"] = create_evidence_label(
            source="visual_accessibility_engine",
            status=EvidenceStatus.OBSERVED,
            confidence=0.90,
            notes="Rendered contrast or color-only analysis from screenshot/styles.",
        )
    else:
        evidence_labels["visual"] = create_evidence_label(
            source="visual_accessibility_engine",
            status=EvidenceStatus.NOT_TESTED,
            confidence=0.0,
            notes="Visual inspection not performed for this finding.",
        )

    # 4. Assistive Technology Evidence
    at_ev = finding.get("at_evidence") or finding.get("evidence", {}).get("assistive_technology")
    if at_ev and at_ev.get("tested"):
        evidence_labels["assistive_technology"] = create_evidence_label(
            source="at_screen_reader_bridge",
            status=EvidenceStatus.OBSERVED,
            confidence=0.92,
            notes=f"Screen reader tested ({at_ev.get('at_name', 'AT')}).",
        )
    else:
        evidence_labels["assistive_technology"] = create_evidence_label(
            source="assistive_technology",
            status=EvidenceStatus.NOT_TESTED,
            confidence=0.0,
            notes="Assistive technology screen reader test not run.",
        )

    # 5. Template inference check
    if finding.get("is_template_inferred"):
        evidence_labels["template_inference"] = create_evidence_label(
            source="template_clustering_engine",
            status=EvidenceStatus.INFERRED,
            confidence=0.80,
            notes="Finding inferred from shared page template, not individually tested on this URL.",
        )

    enriched["evidence_provenance"] = evidence_labels
    return enriched
