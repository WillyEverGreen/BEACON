"""Fixture loader for GenA11y-style benchmark datasets."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from evaluation.benchmark_runner import FixtureCase


_PASS_MARKERS = {
    "pass",
    "valid",
    "compliant",
    "no-violation",
    "negative",
    "expected-false",
}

_TOKEN_TO_SC = {
    "alt": "1.1.1",
    "image": "1.1.1",
    "label": "1.3.1",
    "form": "1.3.1",
    "heading": "1.3.1",
    "lang": "3.1.1",
    "language": "3.1.1",
    "button": "4.1.2",
    "link": "2.4.4",
    "contrast": "1.4.3",
    "table": "1.3.1",
    "aria": "4.1.2",
}

_SC_PATTERN = re.compile(r"(?:sc|wcag)[-_]?(\d)[._-](\d+)[._-](\d+)", re.IGNORECASE)


def _read_annotation(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return payload[0]
    return None


def _infer_sc_from_name(file_name: str) -> str:
    normalized = file_name.lower()
    match = _SC_PATTERN.search(normalized)
    if match:
        return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"

    for token, sc_id in _TOKEN_TO_SC.items():
        if token in normalized:
            return sc_id

    return ""


def _infer_expected_from_name(file_name: str) -> bool:
    normalized = file_name.lower()
    return not any(marker in normalized for marker in _PASS_MARKERS)


def load_gena11y_cases(fixtures_root: str | Path) -> list[FixtureCase]:
    root = Path(fixtures_root)
    if not root.exists():
        return []

    cases: list[FixtureCase] = []
    for html_file in sorted(root.rglob("*.html")):
        annotation = _read_annotation(html_file.with_suffix(".json"))

        sc_id = ""
        expected = _infer_expected_from_name(html_file.name)

        if annotation:
            sc_id = str(annotation.get("sc_id", "") or annotation.get("wcag_sc", "")).strip()
            if "expected_violation" in annotation:
                expected = bool(annotation.get("expected_violation"))
            elif "expected" in annotation:
                expected = bool(annotation.get("expected"))

        if not sc_id:
            sc_id = _infer_sc_from_name(html_file.stem)

        if not sc_id:
            # Keep dataset strict: skip ambiguous rows instead of silently mis-labeling.
            continue

        cases.append(
            FixtureCase(
                fixture_file=html_file,
                sc_id=sc_id,
                expected_violation=expected,
                source="gena11y",
            )
        )

    return cases
