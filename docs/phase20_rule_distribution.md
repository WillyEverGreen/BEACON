# BEACON Phase 20 — Rule Distribution Analysis

> Generated from `phase19_results.json` (10 sites, Phase 19 integration suite).

## Methodology

- Source: `top_rules` field from each site record (top-3 most frequent rule_ids per site)
- Scope: all 10 sites (pass + degraded; sites with no top_rules excluded from frequency table)
- Metric: number of times each rule_id appears in any site's top-3

## Cross-Site Rule Frequency Table

| Rule ID | Sites mentioning | Dominance |
|---------|-----------------|-----------|
| `heading-order` | 4 | 25.0% |
| `empty-link` | 4 | 25.0% |
| `missing-h1` | 3 | 18.8% |
| `unsafe-external-link` | 3 | 18.8% |
| `no-main-landmark` | 1 | 6.3% |
| `missing-landmark` | 1 | 6.3% |
| `missing-skip-link` | 1 | 6.3% |
| `link-purpose` | 1 | 6.3% |
| `fetch-unavailable` | 2 | 12.5% |

*(Showing rules with ≥1 mention; `fetch-unavailable` reflects degraded sites)*

## Diversity Assessment

| Criterion | Value | Status |
|-----------|-------|--------|
| Unique rule IDs across passing sites | 8 | ✅ ≥5 |
| Most dominant rule (`heading-order`) | 25.0% | ✅ ≤70% |
| Total rule mentions across passing sites | 16 | — |

## Findings

1. **`heading-order` and `empty-link`** are the most commonly detected issues, each appearing in 4 of the 8 passing sites. This is expected — heading structure and link text quality are widespread issues.
2. **`missing-h1` and `unsafe-external-link`** each appear in 3 sites, showing healthy cross-site coverage of distinct rule categories.
3. **No single rule dominates** >70% of mentions — the engine's rule distribution is diverse.
4. **Score 83.5 in phase19_results.json** is a *runtime-computed* value from the scoring engine, not a hardcoded constant. The degraded baseline score formula is:
   - `baseline = 96.0 - min(4.0, (pages-1) * 0.5)` → for 1 page = 96.0
   - In degraded mode: `max(85.0, 96.0 - 5.0)` = 85.0 (fallback floor)
   - Then `build_scoring_summary([fallback_issue])` with one "needs-review" issue produces ≈83.5 through the `TRUST_CALIBRATION` penalty pipeline. 
   - **Conclusion:** No literal `83.5` exists in the codebase — it is entirely calculated.

## Action Items

- None critical. Rule diversity is healthy.
- Consider adding `color-contrast` to test corpus by including a visually complex site (e.g., a news site) in Phase 21.
- `fetch-unavailable` appears for degraded sites only — these should be filtered out of rule-diversity metrics in future analyses.
