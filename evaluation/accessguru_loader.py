"""AccessGuru dataset loader for semantic baseline measurement."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class AccessGuruExample:
    html_snippet: str
    violation_type: str
    category: str
    wcag_sc: str


_VIOLATION_TO_SC = {
    "missing alt": "1.1.1",
    "alt": "1.1.1",
    "label": "1.3.1",
    "heading": "1.3.1",
    "link": "2.4.4",
    "button": "4.1.2",
    "lang": "3.1.1",
    "contrast": "1.4.3",
}


def _as_rows(data: Any) -> Iterable[dict[str, Any]]:
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item
        return

    if isinstance(data, dict):
        for key in ("rows", "items", "examples", "data"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        yield item
                return


def _infer_sc(violation_type: str, fallback: str = "") -> str:
    if fallback:
        return fallback
    lowered = violation_type.lower()
    for token, sc_id in _VIOLATION_TO_SC.items():
        if token in lowered:
            return sc_id
    return ""


def _parse_row(row: dict[str, Any]) -> AccessGuruExample | None:
    html_snippet = str(
        row.get("html_snippet")
        or row.get("html")
        or row.get("snippet")
        or ""
    ).strip()
    if not html_snippet:
        return None

    violation_type = str(
        row.get("violation_type")
        or row.get("type")
        or row.get("label")
        or "unknown"
    ).strip()
    category = str(row.get("category") or row.get("violation_category") or "").strip()
    wcag_sc = _infer_sc(violation_type, str(row.get("wcag_sc") or row.get("sc_id") or "").strip())

    return AccessGuruExample(
        html_snippet=html_snippet,
        violation_type=violation_type,
        category=category,
        wcag_sc=wcag_sc,
    )


def _load_json(path: Path) -> list[AccessGuruExample]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[AccessGuruExample] = []
    for row in _as_rows(payload):
        parsed = _parse_row(row)
        if parsed is not None:
            out.append(parsed)
    return out


def _load_jsonl(path: Path) -> list[AccessGuruExample]:
    out: list[AccessGuruExample] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        parsed = _parse_row(payload)
        if parsed is not None:
            out.append(parsed)
    return out


def _load_csv(path: Path) -> list[AccessGuruExample]:
    out: list[AccessGuruExample] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            parsed = _parse_row(dict(row))
            if parsed is not None:
                out.append(parsed)
    return out


def load_accessguru_examples(dataset_file: str | Path, *, semantic_only: bool = True) -> list[AccessGuruExample]:
    path = Path(dataset_file)
    if not path.exists():
        return []

    suffix = path.suffix.lower()
    if suffix == ".json":
        rows = _load_json(path)
    elif suffix in {".jsonl", ".ndjson"}:
        rows = _load_jsonl(path)
    elif suffix == ".csv":
        rows = _load_csv(path)
    else:
        rows = []

    if semantic_only:
        return [r for r in rows if r.category.lower() == "semantic"]
    return rows
