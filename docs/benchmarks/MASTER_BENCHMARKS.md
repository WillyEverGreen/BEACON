# BEACON Engine Benchmarks

This file tracks baseline scores for 5 diverse, high-traffic websites. Use these to detect regressions or drift in the audit engine, crawler, or scoring algorithms.

## Baseline: 2026-05-03 (v2.8, AI Disabled)
| Site | Score | Date | Mode | Engine Version |
| :--- | :--- | :--- | :--- | :--- |
| **Apple** | 70.0 | 2026-05-03 | MAX | v2.8 |
| **Wikipedia** | 88.5 | 2026-05-03 | MAX | v2.8 |
| **Amazon** | 66.5 | 2026-05-03 | MAX | v2.8 |
| **Medium** | 85.0 | 2026-05-03 | MAX | v2.8 |
| **BBC** | 67.2 | 2026-05-03 | MAX | v2.8 |

---

## AI Enrichment Benchmark: 2026-05-03 (v2.8, AI Enabled)
| Site | Mode | Total Issues | AI Enriched | Quality Score (Avg) |
| :--- | :--- | :--- | :--- | :--- |
| **Wikipedia** | DEEP | 10 | 5 | 92.0 (High) |

---

## Regression Testing Instructions
1. Ensure `BEACON_AI_ENABLED` is `False` to match the baseline.
2. Run the benchmarking script: `python scratch/test_real_sites.py`.
3. Compare scores. A delta of > ±2.0 on any site requires investigation into recent scoring or crawler changes.
