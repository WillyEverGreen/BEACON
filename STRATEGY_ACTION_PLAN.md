# 90+ Master Plan (Codebase-Scanned)

Date: 2026-04-07

## Objective

Drive all primary quality parameters above 90 using code-level fixes, not only benchmark-script tuning.

## Current Baseline (From Latest Artifacts)

- 50-site pass rate: 56.0% (28/50)
- 50-site SPA detected: 48/50 (historically over-detected in this artifact)
- Strategic 10-site expectations met: 6/10
- Strategic SPA detected: 0/10 (after heuristic hardening)
- RAG status trend: pending reduced from 10/10 to 0/4 in postfix quick run
- ACT benchmark (high_precision deep):
  - Micro: P=0.0486, R=0.35, F1=0.0854
  - Adjudicated micro: P=1.00, R=0.35, F1=0.5185
- Reliability gate recommends high_precision but with low absolute values:
  - mean precision=0.125, mean recall=0.35

## 90+ Parameter Contract

Normalize all targets to percentages and make them enforceable in CI:

1. Audit success rate >= 90%
2. Non-degraded deep scans >= 90%
3. Strategic expectations met >= 90%
4. SPA classification precision >= 90% and recall >= 90% on labeled SPA set
5. RAG completion rate (complete/not pending, not timed out) >= 90%
6. Category deep-score floor: each category average >= 90
7. ACT adjudicated precision >= 90%, recall >= 90%, F1 >= 90%
8. Runtime reliability: fast timeout rate < 10%, deep timeout rate < 10%

## Root Causes Found in Code Scan

1. Benchmark contamination in evaluation harness:

- evaluation/benchmark_precision_recall.py clears PAGE_LEVEL_RULES at import time, which weakens fragment-aware filtering and distorts precision/recall.

2. Pass-rate metric mismatch in large suites:

- tests/comprehensive_50_sites_test.py marks pass/fail against static expected ranges that are partially calibrated for old behavior and can penalize improvements.

3. RAG dependency fragility:

- rag-pipeline/query.py hard-depends on Chroma collection availability; on failure it returns empty retrieval, leading to enrichment failures/timeouts.

4. Recall bottlenecks in rule detection:

- evaluation/fn_analysis_report_current.json shows large FN mass concentrated in a few rules (text-spacing, video-transcript, svg-no-accessible-name, semantic-html, link-purpose).

5. Precision/recall profile calibration drift:

- app/services/audit_runner.py profile gating is broad but still not aligned to 90/90 targets for adjudicated ACT metrics.

6. Suite/data integrity drift:

- tests/100_site_benchmark.py still uses variable name SITES_100 with 110 entries; this can create expectation drift in reports.

## Execution Plan

### Phase 1 (Day 1-2): Benchmark Integrity and KPI Contract

Goal: Ensure metrics are trustworthy before tuning detectors.

Tasks:

1. Remove harness-side policy mutation:

- File: evaluation/benchmark_precision_recall.py
- Action: remove PAGE_LEVEL_RULES.clear() side effect.

2. Define one KPI schema for all suites:

- Files: tests/comprehensive_50_sites_test.py, tests/test_deep_scan_playwright.py, tests/100_site_benchmark.py
- Action: emit a common summary block with fields for success_rate, degraded_rate, spa_precision, spa_recall, rag_completion_rate, category_score_floor.

3. Split pass/fail from score-range legacy logic:

- File: tests/comprehensive_50_sites_test.py
- Action: keep legacy range-check as informational, but gate final pass on new KPI contract.

Exit criteria:

- One report format across strategic/50/large suites.
- No hidden profile mutation in evaluation scripts.

### Phase 2 (Day 2-4): Reliability and Timeout Reduction to 90+

Goal: push success and non-degraded rates over 90.

Tasks:

1. Deep scan stability envelope:

- File: app/services/audit_runner.py
- Action: add tiered retry for browser engines (short retry for navigation failure, long retry for render failure), with explicit failure classes.

2. Dynamic timeout policy by site complexity:

- Files: app/services/browser_probes.py, tests/comprehensive_50_sites_test.py
- Action: adaptive timeout for known complex domains; avoid hard static timeout for all categories.

3. Degraded-mode observability and quarantine:

- File: app/services/audit_runner.py
- Action: export degraded_reason taxonomy and per-engine failure counters for each run.

Exit criteria:

- Deep non-degraded rate >= 90% on strategic + 50-site rerun.
- Timeout rate < 10% for both fast and deep.

### Phase 3 (Day 3-6): SPA Precision/Recall Calibration to 90+

Goal: avoid both over-detection and under-detection.

Tasks:

1. Build labeled SPA truth set:

- Files: tests/diagnostics/ (new labeled manifest), tests/test_deep_scan_playwright.py
- Action: maintain list of known SPA/non-SPA sites and compute confusion matrix.

2. Tune generic SPA fallback with negative signals:

- File: app/services/browser_probes.py
- Action: require positive runtime framework markers and reject static-content-heavy pages even with script-heavy shells.

3. Add hydration completion confidence:

- File: app/services/browser_probes.py
- Action: classify SPA only when hydration waits succeed or known framework root mounts.

Exit criteria:

- SPA precision >= 90% and recall >= 90% on labeled set.

### Phase 4 (Week 2): Rule Recovery for High-FN Rules

Goal: raise ACT adjudicated recall from 35% toward 90%.

Tasks:

1. Implement high-FN rules as deterministic checks first:

- Files: app/services/static_checks.py, app/services/browser_probes.py
- Priority rules: text-spacing, video-transcript, svg-no-accessible-name, semantic-html, link-purpose.

2. Strengthen precision guards on high-FP rules:

- Files: app/services/static_checks.py, app/services/confidence.py, app/data/rule_quality_policy.json
- Rules to control: missing-label, multiple-h1, no-h1, aria-hidden-focusable, clickable-no-role.

3. Per-rule telemetry and acceptance gating:

- Files: app/services/static*checks.py, evaluation/rule_level_metrics*\*.json generation path
- Action: enforce per-rule minimum recall and precision gates before profile promotion.

Exit criteria:

- Top-10 FN rules each reduced by >= 60%.
- Adjudicated recall >= 75% interim checkpoint.

### Phase 5 (Week 2-3): RAG Completion and Value to 90+

Goal: keep enrichment complete and useful under load.

Tasks:

1. Retrieval failover chain:

- Files: rag-pipeline/query.py, app/services/retrieval.py
- Action: on Chroma failure, fallback to local vector_store semantic search and return bounded context.

2. Startup health checks and warmup:

- Files: app/main.py (or startup path), app/services/retrieval.py
- Action: verify collection existence at startup and preload lightweight query.

3. Enrichment timeout hardening:

- File: app/services/llm.py
- Action: reduce batch size on retry, maintain per-batch budgets, and switch to deterministic fallback before timeout edge.

Exit criteria:

- Enrichment complete+failed-resolved >= 90% (pending <= 10%).
- Enriched issue ratio >= 90% for eligible issues in strategic set.

### Phase 6 (Week 3): Score Calibration and Category 90+ Lift

Goal: each category average deep score >= 90 while preserving detection quality.

Tasks:

1. Severity/penalty calibration using audited samples:

- File: app/services/audit_runner.py (\_calculate_score)
- Action: rebalance per-severity caps and grouped issue handling to avoid over-penalization spikes.

2. Split compliance score from risk score:

- Files: app/services/audit_runner.py, reporting outputs
- Action: keep one strict risk score and one normalized compliance score to avoid metric collapse in dynamic pages.

3. Category-specific remediation loops:

- Inputs: tests/50*sites_test_results*\*.json category stats
- Action: run targeted fixes per weak category (tech/ecommerce/social/news/education/finance/healthcare/blog).

Exit criteria:

- Every category deep-score average >= 90 on full rerun.

## Validation Sequence (Do Not Skip)

After each phase:

1. Unit tests for touched modules
2. Strategic 10-site rerun
3. 50-site rerun
4. ACT-20 adjudicated rerun
5. Reliability gate rerun

Final acceptance run order:

1. tests/test_deep_scan_playwright.py
2. tests/comprehensive_50_sites_test.py
3. tests/100_site_benchmark.py
4. evaluation/benchmark_precision_recall.py (high_precision_recall_strict)
5. evaluation/reliability_gate.py

## Weekly Milestones

Week 1:

- KPI contract and reliability stabilization complete
- Strategic metrics >= 90 on success/degraded/SPA

Week 2:

- High-FN rule recovery and RAG failover complete
- ACT adjudicated metrics >= 80 interim

Week 3:

- Score/category calibration complete
- All defined parameters >= 90

## Risk Controls

1. Never tune benchmark scripts to fake gains; tune engine or labeling policy only.
2. Keep legacy metrics for historical comparison, but gate release on new KPI contract.
3. Use per-phase rollback checkpoints with tagged artifacts.

## Immediate Next 5 Actions

1. Remove PAGE_LEVEL_RULES.clear() from evaluation harness.
2. Implement unified KPI summary schema across test suites.
3. Add SPA confusion-matrix report to strategic test.
4. Add Chroma failover retrieval path.
5. Run strategic + 50-site rerun and compare against this KPI contract.
