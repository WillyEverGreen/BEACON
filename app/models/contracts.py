"""Core Canonical Contracts & Normalized Finding Schema for BEACON.

Provides immutable, versioned domain contracts for multi-engine accessibility auditing,
topology fingerprinting, anti-bot state observability, and AI remediation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Tuple


class AntiBotState(str, Enum):
    """Observability states for anti-bot / WAF / Turnstile tracking."""
    CLEAR = "clear"
    CHALLENGE_DETECTED = "challenge_detected"
    CHALLENGE_SOLVED = "challenge_solved"
    DEGRADED_TIMEOUT = "degraded_timeout"
    RETRYABLE = "retryable"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class Fingerprint:
    """Multi-signal structural and interactive fingerprint of a web page."""
    dom_hash: str
    landmarks: Tuple[str, ...] = field(default_factory=tuple)
    roles: Tuple[str, ...] = field(default_factory=tuple)
    interactive_counts: Dict[str, int] = field(default_factory=dict)
    form_count: int = 0
    text_density_ratio: float = 0.0

    def signature(self) -> str:
        """Returns a composite identifier representing structural + interactive archetype."""
        landmarks_str = ",".join(sorted(self.landmarks))
        roles_str = ",".join(sorted(self.roles))
        total_interactive = sum(self.interactive_counts.values())
        return f"{self.dom_hash[:12]}|LM:{landmarks_str}|ROLES:{roles_str}|ACT:{total_interactive}|FORMS:{self.form_count}"


@dataclass
class Finding:
    """Canonical, normalized accessibility finding produced across all audit engines."""
    id: str
    rule_id: str
    engine: str                         # e.g., 'axe', 'ibm', 'alfa', 'beacon_heuristics'
    engine_version: str
    rule_version: str
    beacon_version: str
    wcag_criterion: str                 # e.g., '1.4.3', '4.1.2'
    wcag_level: str                     # 'A', 'AA', 'AAA'
    severity: str                       # 'critical', 'serious', 'moderate', 'minor'
    selector: str
    selector_fingerprint: str
    html_snippet: str
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5             # Calibrated BEACON confidence [0.0 - 1.0]
    agreement_count: int = 1
    participating_engines: List[str] = field(default_factory=list)
    act_rule_id: Optional[str] = None
    act_adjudicated: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert finding to standard serialized dictionary."""
        return {
            "id": self.id,
            "rule_id": self.rule_id,
            "engine": self.engine,
            "engine_version": self.engine_version,
            "rule_version": self.rule_version,
            "beacon_version": self.beacon_version,
            "wcag_criterion": self.wcag_criterion,
            "wcag_level": self.wcag_level,
            "severity": self.severity,
            "selector": self.selector,
            "selector_fingerprint": self.selector_fingerprint,
            "html_snippet": self.html_snippet,
            "message": self.message,
            "evidence": self.evidence,
            "confidence": round(self.confidence, 4),
            "agreement_count": self.agreement_count,
            "participating_engines": self.participating_engines,
            "act_rule_id": self.act_rule_id,
            "act_adjudicated": self.act_adjudicated,
            "timestamp": self.timestamp,
        }


@dataclass
class PatchResult:
    """Result of an AI-generated code remediation verified in the sandbox."""
    finding_id: str
    original_html: str
    patched_html: str
    patch_accepted: bool
    rejection_reason: Optional[str] = None
    violations_before_count: int = 0
    violations_after_count: int = 0
    new_violations_introduced: int = 0
    syntax_valid: bool = True
    execution_time_ms: float = 0.0


class FindingNormalizer(Protocol):
    """Protocol implemented by engine adapters to convert native findings to Finding."""

    def normalize(self, raw_finding: Dict[str, Any], context: Dict[str, Any]) -> Finding:
        """Convert engine-specific finding dictionary to canonical Finding."""
        ...
