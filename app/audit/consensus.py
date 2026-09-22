"""Multi-Engine Consensus and ACT Rule Adjudication Engine.

Aggregates, deduplicates, and calibrates accessibility findings across diverse
engines (Axe-core, IBM Equal Access, Siteimprove Alfa, BEACON heuristics, Guidepup)
using DOM selector fingerprints and WCAG success criteria mappings.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.models.contracts import Finding

SEVERITY_RANKS: dict[str, int] = {
    "critical": 4,
    "serious": 3,
    "moderate": 2,
    "minor": 1,
}

REVERSE_SEVERITY: dict[int, str] = {v: k for k, v in SEVERITY_RANKS.items()}


class ConsensusEngine:
    """Combines findings from multiple audit engines into calibrated consensus findings."""

    def __init__(self, min_confidence: float = 0.50) -> None:
        self.min_confidence = min_confidence

    @staticmethod
    def cluster_key(finding: Finding) -> tuple[str, str]:
        """Compute the clustering key for cross-engine correlation.
        
        Matches findings that target the exact same DOM element fingerprint and address
        the same WCAG success criterion. If WCAG criterion is not mapped, falls back to rule_id.
        """
        criterion = finding.wcag_criterion.strip() if finding.wcag_criterion else finding.rule_id
        return (criterion, finding.selector_fingerprint)

    def reconcile(self, raw_findings: list[Finding]) -> list[Finding]:
        """Group and reconcile a heterogeneous list of findings into a consensus list."""
        if not raw_findings:
            return []

        clusters: dict[tuple[str, str], list[Finding]] = defaultdict(list)
        for f in raw_findings:
            clusters[self.cluster_key(f)].append(f)

        consensus_findings: list[Finding] = []
        for (criterion, fp), group in clusters.items():
            consensus = self._merge_cluster(criterion, fp, group)
            if consensus.confidence >= self.min_confidence:
                consensus_findings.append(consensus)

        # Sort by severity descending, then confidence descending
        consensus_findings.sort(
            key=lambda f: (SEVERITY_RANKS.get(f.severity.lower(), 1), f.confidence),
            reverse=True,
        )
        return consensus_findings

    def _merge_cluster(self, criterion: str, fp: str, cluster: list[Finding]) -> Finding:
        """Merge multiple findings for the same element and criterion into a single canonical Finding."""
        # Engines involved
        engines = sorted(list({f.engine for f in cluster}))
        agreement_count = len(engines)

        # Primary finding is the one with highest individual confidence or most authoritative engine
        sorted_by_auth = sorted(
            cluster,
            key=lambda f: (
                1 if f.act_adjudicated else 0,
                f.confidence,
                SEVERITY_RANKS.get(f.severity.lower(), 1),
            ),
            reverse=True,
        )
        primary = sorted_by_auth[0]

        # Resolve highest severity
        max_severity_rank = max(SEVERITY_RANKS.get(f.severity.lower(), 1) for f in cluster)
        final_severity = REVERSE_SEVERITY.get(max_severity_rank, primary.severity)

        # ACT Rule adjudication check
        act_rule_id = next((f.act_rule_id for f in cluster if f.act_rule_id), None)
        has_act_adjudication = any(f.act_adjudicated for f in cluster)

        # Calibrated confidence calculation
        # Base confidence from primary engine
        base_conf = primary.confidence
        if agreement_count > 1:
            # Multi-engine consensus bonus: +0.12 per additional agreeing engine
            bonus = (agreement_count - 1) * 0.12
            calibrated_conf = min(0.99, base_conf + bonus)
        else:
            calibrated_conf = base_conf

        if has_act_adjudication:
            # Authoritative W3C ACT rule evaluation pins confidence >= 0.95
            calibrated_conf = max(0.95, calibrated_conf)

        # Merge evidence from all participating findings
        combined_evidence: dict[str, Any] = {}
        messages: list[str] = []
        for f in cluster:
            combined_evidence[f.engine] = {
                "rule_id": f.rule_id,
                "evidence": f.evidence,
                "confidence": f.confidence,
                "severity": f.severity,
            }
            if f.message and f.message not in messages:
                messages.append(f.message)

        # Prefer most complete html snippet
        longest_snippet = max((f.html_snippet for f in cluster), key=len, default=primary.html_snippet)

        return Finding(
            id=primary.id,
            rule_id=primary.rule_id,
            engine=primary.engine if agreement_count == 1 else "beacon_consensus",
            engine_version=primary.engine_version,
            rule_version=primary.rule_version,
            beacon_version=primary.beacon_version,
            wcag_criterion=primary.wcag_criterion or criterion,
            wcag_level=primary.wcag_level,
            severity=final_severity,
            selector=primary.selector,
            selector_fingerprint=fp,
            html_snippet=longest_snippet,
            message=" | ".join(messages) if len(messages) > 1 else primary.message,
            evidence=combined_evidence,
            confidence=round(calibrated_conf, 3),
            agreement_count=agreement_count,
            participating_engines=engines,
            act_rule_id=act_rule_id,
            act_adjudicated=has_act_adjudication,
        )
