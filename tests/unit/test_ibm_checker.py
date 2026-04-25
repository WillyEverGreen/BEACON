import asyncio
import json

import pytest

from app.services.ibm_checker import parse_ibm_report, run_ibm_scan_url
from app.services.normalizer import normalize_all, normalize_ibm_results


@pytest.mark.asyncio
async def test_run_ibm_scan_url_parses_json(monkeypatch):
    class _FakeProc:
        returncode = 0

        async def communicate(self):
            payload = {
                "results": [
                    {
                        "ruleId": "WCAG20_Img_HasAlt",
                        "message": "Image has no alt",
                        "path": ["img.hero"],
                        "level": "serious",
                    }
                ]
            }
            return str.encode(json.dumps(payload)), b""

    async def _fake_create_subprocess_exec(*_args, **_kwargs):
        return _FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_subprocess_exec)

    findings = await run_ibm_scan_url("https://example.com")
    assert len(findings) == 1
    assert findings[0]["rule_id"] == "WCAG20_Img_HasAlt"
    assert findings[0]["selector"] == "img.hero"


def test_ibm_normalizer_maps_to_wcag():
    raw = parse_ibm_report(
        {
            "results": [
                {
                    "ruleId": "WCAG20_Img_HasAlt",
                    "message": "Missing alt",
                    "path": ["img"],
                    "level": "serious",
                }
            ]
        },
        page_url="https://example.com",
    )

    normalized = normalize_ibm_results(raw, "https://example.com")
    assert normalized
    assert normalized[0]["wcag_criterion"] == "1.1.1"
    assert normalized[0]["confidence"] == pytest.approx(0.85)


def test_axe_and_ibm_corroboration_boosts_confidence():
    axe_violations = [
        {
            "id": "image-alt",
            "impact": "serious",
            "description": "Images must have alternate text",
            "help": "Add alt text",
            "helpUrl": "https://dequeuniversity.com",
            "tags": ["wcag2a"],
            "nodes": [
                {
                    "target": ["img.hero"],
                    "html": "<img class='hero'>",
                    "failureSummary": "Fix image alt",
                }
            ],
        }
    ]

    ibm_raw = [
        {
            "rule_id": "WCAG20_Img_HasAlt",
            "selector": "img.hero",
            "message": "Missing alt",
            "severity": "serious",
        }
    ]

    issues = normalize_all(
        static_issues=[],
        heuristic_issues=[],
        browser_issues=[],
        axe_issues=axe_violations,
        ibm_issues=ibm_raw,
        url="https://example.com",
    )

    corroborated = [
        issue
        for issue in issues
        if "axe-core" in issue.get("confidence_sources", [])
        and "ibm" in issue.get("confidence_sources", [])
    ]
    assert corroborated, "Expected at least one corroborated axe+ibm finding"
    assert all(issue["confidence"] >= 0.85 for issue in corroborated)
