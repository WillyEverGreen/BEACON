# BEACON CI Expansion Plan — Phase 2+ Test Gates

> Status: **Future Plan** — not yet wired into `beacon_tests.yml`
> Current CI: Phase 1 gates only (see `.github/workflows/beacon_tests.yml`)
> Add these steps once Phase 3 gate passes and the full test suite is stable

---

## Why This Is Deferred

The Phase 1 CI workflow (`beacon_tests.yml`) runs the fast, per-commit unit tests only.
Phase 2 tests (cognitive COGA, captcha detection, new SC rules) and Phase 2+ benchmark
jobs are validated locally and confirmed passing, but are **not yet added to CI** because:

1. Phase 2 tests depend on GenA11y fixture paths that are not in the remote repo checkout
   (fixtures cloned locally but not committed — GPL-3.0 redistribution constraint).
2. The `test_new_sc_rules.py` fixture paths require `evaluation/fixtures/gena11y/` to be
   present, which is a local-only asset.
3. Full Phase 2 + Phase 3 CI expansion should happen together once Phase 3 gate passes,
   to avoid a partial CI state that is harder to maintain.

---

## Planned Additions to `beacon_tests.yml` (Phase 3+)

### Step 1 — Add to `unit_tests` job (per-commit)

```yaml
      - name: Run Phase 2 unit tests
        run: |
          pytest tests/unit/test_cognitive_coga.py \
                 tests/unit/test_captcha_detection.py \
                 -v --tb=short -q
        env:
          PYTHONPATH: .

      - name: Validate site archetypes (deterministic, no-network)
        run: python evaluation/validate_site_archetypes.py
        env:
          PYTHONPATH: .
```

**Note on `test_new_sc_rules.py`:** This test requires GenA11y fixtures. Two options:
- Option A: Commit a minimal subset of GenA11y fixtures (4 files) to `evaluation/fixtures/gena11y/` with a LICENSE note. Preferred if W3C-origin files are safe to include.
- Option B: Skip in CI with `@pytest.mark.skipif(not GENA11Y_AVAILABLE, ...)` and run only locally.

### Step 2 — Add `validate_site_archetypes` step

```yaml
      - name: Validate site archetypes (deterministic, no-network)
        run: python evaluation/validate_site_archetypes.py
        env:
          PYTHONPATH: .
```

This is 100% deterministic (no external calls), ~1 min, safe to add any time.

### Step 3 — Add Phase 2 gate job (on `main` branch push only)

```yaml
  phase2_gate:
    name: Phase 2 Gate Validation
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    needs: [unit_tests, smoke_benchmark]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r requirements.txt
      - name: Phase 2 — WCAG coverage check
        run: python evaluation/validate_site_archetypes.py
        env:
          PYTHONPATH: .
      - name: Phase 2 — Cognitive COGA citations
        run: pytest tests/unit/test_cognitive_coga.py -v
        env:
          PYTHONPATH: .
      - name: Phase 2 — CAPTCHA detection
        run: pytest tests/unit/test_captcha_detection.py -v
        env:
          PYTHONPATH: .
      - name: Phase 2 — WebAccessBench baseline exists
        run: |
          python -c "
          import json, pathlib, sys
          p = pathlib.Path('evaluation/results')
          files = list(p.glob('webaccessbench_beacon_*.json'))
          if not files:
              print('ERROR: No webaccessbench_beacon_*.json found', file=sys.stderr)
              sys.exit(1)
          data = json.loads(files[-1].read_text())
          if not data.get('tasks'):
              print('ERROR: webaccessbench file has no tasks field', file=sys.stderr)
              sys.exit(1)
          print(f'OK: {files[-1].name} — {len(data[\"tasks\"])} tasks recorded')
          "
```

### Step 4 — Add `make phase2-gate` Makefile target

```makefile
phase2-gate: unit-tests
	@echo "=== Phase 2 Gate Check ==="
	@echo "[1] WCAG coverage ≥62%"
	python evaluation/validate_site_archetypes.py
	@echo "[2] New SC rules on GenA11y fixtures (≥4 SC)"
	pytest tests/unit/test_new_sc_rules.py -q
	@echo "[3] Cognitive COGA citations"
	pytest tests/unit/test_cognitive_coga.py -q
	@echo "[4] CAPTCHA detection (3/3)"
	pytest tests/unit/test_captcha_detection.py -q
	@echo "[5] WebAccessBench baseline exists"
	@ls evaluation/results/webaccessbench_beacon_*.json
	@echo "[6] No regression on Phase 1 gates"
	$(MAKE) phase1-gate
	@echo ""
	@echo "✅ Phase 2 Gate PASSED"
	@echo "Proceed to Phase 3: Fix Quality and Broader Benchmarking."
```

---

## Makefile Changes (deferred)

The `unit-tests` target should be extended once GenA11y fixtures are resolvable in CI:

```makefile
unit-tests:
	pytest tests/unit/test_webaim_six.py \
	       tests/unit/test_ibm_checker.py \
	       tests/unit/test_rag_techniques.py \
	       tests/unit/test_cognitive_coga.py \
	       tests/unit/test_captcha_detection.py \
	       tests/unit/test_new_sc_rules.py \
	       -v -q
```

---

## Local Validation (Current — All Passing)

Run these locally to confirm Phase 1 + 2 are fully done:

```bash
# All Phase 1 + 2 unit tests
pytest tests/unit/test_webaim_six.py \
       tests/unit/test_ibm_checker.py \
       tests/unit/test_rag_techniques.py \
       tests/unit/test_cognitive_coga.py \
       tests/unit/test_captcha_detection.py \
       tests/unit/test_new_sc_rules.py \
       -v

# Site archetype validation (Phase 2 coverage gate)
python evaluation/validate_site_archetypes.py

# Full Phase 1 gate (benchmarks + loaders)
make phase1-gate
```

**Result as of 2026-04-25: 19/19 tests passing, site archetypes 10/10.**

---

_Created: 2026-04-25. Revisit after Phase 3 gate passes._
