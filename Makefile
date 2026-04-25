# BEACON Makefile — Phase 1 gate targets
# Usage:
#   make phase1-gate     — Run all Phase 1 gate conditions
#   make eval-gena11y    — GenA11y 148-fixture benchmark (weekly)
#   make eval-act-full   — ACT ~80-rule full benchmark (weekly)
#   make eval-accessguru — AccessGuru semantic baseline + gap table (monthly)
#   make unit-tests      — Per-commit unit test suite
#   make build-act-index — Rebuild ACT fixture index from cloned repo

.PHONY: eval-gena11y eval-act-full eval-accessguru phase1-tests unit-tests \
        phase1-gate build-act-index build-gena11y-fixtures

# ── Benchmark targets ─────────────────────────────────────────────────────────

eval-gena11y:
	python evaluation/benchmark_gena11y.py

eval-act-full:
	python evaluation/benchmark_act_full.py

eval-accessguru:
	python evaluation/benchmark_accessguru.py

# ── Fixture builders ──────────────────────────────────────────────────────────

build-act-index:
	python scripts/build_act_fixture_index.py
	@echo "ACT fixture index rebuilt."

build-gena11y-fixtures:
	python -c "\
import shutil; from pathlib import Path; \
src=Path('GenA11y/Augmented Accessibility Tool Audit/tests'); \
dst=Path('evaluation/fixtures/gena11y'); dst.mkdir(parents=True, exist_ok=True); \
[shutil.copy2(f, dst / f.name) for f in src.glob('*.html') if not (dst/f.name).exists()]; \
[shutil.copy2(f, dst / f'sc-{d.name.replace(\"SC \",\"\").replace(\" \",\"-\")}-{f.name}') \
 for d in src.iterdir() if d.is_dir() \
 for f in d.glob('*.html') \
 if not (dst / f'sc-{d.name.replace(\"SC \",\"\").replace(\" \",\"-\")}-{f.name}').exists()]; \
print('Done')"

# ── Unit tests (per-commit) ───────────────────────────────────────────────────

unit-tests:
	pytest tests/unit/test_webaim_six.py \
	       tests/unit/test_ibm_checker.py \
	       tests/unit/test_rag_techniques.py \
	       -v -q

phase1-tests: unit-tests
	pytest evaluation/test_gena11y.py \
	       evaluation/test_phase1_loaders.py \
	       -v -q

# ── Phase 1 Gate (all conditions) ────────────────────────────────────────────
# Runs all 7 gate conditions from more_resources.md §3 Gate 1.
# All must pass before Phase 2 begins.

phase1-gate: phase1-tests
	@echo "=== Phase 1 Gate Check ==="
	@echo "[1/7] WebAIM Six — 6/6 passing in fast mode"
	pytest tests/unit/test_webaim_six.py -q
	@echo "[2/7] IBM Equal Access — all tests passing"
	pytest tests/unit/test_ibm_checker.py -q
	@echo "[3/7] WCAG Techniques indexed — all 12 partial SC have ≥3 chunks"
	pytest tests/unit/test_rag_techniques.py -q
	@echo "[4/7] GenA11y benchmark — all 148+ fixtures processed"
	$(MAKE) eval-gena11y
	@echo "[5/7] ACT full suite — all ~80 rules processed"
	$(MAKE) eval-act-full
	@echo "[6/7] AccessGuru gap table — semantic baseline JSON exists"
	$(MAKE) eval-accessguru
	@echo "[7/7] Loaders — both act and accessguru loaders working"
	pytest evaluation/test_phase1_loaders.py evaluation/test_gena11y.py -q
	@echo ""
	@echo "✅ Phase 1 Gate PASSED — all conditions met."
	@echo "Proceed to Phase 2: Detection Expansion and Cognitive Hardening."
