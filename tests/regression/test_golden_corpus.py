"""Regression test suite running against permanent golden fixtures in tests/regression/corpus."""

from pathlib import Path
import pytest
from app.services.static_checks import StaticChecker

CORPUS_DIR = Path(__file__).parent / "corpus"


def test_golden_missing_alt_image():
    fixture = CORPUS_DIR / "missing_alt_image.html"
    html = fixture.read_text(encoding="utf-8")
    checker = StaticChecker(html, url="http://golden.test/missing-alt")
    issues = checker.run_all()

    rule_ids = {iss.get("rule_id") for iss in issues}
    assert any("alt" in rid for rid in rule_ids)


def test_golden_unlabelled_form_input():
    fixture = CORPUS_DIR / "unlabelled_form_input.html"
    html = fixture.read_text(encoding="utf-8")
    checker = StaticChecker(html, url="http://golden.test/form-label")
    issues = checker.run_all()

    rule_ids = {iss.get("rule_id") for iss in issues}
    assert any("label" in rid or "form" in rid for rid in rule_ids)


def test_golden_heading_hierarchy_skip():
    fixture = CORPUS_DIR / "heading_hierarchy_skip.html"
    html = fixture.read_text(encoding="utf-8")
    checker = StaticChecker(html, url="http://golden.test/headings")
    issues = checker.run_all()

    rule_ids = {iss.get("rule_id") for iss in issues}
    assert any("heading" in rid for rid in rule_ids)


def test_golden_missing_html_lang():
    fixture = CORPUS_DIR / "missing_html_lang.html"
    html = fixture.read_text(encoding="utf-8")
    checker = StaticChecker(html, url="http://golden.test/lang")
    issues = checker.run_all()

    rule_ids = {iss.get("rule_id") for iss in issues}
    assert any("lang" in rid for rid in rule_ids)


def test_golden_empty_button_and_link():
    fixture = CORPUS_DIR / "empty_button_link.html"
    html = fixture.read_text(encoding="utf-8")
    checker = StaticChecker(html, url="http://golden.test/buttons-links")
    issues = checker.run_all()

    rule_ids = {iss.get("rule_id") for iss in issues}
    assert any("button" in rid or "link" in rid for rid in rule_ids)
