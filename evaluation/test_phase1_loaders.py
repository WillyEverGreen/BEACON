from pathlib import Path

from evaluation.accessguru_loader import load_accessguru_examples
from evaluation.act_loader import load_act_cases


def test_act_loader_reads_index_fixture_set() -> None:
    cases = load_act_cases("evaluation/fixtures/act")
    assert len(cases) >= 4
    assert all(case.sc_id for case in cases)


def test_accessguru_loader_semantic_rows() -> None:
    dataset = Path("evaluation/fixtures/accessguru/semantic.jsonl")
    rows = load_accessguru_examples(dataset, semantic_only=True)
    assert rows
    assert all(row.category.lower() == "semantic" for row in rows)
    assert any(row.wcag_sc == "1.1.1" for row in rows)
