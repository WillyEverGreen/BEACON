from pathlib import Path

import pytest

from app.services.static_checks import StaticChecker


def run_beacon_fast_fixture(fixture_path: Path) -> dict:
    html = fixture_path.read_text(encoding="utf-8")
    checker = StaticChecker(html, fixture_path.resolve().as_uri())
    issues = checker.run_all()
    findings = [
        {
            "rule_id": issue.get("rule_id", ""),
            "sc_id": issue.get("wcag_criterion", ""),
        }
        for issue in issues
    ]
    return {"findings": findings}


WEBAIM_SIX_FIXTURES = [
    ("low_contrast", "evaluation/fixtures/webaim/low_contrast.html", "1.4.3"),
    ("missing_alt", "evaluation/fixtures/webaim/missing_alt.html", "1.1.1"),
    ("missing_form_label", "evaluation/fixtures/webaim/form_no_label.html", "1.3.1"),
    ("empty_link", "evaluation/fixtures/webaim/empty_link.html", "2.4.4"),
    ("empty_button", "evaluation/fixtures/webaim/empty_button.html", "4.1.2"),
    ("missing_lang", "evaluation/fixtures/webaim/no_lang.html", "3.1.1"),
]


@pytest.mark.parametrize("name,fixture,sc", WEBAIM_SIX_FIXTURES)
def test_webaim_failure_detected(name: str, fixture: str, sc: str) -> None:
    result = run_beacon_fast_fixture(Path(fixture))
    assert any(f["sc_id"] == sc for f in result["findings"]), (
        f"BEACON missed {name} ({sc}) - WebAIM top-6 regression failure"
    )
