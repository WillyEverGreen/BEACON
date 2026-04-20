# Contributing to BEACON

Thank you for your interest in contributing. This document covers how to get set up, what areas need help, and what to do before opening a PR.

---

## 🎯 High-Value Contribution Areas

| Area | What is Needed |
|---|---|
| **Accessibility rules** | New static / heuristic detectors for uncovered WCAG 2.2 A/AA criteria |
| **Engine improvements** | Better cognitive scoring, interaction heuristics, SPA detection |
| **Benchmark datasets** | Additional ACT test cases, real-world site fixtures |
| **Dashboard UI** | Visualisations, export features, issue timeline views |
| **Documentation** | Improving clarity, adding examples, fixing inaccuracies |

---

## 🚀 Getting Started

### 1. Fork and clone

```bash
git clone https://github.com/<your-fork>/beacon.git
cd beacon
cp .env.example .env
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
python -m camoufox fetch
npm install -g lighthouse
```

### 3. Set up the database

```bash
alembic upgrade head
```

### 4. Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Interactive API docs available at: **http://localhost:8000/docs**

---

## 🧪 Before Opening a PR

Run the full pre-push checklist:

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

# Full unit test suite
python -m pytest tests/unit/ -q

# Integration smoke test (fast mode only)
python -m pytest tests/integration/test_phase20_all_modes.py -k fast -q --timeout=90

# Confirm DB migrations are at head
alembic current

# Confirm .env is NOT staged
git status --short
```

All unit tests must pass. Do not open a PR with failing tests.

---

## 📐 Code Style

- **Python:** follow existing conventions. Run `ruff check .` before committing.
- **TypeScript:** run `npm run lint` inside `frontend/`.
- No hardcoded `max_pages` values in `app/services/` or `app/routers/` — use `resolve_max_pages()` from `app/config.py`.
- All new scan limits must go through `app/config.py::SCAN_MODES`.

---

## 📝 PR Guidelines

- **Open an issue first** for anything larger than a bug fix or small improvement.
- Keep PRs focused — one concern per PR.
- Include a short description of what changed and why.
- Reference related issues with `Closes #N`.
- BEACON findings must **never** be deleted, suppressed, or downgraded by any enrichment layer — PRs that violate this will be rejected.

---

## 🔐 Security

Never commit:
- `.env` files
- API keys or tokens
- `serviceAccountKey.json`
- Database credentials

If you discover a security issue, please open a private GitHub security advisory instead of a public issue.