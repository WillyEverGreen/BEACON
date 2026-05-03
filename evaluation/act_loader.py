"""ACT fixture loader for expanded benchmark execution.

Supports two input layouts:
1. A curated index file at fixtures_index.json (recommended for local runs).
2. A best-effort parser over ACT repository snapshots.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from evaluation.benchmark_runner import FixtureCase


_EXPECTED_PASS_MARKERS = {"pass", "inapplicable", "valid"}
_EXPECTED_FAIL_MARKERS = {"fail", "failed", "violation", "invalid"}

_WCAG_REQ_PATTERN = re.compile(r"(\d\.\d+\.\d+)\s*\(?\s*(A|AA|AAA)?\s*\)?", re.IGNORECASE)
_RULE_ID_PATTERN = re.compile(r"^id:\s*([a-zA-Z0-9_-]+)\s*$", re.MULTILINE)


def _expected_from_name(file_name: str) -> bool:
    lowered = file_name.lower()
    if any(token in lowered for token in _EXPECTED_FAIL_MARKERS):
        return True
    if any(token in lowered for token in _EXPECTED_PASS_MARKERS):
        return False
    return True


def _load_index_file(index_file: Path, allowed_levels: set[str]) -> list[FixtureCase]:
    payload = json.loads(index_file.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("cases", [])

    cases: list[FixtureCase] = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        sc_id = str(row.get("sc_id", "") or "").strip()
        if not sc_id:
            continue

        level = str(row.get("wcag_level", "AA") or "AA").upper()
        if allowed_levels and level not in allowed_levels:
            continue

        fixture_file = Path(str(row.get("fixture_file", "") or "").strip())
        if not fixture_file.is_absolute():
            fixture_file = index_file.parent / fixture_file
        if not fixture_file.exists():
            continue

        expected = bool(row.get("expected_outcome", row.get("expected_violation", True)))

        cases.append(
            FixtureCase(
                fixture_file=fixture_file,
                sc_id=sc_id,
                expected_violation=expected,
                rule_id=str(row.get("rule_id", "") or "").strip(),
                source="act",
            )
        )

    return cases


def _parse_rule_file(rule_file: Path, allowed_levels: set[str]) -> tuple[str, str] | None:
    text = rule_file.read_text(encoding="utf-8", errors="ignore")

    rule_match = _RULE_ID_PATTERN.search(text)
    if not rule_match:
        return None
    rule_id = rule_match.group(1).strip()

    wcag_matches = _WCAG_REQ_PATTERN.findall(text)
    for sc_id, level in wcag_matches:
        normalized_level = (level or "AA").upper()
        if allowed_levels and normalized_level not in allowed_levels:
            continue
        return rule_id, sc_id

    return None


def _best_effort_repo_parse(root: Path, allowed_levels: set[str]) -> list[FixtureCase]:
    rules_dir = root / "_rules"
    test_assets_dir = root / "test-assets"
    if not rules_dir.exists() or not test_assets_dir.exists():
        return []

    cases: list[FixtureCase] = []
    for rule_file in sorted(rules_dir.glob("*.yml")) + sorted(rules_dir.glob("*.yaml")):
        parsed = _parse_rule_file(rule_file, allowed_levels)
        if not parsed:
            continue
        rule_id, sc_id = parsed

        html_candidates = list(test_assets_dir.rglob(f"*{rule_id}*.html"))
        for html_file in html_candidates:
            cases.append(
                FixtureCase(
                    fixture_file=html_file,
                    sc_id=sc_id,
                    expected_violation=_expected_from_name(html_file.name),
                    rule_id=rule_id,
                    source="act",
                )
            )

    return cases


def load_act_cases(fixtures_root: str | Path, *, levels: tuple[str, ...] = ("A", "AA")) -> list[FixtureCase]:
    root = Path(fixtures_root)
    if not root.exists():
        return []

    allowed_levels = {str(level).upper() for level in levels}

    index_file = root / "fixtures_index.json"
    if index_file.exists():
        return _load_index_file(index_file, allowed_levels)

    return _best_effort_repo_parse(root, allowed_levels)
