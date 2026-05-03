# BEACON Master Test Manifest

This document serves as the definitive map for the BEACON testing ecosystem.

---

## 🛡️ Tier 1: Quick Push Verification (Pre-Commit)
**Frequency**: Every code change | **Goal**: Zero syntax errors, zero regressions on core logic.
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
**Frequency**: Before merging to `main` | **Goal**: Cross-platform stability and security.
**Run Command**: `.\testing_toolkit\run_tier_2.ps1` (or `bash testing_toolkit/run_tier_2.sh`)

| Component | Test File | Description | Status |
|-----------|-----------|-------------|--------|
| **Auth/Security** | `tests/security/test_auth_boundary.py` | **CRITICAL**: User A cannot access User B's data | 🔴 Needed |
| Archetypes | `evaluation/validate_site_archetypes.py` | Validates BEACON handles React/Next/Dashboards | ✅ Active |
| Coverage | `tests/integration/test_phase20_all_modes.py` | Full matrix (Fast/Deep/Rendered/Heuristic) | ✅ Active |
| IBM | `tests/unit/test_ibm_checker.py` | Verifies IBM engine loads and analyzes | ✅ Active |
| Global | `evaluation/benchmark_a11ybench.py` | Global regression tracker for all rules | ✅ Active |

---

## 🌐 Tier 3: API & Application Layer (Weekly)
**Frequency**: Weekly | **Goal**: Verify endpoint reliability and schema integrity.

| Component | Test File | Description | Status |
|-----------|-----------|-------------|--------|
| Endpoints | `tests/api/test_endpoints.py` | Status code and schema checks for /audit, /history | 🔴 Needed |
| Persistence | `tests/integration/test_supabase_persistence.py` | End-to-end DB write and retrieval | 🔴 Needed |
| SSE | `tests/api/test_sse_streaming.py` | Verify progress event stream reliability | 🔴 Needed |
| Health | `tests/api/test_health.py` | System availability and dependency heartbeats | 🔴 Needed |

---

## 🧪 Tier 4: Deep Logic & Calibration (Weekly/Scheduled)
**Frequency**: Scheduled | **Goal**: Fine-tune scoring and crawling accuracy.

| Component | Test File | Description | Status |
|-----------|-----------|-------------|--------|
| Scoring | `tests/calibration/test_scoring_alignment.py` | Ensures weights (Critical/Serious) are balanced | ✅ Automated |
| Focus | `tests/calibration/test_focus_trap_detection.py` | Validates keyboard trap detection logic | ✅ Automated |
| Crawler | `tests/crawlers/test_crawl_limits.py` | Stress tests BFS/Sitemap discovery | ✅ Automated |
| RAG | `tests/unit/test_rag_techniques.py` | Evaluates LLM fix suggestion quality | ✅ Automated |

---

## 🔮 Future / Planned Tests
These tests are planned but not yet applicable to the current codebase.

| Component | Planned For | Description |
|-----------|-------------|-------------|
| Payment | Phase 4 | Verify billing tier enforcement and credit usage |
| Team Auth | Phase 4 | Organization-level RLS and permission sharing |

---

## 🛠️ Maintenance Commands

### Run all Unit Tests
```powershell
python -m pytest tests/unit/
```

### Run all Security Tests
```powershell
python -m pytest tests/security/
```

### Run all API Tests
```powershell
python -m pytest tests/api/
```
