# Evaluation Folder Guide

This folder mixes source scripts, benchmark datasets, and generated outputs.

## Keep in Git (source of truth)

- Benchmark runners and analysis tools:
  - `benchmark_precision_recall.py`
  - `reliability_gate.py`
  - `analyze_benchmark.py`
  - `tune_detection.py`
  - `ingest_benchmark_sources.py`
  - `verify_issues_against_local_repo.py`
- Benchmark inputs:
  - `benchmark_cases.json`
  - `benchmark_cases_20.json`
  - `benchmark_sources.json`
  - `sample_benchmark.json`
- Mapping/config data:
  - `act_rule_mapping.json`
  - `adjudication_template.json`

## Generated outputs (ignored by .gitignore)

- `benchmark_results*.json`
- `benchmark_ingestion_report*.json`
- `gate_*_run*.json`
- `reliability_gate_report*.json`
- `tmp_*.json`
- `analysis_current.json`
- `detection_tuning_guide.json`
- `repo_validation_results.json`

## Recommended workflow

1. Update source scripts/config.
2. Run benchmarks locally.
3. Commit only scripts + benchmark inputs + stable mapping data.
4. Do not commit transient result artifacts.
