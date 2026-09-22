"""
Unit tests for Batch 1: Platform Foundation (§1–§7).
Verifies:
- §1: Engine manifest and version freeze
- §2: Master WCAG 2.2 capability matrix
- §3: WCAG 2.2 new criteria audit
- §4: Historical WCAG legacy mapping
- §5: Detector capability registry
- §6: Detection engine field preservation
- §7: Offline axe vendoring and fallback handling
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.services.engine_manifest import attach_manifest_to_result, get_engine_manifest
from app.services.normalizer import (
    normalize_axe_results,
    normalize_ibm_results,
    normalize_static_results,
)
from app.services.vendor_axe import (
    get_axe_version,
    get_vendored_axe_path,
    inject_axe,
)


class TestBatch1EngineManifest:
    """Tests for §1: Engine Manifest."""

    def test_engine_manifest_structure(self):
        manifest = get_engine_manifest(reload=True)
        assert isinstance(manifest, dict)
        assert manifest.get("wcag_baseline") == "2.2"
        assert "beacon_engine_version" in manifest
        assert "adjudicator_version" in manifest
        assert "calibrator_version" in manifest
        assert "benchmark_version" in manifest
        assert "scan_engine_versions" in manifest
        
        engines = manifest["scan_engine_versions"]
        assert "axe" in engines
        assert "ibm" in engines
        assert "beacon_static" in engines
        assert "beacon_browser" in engines

    def test_attach_manifest_to_result(self):
        result = {"url": "https://example.com", "score": 95.0}
        attached = attach_manifest_to_result(result)
        assert "engine_manifest" in attached
        assert attached["beacon_engine_version"] == attached["engine_manifest"]["beacon_engine_version"]
        assert attached["wcag_baseline"] == "2.2"


class TestBatch1WCAGCapabilityMatrix:
    """Tests for §2, §3, §4: WCAG Capability Matrix and Legacy Mappings."""

    @pytest.fixture
    def matrix_data(self):
        path = Path("app/data/wcag_capability_matrix.json")
        assert path.exists(), "wcag_capability_matrix.json must exist"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture
    def legacy_mapping_data(self):
        path = Path("app/data/wcag_legacy_mapping.json")
        assert path.exists(), "wcag_legacy_mapping.json must exist"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_matrix_criterion_count_and_fields(self, matrix_data):
        assert len(matrix_data) >= 86
        valid_states = {
            "IMPLEMENTED_DETERMINISTIC",
            "IMPLEMENTED_BROWSER",
            "IMPLEMENTED_VISUAL",
            "IMPLEMENTED_ASSISTIVE_TECH",
            "IMPLEMENTED_AI_CONTEXTUAL",
            "PARTIAL",
            "ADVISORY_ONLY",
            "HUMAN_REVIEW_REQUIRED",
            "NOT_IMPLEMENTED",
            "NOT_APPLICABLE",
        }
        for entry in matrix_data:
            assert "criterion" in entry
            assert "title" in entry
            assert "level" in entry
            assert entry["capability_state"] in valid_states, f"Invalid state {entry['capability_state']} in {entry['criterion']}"
            assert isinstance(entry["implemented"], bool)
            assert isinstance(entry["automation_type"], list)
            assert "requires_browser" in entry
            assert "requires_visual" in entry
            assert "requires_at" in entry
            assert "human_review" in entry
            assert isinstance(entry["detector_ids"], list)
            assert isinstance(entry["evidence_requirements"], list)
            assert isinstance(entry["limitations"], list)

    def test_parsing_411_is_obsolete(self, matrix_data):
        p = [c for c in matrix_data if c["criterion"] == "4.1.1"]
        assert len(p) == 1
        entry = p[0]
        assert entry["capability_state"] == "NOT_APPLICABLE"
        assert entry["implemented"] is False
        assert entry["human_review"] == "not_applicable"

    def test_wcag_22_new_criteria_presence(self, matrix_data):
        new_criteria = ["2.4.11", "2.4.12", "2.4.13", "2.5.7", "2.5.8", "3.2.6", "3.3.7", "3.3.8", "3.3.9"]
        found = {c["criterion"]: c for c in matrix_data if c["criterion"] in new_criteria}
        assert len(found) == 9
        
        # 2.4.11 Focus Not Obscured (Minimum) is implemented via browser/visual probe
        assert found["2.4.11"]["implemented"] is True
        assert found["2.4.11"]["capability_state"] == "IMPLEMENTED_VISUAL"
        
        # 2.5.8 Target Size (Minimum) is implemented via browser/visual probe
        assert found["2.5.8"]["implemented"] is True
        assert found["2.5.8"]["capability_state"] == "IMPLEMENTED_VISUAL"
        
        # 3.3.7 Redundant Entry is implemented deterministically
        assert found["3.3.7"]["implemented"] is True
        
        # 3.3.8 Accessible Authentication is implemented deterministically
        assert found["3.3.8"]["implemented"] is True

    def test_legacy_mapping_spec(self, legacy_mapping_data):
        assert legacy_mapping_data.get("baseline_version") == "2.2"
        mappings = legacy_mapping_data.get("mappings", [])
        assert len(mappings) >= 3
        
        # Check 4.1.1 mapping
        sc411 = [m for m in mappings if m["historical_criterion"] == "4.1.1"][0]
        assert sc411["current_status"] == "OBSOLETE"
        assert "1.3.1" in sc411["current_equivalent"]
        assert "4.1.2" in sc411["current_equivalent"]


class TestBatch1DetectorRegistry:
    """Tests for §5: Detector Capability Registry."""

    @pytest.fixture
    def registry_data(self):
        path = Path("app/data/detector_registry.json")
        assert path.exists(), "detector_registry.json must exist"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_detector_registry_fields(self, registry_data):
        assert len(registry_data) >= 150
        valid_severities = {"critical", "serious", "moderate", "minor"}
        valid_human = {"never", "conditional", "always"}
        
        for rule_id, rule in registry_data.items():
            assert rule["rule_id"] == rule_id
            assert "category" in rule
            assert "wcag_criterion" in rule
            assert rule["severity_class"] in valid_severities
            assert isinstance(rule["deterministic"], bool)
            assert isinstance(rule["requires_dom"], bool)
            assert isinstance(rule["requires_runtime"], bool)
            assert isinstance(rule["requires_visual"], bool)
            assert isinstance(rule["requires_at"], bool)
            assert rule["requires_human"] in valid_human
            assert isinstance(rule["engines"], list)
            assert len(rule["engines"]) >= 1


class TestBatch1NormalizerPreservation:
    """Tests for §6: Normalizer Preservation of Engine Metadata."""

    def test_axe_normalization_preserves_engine_metadata(self):
        sample_axe = [{
            "id": "image-alt",
            "impact": "critical",
            "description": "Images must have alternate text",
            "help": "Add alt text",
            "helpUrl": "https://dequeuniversity.com/rules/axe/4.11/image-alt",
            "nodes": [{
                "target": ["img#logo"],
                "html": "<img id='logo' src='logo.png'>",
                "failureSummary": "Fix alt attribute",
            }]
        }]
        res = normalize_axe_results(sample_axe, "https://example.com")
        assert len(res) == 1
        item = res[0]
        assert item["source_engine"] == "axe-core"
        assert item["engine_version"] == "4.11.1"
        assert item["raw_rule_id"] == "image-alt"
        assert item["selector"] == "img#logo"
        assert item["html"] == "<img id='logo' src='logo.png'>"
        assert item["page_url"] == "https://example.com"
        assert isinstance(item["evidence"], dict)

    def test_static_normalization_preserves_engine_metadata(self):
        sample_static = [{
            "rule_id": "empty-heading",
            "element": "h1.title",
            "html_snippet": "<h1 class='title'></h1>",
            "page_url": "https://example.com",
            "severity": "moderate",
            "wcag_criterion": "1.3.1",
            "wcag_level": "A",
            "category": "structure",
            "confidence": 0.9,
            "confidence_sources": ["static"],
            "needs_manual_review": False,
            "description": "Empty heading",
            "suggested_fix": "Add text",
            "code_fix": "",
            "fix_effort": "low",
        }]
        res = normalize_static_results(sample_static)
        assert len(res) == 1
        item = res[0]
        assert item["source_engine"] == "beacon_static"
        assert "engine_version" in item
        assert item["raw_rule_id"] == "empty-heading"
        assert item["selector"] == "h1.title"
        assert item["html"] == "<h1 class='title'></h1>"

    def test_ibm_normalization_preserves_engine_metadata(self):
        sample_ibm = [{
            "rule_id": "WCAG20_Img_HasAlt",
            "selector": "img#hero",
            "html_snippet": "<img id='hero'>",
            "message": "Image requires alt",
            "severity": "violation",
        }]
        res = normalize_ibm_results(sample_ibm, "https://example.com")
        assert len(res) == 1
        item = res[0]
        assert item["source_engine"] == "ibm"
        assert item["engine_version"] == "3.1.60"
        assert item["raw_rule_id"] == "WCAG20_Img_HasAlt"
        assert item["selector"] == "img#hero"
        assert item["html"] == "<img id='hero'>"


class TestBatch1VendoredAxe:
    """Tests for §7: Axe Vendored Execution."""

    def test_vendored_axe_path_exists(self):
        path = get_vendored_axe_path()
        assert path is not None, "Vendored axe runtime must be located locally"
        assert path.exists()
        assert path.stat().st_size > 100000, "Vendored axe asset should be >100KB"

    def test_vendored_axe_version(self):
        version = get_axe_version()
        assert version.startswith("4.")

    @pytest.mark.asyncio
    async def test_inject_axe_offline_vendored(self):
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = "4.11.1"
        success, source, version = await inject_axe(mock_page, allow_cdn_fallback=False)
        assert success is True
        assert source == "vendored"
        assert version == "4.11.1"
        mock_page.add_script_tag.assert_called_once()
        # Ensure it was called with path (local file), NOT url (remote CDN)
        call_kwargs = mock_page.add_script_tag.call_args.kwargs
        assert "path" in call_kwargs

    @pytest.mark.asyncio
    async def test_inject_axe_missing_no_cdn_fails_cleanly(self):
        mock_page = AsyncMock()
        with patch("app.services.vendor_axe.get_vendored_axe_path", return_value=None):
            success, source, version = await inject_axe(mock_page, allow_cdn_fallback=False)
            assert success is False
            assert source == "none"
            mock_page.add_script_tag.assert_not_called()

    @pytest.mark.asyncio
    async def test_inject_axe_missing_with_cdn_fallback(self):
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = "4.11.1"
        with patch("app.services.vendor_axe.get_vendored_axe_path", return_value=None):
            success, source, version = await inject_axe(mock_page, allow_cdn_fallback=True)
            assert success is True
            assert source == "cdn"
            mock_page.add_script_tag.assert_called_once()
            assert "url" in mock_page.add_script_tag.call_args.kwargs
