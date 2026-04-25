from collections import defaultdict

import pytest

from app.services import retrieval
from scripts.ingest_wcag_techniques import PARTIAL_COVERAGE_SC, build_chunks_from_documents


def test_techniques_indexed_for_partial_sc() -> None:
    docs = []
    for sc_id in PARTIAL_COVERAGE_SC:
        for idx in range(3):
            docs.append(
                {
                    "url": f"https://www.w3.org/WAI/WCAG22/Techniques/general/H{idx + 90}.html",
                    "html": (
                        f"<html><head><title>H{idx + 90}</title></head><body>"
                        f"Technique H{idx + 90}. Success Criterion {sc_id}. Failure examples and tests."  # noqa: E501
                        "</body></html>"
                    ),
                }
            )

    chunks = build_chunks_from_documents(docs)
    counts = defaultdict(int)
    for chunk in chunks:
        sc_id = chunk.get("metadata", {}).get("sc_id", "")
        if sc_id:
            counts[sc_id] += 1

    for sc_id in PARTIAL_COVERAGE_SC:
        assert counts[sc_id] >= 3


@pytest.mark.asyncio
async def test_retrieve_for_issue_prefers_sc_filter(monkeypatch) -> None:
    async def _fake_primary(_query: str, _window: int):
        return [
            {
                "content": "Technique G1 for SC 2.4.7 focus visible.",
                "metadata": {
                    "source": "wcag_techniques",
                    "source_silo": "wcag",
                    "chunk_type": "sufficient",
                    "sc_id": "2.4.7",
                },
                "score": 0.9,
            },
            {
                "content": "Technique H98 for SC 1.3.5 autocomplete guidance.",
                "metadata": {
                    "source": "wcag_techniques",
                    "source_silo": "wcag",
                    "chunk_type": "failure",
                    "sc_id": "1.3.5",
                },
                "score": 0.8,
            },
        ]

    monkeypatch.setattr(retrieval, "_retrieve_primary_candidates", _fake_primary)
    monkeypatch.setattr(retrieval, "_cache_get", lambda _key: None)
    monkeypatch.setattr(retrieval, "_cache_put", lambda _key, _value: None)

    issue = {
        "rule_id": "autocomplete-valid",
        "description": "autocomplete value missing",
        "wcag_criterion": "1.3.5",
        "issue_type": "violation",
    }

    chunks = await retrieval.retrieve_for_issue(issue, n_results=2)
    assert chunks
    assert chunks[0].get("metadata", {}).get("sc_id") == "1.3.5"
