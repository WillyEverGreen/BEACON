"""
app/services/lighthouse_mapper.py

Single responsibility: transform raw Lighthouse JSON into a list of normalized
findings in BEACON's findings_schema.

Has no knowledge of BEACON's existing findings. Pure transformation.

Key behaviours:
  - Loads app/data/lighthouse_mapping.json once at module import (cached).
  - Applies the inclusion list filter: audits not in the mapping are silently dropped.
  - Score normalization: raw Lighthouse 0.0–1.0 float → 0–100 integer, done ONCE HERE.
    Null scores (informational audits) are stored as None, never as 0.
  - Severity thresholds:
      score_100 < 50  → serious
      score_100 50–89 → moderate
      score_100 ≥ 90  → drop silently (no finding emitted)
  - output finding includes mapping_version for traceability.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── Mapping file ──────────────────────────────────────────────────────────────
_MAPPING_PATH = Path(__file__).parent.parent / "data" / "lighthouse_mapping.json"
_MAPPING: dict[str, Any] | None = None


def _load_mapping() -> dict[str, Any]:
    """Load and cache the versioned mapping file. Fails loudly if missing."""
    global _MAPPING
    if _MAPPING is not None:
        return _MAPPING
    try:
        _MAPPING = json.loads(_MAPPING_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load lighthouse_mapping.json from {_MAPPING_PATH}: {exc}"
        ) from exc
    return _MAPPING


def get_mapping_version() -> str:
    """Return the mapping_version string from the loaded mapping file."""
    return str(_load_mapping().get("mapping_version", "unknown"))


def get_lighthouse_version() -> str:
    """Return the lighthouse_version string from the loaded mapping file."""
    return str(_load_mapping().get("lighthouse_version", "unknown"))


# ── Score normalization ───────────────────────────────────────────────────────

def _normalize_score(raw_score: float | None) -> int | None:
    """Convert Lighthouse 0.0–1.0 score to 0–100 integer.

    None is preserved (informational audits with scoreDisplayMode = 'informative').
    A null score and a score of 0 mean different things — never conflate them.
    """
    if raw_score is None:
        return None
    return round(float(raw_score) * 100)


def _score_to_severity(score_100: int | None) -> str | None:
    """Map a 0–100 score to a severity level.

    Returns None if the score indicates the finding should be dropped silently.
    """
    if score_100 is None:
        return None  # informational — drop
    if score_100 < 50:
        return "serious"
    if score_100 < 90:
        return "moderate"
    return None  # ≥ 90 → drop silently


# ── Category score extraction ─────────────────────────────────────────────────

def extract_category_scores(raw_report: dict[str, Any]) -> dict[str, int | None]:
    """Extract the four Lighthouse category scores as 0–100 integers.

    Keys: performance, accessibility, seo, best_practices.
    None means the category was not present in the report.
    """
    categories = raw_report.get("categories") or {}
    return {
        "performance":    _normalize_score(categories.get("performance",    {}).get("score")),
        "accessibility":  _normalize_score(categories.get("accessibility",  {}).get("score")),
        "seo":            _normalize_score(categories.get("seo",            {}).get("score")),
        "best_practices": _normalize_score(categories.get("best-practices", {}).get("score")),
    }


# ── Main transform ────────────────────────────────────────────────────────────

def map_lighthouse_report(
    raw_report: dict[str, Any],
    *,
    page_url: str,
) -> list[dict[str, Any]]:
    """Transform a raw Lighthouse JSON report into normalized BEACON findings.

    Args:
        raw_report: The full Lighthouse JSON report dict.
        page_url: The URL this report was generated for.

    Returns:
        List of normalized finding dicts. Empty list if the report has no
        qualifying audits. Silently drops audits not in the inclusion list and
        audits whose score is ≥ 90 (no issue).
    """
    mapping = _load_mapping()
    mapping_version = str(mapping.get("mapping_version", "v1"))
    included_audits: dict[str, dict] = mapping.get("audits", {})

    raw_audits = raw_report.get("audits") or {}
    findings: list[dict[str, Any]] = []

    for audit_id, audit_def in included_audits.items():
        raw_audit = raw_audits.get(audit_id)
        if raw_audit is None:
            # Audit not present in this report — silently skip.
            continue

        score_display_mode = str(raw_audit.get("scoreDisplayMode") or "")
        raw_score = raw_audit.get("score")

        # Informational audits have no numeric score — drop silently.
        if score_display_mode in ("informative", "manual", "notApplicable"):
            continue

        score_100 = _normalize_score(raw_score)
        severity = _score_to_severity(score_100)

        if severity is None:
            # Score ≥ 90 or None → drop silently. No log entry.
            continue

        normalized_key = str(audit_def.get("normalized_issue_key", audit_id))
        beacon_category = str(audit_def.get("beacon_category", "performance"))
        title = str(audit_def.get("title") or raw_audit.get("title") or normalized_key)
        description = str(raw_audit.get("description") or audit_def.get("title") or "")
        wcag_criterion = str(audit_def.get("wcag_criterion") or "")

        # Deterministic issue_id: hash of (normalized_key + url)
        issue_seed = f"{normalized_key}|{page_url}"
        issue_id = hashlib.sha256(issue_seed.encode("utf-8", errors="ignore")).hexdigest()[:16]

        findings.append({
            "issue_id": issue_id,
            "rule_id": normalized_key,
            "source": "lighthouse",
            "lighthouse_audit_id": audit_id,
            "lighthouse_score": score_100,
            "severity": severity,
            "category": beacon_category,
            "page_url": page_url,
            "title": title,
            "description": description,
            "wcag_criterion": wcag_criterion,
            "mapping_version": mapping_version,
            # Fields that will be set by the enricher after merge decision:
            "lighthouse_confirmed": False,
            "confidence": "supplementary" if score_100 is not None and score_100 < 50 else "additional_insight",
        })

    logger.debug(
        "lighthouse_mapper map_complete url=%s raw_audits=%d included=%d emitted=%d",
        page_url, len(raw_audits), len(included_audits), len(findings),
    )
    return findings
