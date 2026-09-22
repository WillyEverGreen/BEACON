"""
Data models for Regulatory Control Profiles & Persona Lenses (§25–§38).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegulatoryProfile:
    """Defines a jurisdiction or policy compliance control profile (§25)."""
    profile_id: str
    name: str
    jurisdiction: str
    scope: str
    technical_standard: str
    mapped_requirements: dict[str, str]  # standard criteria -> local clause
    mandatory_criteria: set[str]
    optional_advisory_checks: set[str] = field(default_factory=set)
    report_sections: list[str] = field(default_factory=list)
    export_format: str = "json"
    disclaimer: str = (
        "This assessment provides automated technical findings against accessibility standards. "
        "It does not constitute formal legal compliance advice."
    )
    verification_source: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "jurisdiction": self.jurisdiction,
            "scope": self.scope,
            "technical_standard": self.technical_standard,
            "mapped_requirements": self.mapped_requirements,
            "mandatory_criteria": sorted(list(self.mandatory_criteria)),
            "optional_advisory_checks": sorted(list(self.optional_advisory_checks)),
            "report_sections": self.report_sections,
            "export_format": self.export_format,
            "disclaimer": self.disclaimer,
            "verification_source": self.verification_source,
        }


@dataclass
class PersonaMapping:
    """Represents a finding's relevance and impact under a persona lens (§33)."""
    id: str
    name: str
    relevance: float  # 0.0 to 1.0 relevance to this perspective
    reason: str
    user_impact_explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "relevance": round(self.relevance, 2),
            "reason": self.reason,
            "user_impact_explanation": self.user_impact_explanation,
        }


@dataclass
class PersonaLens:
    """Defines a persona lens perspective (§32)."""
    id: str
    name: str
    description: str
    relevant_criteria: set[str]
    user_impact_template: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "relevant_criteria": sorted(list(self.relevant_criteria)),
        }
