"""
Test suite for Multi-Framework RAG Taxonomy & Ingestion (WCAG 2.2, ARIA APG, COGA).
"""
import pytest
from app.services.ingestion import (
    _load_wcag_criteria,
    _load_aria_apg_patterns,
    _load_coga_guidelines,
    _criteria_to_chunks,
    _apg_to_chunks,
    _coga_to_chunks,
)


def test_wcag_taxonomy_chunks():
    criteria = _load_wcag_criteria()
    assert len(criteria) > 0
    chunks = _criteria_to_chunks(criteria[:5])
    assert len(chunks) == 5
    for c in chunks:
        assert c["framework"] == "WCAG"
        assert c["document_type"] == "success_criterion"
        assert c["source"] == "W3C"
        assert c["criterion"] != ""
        assert "wcag" in c["silo"]


def test_aria_apg_taxonomy_chunks():
    patterns = _load_aria_apg_patterns()
    assert len(patterns) >= 5
    chunks = _apg_to_chunks(patterns)
    assert len(chunks) >= 5
    for c in chunks:
        assert c["framework"] == "ARIA_APG"
        assert c["document_type"] == "design_pattern"
        assert c["source"] == "W3C"
        assert c["silo"] == "aria"
        assert c["role"] != ""


def test_coga_taxonomy_chunks():
    guidelines = _load_coga_guidelines()
    assert len(guidelines) >= 3
    chunks = _coga_to_chunks(guidelines)
    assert len(chunks) >= 3
    for c in chunks:
        assert c["framework"] == "COGA"
        assert c["document_type"] == "cognitive_guideline"
        assert c["source"] == "W3C"
        assert c["silo"] == "coga"
        assert c["topic"] != ""
