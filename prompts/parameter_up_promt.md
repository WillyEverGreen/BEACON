=======================================================================
BEACON AUTONOMOUS EXECUTION PROMPT - SYSTEM HARDENING MASTER PLAN v5.0
=======================================================================

ROLE:
You are a senior staff engineer accountable for evolving BEACON into a
production-grade accessibility intelligence platform that is reliable,
auditable, cost-aware, and useful for real users.

PRIMARY DIRECTIVE:
Improve the system by shipping measurable, validated increments across
the entire codebase. Every change must increase real user value.

YOU MUST:

- improve measurable KPIs
- maintain system stability
- keep architecture understandable
- enforce deterministic behavior where possible
- produce reproducible before/after evidence

YOU MUST NOT:

- optimize benchmarks artificially
- trade precision for headline recall
- hide failures behind silent fallbacks
- ship changes without regression proof

=======================================================================
CODEBASE COVERAGE MAP (MANDATORY)
=================================

You must cover all relevant layers below during execution planning.

1. Platform and config core

- app/main.py
- app/config.py
- app/adapter.py
- app/models.py
- app/schema_compat.py

2. Audit engine and rule stack

- app/services/audit_runner.py
- app/services/static_checks.py
- app/services/heuristics.py
- app/services/browser_probes.py
- app/services/cognitive_checks.py
- app/services/confidence.py
- app/services/normalizer.py
- app/services/dedup_engine.py
- app/services/grouper.py
- app/services/prioritizer.py
- app/services/report.py

3. Caching and enrichment services

- app/services/page_cache.py
- app/services/fix_cache.py
- app/services/llm.py
- app/services/retrieval.py
- app/services/vector_store.py
- app/services/embedding.py
- app/services/feedback.py

4. Crawl and site-level orchestration

- app/crawlers/\*
- app/audit/\*

5. API, security, and persistence

- app/routers/\*
- app/security/\*
- app/db/\*

6. Observability and telemetry

- app/observability/\*
- logs/telemetry.jsonl

7. Rules, policy, and local data contracts

- app/data/rule_quality_policy.json
- app/data/wcag_criteria.json
- app/data/fix_library.json
- app/data/scans.json
- app/data/projects.json

8. RAG ingestion/query pipeline

- rag/\*
- run_ingestion.py

9. Evaluation and test harnesses

- tests/\*
- evaluation/\*

10. Product/UI reporting layer

- frontend/src/\*

If a phase ignores a relevant layer, phase is incomplete.

=======================================================================
GLOBAL KPI CONTRACT (ENFORCED)
==============================

Hard targets:

- precision >= 90%
- reliability >= 90%
- recall between 60% and 70% minimum, then push safely upward
- rag effectiveness >= 80%
- spa precision >= 90%
- spa recall >= 90%
- audit success rate >= 90%
- timeout rate <= 10%
- fast_mode_p95_time <= 10s (target band: 5s to 10s)
- fast_mode_usage >= 70%

User value KPI targets:
{
"useful_issues_per_site": 5,
"fix_acceptance_rate": 0.7
}

Hard rollback rule:

- if precision drops below 90% in any phase, rollback that phase

Secondary quality targets:

- degraded_mode rate <= 10%
- enrichment pending rate <= 10%
- cache observability accuracy >= 95%
- category score floor >= 90 over validated category set

Cost budget guard (enforced):
{
"cost_per_audit": "<= X",
"LLM_calls_per_audit": "<= N"
}

If either budget guard is violated in a phase, phase cannot be promoted.

=======================================================================
GLOBAL ENGINEERING RULES
========================

1. Every phase must include:

- unit or integration tests
- validation runs
- metrics delta report

2. No release without:

- regression tests passing
- before vs after KPI comparison

3. If cost rises materially:

- add gating condition
- add cache or batching

4. Prefer:

- deterministic logic over AI-only heuristics
- simple and explainable implementation over complexity

5. Benchmark integrity rules:

- no hidden global state mutation in evaluation scripts
- no cross-profile cache contamination
- no mislabeled dataset cardinality in published summaries

6. Telemetry rules:

- per-rule activity telemetry required for every new detector
- telemetry hooks must not be nested in branches that skip counts

=======================================================================
MANDATORY EXECUTION LOOP (PER PHASE)
====================================

For each phase, execute this exact loop:

1. Baseline snapshot

- capture current KPI values and artifacts

2. Scope lock

- identify files, tests, and acceptance checks

3. Implement minimal high-leverage changes

4. Validate locally

- unit tests + targeted integration

5. Run benchmark sequence

- strategic 10-site
- 50-site suite
- ACT subset

6. Compare KPI deltas

- publish gains, regressions, confidence

7. Decision

- promote / iterate / rollback

No phase may skip loop steps.

=======================================================================
PHASE 0 - METRIC INTEGRITY, REPRODUCIBILITY, BASELINE
=====================================================

OBJECTIVE:
Ensure metrics are clean, deterministic, and reproducible.

TASKS:

1. Remove hidden mutations and side effects

- eliminate global policy mutation in benchmark/evaluation code

2. Unified KPI schema for all benchmark outputs

Output object:
{
success_rate,
degraded_rate,
precision,
recall,
f1,
spa_precision,
spa_recall,
rag_completion,
timeout_rate,
avg_runtime
}

3. Add deterministic enrichment mode

- await_enrichment flag for benchmark paths
- block completion until enrichment terminal state in controlled runs

4. Add RAG retrieval diagnostics
   {
   query,
   retrieved_chunks,
   similarity_scores,
   source,
   fallback_used
   }

EXIT CRITERIA:

- metrics stable across 3 consecutive runs
- no side-effect contamination
- KPI schema emitted by all target suites

=======================================================================
PHASE 1 - RECALL ENGINE UPLIFT (PRECISION-SAFE)
===============================================

OBJECTIVE:
Increase deterministic recall while holding precision >= 90%.

TASKS:

1. Build or formalize rule execution abstraction

2. Prioritize high-FN rule families first

- aria-required-parent
- aria-required-children
- aria-allowed-role
- aria-hidden-focusable
- missing-h1
- multiple-h1
- heading-order
- missing-label variants
- link-purpose
- clickable-no-role
- svg accessible name
- media text alternatives

Top 20 rule priority list (implement in this exact order):

1. missing-label
2. aria-required-parent
3. link-purpose
4. aria-required-children
5. aria-allowed-role
6. aria-hidden-focusable
7. button-name
8. missing-lang
9. missing-h1
10. multiple-h1
11. heading-order
12. clickable-no-role
13. landmark roles
14. text-spacing
15. svg-no-accessible-name
16. video-transcript
17. semantic-html
18. missing-alt variants
19. autocomplete-missing
20. duplicate-label

21. Heuristic isolation

- low-confidence findings must be tagged and governed

4. ACT gap tracker

- track rule coverage percent and FN mass reduction

5. Per-rule activity telemetry

- elements_checked
- violations_found
- confidence_bucket

EXIT CRITERIA:

- recall >= 50% initial checkpoint
- precision >= 90%
- no uncontrolled FP surge in top 10 FP rules

=======================================================================
PHASE 2 - RELIABILITY AND PERFORMANCE HARDENING
===============================================

OBJECTIVE:
Achieve stable deep/fast execution under real-world conditions.

TASKS:

1. Browser runtime optimization

- block non-essential assets where safe
- cap heavy interactions with tuned thresholds
- classify retryable vs non-retryable failures

2. Smart fallback strategy

- if deep browser path fails, fallback must be explicit and observable

3. Adaptive timeout policy

- tune by complexity and historical behavior

4. Degraded mode transparency

- emit degraded_reason taxonomy per engine

5. Cache hardening

- page cache integrity
- fix cache hit/miss counters correctness
- no cache poisoning by invalid payload signatures

EXIT CRITERIA:

- audit success rate >= 90%
- timeout rate <= 10%
- degraded mode rate <= 10%
- fast_mode_p95_time <= 10s (target band: 5s to 10s)
- fast_mode_usage >= 70%

=======================================================================
PHASE 3 - SPA DETECTION CALIBRATION
===================================

OBJECTIVE:
Reach spa precision >= 90% and spa recall >= 90%.

TASKS:

1. Build and maintain labeled SPA truth set

- known SPA and non-SPA classes

2. Multi-signal detection policy

- framework markers
- hydration success
- dynamic DOM evidence

3. Negative evidence policy

- static-only behavior
- no meaningful post-load dynamics

4. Confusion matrix reporting

- TP, FP, FN, TN per run

EXIT CRITERIA:

- spa precision >= 90%
- spa recall >= 90%

=======================================================================
PHASE 4 - RAG STABILITY, QUALITY, COST CONTROL
==============================================

OBJECTIVE:
Make enrichment reliable, useful, and affordable.

TASKS:

1. Retrieval failover chain

- primary vector retrieval
- fallback local semantic retrieval
- explicit source tagging

2. Retrieval quality controls

- wcag-aware filtering
- bounded chunk count
- similarity threshold policy

3. Prompt and response hardening

- structured issue context
- deterministic output schema

4. Effectiveness scoring

- fix usefulness rate
- accepted suggestion rate

5. Cost controls

- batching
- caching
- bounded retries and timeout budgets

6. Enforce budget guard per audit

- cost_per_audit <= X
- LLM_calls_per_audit <= N

EXIT CRITERIA:

- rag completion >= 80%
- rag effectiveness >= 80%
- no precision regression below 90%
- cost_per_audit <= X
- LLM_calls_per_audit <= N

=======================================================================
PHASE 5 - SCORING, POLICY, AND CALIBRATION
==========================================

OBJECTIVE:
Ensure scores are stable, interpretable, and aligned with true risk.

TASKS:

1. Penalty rebalancing

- prevent over-penalizing issue clusters

2. Dual-score model

- compliance score
- risk score

3. Category normalization

- enforce stable cross-category interpretation

4. Rule quality governance updates

- policy thresholds tied to observed rule metrics

EXIT CRITERIA:

- score stability across repeated runs
- no extreme unexplained score drops
- category score floor progression toward >= 90

=======================================================================
PHASE 6 - CRAWLING, ORCHESTRATION, AND SITE AGGREGATION HARDENING
==================================================================

OBJECTIVE:
Make multi-page/site workflows robust and consistent.

TASKS:

1. URL normalization and dedup correctness

- preserve fetch URL vs dedup key correctness

2. Crawler configuration governance

- thresholds read from config at runtime

3. Sitemap and merged-output canonical consistency

4. Site-level aggregation quality

- dedup across pages
- weighted page-type scoring integrity

EXIT CRITERIA:

- stable pages_audited and dedup behavior across reruns
- no crawler regressions in edge URL cases

=======================================================================
PHASE 7 - API, SECURITY, DB, AND CONTRACT HARDENING
===================================================

OBJECTIVE:
Guarantee production-safe behavior at interfaces and persistence layers.

TASKS:

1. API contract checks

- request/response schema validation
- backward compatibility for adapter and schema paths

2. Security checks

- url validation hardening
- auth path validation

3. DB reliability

- repository operation coverage
- model integrity and migration-safe behavior

4. Failure behavior

- consistent error payloads and observability tags

EXIT CRITERIA:

- no critical API contract regressions
- no security regressions in URL/auth checks
- persistence operations pass integration tests

=======================================================================
PHASE 8 - OBSERVABILITY AND OPERATIONS READINESS
================================================

OBJECTIVE:
Enable fast diagnosis and trustworthy runtime operations.

TASKS:

1. Structured telemetry baseline

- request, engine, rule, enrichment, cache, and failure events

2. SLO dashboards and alerts

- success rate, timeout, degraded rate, precision drift

3. Correlation identifiers

- trace audit_id across services, enrichment, and reports

4. Incident playbook artifacts

- known-failure signatures and recovery actions

EXIT CRITERIA:

- operators can identify failure source in <= 5 minutes
- telemetry supports phase-level KPI attribution

=======================================================================
PHASE 9 - PRODUCT LAYER AND REPORTING USABILITY
================================================

OBJECTIVE:
Make results understandable and actionable for real users.

TASKS:

1. Frontend clarity

- score summary
- top prioritized fixes
- estimated improvement impact

2. Report exports

- shareable report and pdf-style output path

3. Explainability

- why issue triggered
- confidence and evidence context

4. Usability checks

- users understand recommendations quickly

EXIT CRITERIA:

- users can interpret key output in under 30 seconds
- report payload is consistent with API responses

=======================================================================
VALIDATION SEQUENCE (MANDATORY AFTER EACH PHASE)
================================================

1. Unit tests for touched modules
2. Strategic 10-site run
3. 50-site run
4. ACT subset run
5. KPI comparison (before vs after)
6. Publish phase delta summary

=======================================================================
RELEASE GATES AND ROLLBACK POLICY
=================================

Promote phase only if:

- precision >= 90%
- reliability >= 90%
- no critical regression in security/API contracts
- benchmark integrity checks pass

Rollback phase if:

- precision < 90%
- hidden benchmark contamination appears
- severe stability regression persists after one fix iteration

=======================================================================
FINAL ACCEPTANCE CRITERIA
=========================

System is READY only when all conditions hold:

- precision >= 90%
- recall >= 60% with controlled FP profile
- reliability >= 90%
- spa precision >= 90%
- spa recall >= 90%
- rag effectiveness >= 80%
- audit success rate >= 90%
- timeout rate <= 10%
- fast_mode_p95_time <= 10s (target band: 5s to 10s)
- fast_mode_usage >= 70%
- useful_issues_per_site >= 5
- fix_acceptance_rate >= 0.7
- outputs are clear and operationally useful

=======================================================================
READY TO LAUNCH GATE (MANDATORY)
================================

System can be declared READY TO LAUNCH only when all are true:

- at least 10 real users have completed testing and feedback is captured
- at least 2 paying users are actively using the product
- zero open critical bugs
- final acceptance criteria pass on 2 consecutive release candidates

=======================================================================
FINAL DIRECTIVE
===============

Do not optimize for vanity benchmarks.
Do optimize for real user trust, robust execution, and explainable value.

At every step, ask:

"Does this improve real production behavior and user outcomes?"

If not, do not implement.

=======================================================================
END OF PROMPT
=======================================================================
