# Full Benchmark Recheck Report (2026-04-01)

## Scope
- Objective: verify whether v2 performance claims hold beyond stale v1 artifacts.
- Benchmark runner: `evaluation/benchmark_precision_recall.py`
- Dataset (full): `evaluation/benchmark_cases.json` (1134 ACT cases)
- Dataset (sanity check): `evaluation/benchmark_cases_20.json` (20 cases)
- Profile: `high_precision`
- Scan mode: `fast`

## Fresh Full Recheck (authoritative)
- Output file: `evaluation/benchmark_results_full_recheck_2026-04-01_high_precision.json`
- Micro Precision: **4.12%**
- Micro Recall: **15.21%**
- Micro F1: **6.48%**
- TP / FP / FN: **184 / 4286 / 1026**
- Adjudicated Precision: **100.00%**
- Adjudicated Recall: **15.21%**
- Adjudicated F1: **26.40%**

## Previous Full Artifact (for comparison)
- File: `evaluation/benchmark_results_full_now.json`
- Micro Precision: 2.07%
- Micro Recall: 7.44%
- Micro F1: 3.24%
- TP / FP / FN: 90 / 4257 / 1120
- Adjudicated F1: 13.85%

## Delta: Fresh Full Recheck vs Previous Full Artifact
- Recall: **+7.77 pp** (7.44% -> 15.21%)
- Micro F1: **+3.24 pp** (3.24% -> 6.48%)
- Adjudicated F1: **+12.55 pp** (13.85% -> 26.40%)
- TP: **+94** (90 -> 184)
- FP: **+29** (4257 -> 4286)

## 20-Case Recheck (sanity check)
- Output file: `evaluation/benchmark_results_20_recheck_2026-04-01.json`
- Micro Precision: 12.73%
- Micro Recall: 35.00%
- Micro F1: 18.67%
- Adjudicated F1: 51.85%

## Interpretation
- The v2 claim (**35.0% recall, 51.8% adjudicated F1**) is **confirmed on the 20-case set**.
- On the full 1134-case benchmark, current reproducible performance is **better than old v1-style full artifacts** but does **not** match the 20-case v2 level.
- Current full-scale performance appears to be:
  - Recall: **15.21%**
  - Adjudicated F1: **26.40%**

## Runtime Observations
- During full run, repeated quality-gate warnings appeared: duplicate rate exceeded 5% on multiple cases.
- XMLParsedAsHTML warnings were emitted from:
  - `app/services/static_checks.py`
  - `app/services/heuristics.py`

## Recommended Next Verification Step
- Re-run full benchmark on the explicit v2 profile/config used for the 20-case claim (if different from `high_precision`) and record to a dated file:
  - `evaluation/benchmark_results_full_recheck_2026-04-01_<v2-profile>.json`
