"""Base adapter interface for multi-engine accessibility auditing."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import uuid

from app.models.contracts import Finding
from app.audit.fingerprint import stable_selector_fingerprint


class BaseAuditAdapter(ABC):
    """Abstract base adapter normalizing engine-specific audit results to canonical Findings."""

    def __init__(self, name: str, engine_version: str, rule_version: str) -> None:
        self.name = name
        self.engine_version = engine_version
        self.rule_version = rule_version
        self.beacon_version = "2.1.0"

    @abstractmethod
    def normalize(self, raw_issue: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Finding:
        """Transform an engine-specific issue dictionary into a canonical Finding."""
        pass

    def generate_finding_id(self, rule_id: str, selector: str) -> str:
        """Generate a deterministic finding ID based on rule and selector fingerprint."""
        norm_selector = stable_selector_fingerprint(selector)
        seed = f"{self.name}:{rule_id}:{norm_selector}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))
