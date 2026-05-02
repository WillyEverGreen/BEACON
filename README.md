# 🔦 BEACON (formerly TSEC Legal AI) — Accessibility Intelligence Engine

<div align="center">

![BEACON Logo](assets/beacon.png)

**Production-grade web accessibility auditing with multi-engine scanning, AI-powered remediation, and Lighthouse enrichment.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-3.x-009688.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-15-black.svg)](https://nextjs.org/)
[![WCAG 2.2](https://img.shields.io/badge/WCAG-2.2%20A%2FAA-brightgreen.svg)](https://www.w3.org/TR/WCAG22/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![ACT F1](https://img.shields.io/badge/ACT%20F1-1.00-success.svg)](#act-benchmark)

</div>

---

## 🚀 What is BEACON?

BEACON is an accessibility intelligence platform that helps teams:

- **Detect** issues across entire websites — not just single pages
- **Prioritize** the most critical problems by severity and confidence score
- **Fix** them faster with actionable, WCAG-grounded remediation suggestions

> Built to move from raw violation reports → fixable, prioritized insights.

---

## 🎯 Who is this for?

- **Frontend developers** who need clear, fix-ready accessibility findings
- **QA teams** running automated audits across large site surfaces
- **Accessibility engineers** who need WCAG 2.2 coverage tracking and evidence
- **Product teams** working toward WCAG A/AA compliance

---

## ⚡ Example Output

```json
{
  "issue": "Image missing alt text",
  "wcag_criterion": "1.1.1 Non-text Content",
  "severity": "serious",
  "confidence": 0.92,
  "fix": "Add a descriptive alt attribute, e.g. alt=\"Company logo\"",
  "source": "axe-core",
  "lighthouse_confirmed": true
}
```

---

## ✨ Why BEACON?

Most accessibility tools give you a **list of rule violations**.
BEACON gives you **actionable intelligence**.

| | Traditional Tools | BEACON |
|---|---|---|
| Detection | Single engine, static rules | 5 parallel engines (static + browser + cognitive) |
| Scope | Page-level only | Full site crawl with topology detection |
| Fix guidance | Generic rule descriptions | AI-grounded fixes via WCAG 2.2 RAG |
| Signal quality | Raw violations | Deduplicated, confidence-scored, prioritized findings |
| Enrichment | None | Google Lighthouse fusion (deterministic merge) |
| Reliability | Silent failures common | Graceful degradation with explicit status contracts |

---

## 🔥 Key Features

- 🕷️ **Multi-Engine Scanning** — static, heuristic, browser-based (Camoufox), axe-core, and cognitive layers run in parallel
- 🌐 **Intelligent Site Crawling** — Sitemap, BFS, and DOM crawlers auto-discover pages and detect site topology before auditing
- 🤖 **AI-Powered Fix Suggestions** — hybrid BM25 + vector RAG retrieval grounded in WCAG 2.2, ARIA APG, COGA, and WebAIM
- 🏮 **Lighthouse Enrichment** — deterministic 5-rule merge pipeline adds Google Lighthouse signal without ever deleting BEACON findings
- 📡 **Real-time SSE Streaming** — live audit progress via Server-Sent Events
- 🔐 **API-key RBAC** — viewer / auditor / admin roles enforced at middleware level
- 📊 **Full Observability** — Prometheus metrics, structured telemetry, and Lighthouse CI self-audit on every push
- 🗄️ **Persistent Scan History** — PostgreSQL-backed longitudinal tracking via SQLAlchemy + Alembic
- 🖥️ **Next.js Dashboard** — interactive UI surfacing topology labels, scan metrics, and issue breakdowns

---

## 🧠 What Makes BEACON Different?

### 1. Multi-Engine Fusion

BEACON does not rely on a single detection strategy. Five engines run concurrently and their outputs are normalized, deduplicated, confidence-scored, and prioritized before the response is assembled. This reduces false positives, improves coverage, and ensures every finding has a clear source.

### 2. RAG-Based Remediation — Not Generic AI

Suggested fixes are grounded in a curated knowledge base ingested from:
- WCAG 2.2 (A/AA criteria)
- ARIA Authoring Practices Guide (APG)
- Cognitive Accessibility Guidelines (COGA)
- WebAIM articles and MDN references
- axe-core rule documentation

A self-learning Fix Library caches validated fixes and gates acceptance at an 85% success rate. Fixes are not hallucinated — they are retrieved and validated.

### 3. Lighthouse + BEACON Hybrid — Additive, Never Destructive

Lighthouse signals are merged through a 5-rule deterministic engine:

| Rule | Condition | Action |
|---|---|---|
| 1 | BEACON + Lighthouse confirm same `rule_id` | Set `lighthouse_confirmed=True`. If LH score < 50: upgrade severity. |
| 2 | Lighthouse-only, score < 50 | Add as `source=lighthouse`, `confidence=supplementary`. |
| 3 | Lighthouse-only, score 50–89 | Add as `source=lighthouse`, `confidence=additional_insight`. |
| 4 | Lighthouse-only, score ≥ 90 | Drop silently. |
| 5 | All BEACON findings | **NEVER deleted, suppressed, or downgraded. No exceptions.** |

Result: +30–50% additional finding coverage on reachable sites with zero regression risk.

### 4. Site-Level Intelligence

BEACON classifies every crawl before page selection using topology detection:

| Topology | Description |
|---|---|
| `single_page` | SPA or minimal surface |
| `thin` | Few unique templates |
| `deep_uniform` | Many pages, one template |
| `paginated` | List/index structure |
| `multi_template` | Rich multi-section site |

Topology influences page budget allocation, ensuring template-diverse coverage rather than redundant page sampling.

### 5. Production-Grade Reliability

Every failure path has an explicit contract:
- `ChromeLaunchError` → immediate batch abort, remaining URLs marked `failed`
- DNS failures → 1 retry, then graceful bail, BEACON-only output preserved
- Per-URL timeout (90 s) and global timeout (300 s) are independent hard safety nets
- Stale/invalid cached payloads are automatically discarded and recomputed
- Issues payload is always list-normalised before serialisation
- Pages cannot return a non-positive score without a safe repair pass

---

## 🏗️ Architecture

```mermaid
flowchart LR
    C[Client] --> API[FastAPI API Layer]
    API --> AUTH[API Key RBAC]
    API --> RUN[Audit Runner]

    RUN --> FETCH[Fetch & Render]
    RUN --> ENGINES[Static · Heuristic · Browser · Axe · Cognitive]
    RUN --> SCORE[Normalize · Dedup · Confidence · Prioritize]
    RUN --> ENRICH[Async Enrichment — LLM + Fix Cache]
    RUN --> LH[Lighthouse Enrichment — deep/max only]
    RUN --> CRAWL[Crawlers: Sitemap · BFS · DOM]
    RUN --> SITE[Site Aggregation & Parallel Audit]

    LH --> LH_RUNNER[lighthouse_runner.py]
    LH --> LH_MAPPER[lighthouse_mapper.py]
    LH --> LH_MERGER[lighthouse_enricher.py]

    ENRICH --> RAG[Hybrid Retrieval — BM25 + Vector]
    RAG --> VDB[(ChromaDB)]

    API --> DB[(PostgreSQL / Neon — SQLAlchemy + Alembic)]
    API --> OBS[Telemetry · Alerts · Prometheus Metrics]
```

### Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI 3.x + Uvicorn |
| Dashboard | Next.js 15 (TypeScript) |
| Browser Automation | Camoufox (primary) · Playwright (fallback) |
| Accessibility Engines | axe-core · custom static + heuristic engines |
| Lighthouse Enrichment | Lighthouse CLI (Node.js 18+) |
| Vector Store | ChromaDB |
| LLM | Featherless API (model configurable) |
| Database | PostgreSQL (Neon) via SQLAlchemy + Alembic |
| Auth | API-key RBAC middleware |
| Observability | Prometheus + custom sliding telemetry window |

---

## 🔎 Scan Modes

| Mode | Description | Engines Activated |
|:---|:---|:---|
| `minimal` | Quickest deterministic baseline | Static + Heuristic |
| `fast` | Rapid production checks (~15 s) | Static + Heuristic |
| `deep` | Comprehensive page analysis (~120 s) | Static + Heuristic + Browser + axe-core + Lighthouse enrichment |
| `max` | Deepest interactive exploration (~240 s) | All `deep` engines + Interaction/Scroll + Cognitive + Lighthouse enrichment |

### Production Scan Profiles

All limits are centralised in `app/config.py`. No hardcoded `max_pages` anywhere in application code.

| Mode | max_pages | crawl_cap | bfs_depth | stage1_timeout | stage2_timeout | global SLA | concurrency |
|:---|---:|---:|---:|---:|---:|---:|---:|
| `fast` | 1 | 10 | 1 | 12 s | 4 s | 35 s | 5 |
| `deep` | 12 | 30 | 3 | 25 s | 12 s | 120 s | 3 |
| `max` | 25 | 70 | 4 | 40 s | 18 s | 240 s | 2 |

Global safety caps:

```
MAX_SCAN_GLOBAL_CAP        = 80
MAX_CONCURRENT_SITE_AUDITS = 3
```

---

## 📈 Benchmark Results

### Lighthouse Enrichment — Live 10-Site Integration Test

| URL Target | BEACON Issues | LH Mapped | Merged Total | New Insights | Time |
|---|:---:|:---:|:---:|:---:|:---:|
| sightsavers.in | 1 | 7 | **8** | +7 | 81.4 s |
| varsity.zerodha.com | 7 | 5 | **12** | +5 | 63.9 s |
| cleartax.in | 13 | 6 | **19** | +6 | 84.9 s |
| zerodha.com | 6 | 6 | **12** | +6 | 61.2 s |
| practo.com | 9 | 8 | **17** | +8 | 64.1 s |
| groww.in | 8 | 6 | **14** | +6 | 80.3 s |
| diksha.gov.in | 12 | 7 | **19** | +7 | 71.9 s |

**7/10 Lighthouse runs successful** · Average **+30–50% finding uplift** · **0 BEACON findings deleted or overwritten**

---

### All-Modes Production Validation (10 sites × fast / deep / max)

| Mode | PASS | DEGRADED | FAIL |
|---|:---:|:---:|:---:|
| `fast` | 8 | 2 | **0** |
| `deep` | 9 | 1 | **0** |
| `max` | 9 | 1 | **0** |
| **Total** | **26** | **4** | **0** |

> The 4 DEGRADED results are expected: `nab.org.in` is unreachable from this network; `tiss.edu` blocks fast-mode HTTP but succeeds under `deep` and `max`.

---

### ACT Benchmark

| Metric | Result |
|---|---|
| Cases evaluated | 23 |
| True Positives | 38 |
| False Positives | **0** |
| False Negatives | **0** |
| Precision / Recall / F1 | **1.00 / 1.00 / 1.00** |

---

### WCAG 2.2 Coverage

BEACON currently implements **55.2% (32/58)** of WCAG 2.2 A/AA criteria.
See [`ACCESSIBILITY_COVERAGE.md`](docs/architecture/ACCESSIBILITY_COVERAGE.md) for the full criterion-level breakdown.

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Purpose |
|---|---|
| Python 3.10+ | Core API runtime |
| Node.js 18+ | Lighthouse enrichment + Next.js dashboard |
| PostgreSQL | Scan history storage (or use Neon cloud) |

Install optional browser runtimes — required for `deep` / `max` scans:

```bash
# Lighthouse CLI (global)
npm install -g lighthouse

# Camoufox browser binary (one-time, ~200 MB)
python -m camoufox fetch

# Optional: GeoIP database for bot-wall bypass realism
python -m camoufox fetch --geoip
```

> **Why Camoufox?** Camoufox ships without a bundled browser binary to keep the PyPI package small. The first `deep` or `max` scan will fail with `camoufox: browser binary not found` unless you run this command. Re-run after upgrading Camoufox to a new major release.

---

### 1. Clone & Configure

```bash
git clone <repo-url>
cd beacon
cp .env.example .env        # Windows: Copy-Item .env.example .env
```

Minimum required variables in `.env`:

```env
# LLM
FEATHERLESS_API_KEY=your_llm_api_key

# Bootstrap API keys (created on first launch)
BOOTSTRAP_ADMIN_API_KEY=your_admin_key
BOOTSTRAP_AUDITOR_API_KEY=your_auditor_key
BOOTSTRAP_VIEWER_API_KEY=your_viewer_key

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host/dbname
```

Optional scan tuning (all have sane defaults in `app/config.py`):

```env
DASHBOARD_DEEP_SCAN_MAX_PAGES=12
DASHBOARD_MAX_SCAN_MAX_PAGES=25
MAX_SCAN_GLOBAL_CAP=80
MAX_CONCURRENT_SITE_AUDITS=3

# Lighthouse enrichment tuning
LIGHTHOUSE_MAX_URLS_PER_SCAN=5
LIGHTHOUSE_PER_URL_TIMEOUT_SECONDS=90
LIGHTHOUSE_GLOBAL_TIMEOUT_SECONDS=300
LIGHTHOUSE_MAX_CONCURRENT_RUNS=2
LIGHTHOUSE_CACHE_TTL_SECONDS=3600
LIGHTHOUSE_RETRY_COUNT=1
```

---

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Optional Playwright fallback (Camoufox is the primary runtime):

```bash
pip install playwright
playwright install chromium
```

---

### 3. Run Database Migrations

```bash
alembic upgrade head
```

---

### 4. Start the API Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API docs: **http://localhost:8000/docs**

---

### 5. Start the Dashboard (optional)

```bash
cd frontend
npm install
npm run dev
```

Dashboard: **http://localhost:3000**

---

### 6. Ingest the WCAG Corpus (recommended)

```bash
# Basic ingestion — WCAG criteria only
python run_ingestion.py

# Full ingestion — also scrapes ARIA APG, COGA, WebAIM, MDN, axe-core docs (22 sources)
curl -X POST "http://localhost:8000/ingest?expand_corpus=true" \
  -H "Authorization: Bearer <ADMIN_KEY>"
```

---

## 📡 API Reference

All endpoints accept two equivalent authentication schemes:

```
Authorization: Bearer <key>
X-API-Key: <key>
```

### Roles

| Role | Permissions |
|---|---|
| `viewer` | Read-only: history, enrichment polling, RAG queries |
| `auditor` | Run audits, submit feedback |
| `admin` | All above + metrics, cache stats, alert triggers |

---

### Health Probes

```bash
# General health
curl http://localhost:8000/health

# Liveness — process is up and serving
curl http://localhost:8000/health/live

# Readiness — DB + vector store available
curl http://localhost:8000/health/ready

# Audit runtime — backpressure and saturation
curl http://localhost:8000/health/audit
```

---

### Run an Audit

```bash
curl -X POST http://localhost:8000/audit \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUDITOR_KEY>" \
  -d '{
    "url": "https://example.com",
    "scan_mode": "deep"
  }'
```

---

### Streamed Audit (Server-Sent Events)

```bash
curl -N -X POST http://localhost:8000/audit/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUDITOR_KEY>" \
  -d '{
    "url": "https://example.com",
    "scan_mode": "deep"
  }'
```

---

### Poll Async Enrichment

```bash
curl -H "Authorization: Bearer <VIEWER_KEY>" \
  http://localhost:8000/audit/enrichment/<AUDIT_ID>
```

---

### Audit History

```bash
curl -H "Authorization: Bearer <VIEWER_KEY>" \
  "http://localhost:8000/history?url=https://example.com&limit=10"
```

---

### RAG Knowledge Base Query

```bash
curl -X POST http://localhost:8000/rag \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <AUDITOR_KEY>" \
  -d '{
    "query": "How do I fix missing alt text on images?",
    "level": "AA"
  }'
```

---

### Observability (admin only)

```bash
# Prometheus metrics
curl -H "Authorization: Bearer <ADMIN_KEY>" http://localhost:8000/metrics

# Fix library + page cache telemetry
curl -H "Authorization: Bearer <ADMIN_KEY>" http://localhost:8000/audit/cache/stats
```

---

## 🖥️ CLI Audit Tool

Run a complete audit bundle — raw JSON + markdown report + CSV + dedup/group/WCAG summaries:

```bash
# Fast scan
python scripts/run_detailed_audit_cli.py https://example.com --scan-mode fast

# Deep scan — show top 30 findings
python scripts/run_detailed_audit_cli.py https://www.nytimes.com --scan-mode deep --show-top 30

# Max scan with RAG enrichment awaited
python scripts/run_detailed_audit_cli.py https://www.wikipedia.org \
  --scan-mode max --enable-enrichment --await-enrichment
```

Full flag reference: [`docs/detailed_cli_audit.md`](docs/detailed_cli_audit.md)

---

## 🧪 Testing

### Unit Tests

```bash
python -m pytest tests/unit/ -q
```

### Lighthouse Pipeline Tests (~10 s)

```bash
python -m pytest \
  tests/unit/services/test_lighthouse_runner.py \
  tests/unit/services/test_lighthouse_mapper.py \
  tests/unit/services/test_lighthouse_enricher.py \
  -q --timeout=30
```

### Regression Validation

```bash
python -m pytest \
  tests/unit/services/test_audit_runner_critical_bug.py \
  tests/unit/services/test_browser_prober_max_exploration.py \
  tests/unit/audit/test_site_aggregator.py -q
```

### Integration Smoke Test (fast mode, ~40 s)

```bash
python -m pytest tests/integration/test_phase20_all_modes.py -k "fast" -q --timeout=90
```

### Live 10-Site Benchmark (BEACON vs BEACON+Lighthouse)

```bash
# Requires Node.js + Lighthouse CLI — runs ~10–15 minutes
python test_comparison.py
```

### Site Archetype & ACT Benchmarks

```bash
python evaluation/validate_site_archetypes.py   # 10/10 archetypes passing
python evaluation/benchmark_act.py              # F1 = 1.00
python evaluation/benchmark_production.py       # 10-site production run
```

---

## 📦 Repository Layout

```
beacon/
├── app/
│   ├── main.py                      # FastAPI entry point & router registration
│   ├── config.py                    # Centralised scan limits, feature flags, Lighthouse constants
│   ├── audit/                       # Page auditor, parallel runner, site aggregator, scan-mode runner
│   ├── crawlers/                    # Sitemap, BFS, DOM crawlers + orchestrator
│   ├── services/
│   │   ├── audit_runner.py          # Core audit orchestration & backpressure guard
│   │   ├── topology_detector.py     # Site topology classification (single_page → multi_template)
│   │   ├── lighthouse_runner.py     # Headless Chrome Lighthouse subprocess runner
│   │   ├── lighthouse_mapper.py     # Raw Lighthouse JSON → BEACON findings schema
│   │   ├── lighthouse_enricher.py   # 5-rule deterministic merge engine
│   │   └── vector_store.py          # ChromaDB hybrid retrieval (BM25 + vector)
│   ├── data/
│   │   └── lighthouse_mapping.json  # Versioned Lighthouse audit inclusion list (v1)
│   ├── security/                    # API-key RBAC + URL SSRF validation
│   ├── observability/               # Telemetry, alerts, structured logging, Prometheus metrics
│   └── db/                          # SQLAlchemy models, Alembic migrations, repository layer
├── alembic/versions/                # Git-tracked DB migrations
│   ├── c9e1f3a27b84                 # Adds lighthouse_enrichment JSON column to scans table
│   └── 81e9864e53a7                 # Adds topology columns (site_topology, templates_found, urls_discovered)
├── frontend/                        # Next.js 15 dashboard (TypeScript)
│   └── src/
│       ├── app/                     # Next.js app router pages
│       └── components/              # UI components (timeline, features, theme)
├── tests/
│   ├── unit/                        # Unit tests: engines, Lighthouse pipeline, topology, aggregator
│   └── integration/                 # Real-site integration suites
├── evaluation/
│   ├── benchmark_act.py             # ACT rule benchmark (23 cases, F1=1.00)
│   ├── benchmark_production.py      # 10-site production benchmark
│   └── validate_site_archetypes.py  # Deterministic site-archetype validation
├── scripts/                         # CLI audit runner and validation helpers
├── corpus/                          # Source corpus for RAG ingestion
├── docs/
│   ├── architecture/
│   │   ├── master_architecture.md   # Full system architecture (v2.5)
│   │   └── ACCESSIBILITY_COVERAGE.md
│   ├── detailed_cli_audit.md        # Full CLI flag reference
│   └── phase20_rule_distribution.md # Rule diversity analysis
├── .github/workflows/
│   └── lighthouse_ci.yml            # Lighthouse self-audit CI on every push to main
├── .lighthouserc.json               # Lighthouse CI assertion thresholds
├── test_comparison.py               # Live 10-site BEACON vs BEACON+Lighthouse benchmark
├── run_ingestion.py                 # Corpus ingestion entry point
├── requirements.txt
└── .env.example                     # Environment variable template — never commit .env
```

---

## ⚙️ Pre-Push Checklist

```bash
# Syntax check core modules
python -m py_compile \
  app/config.py \
  app/audit/scan_mode_runner.py \
  app/routers/dashboard_api.py \
  app/services/topology_detector.py \
  app/services/lighthouse_runner.py \
  app/services/lighthouse_mapper.py \
  app/services/lighthouse_enricher.py

# Full unit test suite (~6–10 s)
python -m pytest tests/unit/ -q

# Integration smoke — fast mode only (~40 s)
python -m pytest tests/integration/test_phase20_all_modes.py -k "fast" -q --timeout=90

# Confirm DB migrations are at head
alembic current

# Verify .env is NOT staged
git status --short
```

**Push hygiene reminders:**
- `.env` must **never** be committed — always verify with `git status` before pushing
- Keep `.env.example` updated whenever new env keys are introduced
- Phase run outputs (`phase*.json`, `*.log`) are gitignored — keep them local only
- Ensure the scan mode table in this README matches values in `app/config.py::SCAN_MODES`

---

## 🧭 Roadmap

- [ ] Expand WCAG 2.2 A/AA criterion coverage from 55% to 80%+
- [ ] Improve cognitive engine accuracy and reduce experimental flag dependency
- [ ] Add interaction-replay analysis for authenticated flows
- [ ] Learning-based page selection to maximise template diversity per crawl budget
- [ ] Export to EARL / JSON-LD format for standards-compliant reporting
- [ ] Expand benchmark dataset beyond 10 sites for production validation
- [ ] Dashboard: issue timeline view and trend graphs across scan history

---

## 🤝 Contributing

Contributions are welcome. High-value areas:

- **Accessibility rules** — new static / heuristic detectors for uncovered WCAG criteria
- **Engine improvements** — better cognitive scoring, interaction heuristics
- **Benchmark datasets** — additional ACT test cases, real-world site fixtures
- **Dashboard UI** — visualisations, export features, accessibility of the dashboard itself

Please open an issue before submitting a large PR so we can align on approach.

---

## 📝 Important Notes

- **Cognitive scoring** is experimental and deliberately isolated from core hard-rule detection; it does not affect WCAG pass/fail determinations
- **RAG enrichment** is asynchronous — initial audit responses may return `enrichment: pending`; poll `/audit/enrichment/<id>` to retrieve results
- **Camoufox binary** must be fetched once (`python -m camoufox fetch`) before any `deep` or `max` scan will succeed; re-run after major Camoufox upgrades
- **Lighthouse enrichment** requires Node.js 18+ and `npm install -g lighthouse`; without it, `deep`/`max` scans continue normally with BEACON-only results
- **WCAG 2.2 coverage:** 55.2% (32/58) criteria — see [`ACCESSIBILITY_COVERAGE.md`](docs/architecture/ACCESSIBILITY_COVERAGE.md) for the full breakdown

---

## 📚 Documentation

| Document | Description |
|---|---|
| [`docs/architecture/master_architecture.md`](docs/architecture/master_architecture.md) | Full system architecture (v2.5) |
| [`docs/architecture/ACCESSIBILITY_COVERAGE.md`](docs/architecture/ACCESSIBILITY_COVERAGE.md) | WCAG 2.2 criterion-level coverage breakdown |
| [`docs/detailed_cli_audit.md`](docs/detailed_cli_audit.md) | Full CLI flag reference |
| [`docs/phase20_rule_distribution.md`](docs/phase20_rule_distribution.md) | Rule diversity analysis across production sites |
| [`RELEASE_NOTES.md`](RELEASE_NOTES.md) | Detailed per-phase release notes |
| [`docs/plans/completed/`](docs/plans/completed/) | Completed implementation plans per phase |

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built with ❤️ for a more accessible web.

**BEACON** · Accessibility Intelligence Engine · v3.0.0

</div>