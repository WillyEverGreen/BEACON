"""Adapter for normalizing Deque axe-core violations into canonical Findings."""

from __future__ import annotations

import re
from typing import Any

from app.audit.adapters.base import BaseAuditAdapter
from app.audit.fingerprint import stable_selector_fingerprint
from app.models.contracts import Finding

_WCAG_TAG_PATTERN = re.compile(r"^wcag(\d)(\d)(\d+)$", re.IGNORECASE)
_WCAG_LEVEL_PATTERN = re.compile(r"^wcag2(\w+)$", re.IGNORECASE)


class AxeAdapter(BaseAuditAdapter):
    """Adapter for Deque axe-core."""

    def __init__(self, engine_version: str = "4.10.2", rule_version: str = "4.10.2") -> None:
        super().__init__(name="axe", engine_version=engine_version, rule_version=rule_version)

    def normalize(self, raw_issue: dict[str, Any], context: dict[str, Any] | None = None) -> Finding:
        """Convert a single node violation from axe-core into a canonical Finding."""
        rule_id = str(raw_issue.get("id") or "unknown-rule")
        impact = str(raw_issue.get("impact") or "minor").lower()
        severity = self._map_impact_to_severity(impact)

        tags = raw_issue.get("tags") or []
        wcag_sc, wcag_level = self._extract_wcag_info(tags)

        # A violation in axe has one or more nodes. Context can specify node index.
        node_idx = 0
        if context and "node_index" in context:
            node_idx = int(context["node_index"])

        nodes = raw_issue.get("nodes") or []
        node = nodes[node_idx] if node_idx < len(nodes) else {}

        target = node.get("target") or []
        selector = target[0] if target else "body"
        if isinstance(selector, list):
            selector = " > ".join(str(s) for s in selector)
        else:
            selector = str(selector)

        selector_fp = stable_selector_fingerprint(selector)
        html_snippet = str(node.get("html") or "")
        message = str(node.get("failureSummary") or raw_issue.get("help") or raw_issue.get("description") or "")

        finding_id = self.generate_finding_id(rule_id, selector)

        act_ids = [t for t in tags if str(t).lower().startswith("act-") or (len(str(t)) == 6 and str(t).isalnum() and not str(t).startswith("wcag"))]
        act_id = act_ids[0] if act_ids else None

        evidence = {
            "axe_help_url": raw_issue.get("helpUrl"),
            "axe_tags": tags,
            "any_checks": node.get("any") or [],
            "all_checks": node.get("all") or [],
            "none_checks": node.get("none") or [],
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
            confidence=0.90,  # axe-core rules have high static reliability
            agreement_count=1,
            participating_engines=[self.name],
            act_rule_id=act_id,
        )

    def normalize_all_nodes(self, raw_violation: dict[str, Any]) -> list[Finding]:
        """Normalize all offending nodes within an axe violation into individual Findings."""
        nodes = raw_violation.get("nodes") or []
        if not nodes:
            return [self.normalize(raw_violation)]
        return [self.normalize(raw_violation, {"node_index": i}) for i in range(len(nodes))]

    @staticmethod
    def _map_impact_to_severity(impact: str) -> str:
        mapping = {
            "critical": "critical",
            "serious": "serious",
            "moderate": "moderate",
            "minor": "minor",
        }
        return mapping.get(impact, "minor")

    @staticmethod
    def _extract_wcag_info(tags: list[str]) -> tuple[str, str]:
        sc = ""
        level = "AA"

        for tag in tags:
            tag_str = str(tag).strip().lower()
            m_sc = _WCAG_TAG_PATTERN.match(tag_str)
            if m_sc:
                sc = f"{m_sc.group(1)}.{m_sc.group(2)}.{m_sc.group(3)}"

            m_lvl = _WCAG_LEVEL_PATTERN.match(tag_str)
            if m_lvl:
                level = m_lvl.group(1).upper()

        return sc, level
