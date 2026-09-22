"""
Engine Manifest Service (§1)
Provides versioned metadata and environment snapshot for BEACON.
Ensures audits, reports, and benchmarks trace directly back to the frozen engine configuration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_MANIFEST_PATH = Path(__file__).resolve().parents[1] / "data" / "engine_manifest.json"
_CACHED_MANIFEST: dict[str, Any] | None = None


def get_engine_manifest(reload: bool = False) -> dict[str, Any]:
    """Retrieve the frozen engine manifest."""
    global _CACHED_MANIFEST
    if _CACHED_MANIFEST is not None and not reload:
        return dict(_CACHED_MANIFEST)

    if _MANIFEST_PATH.exists():
        try:
            with open(_MANIFEST_PATH, "r", encoding="utf-8") as f:
                _CACHED_MANIFEST = json.load(f)
                return dict(_CACHED_MANIFEST)
        except Exception:
            pass

    # Fallback default manifest if file missing or corrupted
    _CACHED_MANIFEST = {
        "beacon_engine_version": "2.2.0",
        "wcag_baseline": "2.2",
        "knowledge_base_version": "2.2.0",
        "adjudicator_version": "2.0.0",
        "calibrator_version": "2.0.0",
        "benchmark_version": "2.0.0",
        "prompt_version": "2.0.0",
        "remediation_sandbox_version": "2.0.0",
        "scan_engine_versions": {
            "axe": "4.11.1",
            "ibm": "3.1.60",
            "beacon_static": "2.0.0",
            "beacon_heuristics": "2.0.0",
            "beacon_browser": "2.0.0",
            "beacon_coga": "2.0.0",
        },
    }
    return dict(_CACHED_MANIFEST)


def attach_manifest_to_result(result: dict[str, Any]) -> dict[str, Any]:
    """Injects the engine manifest into an audit or benchmark result dict."""
    manifest = get_engine_manifest()
    result["engine_manifest"] = manifest
    result["beacon_engine_version"] = manifest.get("beacon_engine_version", "2.2.0")
    result["wcag_baseline"] = manifest.get("wcag_baseline", "2.2")
    return result
