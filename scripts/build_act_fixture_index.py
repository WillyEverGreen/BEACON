"""Build expanded ACT fixture index from the act-rules.github.io repo.

Parses the _rules/*.md files to extract:
- rule_id, sc_id, wcag_level from YAML front matter
- Inline pass/fail test case HTML snippets from markdown code blocks

Writes extracted HTML fixtures to evaluation/fixtures/act/
and generates evaluation/fixtures/act/fixtures_index.json

Usage:
    python scripts/build_act_fixture_index.py
    python scripts/build_act_fixture_index.py --rules-dir act-rules.github.io/_rules
                                               --out-dir evaluation/fixtures/act
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Patterns ─────────────────────────────────────────────────────────────────

_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)
_ID_RE = re.compile(r"^id:\s*([a-zA-Z0-9_-]+)", re.MULTILINE)
_WCAG_SC_RE = re.compile(r"wcag\d+:(\d+\.\d+\.\d+)", re.MULTILINE)
_LEVEL_RE = re.compile(r"\(([A-Z]{1,3})\)", re.MULTILINE)

# Match fenced code blocks labelled as pass/fail examples
# Pattern: #### Passed/Failed example ... ```html ... ```
_EXAMPLE_RE = re.compile(
    r"####\s+(Passed|Failed|Inapplicable)\s+[Ee]xample[^\n]*\n(.*?)```html\s*\n(.*?)```",
    re.DOTALL | re.IGNORECASE,
)

# Fallback: any ```html block with pass/fail in surrounding 300 chars
_FALLBACK_HTML_RE = re.compile(r"```html\s*\n(.*?)```", re.DOTALL)

_ALLOWED_LEVELS = {"A", "AA"}


def _parse_front_matter(text: str) -> dict[str, str]:
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}
    fm = match.group(1)
    rule_id_m = _ID_RE.search(fm)
    rule_id = rule_id_m.group(1).strip() if rule_id_m else ""

    sc_matches = _WCAG_SC_RE.findall(fm)
    # prefer first A/AA SC
    sc_id = sc_matches[0] if sc_matches else ""

    level_m = _LEVEL_RE.search(fm)
    level = level_m.group(1).upper() if level_m else "AA"

    return {"rule_id": rule_id, "sc_id": sc_id, "wcag_level": level}


def _extract_cases(text: str, rule_id: str, sc_id: str, wcag_level: str) -> list[dict]:
    """Extract test cases from markdown rule file.

    Returns list of dicts: {rule_id, sc_id, wcag_level, html, expected_violation, label}
    """
    cases: list[dict] = []

    for match in _EXAMPLE_RE.finditer(text):
        category = match.group(1).strip().lower()  # passed / failed / inapplicable
        html_snippet = match.group(3).strip()
        if not html_snippet:
            continue

        # Make it a full page if it's just a fragment
        if "<html" not in html_snippet.lower():
            html_snippet = (
                f'<!DOCTYPE html>\n<html lang="en">\n<head><title>{rule_id}</title></head>\n'
                f"<body>\n{html_snippet}\n</body>\n</html>"
            )

        expected_violation = category == "failed"
        cases.append(
            {
                "rule_id": rule_id,
                "sc_id": sc_id,
                "wcag_level": wcag_level,
                "html": html_snippet,
                "expected_violation": expected_violation,
                "label": category,
            }
        )

    return cases


def build_fixture_index(
    rules_dir: Path,
    out_dir: Path,
    *,
    allowed_levels: set[str] = _ALLOWED_LEVELS,
) -> list[dict]:
    """Parse all rule markdown files and write fixture HTML + index."""
    out_dir.mkdir(parents=True, exist_ok=True)
    index_entries: list[dict] = []

    for md_file in sorted(rules_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8", errors="ignore")
        fm = _parse_front_matter(text)
        rule_id = fm.get("rule_id", "")
        sc_id = fm.get("sc_id", "")
        wcag_level = fm.get("wcag_level", "AA")

        if not rule_id or not sc_id:
            continue
        if allowed_levels and wcag_level not in allowed_levels:
            continue

        cases = _extract_cases(text, rule_id, sc_id, wcag_level)

        for i, case in enumerate(cases):
            fixture_name = f"act_{rule_id}_{case['label']}_{i}.html"
            fixture_path = out_dir / fixture_name
            fixture_path.write_text(case["html"], encoding="utf-8")

            index_entries.append(
                {
                    "rule_id": rule_id,
                    "sc_id": sc_id,
                    "wcag_level": wcag_level,
                    "fixture_file": fixture_name,
                    "expected_outcome": case["expected_violation"],
                    "expected_violation": case["expected_violation"],
                    "label": case["label"],
                    "source": "act",
                }
            )

    return index_entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ACT fixture index from repo")
    parser.add_argument(
        "--rules-dir",
        default="act-rules.github.io/_rules",
        help="Path to _rules/ directory in act-rules.github.io clone",
    )
    parser.add_argument(
        "--out-dir",
        default="evaluation/fixtures/act",
        help="Output directory for fixture HTML files and index",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Don't overwrite existing fixture HTML files",
    )
    args = parser.parse_args()

    rules_dir = Path(args.rules_dir)
    out_dir = Path(args.out_dir)

    if not rules_dir.exists():
        raise SystemExit(f"Rules directory not found: {rules_dir}")

    print(f"Parsing rules from: {rules_dir}")
    entries = build_fixture_index(rules_dir, out_dir)

    # Always include the 4 curated baseline fixtures
    baseline = [
        {
            "rule_id": "image-alt",
            "sc_id": "1.1.1",
            "wcag_level": "A",
            "fixture_file": "act_missing_alt_fail.html",
            "expected_outcome": True,
            "expected_violation": True,
            "label": "failed",
            "source": "act_baseline",
        },
        {
            "rule_id": "html-has-lang",
            "sc_id": "3.1.1",
            "wcag_level": "A",
            "fixture_file": "act_missing_lang_fail.html",
            "expected_outcome": True,
            "expected_violation": True,
            "label": "failed",
            "source": "act_baseline",
        },
        {
            "rule_id": "button-name",
            "sc_id": "4.1.2",
            "wcag_level": "A",
            "fixture_file": "act_button_name_fail.html",
            "expected_outcome": True,
            "expected_violation": True,
            "label": "failed",
            "source": "act_baseline",
        },
        {
            "rule_id": "label",
            "sc_id": "1.3.1",
            "wcag_level": "A",
            "fixture_file": "act_form_label_pass.html",
            "expected_outcome": False,
            "expected_violation": False,
            "label": "passed",
            "source": "act_baseline",
        },
    ]

    # Merge: baseline first, then de-duplicate
    seen = {e["fixture_file"] for e in baseline}
    merged = list(baseline)
    for e in entries:
        if e["fixture_file"] not in seen:
            seen.add(e["fixture_file"])
            merged.append(e)

    index_file = out_dir / "fixtures_index.json"
    index_file.write_text(json.dumps(merged, indent=2), encoding="utf-8")

    rules_covered = len({e["rule_id"] for e in merged})
    sc_covered = len({e["sc_id"] for e in merged})
    failed = sum(1 for e in merged if e.get("expected_violation"))
    passed = sum(1 for e in merged if not e.get("expected_violation"))

    print(f"Total fixtures: {len(merged)}")
    print(f"Rules covered: {rules_covered}")
    print(f"SC covered:    {sc_covered}")
    print(f"Failed cases:  {failed}")
    print(f"Passed cases:  {passed}")
    print(f"Index written: {index_file}")


if __name__ == "__main__":
    main()
