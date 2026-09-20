# BEACON Mastery Architecture v3.0

## Production-Grade Accessibility Intelligence Engine

> **Status**: Production-ready core. Real-world verified against UK GDS Personas, TodoMVC, and W3C WAI-ARIA.
> **Last Updated**: September 2026 — Fully upgraded with Patchright headless automation, Alfa (Siteimprove ACT) & Guidepup adapters, ConsensusEngine cross-calibration, RemediationSandbox security gating, and SARIF 2.1.0 / EARL 1.0 exporters.

---

## 🏗️ 1. High-Level System Map

```
Developer / CI Tool
        │
        ▼
┌──────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend (v3.0)                     │
│  POST /audit │ POST /audit/stream (SSE) │ POST /rag │ GET /health │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Audit Runner (Orchestrator)                     │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │         SCAN MODE ROUTER                                    │  │
│  │  fast    ──► Static + Heuristics        (~5-10s, 1 page)    │  │
│  │  deep    ──► Browser + Multi-Engine     (~60-120s, ~12p)    │  │
│  │  max     ──► Deep + interaction/scroll  (~120-240s, ~25p)   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │  ADAPTIVE TOPOLOGY CONTROLLER (topology.py)                │  │
│  │  fingerprint: tag skeleton + semantic role structural hash │  │
│  │  early_stop: sample representative pages, skip saturated   │  │
│  └────────────────────────────────────────────────────────────┘  │
│                       │                                            │
│          ┌────────────┼──────────────────────┐                   │
│          ▼            ▼                       ▼                   │
│   ┌─────────────┐  ┌───────────────┐  ┌────────────────────┐    │
│   │Static Engine│  │Heuristics Eng.│  │ Browser Automation │    │
│   │(static_     │  │(heuristics.py)│  │ Patchright Driver  │    │
│   │ checks.py)  │  │Heuristics     │  │ + Camoufox/Playw't │    │
│   │ 77KB rules  │  │Adapter v2.1   │  │ Anti-Bot Detect    │    │
│   └─────────────┘  └───────────────┘  └────────────────────┘    │
│          │                                     │                  │
│          │              ┌──────────────────────┤                  │
│          ▼              ▼                      ▼                  │
│   ┌───────────────────────────────┐  ┌─────────────────────┐    │
│   │   Axe-core Engine [deep/max]   │  │ Alfa Engine [ACT]   │    │
│   │   axe-core 4.10 adapter       │  │ AlfaAdapter         │    │
│   └───────────────────────────────┘  └─────────────────────┘    │
│                 │                               │                 │
│                 ▼                               ▼                 │
│   ┌───────────────────────────────┐  ┌─────────────────────┐    │
│   │   IBM Equal Access Engine     │  │ Guidepup Runner     │    │
│   │   IBMAdapter (v3.1)           │  │ Screen Reader Test  │    │
│   └───────────────────────────────┘  └─────────────────────┘    │
│                 │                                                 │
│                 ▼                                                 │
│   ┌─────────────────────────────────────────────────────────┐     │
│   │        Consensus & Reconciliation Engine                │     │
│   │   Cross-calibrate findings, pin CSS selectors,          │     │
│   │   boost confidence on corroborated issues               │     │
│   └─────────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│           Lighthouse Enrichment Layer [deep/max only]            │
│                    [async, non-blocking]                          │
│                                                                   │
│  select_urls_for_lighthouse() ← ≤5 URLs: home→template→priority │
│                                                                   │
│  Per-URL runner (lighthouse_runner.py):                          │
│  ├─ Lighthouse CLI subprocess (headless Chrome)                  │
│  ├─ asyncio.Semaphore(2) — OOM protection                        │
│  ├─ Per-URL timeout: 90s  |  Global batch timeout: 300s         │
│  └─ 1 retry on network_unreachable / parse_error                │
│                                                                   │
│  Mapper (lighthouse_mapper.py):                                  │
│  ├─ Raw JSON → normalized BEACON findings_schema                 │
│  ├─ Score 0–100: <50→serious, 50–89→moderate, ≥90→drop          │
│  └─ Versioned via lighthouse_mapping.json (v1)                  │
│                                                                   │
│  Merge engine (lighthouse_enricher.py):                          │
│  ├─ Rule 1: BEACON+LH match → lighthouse_confirmed=True,         │
│  │          score<50 → severity upgrade (minor→moderate→serious) │
│  ├─ Rule 2: LH-only, score<50 → supplementary finding           │
│  ├─ Rule 3: LH-only, score 50–89 → additional_insight finding   │
│  ├─ Rule 4: LH-only, score≥90 → dropped silently                │
│  └─ Rule 5: BEACON findings NEVER deleted, suppressed, or       │
│             downgraded (no exceptions)                           │
└──────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Intelligence Layer                              │
│                                                                    │
│  normalize_all()  →  deduplicate()  →  apply_confidence_rules()  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              5-Signal Confidence Formula                      │ │
│  │  confidence = 0.35×source + 0.25×signal + 0.15×agreement   │ │
│  │             + 0.20×evidence + 0.05×user_impact (NEW)        │ │
│  │                                                               │ │
│  │  agreement: axe + static + ibm + heuristic corroboration     │ │
│  │  user_impact: missing-alt=1.0, focus-trap=1.0, jargon=0.5   │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                    │
│  _apply_precision_profile()   [12 profiles]                       │
│  ├─ balanced / high_precision / strict / ultra_strict             │
│  └─ per-rule confidence overrides + co-occurrence suppression     │
│                                                                    │
│  prioritize_issues()  ← NEW                                       │
│  ├─ priority_score = impact × frequency × visibility × confidence │
│  └─ Returns top-5 "fix first" ranked list with explanations       │
└──────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                 Remediation Layer (RAG + LLM)                      │
│                  [async, non-blocking]                             │
│                                                                    │
│  hybrid_retrieve()                                                 │
│  ├─ Vector ANN (ChromaDB cosine)                                  │
│  ├─ BM25 Okapi (cached index, built once)                        │
│  └─ Reciprocal Rank Fusion (RRF k=60)                            │
│                                                                    │
│  Contrast-Finder Integration (NEW)                                 │
│  └─ HSL binary search for nearest-passing color replacement       │
│                                                                    │
│  CrossEncoder reranker (ms-marco-MiniLM-L-6-v2)                  │
│  └─ MAX_CONTEXT_CHUNKS = 5  ← hard cap                           │
│                                                                    │
│  LLM: NVIDIA NIM → Llama 3.1 70B / Qwen2.5-Coder-32B-Instruct    │
│  ├─ Batched by WCAG criterion (60-80% cost reduction)             │
│  ├─ AccessGuru-style multimodal prompt patterns (NEW)              │
│  └─ Async enrichment: report returns instantly, AI streams later  │
└──────────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                   4-Tier Cache System                              │
│                                                                    │
│  Tier 1: Page Cache     (URL → result,     TTL 24h)              │
│  Tier 2: DOM Hash Cache (Structure → result, TTL 24h)            │
│  Tier 3: Fix Library    (pattern → fix,    persistent)           │
│  Tier 4: LLM Cache      (question → answer, persistent)          │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │  CACHE OBSERVABILITY  ← NEW  (GET /audit/cache/stats)        │ │
│  │  { "cache_hit_rates": {                                       │ │
│  │      "page": 0.80, "dom": 0.60,                              │ │
│  │      "llm":  0.90, "fix": 0.75 } }                          │ │
│  │                                                               │ │
│  │  Write Policy: Only fully successful (non-degraded) audits    │ │
│  │  are written to cache. No partial pipelines.                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                       │
                       ▼
              Developer / Client
              ├─ score: 74/100
              ├─ expected_score_after_fix: 92       ← NEW (Impact Projection)
              ├─ priority_ranking: [top 5 fixes]    ← NEW
              ├─ issues: [...]
              ├─ cognitive_mode: "experimental"     ← NEW
              ├─ degraded_mode: true                ← NEW (Failure Visibility)
                ├─ degraded_reason: "..."            ← NEW (Contracted reason)
                ├─ trust_level: "low|partial|full"   ← NEW (Operator trust tier)
                ├─ confidence_score: 0.55             ← NEW (0.0-1.0 reliability)
              ├─ skipped_components: ["playwright"] ← NEW
                ├─ site_topology: "multi_template"   ← NEW (Phase 20)
                ├─ templates_found: 6                ← NEW (Phase 20)
                ├─ urls_discovered: 47               ← NEW (Phase 20)
                ├─ site_failure_profile: {...}       ← NEW (dominant_failure etc.)
              ├─ quality_gates.max_mode_validation  ← NEW (phase execution proof)
              ├─ invariant_safe_score_applied       ← NEW (non-zero output guard)
              ├─ enrichment_status: "pending" (SSE)
              ├─ earl_report: { ... }               ← NEW (EARL 1.0 JSON-LD)
              └─ lighthouse_enrichment: {           ← NEW (Phase 21)
                   status, aggregate_scores,
                   merge_telemetry, per_url_results }
```

---

## 📦 2. Offline Knowledge Ingestion Pipeline (Phases 0–8)

| Phase      | Module            | What it Does                                                             |
| :--------- | :---------------- | :----------------------------------------------------------------------- |
| **P0**     | `config.py`       | 21 source silos defined (WCAG 2.2, ARIA, COGA, MDN, WebAIM, Deque, etc.) |
| **P1**     | `crawl.py`        | Async BFS crawl via crawl4ai; MD5-slug file naming; skip-if-cached       |
| **P1b**    | `axe_parser.py`   | Parses local axe-core `lib/rules/*.json` into chunks                     |
| **P1c**    | `local_corpus.py` | Ingests local markdown/JSON corpus (`corpus/wcag-aaa-web-design`)        |
| **P2**     | `extract.py`      | BS4 semantic extraction — KEEP/STRIP tag whitelists                      |
| **P3**     | `chunk.py`        | Tiktoken-bounded chunking (400 tokens, 40 overlap, heading-aware)        |
| **P4**     | `filter.py`       | 33-term relevance gate + noise pattern rejection                         |
| **P5**     | `dedup.py`        | MD5 exact-match + Jaccard trigram near-dedup (threshold=0.85)            |
| **P6**     | `tag.py`          | WCAG SC extraction, issue_type, user_impact, severity tagging            |
| **P7**     | `embed.py`        | `all-MiniLM-L6-v2` via thread-safe singleton `model_registry`            |
| **P8**     | `store.py`        | ChromaDB batched upsert (HNSW cosine, 100/batch)                         |
| **Verify** | `verify.py`       | Confirms 86/86 WCAG 2.2 SC coverage in the vector store                  |

**Current state**: 25,346 chunks, 86/86 SC coverage confirmed. Includes WCAG 2.2 Techniques, ARIA patterns, and MDN reference material. ✅

---

## ⚡ 3. YC-Level Performance Features

| Feature                                 | Implementation                                                                           | Status |
| :-------------------------------------- | :--------------------------------------------------------------------------------------- | :----- |
| **Minimal scan mode**                   | `scan_mode="minimal"` disables browser/RAG/cognitive                                     | ✅     |
| **Fast vs Deep modes**                  | `curl_cffi` fetch path vs browser-rendered path (Camoufox-backed)                        | ✅     |
| **Max exploration mode**                | Deep + SPA interaction/scroll exploration + auth fallback                                | ✅     |
| **Async SSE streaming**                 | Report instant; AI enrichment streams later                                              | ✅     |
| **Global backpressure**                 | Auto-degrade deep→fast at >20 concurrent audits                                          | ✅     |
| **LLM batching**                        | Group issues by WCAG criterion → 1 call                                                  | ✅     |
| **4-tier caching**                      | Page + DOM + Fix + LLM caches                                                            | ✅     |
| **Cache observability**                 | Hit/miss rates per tier at `/audit/cache/stats`                                          | ✅     |
| **RAG context limit**                   | `MAX_CONTEXT_CHUNKS = 5` hard cap                                                        | ✅     |
| **BM25 index cache**                    | Built once at startup, never rebuilt                                                     | ✅     |
| **Browser circuit breaker**             | Semaphore(3) + timeout guards on browser render pipeline                                 | ✅     |
| **Centralized mode profiles**           | `SCAN_MODE_CONFIG` in `app/config.py`                                                    | ✅     |
| **Global scan safety caps**             | `MAX_SCAN_GLOBAL_CAP=80`, `MAX_CONCURRENT_SITE_AUDITS=3`                                 | ✅     |
| **Dashboard mode budgets**              | deep=12 pages, max=25 pages                                                              | ✅     |
| **App-shell structural guardrails**     | Suppresses premature landmark noise on React/Next bootstrap shells                       | ✅     |
| **Access-limited normalization**        | Converts blocked/partial fetch states into explicit availability findings                | ✅     |
| **Lighthouse enrichment pipeline**      | Headless Chrome signal layer for deep/max; supplements, never overwrites BEACON          | ✅ NEW |
| **Lighthouse URL selection**            | Smart ≤5-URL selector: homepage → template-diverse → priority pages                      | ✅ NEW |
| **Lighthouse merge engine**             | 5-rule deterministic merge; BEACON data is immutable primary source                      | ✅ NEW |
| **Lighthouse per-URL cache**            | In-process TTL cache (1h) keyed on url+lh_version+mapping_version                        | ✅ NEW |
| **Lighthouse batch abort**              | ChromeLaunchError propagates immediately; aborts full batch on infra failure             | ✅ NEW |
| **Lighthouse mode gate**                | Enrichment gated to `deep`/`max` only; `fast` continues unchanged                        | ✅ NEW |
| **Topology-aware site audits**          | `topology_detector.py` classifies crawl shape before page-selection                      | ✅     |
| **Centralized max-page resolver**       | `resolve_max_pages()` consumes mode + topology budgets                                   | ✅     |
| **Degraded-mode E2 contract**           | `degraded_mode`, `degraded_reason`, and engine contract fields always emitted            | ✅     |
| **Topology observability in dashboard** | Surfaces `site_topology`, `templates_found`, `urls_discovered` in scan records           | ✅     |
| **Canonical failure normalization**     | `failure_taxonomy.normalize_failure()` used as single reason normalizer                  | ✅     |
| **Adaptive failure routing**            | `crawl_orchestrator` action routing (`slow_down`, `static_only`, `stop`) by failure type | ✅     |
| **Site-level failure profile**          | `site_failure_profile` with `dominant_failure` + weighted distribution + site confidence | ✅     |
| **Domain preflight cache**              | Run-scoped domain cache avoids repeated HEAD checks across pages                         | ✅     |
| **robots.txt Disallow enforcement**     | `parse_robots_disallow()` + `is_disallowed()` wired into BFS + sitemap discovery         | ✅     |
| **Sitemap recursion hard cap**          | Depth cap prevents runaway sitemapindex recursion                                        | ✅     |

---

## ✅ 3.1 Reliability Guardrails (2026-04 Hotfix)

- **Hard output invariants**: audited results cannot return zero-score + zero-issue payloads.
- **Safe score fallback**: if pages were audited and score is invalid/non-positive, a bounded non-zero score is applied.
- **Enrichment isolation**: base audit payload stays valid even if async enrichment fails later.
- **Site-result repairs**: single-page and aggregate payloads are repaired if page counts or site_score become invalid.
- **Stale-cache rejection**: poisoned legacy cache entries are discarded and recomputed (URL cache + DOM cache).

## ✅ 3.2 Detector Robustness Hardening (2026-04-12)

- **Shell-aware structural logic**: app-shell pages are identified early to prevent false landmark findings before hydration.
- **Main-surrogate tolerance**: component layouts using `div#main`-style surrogates avoid invalid "missing main" noise.
- **ARIA role-token enforcement**: mixed valid/invalid role token lists now fail deterministically.
- **Duplicate role-token enforcement**: duplicate role tokens are flagged as `aria-roles` violations.
- **Blocked-page handling**: access-limited pages are normalized into availability findings, not inflated structural findings.

## ✅ 3.3 Production Scan Profiles and Caps (2026-04-14)

All site-scan limits are centralized and consumed by the runner and dashboard paths.

| Mode | max_pages | crawl_cap | bfs_depth | bfs_pages | dom_pages | stage1_timeout_s | stage2_timeout_s | global_sla_s | concurrency |
| :--- | --------: | --------: | --------: | --------: | --------: | ---------------: | ---------------: | -----------: | ----------: |
| fast |         1 |        10 |         1 |        10 |         0 |               12 |                4 |           35 |           5 |
| deep |        12 |        30 |         3 |        30 |         0 |               25 |               12 |          120 |           3 |
| max  |        25 |        70 |         4 |        60 |        15 |               40 |               18 |          240 |           2 |

Global hard caps:

- `MAX_SCAN_GLOBAL_CAP = 80`
- `MAX_CONCURRENT_SITE_AUDITS = 3`

Dashboard hard budgets:

- `DASHBOARD_DEEP_SCAN_MAX_PAGES = 12`
- `DASHBOARD_MAX_SCAN_MAX_PAGES = 25`

Behavioral guarantees from these caps:

- Fast mode remains responsive (single-page, low-latency feedback).
- Deep mode stays in a predictable user-facing range.
- Max mode scales breadth without unconstrained concurrency.
- API response shape is unchanged; only operational limits are standardized.

## ✅ 3.4 Topology-Aware Site Audits (2026-04-20)

- **Topology classifier**: `app/services/topology_detector.py` identifies crawl morphology as `single_page`, `thin`, `deep_uniform`, `paginated`, or `multi_template` before final URL selection.
- **Adaptive page budgeting**: `app/config.py::resolve_max_pages()` centralizes page caps and removes hardcoded `max_pages` literals from runtime code paths.
- **Persistent topology telemetry**: Alembic migration `81e9864e53a7_phase20_topology_columns.py` adds `site_topology`, `templates_found`, and `urls_discovered` to scan persistence.
- **Dashboard visibility**: topology + discovered/scanned page metrics are exposed to client dashboards for audit explainability.
- **Contract hardening under failures**: access-limited and unreachable targets return `degraded_mode=True` with non-empty `degraded_reason` and complete E2 engine contract fields.

## ✅ 3.5 Crawler Stack v3 Modernization (Phases 13-17)

- **HTTP layer replacement**: `curl_cffi.AsyncSession` is now the primary HTTP client for crawler/audit runtime paths (`httpx` runtime usage removed).
- **Browser stealth hardening**: Camoufox-backed browser sessions are used for dynamic crawling and browser-driven scan paths, with graceful backend fallback only when optional dependencies are unavailable.
- **Canonical failure taxonomy**: `DegradedReason` + `normalize_failure()` now govern degraded reason mapping across runners, crawlers, persistence, and dashboard payload normalization.
- **Adaptive crawl strategy**: failure-driven routing supports `reduce_concurrency`, `disable_browser_engines` (static-only continuation), and immediate stop on non-recoverable failure classes.
- **Domain-level preflight deduplication**: run-scoped preflight cache avoids repeated domain checks during multi-page site audits.
- **Confidence gating contract**: low-confidence scans can suppress numeric score display (`score=null` when confidence floor is not met) while preserving explicit degraded metadata.

---

## 🧠 4. Confidence Engine (5-Signal Formula)

```
confidence = (
    0.35 × source_reliability       # axe=0.95, static=0.90, heuristic=0.50
  + 0.25 × signal_strength          # violation=0.9, needs-review=0.4
  + 0.15 × cross_engine_agreement   # 3 engines=1.0, 2=0.7, 1=0.3
  + 0.20 × evidence_quality         # html_snippet + evidence + reproducibility
  + 0.05 × user_impact              # missing-alt=1.0, focus-trap=1.0 (NEW)
)
```

Then calibrated by rule_type: `hard +0.03`, `visual -0.02`, `contextual -0.07`

**Precision gating (12 profiles)**:

- `balanced`: min_conf=0.55, includes needs-review
- `high_precision`: min_conf=0.75, adaptive thresholds by rule type
- `strict`: excludes 4 over-reported page-level rules → -92.5% false positives
- _(+ 9 more specialist profiles)_

**Confidence Explainability**: Instead of just emitting a raw float, the engine exposes a human-readable `confidence_reason` as a receipt of its trust level:

> _"Confirmed by 3+ engines (axe-core, static, heuristic) with strong code evidence."_

---

## 🎯 5. Issue Prioritization Layer (NEW)

```python
priority_score = impact × frequency × visibility × confidence × effort

# impact:     critical=4, serious=3, moderate=2, minor=1
# frequency:  affected_count (capped at 10)
# visibility: hard=1.0, visual=0.8, contextual=0.6
# confidence: from 5-signal formula above
# effort:     low=1.2 (boost quick wins), medium=1.0, high=0.6 (moderate/minor only)
#
# COMPLIANCE GUARD: critical/serious issues are NEVER demoted by effort.
# max(effort, 1.0) is enforced so compliance buyers see them regardless of difficulty.
```

Output: `priority_ranking` — top-5 rules to fix first, with:

- Total score, affected_count, severity, domain
- Human-readable `fix_first_reason` explanation

> **User Layer Translation (Why This Matters)**: Every recorded issue now maps to an `impact_summary` field that translates code into human friction for Product Managers & Designers to understand severity:
> _"Screen reader users may miss the meaning of this meaningful image, or have to listen to the filename."_

---

## 🔎 6. Cognitive Engine (Experimental)

> **Status**: Isolated to `max` mode in site-scan orchestration. Single-page `/audit` deep runs may still include cognitive checks when explicitly enabled. Does not contribute to core score without explicit flag.
> API response includes `cognitive_mode: "experimental"` to signal this to clients.

Checks: Flesch-Kincaid readability, Gunning Fog, jargon density, CTA clarity,
form usability, nav complexity, error message quality (WCAG COGA-aligned).

**Risk**: Subjective, higher false-positive rate. Keep separate from hard violations.

---

## 📊 7. Benchmark & Evaluation

### Multi-Dataset Benchmark Baseline (v2.8)

| Dataset         | Source                      | Scope                                  | Latest F1/Recall |
| :-------------- | :-------------------------- | :------------------------------------- | :--------------- |
| **ACT Full**    | W3C ACT Rules               | ~80 rules (pass/fail HTML fixtures)    | 0.94 (Full)      |
| **GenA11y**     | seal-hub/GenA11y            | 148 labelled HTML pages (37 SC)        | 0.82 (Recall)    |
| **AccessGuru**  | DARUS/AccessGuru            | 3,500+ real-world violations (Semantic) | 0.58 (Baseline)  |
| **A11YBench**   | LLM4APR/A11YBench           | 60 real GitHub projects (IBM-grounded) | 0.77 (Agreement) |
| **WebAIM Six**  | WebAIM Million 2026         | Top 6 common failures (Regression)      | 1.00 (Pass)      |

Artifacts: `evaluation/results/*_baseline_*.json`

### Real-World Production Benchmark (10 sites, fast + deep)

| Mode    | Successful Sites | Avg Score | Avg Time | P95 Time | Alignment (Applicable Only) | Access-Limited | Suppression Warnings |
| :------ | :--------------: | :-------: | :------: | :------: | :-------------------------: | :------------: | :------------------: |
| Fast    |      10/10       |   77.38   |  1.331s  |  2.56s   |        33.33% (2/6)         |       4        |          0           |
| Deep    |      10/10       |   84.75   | 11.844s  |  27.86s  |        40.00% (4/10)        |       0        |          0           |
| Overall |   20/20 audits   |     -     |    -     |    -     |        37.50% (6/16)        |       4        |          0           |

Artifact: `evaluation/production_benchmark_results.json`

### Real-Site All-Modes Validation (Phase 20)

30-run suite (10 sites × fast/deep/max):

| Mode      |   PASS | DEGRADED |  FAIL |
| :-------- | -----: | -------: | ----: |
| fast      |      8 |        2 |     0 |
| deep      |      9 |        1 |     0 |
| max       |      9 |        1 |     0 |
| **Total** | **26** |    **4** | **0** |

Expected degraded runs were external conditions (`nab.org.in` unreachable on test network; `tiss.edu` fast-mode bot block). No internal pipeline regressions were observed.

Artifact: `phase20_all_modes_results.json`

### Lighthouse Enrichment Integration — Live 10-Site Validation (Phase 21)

| URL Target          | BEACON Issues |   LH Mapped   | Merged Total | New Insights Added | Time Elapsed |
| :------------------ | :-----------: | :-----------: | :----------: | :----------------: | :----------: |
| nab.org.in          |       0       |   ERR (DNS)   |      0       |         —          |    29.5s     |
| sightsavers.in      |       1       |       7       |      8       |         +7         |    81.4s     |
| tiss.edu            |       1       |  ERR (Parse)  |      1       |         —          |    24.6s     |
| varsity.zerodha.com |       7       |       5       |      12      |         +5         |    63.9s     |
| cleartax.in         |      13       |       6       |      19      |         +6         |    84.9s     |
| zerodha.com         |       6       |       6       |      12      |         +6         |    61.2s     |
| scholarships.gov.in |       1       | ERR (Timeout) |      1       |         —          |    91.3s     |
| practo.com          |       9       |       8       |      17      |         +8         |    64.1s     |
| groww.in            |       8       |       6       |      14      |         +6         |    80.3s     |
| diksha.gov.in       |      12       |       7       |      19      |         +7         |    71.9s     |

**Key observations:**

- **Failsafes proven**: `scholarships.gov.in` hit the 90s per-URL timeout lock at 91.3s and bailed cleanly — zero crash, BEACON baseline preserved.
- **DNS/unreachable** (`nab.org.in`) and **parse failures** (`tiss.edu`) triggered 1-retry logic, failed safely, and preserved BEACON-only output.
- **Coverage uplift**: Average +30–50% new findings added on all 7 reachable sites with Lighthouse available.
- **Zero data loss**: `cleartax.in` returned 13 BEACON findings; after merge total became 19. **Not a single BEACON finding was deleted or overwritten.**
- **Concurrency**: Semaphore(2), pairs of 2 concurrent Chrome instances, ran without OOM events on local hardware.

Artifact: `test_comparison.py` (live comparison script)

### Rollout-Gate Result (Latest Run)

- Runtime success rate: **100%**
- False zero-score audits: **0**
- Suppression warnings: **0**
- Fast P95 latency gate ($\leq 3.5s$): **PASS**
- Deep P95 latency gate ($< 60s$): **PASS**
- Fast average score gate (70-95): **PASS**
- Fast average confidence gate ($> 0.70$): **PASS**
- Expectation alignment gate: **Advisory only** (non-blocking, evaluated on applicable non-access-limited audits)

**Verdict**: All blocking checks passed. Production profile is rollout-ready.

### Deterministic Site Archetype Validation

- New validator: `evaluation/validate_site_archetypes.py`
- Latest result: **10/10 passed**
- Coverage includes:
  - React and Next.js app-shell bootstrap pages
  - dashboard nav-without-main structures
  - component-level `div#main` surrogates
  - ARIA unknown attributes and mixed/duplicate role token lists
  - semantic overuse and SVG naming checks

Artifact: `evaluation/site_archetype_validation_results.json`

---

## 🛡️ 8. LLM Fallback & Degradation Strategy

When the NVIDIA NIM LLM endpoint is unreachable:

1. **Fix Cache** checked first — previously-validated LLM fixes are reused (85% success gate)
2. **Rule-Based Fallback** (`RULE_BASED_FALLBACK_FIXES`) — 10 hand-written static remediation packets for the most common rules (missing-alt, missing-label, color-contrast, etc.)
3. **Generic Fallback** — returns WCAG criterion reference with `needs_manual_review = true`

The report is **never empty** during LLM outage. Each issue is tagged with `_enrichment_source: "llm" | "rule_fallback" | "cache"` for full transparency.

---

## 🗺️ 9. Strategic Roadmap (Do AFTER product-market fit)

> [!WARNING]
> **YC Advice**: Ship current system. Get users. Measure pain. Then expand.
> Do NOT build Vision/GraphRAG/Agentic before confirming what users actually need.

| Feature                                                        | Why                                                                       | When                    |
| :------------------------------------------------------------- | :------------------------------------------------------------------------ | :---------------------- |
| **Lighthouse CI enrichment**                                   | Runtime JS coverage boost (+30–50% new findings on live sites)            | ✅ **Shipped Phase 21** |
| Lighthouse Dashboard Badges                                    | Surface `lighthouse_confirmed` and `lighthouse_insight` visually to users | Next sprint             |
| Vision Layer (Playwright screenshot + Vision LLM)              | Catches gradient/image contrast failures                                  | After PMF               |
| GraphRAG (WCAG ↔ ARIA ↔ Axe knowledge graph)                   | Deep reasoning across guidelines                                          | After PMF               |
| Agentic Fix Loop (propose → sandbox → validate → self-correct) | Guarantees 100% valid fixes                                               | After PMF               |
| Multi-page Journey Audits                                      | Catches focus-management issues across transitions                        | After PMF               |
| Framework-Aware Fixes (React/Vue/Next.js idioms)               | Developer adoption booster                                                | Near-term               |
| Quantized local models (Ollama/Llama-3-8B)                     | No cloud API dependency                                                   | Near-term               |
| WCAG 3.0 Bronze/Silver/Gold scoring                            | Future compliance standard                                                | Near-term               |

---

## 📂 10. Full Tech Stack

| Layer               | Technology                                                                                       |
| :------------------ | :----------------------------------------------------------------------------------------------- |
| Language            | Python 3.11+                                                                                     |
| API Framework       | FastAPI + Pydantic v2                                                                            |
| LLM                 | NVIDIA NIM → Llama 3.1 70B (OpenAI-compatible)                                                   |
| Embedding           | sentence-transformers `all-MiniLM-L6-v2`                                                         |
| Reranker            | `cross-encoder/ms-marco-MiniLM-L-6-v2`                                                           |
| Vector Store        | ChromaDB (HNSW, cosine, 25,346 chunks)                                                           |
| Browser Engine      | Playwright (Chromium, async, semaphore-gated)                                                    |
| Crawler             | crawl4ai (AsyncWebCrawler)                                                                       |
| Caching             | In-process JSON (page/DOM) + file-locking, Fix Library (persistent)                              |
| Lexical Search      | BM25Okapi (rank-bm25)                                                                            |
| HTTP Runtime Client | `curl_cffi` (`AsyncSession`, Chrome impersonation)                                               |
| Lighthouse Engine   | Google Lighthouse CLI 10.x (headless Chrome, subprocess, semaphore-gated)                        |
| Lighthouse Mapping  | `app/data/lighthouse_mapping.json` (versioned, v1)                                               |
| Database            | Supabase (PostgreSQL) + RLS + realtime (`supabase/supabase_schema.sql`) |
| Browser Runtime     | Camoufox-backed browser sessions (`camoufox/firefox`) with Playwright-compatible automation APIs |
| Standards           | WCAG 2.2 (86 SC), WAI-ARIA 1.2, ACT Rules, COGA, Lighthouse Accessibility Audits                 |

---

## 🕰️ 11. Architecture Evolution (Earlier Versions → Current)

This section preserves prior architecture eras so teams can reason about historical behavior and migration context.

| Version / Phase Window               | Primary Focus                                                    | Stack Characteristics                                                                                               | Current Status                     |
| :----------------------------------- | :--------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------ | :--------------------------------- |
| **v1.x (Phases 0-8)**                | Knowledge ingestion + retrieval base                             | Crawl/extract/chunk/tag/embed/store pipeline; WCAG corpus foundation                                                | Historical baseline                |
| **v2.0-v2.2 (Phases 9-12)**          | Scoring integrity + confidence + suppression hardening           | Trust tiers, invariant protection, precision profiles, anti-zero-score guards                                       | Shipped, retained                  |
| **v2.3 (Phases 13-17 plan)**         | Failure normalization + crawler resilience redesign              | Canonical degraded taxonomy, adaptive crawl strategy, preflight/domain intelligence model                           | Substantially shipped (v3 runtime) |
| **v2.4 (Phase 20)**                  | Topology-aware site auditing + dashboard observability           | `topology_detector`, centralized page budgeting, degraded E2 contract, topology telemetry columns                   | Shipped                            |
| **v2.5 (Phase 21 + reconciliation)** | Lighthouse enrichment + crawler stack v3 documentation alignment | Deterministic Lighthouse merge + modern crawler runtime (`curl_cffi` + Camoufox) + historical compatibility mapping | Shipped                            |
| **v2.8 (Current)**                   | Phase 1+2 External Resource Integration            | IBM Engine 6, Contrast-Finder, EARL 1.0, and Multi-Dataset Benchmarking (GenA11y, AccessGuru, A11YBench)            | **Active**                         |

### Legacy Compatibility Notes

- Legacy degraded reason aliases (for older payloads) are still normalized into canonical `DegradedReason` values.
- Historical dashboard records remain queryable; normalization happens at repository/API boundaries.
- Earlier architecture behaviors are intentionally documented here, but runtime contracts and operational guidance should follow v2.5 sections above.

---

## 🧩 12. Scrawl v3 Reconciliation Snapshot

Source of truth cross-check: `docs/plans/completed/scrawl_update.md` vs implemented architecture/runtime.

| Scrawl v3 Theme                                       | Reconciled in Architecture v2.5                                           | Status  |
| :---------------------------------------------------- | :------------------------------------------------------------------------ | :------ |
| Direct stack swap (`httpx` → `curl_cffi`)             | Documented in Sections 3.5 and 10                                         | ✅      |
| Browser hardening (`Camoufox`)                        | Reflected in system map and tech stack                                    | ✅      |
| Canonical failure normalization                       | Reflected via `DegradedReason`/`normalize_failure` architecture contracts | ✅      |
| Adaptive crawl routing by failure type                | Included as production reliability behavior                               | ✅      |
| Domain-level preflight caching                        | Included in reliability/crawler modernization section                     | ✅      |
| robots.txt disallow enforcement + sitemap safety caps | Included in feature matrix and v3 section                                 | ✅      |
| Site-level failure profile / confidence surfacing     | Included in client payload and feature matrix                             | ✅      |
| Forward-learning system (Phase 18+)                   | Captured as future roadmap, not current runtime guarantee                 | Planned |
