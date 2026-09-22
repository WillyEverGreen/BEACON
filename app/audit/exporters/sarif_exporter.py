"""OASIS SARIF 2.1.0 exporter for BEACON accessibility findings.

Generates standard Static Analysis Results Interchange Format (SARIF) documents
directly compatible with GitHub Code Scanning, GitHub Actions, GitLab SAST,
and enterprise DevSecOps pipelines.
"""

from __future__ import annotations

from typing import Any

from app.models.contracts import Finding

SARIF_SCHEMA_URI = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
BEACON_INFO_URI = "https://github.com/WillyEverGreen/BEACON"


def export_to_sarif(
    findings: list[Finding],
    target_url: str = "https://scan.target",
    tool_version: str = "2.1.0",
) -> dict[str, Any]:
    """Export canonical Findings to standard SARIF 2.1.0 representation."""
    rules_dict: dict[str, dict[str, Any]] = {}
    rule_id_to_index: dict[str, int] = {}
    results: list[dict[str, Any]] = []

    # 1. Build rules index
    for f in findings:
        if f.rule_id not in rules_dict:
            rule_index = len(rules_dict)
            rule_id_to_index[f.rule_id] = rule_index

            tags = ["accessibility"]
            if f.wcag_criterion:
                tags.append(f"wcag{f.wcag_criterion.replace('.', '')}")
            if f.wcag_level:
                tags.append(f"wcag-level-{f.wcag_level.lower()}")
            if f.act_rule_id:
                tags.append(f"act-{f.act_rule_id.lower()}")

            rules_dict[f.rule_id] = {
                "id": f.rule_id,
                "name": f.rule_id.replace("-", " ").title(),
                "shortDescription": {
                    "text": f"WCAG {f.wcag_criterion} ({f.wcag_level}): {f.rule_id}" if f.wcag_criterion else f.rule_id
                },
                "fullDescription": {
                    "text": f.message or f"Accessibility violation flagged by {f.engine}"
                },
                "helpUri": (
                    f"https://www.w3.org/WAI/WCAG21/Understanding/{f.wcag_criterion.replace('.', '')}.html"
                    if f.wcag_criterion
                    else BEACON_INFO_URI
                ),
                "properties": {
                    "tags": tags,
                    "wcag_criterion": f.wcag_criterion,
                    "wcag_level": f.wcag_level,
                    "act_rule_id": f.act_rule_id,
                },
            }

    # 2. Map findings to SARIF results
    for f in findings:
        # Map severity to SARIF level
        sev = f.severity.lower()
        if sev in ("critical", "serious"):
            level = "error"
        elif sev == "moderate":
            level = "warning"
        else:
            level = "note"

        rule_idx = rule_id_to_index.get(f.rule_id, 0)

        result_item: dict[str, Any] = {
            "ruleId": f.rule_id,
            "ruleIndex": rule_idx,
            "level": level,
            "message": {
                "text": f.message
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": target_url
                        },
                        "region": {
                            "snippet": {
                                "text": f.html_snippet[:300] if f.html_snippet else ""
                            }
                        }
                    },
                    "logicalLocations": [
                        {
                            "name": f.selector,
                            "fullyQualifiedName": f.selector,
                            "kind": "element"
                        }
                    ]
                }
            ],
            "properties": {
                "confidence": f.confidence,
                "agreement_count": f.agreement_count,
                "participating_engines": f.participating_engines,
                "selector_fingerprint": f.selector_fingerprint,
                "act_rule_id": f.act_rule_id,
                "act_adjudicated": f.act_adjudicated,
                "evidence": f.evidence,
            }
        }
        results.append(result_item)

    sarif_doc: dict[str, Any] = {
        "$schema": SARIF_SCHEMA_URI,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "BEACON",
                        "version": tool_version,
                        "informationUri": BEACON_INFO_URI,
                        "rules": list(rules_dict.values()),
                    }
                },
                "results": results,
            }
        ],
    }

    return sarif_doc
