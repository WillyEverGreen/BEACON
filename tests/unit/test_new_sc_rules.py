from pathlib import Path

import pytest

from app.services.heuristics import HeuristicAnalyzer


def run_heuristics_on_fixture(fixture_path: Path) -> dict:
    html = fixture_path.read_text(encoding="utf-8")
    analyzer = HeuristicAnalyzer(html, fixture_path.resolve().as_uri())
    issues = analyzer.run_all()
    findings = [
        {
            "rule_id": issue.get("rule_id", ""),
            "sc_id": issue.get("wcag_criterion", ""),
        }
        for issue in issues
    ]
    return {"findings": findings}


NEW_SC_FIXTURES = [
    ("1.3.2", "evaluation/fixtures/gena11y/sc-1.3.2-content-content-is-not-in-correct-reading-order-in-source-code.html"),
    ("1.3.4", "evaluation/fixtures/gena11y/sc-1.3.4-Failure1.html"),
    ("1.4.5", "evaluation/fixtures/gena11y/sc-1.4.5-Failure 1.html"),
    ("3.2.2", "evaluation/fixtures/gena11y/sc-3.2.2-forms-form-control-that-changes-context-without-warning.html"),
]


@pytest.mark.parametrize("sc,fixture", NEW_SC_FIXTURES)
def test_new_rule_fires_on_fixture(sc: str, fixture: str) -> None:
    result = run_heuristics_on_fixture(Path(fixture))
    assert any(f["sc_id"] == sc for f in result["findings"]), (
        f"BEACON missed SC {sc} on GenA11y fixture {fixture}"
    )
