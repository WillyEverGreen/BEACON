"""
Custom Profile System & Pre-Scan Configuration (§69, §70).

Allows organizations to define:
- required criteria
- excluded criteria
- custom rules (strictly labeled 'ORGANIZATION_RULE', never presented as official WCAG)
- severity overrides
- profile metadata & custom persona mappings
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.profiles.models import RegulatoryProfile
from app.profiles.registry import GLOBAL_WCAG_22_AA, REGULATORY_PROFILES


@dataclass
class CustomRuleDefinition:
    """Represents an organizational custom accessibility check (§70)."""
    rule_id: str
    name: str
    description: str
    severity: str = "moderate"
    wcag_criterion_override: str | None = None
    rule_type: str = "ORGANIZATION_RULE"  # Mandated label per §70

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "severity": self.severity,
            "wcag_criterion_override": self.wcag_criterion_override,
            "rule_type": "ORGANIZATION_RULE",  # Guarantee rule_type is always ORGANIZATION_RULE
        }


@dataclass
class CustomProfileDefinition:
    """Complete specification for an organization-defined profile (§70)."""
    profile_id: str
    name: str
    organization_id: str
    base_standard: str = "WCAG 2.2 Level AA"
    required_criteria: set[str] = field(default_factory=set)
    excluded_criteria: set[str] = field(default_factory=set)
    custom_rules: list[CustomRuleDefinition] = field(default_factory=list)
    severity_overrides: dict[str, str] = field(default_factory=dict)
    custom_persona_mappings: dict[str, list[str]] = field(default_factory=dict)

    def to_regulatory_profile(self) -> RegulatoryProfile:
        """Converts custom definition into an operational RegulatoryProfile (§70)."""
        # Start with global criteria
        mandatory = set(GLOBAL_WCAG_22_AA.mandatory_criteria)
        if self.required_criteria:
            mandatory.update(self.required_criteria)
        if self.excluded_criteria:
            mandatory.difference_update(self.excluded_criteria)

        mapped_reqs = dict(GLOBAL_WCAG_22_AA.mapped_requirements)
        for r in self.custom_rules:
            mapped_reqs[r.rule_id] = f"[ORGANIZATION_RULE] {r.name}"

        return RegulatoryProfile(
            profile_id=self.profile_id,
            name=self.name,
            jurisdiction=f"Organization: {self.organization_id}",
            scope=f"Custom enterprise policy for {self.organization_id}",
            technical_standard=f"{self.base_standard} + Organizational Overrides",
            mapped_requirements=mapped_reqs,
            mandatory_criteria=mandatory,
            optional_advisory_checks=set(GLOBAL_WCAG_22_AA.optional_advisory_checks),
            report_sections=["Executive Summary", "Organizational Rules Matrix", "Technical Findings"],
            disclaimer=(
                "Custom organizational accessibility profile. Rules marked ORGANIZATION_RULE "
                "represent internal company policy and are not normative W3C WCAG criteria."
            ),
            verification_source={
                "authority": f"Enterprise Tenant ({self.organization_id})",
                "standard": self.name,
                "status": "custom",
            },
        )


class CustomProfileRegistry:
    """Manages creation and retrieval of custom organizational profiles (§70)."""

    def __init__(self) -> None:
        self._custom_profiles: dict[str, CustomProfileDefinition] = {}

    def register_custom_profile(self, profile: CustomProfileDefinition) -> dict[str, Any]:
        """Registers a new custom profile and integrates it into runtime registry."""
        self._custom_profiles[profile.profile_id] = profile
        
        # Also register into global REGULATORY_PROFILES for seamless profile resolution
        reg_prof = profile.to_regulatory_profile()
        REGULATORY_PROFILES[profile.profile_id] = reg_prof

        return {
            "status": "registered",
            "profile_id": profile.profile_id,
            "organization_id": profile.organization_id,
            "mandatory_criteria_count": len(reg_prof.mandatory_criteria),
            "custom_rules_count": len(profile.custom_rules),
        }

    def get_custom_profile(self, profile_id: str) -> CustomProfileDefinition | None:
        return self._custom_profiles.get(profile_id)

    def list_custom_profiles(self, organization_id: str | None = None) -> list[dict[str, Any]]:
        profiles = list(self._custom_profiles.values())
        if organization_id:
            profiles = [p for p in profiles if p.organization_id == organization_id]
        return [
            {
                "profile_id": p.profile_id,
                "name": p.name,
                "organization_id": p.organization_id,
                "custom_rules_count": len(p.custom_rules),
            }
            for p in profiles
        ]


# Singleton instance
custom_profile_registry = CustomProfileRegistry()
