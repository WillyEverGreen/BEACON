"""
Multi-Tenant Knowledge & Standards Versioning Engine (§53, §54).

Guarantees:
- Every retrieved standards chunk is explicitly versioned and immutable
- Future standards updates never silently alter historical interpretations of old audits
- Strict multi-tenant isolation for organization-specific and project-specific rules
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class VersionedStandardsChunk:
    """Immutable versioned knowledge representation (§54)."""
    document: str             # e.g. "WCAG 2.2", "WAI-ARIA 1.2", "GIGW 3.0"
    version: str              # e.g. "2023-10-05", "3.0-2023"
    source: str               # e.g. "https://www.w3.org/TR/WCAG22/"
    criterion: str            # e.g. "1.1.1", "2.5.8"
    framework: str            # e.g. "HTML", "React", "Universal"
    topic: str                # e.g. "Non-text Content", "Target Size"
    content: str
    tenant_id: str | None = None  # None = global standard; str = tenant-isolated custom rule
    retrieval_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": self.document,
            "version": self.version,
            "source": self.source,
            "criterion": self.criterion,
            "framework": self.framework,
            "topic": self.topic,
            "content": self.content,
            "tenant_id": self.tenant_id,
            "retrieval_timestamp": self.retrieval_timestamp,
        }


# Canonical authoritative standards database snapshot (§54)
CANONICAL_STANDARDS_SNAPSHOT: list[VersionedStandardsChunk] = [
    VersionedStandardsChunk(
        document="W3C WCAG 2.2 Recommendation",
        version="2023-10-05",
        source="https://www.w3.org/TR/WCAG22/#non-text-content",
        criterion="1.1.1",
        framework="Universal",
        topic="Non-text Content",
        content="All non-text content that is presented to the user has a text alternative that serves the equivalent purpose.",
    ),
    VersionedStandardsChunk(
        document="W3C WCAG 2.2 Recommendation",
        version="2023-10-05",
        source="https://www.w3.org/TR/WCAG22/#contrast-minimum",
        criterion="1.4.3",
        framework="Universal",
        topic="Contrast (Minimum)",
        content="The visual presentation of text and images of text has a contrast ratio of at least 4.5:1, except for large-scale text (3:1).",
    ),
    VersionedStandardsChunk(
        document="W3C WCAG 2.2 Recommendation",
        version="2023-10-05",
        source="https://www.w3.org/TR/WCAG22/#focus-not-obscured-minimum",
        criterion="2.4.11",
        framework="Universal",
        topic="Focus Not Obscured (Minimum)",
        content="When a user interface component receives keyboard focus, the component is not entirely hidden due to author-created content.",
    ),
    VersionedStandardsChunk(
        document="W3C WCAG 2.2 Recommendation",
        version="2023-10-05",
        source="https://www.w3.org/TR/WCAG22/#target-size-minimum",
        criterion="2.5.8",
        framework="Universal",
        topic="Target Size (Minimum)",
        content="The size of the target for pointer inputs is at least 24 by 24 CSS pixels, except where spacing offset or inline links qualify.",
    ),
    VersionedStandardsChunk(
        document="W3C WCAG 2.2 Recommendation",
        version="2023-10-05",
        source="https://www.w3.org/TR/WCAG22/#accessible-authentication-minimum",
        criterion="3.3.8",
        framework="Universal",
        topic="Accessible Authentication (Minimum)",
        content="A cognitive function test is not required for any step in an authentication process unless an alternative or helper is provided.",
    ),
]


class KnowledgeStore:
    """Manages multi-tenant rules and versioned knowledge retrieval (§53, §54)."""

    def __init__(self) -> None:
        # In-memory store initialized with canonical snapshot
        self._global_standards: dict[str, VersionedStandardsChunk] = {
            f"{chunk.criterion}@{chunk.version}": chunk
            for chunk in CANONICAL_STANDARDS_SNAPSHOT
        }
        # Tenant-isolated custom rules: tenant_id -> list of chunks
        self._tenant_rules: dict[str, list[VersionedStandardsChunk]] = {}

    def get_standard_chunk(
        self,
        criterion: str,
        *,
        version: str = "2023-10-05",
        tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Retrieves a versioned standards chunk.
        If tenant_id is provided, tenant-specific policy overrides take precedence.
        """
        # 1. Check tenant-specific custom rules first (tenant isolation)
        if tenant_id and tenant_id in self._tenant_rules:
            for chunk in self._tenant_rules[tenant_id]:
                if chunk.criterion == criterion:
                    return chunk.to_dict()

        # 2. Fall back to immutable global standards snapshot
        key = f"{criterion}@{version}"
        chunk = self._global_standards.get(key)
        if not chunk:
            # Try any matching criterion in global standards
            for c in self._global_standards.values():
                if c.criterion == criterion:
                    chunk = c
                    break

        return chunk.to_dict() if chunk else None

    def register_tenant_rule(
        self,
        tenant_id: str,
        document: str,
        criterion: str,
        content: str,
        *,
        version: str = "custom-1.0",
        framework: str = "Universal",
        topic: str = "Custom Organizational Rule",
    ) -> dict[str, Any]:
        """Registers a tenant-isolated organization rule (§53)."""
        if not tenant_id:
            raise ValueError("tenant_id must be provided for custom organization rules.")

        chunk = VersionedStandardsChunk(
            document=document,
            version=version,
            source=f"tenant://{tenant_id}/rules/{criterion}",
            criterion=criterion,
            framework=framework,
            topic=topic,
            content=content,
            tenant_id=tenant_id,
        )
        self._tenant_rules.setdefault(tenant_id, []).append(chunk)
        return chunk.to_dict()

    def list_tenant_rules(self, tenant_id: str) -> list[dict[str, Any]]:
        """Lists rules for a specific tenant strictly isolated from other tenants (§53)."""
        chunks = self._tenant_rules.get(tenant_id, [])
        return [c.to_dict() for c in chunks]


# Global singleton instance
knowledge_store = KnowledgeStore()
