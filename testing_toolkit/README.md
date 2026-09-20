# BEACON Testing Toolkit & Master Test Manifest

Definitive map and execution guide for the BEACON testing ecosystem, ensuring production reliability, compliance, and zero regressions.

---

## ⚡ Quick Reference Cheatsheet

| Frequency | Target / Phase | Linux / Bash Command | Windows / PowerShell Command |
|---|---|---|---|
| **Every Push** | Tier 1: Pre-Commit Unit & Fast Smoke | `./testing_toolkit/run_tier_1.sh` | `.\testing_toolkit\run_tier_1.ps1` |
| **Pre-Release** | Tier 2: Hardening, Security & Mode Matrix | `./testing_toolkit/run_tier_2.sh` | `.\testing_toolkit\run_tier_2.ps1` |
| **Weekly** | Tier 3: API, SSE & Supabase Layer | `pytest tests/api/ tests/integration/` | `pytest tests/api/ tests/integration/` |
| **Scheduled** | Tier 4: Scoring Calibration & Crawlers | `pytest tests/calibration/ tests/crawlers/` | `pytest tests/calibration/ tests/crawlers/` |
| **Manual / E2E** | Tier 5: Playwright Browser Tests | `npm --prefix frontend run test:e2e` | `npm --prefix frontend run test:e2e` |

---

## 🛡️ Tier 1: Quick Push Verification (Pre-Commit)
**Frequency**: Every code change | **Goal**: Zero syntax errors, zero regressions on core logic (~40s).
**Run Command**: `.\testing_toolkit\run_tier_1.ps1` (or `bash testing_toolkit/run_tier_1.sh`)

| Component | Test File | Description | Status |
|-----------|-----------|-------------|--------|
| Syntax | N/A | `py_compile` checks for core services | ✅ Active |
| Logic | `tests/unit/test_static_checker.py` | Core HTML structural audit logic | ✅ Active |
| Regression | `evaluation/benchmark_act.py` | 100% Adjudicated F1 on ACT community rules | ✅ Active |
| A11y | `tests/unit/test_webaim_six.py` | Ground truth for WebAIM top 6 violations | ✅ Active |
| Smoke | `tests/integration/test_phase20_all_modes.py` | Fast mode end-to-end on synthetic sites | ✅ Active |

---

## 🏗️ Tier 2: Pre-Release Hardening (Pre-Deploy)
**Frequency**: Before merging to `main` | **Goal**: Cross-platform stability, security, and multi-engine accuracy.
**Run Command**: `.\testing_toolkit\run_tier_2.ps1` (or `bash testing_toolkit/run_tier_2.sh`)

| Component | Test File | Description | Status |
|-----------|-----------|-------------|--------|
| **Auth/Security** | `tests/security/test_auth_boundary.py` | **CRITICAL**: User A cannot access User B's data | ✅ Active |
| Archetypes | `evaluation/validate_site_archetypes.py` | Validates BEACON handles React/Next/Dashboards | ✅ Active |
| Coverage | `tests/integration/test_phase20_all_modes.py` | Full matrix (Fast/Deep/Rendered/Heuristic) | ✅ Active |
| IBM | `tests/unit/test_ibm_checker.py` | Verifies IBM engine loads and analyzes | ✅ Active |
| Global | `evaluation/benchmark_a11ybench.py` | Global regression tracker for all rules | ✅ Active |

---

## 🌐 Tier 3: API & Application Layer (Weekly)
**Frequency**: Weekly | **Goal**: Verify endpoint reliability, streaming SSE, and database persistence.

| Component | Test File | Description | Status |
|-----------|-----------|-------------|--------|
| Endpoints | `tests/api/test_endpoints.py` | Status code and schema checks for `/audit`, `/history` | ✅ Active |
| Persistence | `tests/integration/test_supabase_persistence.py` | End-to-end DB write and retrieval | ✅ Active |
| SSE | `tests/api/test_sse_streaming.py` | Verify progress event stream reliability | 🟡 Automated |
| Health | `tests/api/test_health.py` | System availability and dependency heartbeats | ✅ Active |

---

## 🧪 Tier 4: Deep Logic & Calibration (Weekly/Scheduled)
**Frequency**: Scheduled | **Goal**: Fine-tune scoring weights and crawling accuracy.

| Component | Test File | Description | Status |
|-----------|-----------|-------------|--------|
| Scoring | `tests/calibration/test_scoring_alignment.py` | Ensures weights (Critical/Serious) are balanced | ✅ Automated |
| Focus | `tests/calibration/test_focus_trap_detection.py` | Validates keyboard trap detection logic | ✅ Automated |
| Crawler | `tests/crawlers/test_crawl_limits.py` | Stress tests BFS/Sitemap discovery | ✅ Automated |
| RAG | `tests/unit/test_rag_techniques.py` | Evaluates LLM fix suggestion quality | ✅ Automated |

---

## 🔮 Future / Planned Tests

| Component | Planned For | Description |
|-----------|-------------|-------------|
| Payment | Phase 4 | Verify billing tier enforcement and credit usage |
| Team Auth | Phase 4 | Organization-level RLS and permission sharing |

---

## 🛠️ Common Maintenance Commands

### Run Fast Unit Suite
```powershell
py -m pytest tests/unit/ tests/calibration/ tests/crawlers/ -q
```

### Run Security Boundary Tests
```powershell
py -m pytest tests/security/ -v
```

### Run Full API Suite
```powershell
py -m pytest tests/api/ -v
```
