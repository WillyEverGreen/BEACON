# BEACON — External Resource Integration Plan

> Version: 1.0  
> Created: 2026-04-21  
> Basis: ACCESSIBILITY_COVERAGE v2.7 (62.1% implemented, 22/58 A/AA SC not covered)  
> Scope: All 23 external resources, sequenced across 4 phases with mandatory test gates between each phase  
> Principle: Fix benchmark integrity first → expand detection → mature fix quality → harden edge cases

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Phase Map Overview](#2-phase-map-overview)
3. [Phase 1 — Benchmark Integrity and Detection Baseline](#3-phase-1--benchmark-integrity-and-detection-baseline)
4. [Phase 2 — Detection Expansion and Cognitive Hardening](#4-phase-2--detection-expansion-and-cognitive-hardening)
5. [Phase 3 — Fix Quality and Broader Benchmarking](#5-phase-3--fix-quality-and-broader-benchmarking)
6. [Phase 4 — Edge Cases, SR Layer, and Standards Readiness](#6-phase-4--edge-cases-sr-layer-and-standards-readiness)
7. [Test Gate Specifications](#7-test-gate-specifications)
8. [Success Metrics Summary](#8-success-metrics-summary)
9. [Risk Register](#9-risk-register)
10. [Dependency Graph](#10-dependency-graph)

---

## 1. Executive Summary

BEACON currently covers 62.1% (36/58) of WCAG 2.2 A/AA success criteria at full or partial depth. The benchmark validating this number runs against GenA11y, ACT full, and AccessGuru datasets. Fix suggestions have a preliminary pass-rate baseline. The cognitive engine is standards-grounded with COGA citations.

This plan integrates all 23 external resources across 4 sequential phases. Each phase ends with a mandatory test gate that must pass before the next phase begins. The gate is not a progress check — it is a binary go/no-go with explicit rollback conditions.

**Target state after all 4 phases:**

| Metric                      | Current       | Target                                           |
| --------------------------- | ------------- | ------------------------------------------------ |
| WCAG A/AA implemented (F+P) | 62.1% (36/58) | ≥75% (44/58)                                     |
| ACT benchmark cases         | 23            | ~80 (full rule set)                              |
| Benchmark datasets          | 1 (ACT)       | 5 (ACT, GenA11y, AccessGuru, A11YBench, Tabular) |
| Detection engines           | 5             | 8 (+ IBM Equal Access, Pa11y, Alfa)              |
| Screen reader layer         | None          | Experimental max+sr mode                         |
| Fix pass rate (axe re-scan) | Unmeasured    | ≥60% pass@1                                      |
| Cognitive engine status     | Experimental  | Standards-grounded (COGA-Usable)                 |

---

## 2. Phase Map Overview

```
Phase 1 (Weeks 1–2): Benchmark Integrity + Detection Baseline
  Resources: GenA11y dataset, ACT expansion, IBM Equal Access,
             AccessGuru dataset, WCAG 2.2 Techniques, WebAIM Million 2026
  Gate 1: Per-SC recall numbers exist and are trustworthy

Phase 2 (Weeks 3–4): Detection Expansion + Cognitive Hardening
  Resources: GenA11y paper, WebAccessBench, COGA-Usable, WebAIM SR Survey
  Gate 2: WCAG A/AA implemented ≥65%, cognitive engine de-experimentalized

Phase 3 (Weeks 5–6): Fix Quality + Broader Benchmarking
  Resources: AccessGuruLLM, microsoft/a11y-llm-eval, A11YBench, Tabular dataset
  Gate 3: Fix pass@1 ≥60%, A11YBench regression suite green

Phase 4 (Weeks 7–9): Edge Cases, SR Layer, Standards Readiness
  Resources: ARIA APG fixtures, MDN ARIA, Pa11y, Siteimprove Alfa, Contrast-Finder,
             Guidepup, EARL 1.0, WCAG 3.0 WD, ADA/EAA GTM, WAI tools list
  Gate 4: max+sr scan mode functional, EARL export passing schema validation
```

---

## 3. Phase 1 — Benchmark Integrity and Detection Baseline

> Duration: Weeks 1–2  
> Objective: Replace the 23-case ACT benchmark with a multi-dataset eval harness that produces per-criterion recall numbers you can trust. Add IBM Equal Access as Engine 6. Validate the 6 most common real-world failures hit 100% recall.

### 3.1 Resource: GenA11y Dataset

**What it is:** 148 HTML pages, each labelled by WCAG success criterion. Covers 37 WCAG SC. From `seal-hub/GenA11y`, dataset in `/Augmented Accessibility Tool Audit/tests`. GPL-3.0.

**Integration steps:**

1. Clone `seal-hub/GenA11y`. Copy the `tests/` fixture directory into `evaluation/fixtures/gena11y/`.
2. Inspect the filename convention — e.g. `buttons-empty-alt-attribute-on-image-button.html` maps to SC 1.1.1. Write a parser (`evaluation/gena11y_loader.py`) that extracts `(file_path, sc_id, expected_violation: bool)` tuples from filenames and the companion annotation JSON if present.
3. Extend `evaluation/benchmark_act.py` into a generic `evaluation/benchmark_runner.py` that accepts any fixture loader and produces a standard result schema:

```python
{
  "sc_id": "1.1.1",
  "fixture_file": "...",
  "expected": true,
  "beacon_detected": true,
  "engine": "static",
  "scan_mode": "deep",
  "confidence": 0.91
}
```

4. Run all 148 pages through BEACON deep mode. Record per-SC precision, recall, F1.
5. Write results to `evaluation/results/gena11y_baseline_YYYYMMDD.json`.

**Test integration:** Add `pytest evaluation/test_gena11y.py` to the test suite. Fail if any SC with ≥5 fixtures has recall below 0.50 — this is the minimum bar to catch gross engine blind spots.

**Expected output:** Per-SC recall table across 37 criteria. First time you will have this data.

---

### 3.2 Resource: ACT Rules Expansion

**What it is:** ~80 ACT rules with pass/fail/inapplicable HTML fixtures. From `act-rules/act-rules.github.io`. W3C Community license. Currently BEACON benchmarks 23 of these with F1=1.00.

**Integration steps:**

1. Clone `act-rules/act-rules.github.io`. The `_rules/` directory contains one YAML file per rule with `id`, `name`, `accessibility_requirements` (maps to WCAG SC), and links to test cases.
2. Write `evaluation/act_loader.py` that walks `_rules/*.yaml`, resolves test case HTML from `test-assets/`, and builds `(rule_id, sc_id, html_fixture, expected_outcome)` tuples. Filter to WCAG 2.2 A/AA rules only — ignore AAA and non-WCAG.
3. Run all resolved fixtures through `benchmark_runner.py`. Compare results against the 23-case baseline — expect F1 to drop from 1.00 as new cases expose blind spots. That drop is signal, not failure.
4. Record per-rule pass/fail/inapplicable accuracy in `evaluation/results/act_full_YYYYMMDD.json`.

**Test integration:** The existing `evaluation/benchmark_act.py` should remain as a fast smoke-test (23 cases, must stay at F1=1.00). The new full suite runs separately as a slower eval job, not a per-commit gate. Add a `Makefile` target: `make eval-act-full`.

**Expected output:** F1 score across ~80 rules. New blind spots surfaced per SC.

---

### 3.3 Resource: IBM Equal Access (Engine 6)

**What it is:** Independent rule engine covering WCAG 2.2 + Section 508 + IBM Accessibility requirements. npm package `accessibility-checker`. Apache 2.0. Node.js API compatible with Playwright.

**Integration steps:**

1. `npm install accessibility-checker --save` in BEACON's Node.js layer (wherever axe-core is injected).
2. Create `app/services/ibm_checker.py` (Python wrapper) that invokes a small Node.js script `scripts/ibm_scan.js` via `asyncio.create_subprocess_exec`. The Node script:

```javascript
const { getCompliance } = require("accessibility-checker");

async function scan(url) {
  const result = await getCompliance(url, "IBM_Accessibility");
  process.stdout.write(JSON.stringify(result.report));
}
scan(process.argv[2]);
```

3. Wire IBM results into `app/services/normalizer.py`. Add a new `IBM_WCAG_MAP` dict mapping IBM rule IDs to WCAG SC identifiers. IBM rule IDs follow the `WCAG20_*` / `WCAG21_*` naming convention — cross-reference against the rule files in `accessibility-checker-engine/src/v4/rules/`.
4. Add `ibm` as a new engine type in `app/audit/failure_taxonomy.py`. Assign default confidence of 0.85 (same posture as axe-core normalized).
5. IBM engine should activate in `deep` and `max` modes only. Add to the scan mode matrix in `ACCESSIBILITY_COVERAGE.md`.
6. Test cross-engine agreement: if IBM and axe-core both fire on the same element+rule, apply the existing 2-engine corroboration boost (confidence floor → 0.85 already). If IBM fires alone, treat as 0.85 base confidence.

**Test integration:**

```python
# tests/unit/test_ibm_checker.py
def test_ibm_fires_on_missing_alt():
    # Use a known fixture with missing alt text
    result = run_ibm_scan("evaluation/fixtures/gena11y/img-alt-missing.html")
    assert any(r['sc_id'] == '1.1.1' for r in result)

def test_ibm_normalizer_maps_to_wcag():
    # All IBM findings should have a valid WCAG SC id after normalization
    ...
```

**Expected output:** IBM findings appearing in deep/max scan results. Cross-engine corroboration visible in `confidence_sources` field.

---

### 3.4 Resource: AccessGuru Dataset + Paper

**What it is:** 3,500+ real-world violations from 448 websites. 112 violation types across Syntactic, Semantic, Layout categories. WCAG 2.1 aligned. CC BY 4.0. DOI: `10.18419/DARUS-5177`.

**Integration steps:**

1. Download the dataset from the DARUS repository. The dataset contains HTML code snippets with violation annotations.
2. Write `evaluation/accessguru_loader.py` that parses the dataset into `(html_snippet, violation_type, category, wcag_sc)` tuples. Focus on Semantic category first — these are the violations your current engines are least likely to catch.
3. Run the Semantic subset through BEACON deep mode. Record recall per violation type. This is your semantic detection baseline — the number that motivates Phase 2 work.
4. Store results in `evaluation/results/accessguru_semantic_baseline_YYYYMMDD.json`.
5. Read the paper's taxonomy table (Table 3 in arXiv:2507.19549) and cross-reference the 112 violation types against BEACON's `AXE_WCAG_MAP` + static rule inventory. Produce a gap table: which violation types have zero BEACON coverage.

**Test integration:** No automated test gate here — this is a measurement exercise. The output is a gap table that informs Phase 2 detection work, not a pass/fail check.

**Expected output:** Semantic detection recall baseline (expected to be low — this is intentional signal). Gap table of uncovered violation types.

---

### 3.5 Resource: WCAG 2.2 Techniques Corpus

**What it is:** W3C Techniques for WCAG 2.2 — per-criterion pages with sufficient techniques, advisory techniques, and failure examples. URL: `https://www.w3.org/WAI/WCAG22/Techniques/`. Currently not in BEACON's RAG corpus.

**Integration steps:**

1. Write a scraper (`scripts/ingest_wcag_techniques.py`) that fetches all Technique pages. The index is at `https://www.w3.org/WAI/WCAG22/Techniques/` — walk the `<ul>` of technique links. Each page follows a predictable structure: Understanding section, When to use, Description, Examples, Tests (procedure + expected results), Failures.
2. Extract per-technique content. Chunk by section: one chunk per Technique page, with metadata `{ technique_id, sc_id, type: "sufficient|advisory|failure", wcag_level }`.
3. Prioritize ingestion order: first ingest Failure techniques for your 12 partial-coverage SC (1.3.3, 1.3.5, 1.4.1, 1.4.10, 2.2.1, 2.2.2, 2.4.5, 2.4.6, 2.4.7, 2.4.11, 3.1.2, 3.3.7). These are the highest-ROI chunks.
4. Embed using your existing sentence-transformers pipeline into ChromaDB. Tag each chunk with `source: "wcag_techniques"` and `sc_id` for filtered retrieval.
5. Update the RAG retrieval query in `app/routers/rag.py` to include a `sc_id` filter when a finding's SC is known — this forces Technique-specific context into fix suggestions.

**Test integration:**

```python
# tests/unit/test_rag_techniques.py
def test_techniques_indexed_for_partial_sc():
    # Each of the 12 partial SC should have ≥3 technique chunks in ChromaDB
    for sc in PARTIAL_COVERAGE_SC:
        results = chroma_client.query(where={"sc_id": sc}, n_results=3)
        assert len(results['documents'][0]) >= 3

def test_fix_suggestion_cites_technique():
    # Fix suggestions for known partial-SC violations should reference a technique ID
    finding = make_finding(sc_id="1.3.5", rule_id="autocomplete-valid")
    suggestion = get_fix_suggestion(finding)
    assert any(t in suggestion for t in ["H98", "ARIA5", "F92"])  # known 1.3.5 techniques
```

**Expected output:** RAG fix suggestions for partial-coverage SC become technique-grounded. Fix text cites specific sufficient techniques or failures rather than generic WCAG prose.

---

### 3.6 Resource: WebAIM Million 2026

**What it is:** Annual analysis of 1M homepages. The 6 most common failures: low contrast (83.9%), missing alt text (53%), missing form labels (51%), empty links (46%), empty buttons (31%), missing document language (14%). URL: `https://webaim.org/projects/million/`.

**Integration steps:**

1. This is a validation exercise, not an ingestion task. Write `evaluation/test_webaim_six.py` — six explicit test cases, one per common failure, each using a minimal HTML fixture that contains exactly that violation:

```python
WEBAIM_SIX_FIXTURES = [
    ("low_contrast", "fixtures/webaim/low_contrast.html", "1.4.3"),
    ("missing_alt", "fixtures/webaim/missing_alt.html", "1.1.1"),
    ("missing_form_label", "fixtures/webaim/form_no_label.html", "1.3.1"),
    ("empty_link", "fixtures/webaim/empty_link.html", "2.4.4"),
    ("empty_button", "fixtures/webaim/empty_button.html", "4.1.2"),
    ("missing_lang", "fixtures/webaim/no_lang.html", "3.1.1"),
]

@pytest.mark.parametrize("name,fixture,sc", WEBAIM_SIX_FIXTURES)
def test_webaim_failure_detected(name, fixture, sc):
    result = run_beacon_fast(fixture)
    assert any(f['sc_id'] == sc for f in result['findings']), \
        f"BEACON missed {name} ({sc}) — WebAIM #1-6 recall failure"
```

2. Run in `fast` mode (not just deep) — these 6 failures should be detectable without a browser. If any of the 6 fail in fast mode, that is a P0 bug in your static engine, not a mode-gating issue.
3. Log results in CI. These 6 tests should run on every commit as part of the unit test suite.

**Test integration:** These 6 tests are not a new benchmark — they are permanent regression tests added to `tests/unit/`. A failure here means a top-6 WebAIM violation is not detectable by BEACON's static engine, which is a critical credibility gap.

**Expected output:** All 6 passing in fast mode. If any fail, the fix is in `app/services/static_checks.py` before Phase 2 begins.

---

### Phase 1 Gate (mandatory before Phase 2)

**Gate 1 conditions — all must be true:**

| Condition                        | Measurement                                | Pass Threshold                                                   |
| -------------------------------- | ------------------------------------------ | ---------------------------------------------------------------- |
| GenA11y benchmark running        | `make eval-gena11y` exits 0                | All 148 fixtures processed, results JSON written                 |
| ACT full suite running           | `make eval-act-full` exits 0               | All ~80 rules processed, results JSON written                    |
| IBM Equal Access active          | `pytest tests/unit/test_ibm_checker.py`    | All tests passing                                                |
| WebAIM Six passing               | `pytest tests/unit/test_webaim_six.py`     | 6/6 passing in fast mode                                         |
| WCAG Techniques indexed          | `pytest tests/unit/test_rag_techniques.py` | All 12 partial SC have ≥3 technique chunks                       |
| AccessGuru gap table exists      | File present                               | `evaluation/results/accessguru_semantic_baseline_*.json` written |
| No regression on existing ACT 23 | `python evaluation/benchmark_act.py`       | F1 remains 1.00 on original 23 cases                             |

**Rollback condition:** If IBM Equal Access integration causes any existing axe-core findings to be suppressed or confidence-downgraded incorrectly, revert `ibm_checker.py` and re-open as a bug before proceeding.

---

## 4. Phase 2 — Detection Expansion and Cognitive Hardening

> Duration: Weeks 3–4  
> Objective: Use the Phase 1 gap data to drive targeted detection improvements. Mature the cognitive engine from heuristic-only to standards-grounded. Add CAPTCHA detection. Re-benchmark and measure the coverage delta.

### 4.1 Resource: GenA11y Paper (FSE 2025)

**What it is:** The methodology behind GenA11y's 94.5% precision / 87.61% recall. Key techniques: element-extraction per SC, criterion-specific LLM prompting, expert role prompting. PDF: `https://seal.ics.uci.edu/publications/2025_FSE_GenA11y.pdf`.

**Integration steps:**

1. Read the paper's ablation study (Section 4 or equivalent). Identify which SC saw the largest gap between GenA11y and existing tools — these are your Phase 2 detection targets.
2. Cross-reference against BEACON's 26 not-covered SC. The intersection is your actionable list.
3. For each SC in the intersection, implement one of:
   - A new static check rule in `app/services/static_checks.py` if the violation is structurally detectable from HTML
   - A new heuristic rule in `app/services/heuristics.py` if it requires pattern matching
   - A new browser probe in `app/services/browser_probes.py` if it requires runtime DOM state
4. Use GenA11y's element-extraction approach: for each new rule, narrow the DOM scope to only elements relevant to that SC (e.g., SC 1.3.2 reading order → only block-level elements with explicit positioning). This reduces false positives.
5. Run each new rule against the GenA11y fixture set to validate it fires on the labelled violations.

**Test integration:**

```python
# tests/unit/test_new_sc_rules.py
# Auto-generated from Phase 1 gap analysis
@pytest.mark.parametrize("sc,fixture", NEW_SC_FIXTURES)
def test_new_rule_fires_on_fixture(sc, fixture):
    result = run_beacon_deep(fixture)
    assert any(f['sc_id'] == sc for f in result['findings'])
```

**Expected output:** Net new SC moved from Not Covered to Partial. Target: at least 4 SC added, successfully pushing implemented rate to 62.1% (Phase 2 achieved).

---

### 4.2 Resource: COGA-Usable

**What it is:** W3C Making Content Usable for People with Cognitive Disabilities. 8 design objectives, 23 specific patterns. URL: `https://www.w3.org/TR/coga-usable/`. GitHub: `w3c/coga`.

**Integration steps:**

1. Fetch and parse `https://www.w3.org/TR/coga-usable/`. The document is structured as: Objective → User Stories → Patterns → How to Test. Extract the "How to Test" and "Patterns" sections for each of the 23 patterns.
2. Map each pattern to the closest WCAG SC. Some map directly (e.g., "Use clear and understandable text" → SC 3.1.5, though that's AAA — note the limitation). Others are cognitive-specific with no A/AA WCAG equivalent — these become COGA-native findings.
3. Ingest into ChromaDB with metadata `{ source: "coga_usable", objective_id, pattern_id, wcag_sc_if_any }`.
4. Update `app/services/cognitive_checks.py` — for each of the 7 existing cognitive rules, add a `coga_pattern_ref` field that cites the relevant COGA pattern. This is the minimum to de-experimentalize the engine: its findings now cite authoritative guidance.
5. Add 3–5 new cognitive rules grounded in COGA patterns that have detectable HTML signals (e.g., Objective 4 — "Help users focus": detect excessive inline animation triggers, auto-advancing carousels, popups on focus events).
6. Remove the `experimental` tag from cognitive findings in the API response once all existing 7 rules have COGA citations.

**Test integration:**

```python
# tests/unit/test_cognitive_coga.py
def test_cognitive_findings_have_coga_citation():
    result = run_beacon_max("fixtures/cognitive/complex_carousel.html")
    cognitive_findings = [f for f in result['findings'] if f['engine'] == 'cognitive']
    for f in cognitive_findings:
        assert 'coga_pattern_ref' in f['metadata'], \
            f"Cognitive finding {f['rule_id']} missing COGA citation"

def test_cognitive_not_experimental_after_coga():
    result = run_beacon_max("fixtures/cognitive/autoplay_video.html")
    cognitive_findings = [f for f in result['findings'] if f['engine'] == 'cognitive']
    assert not any(f.get('experimental') for f in cognitive_findings)
```

**Expected output:** Cognitive engine findings cite COGA patterns. `experimental` flag removed. 3–5 new cognitive rules added.

---

### 4.3 Resource: WebAccessBench

**What it is:** 150 UI implementation tasks evaluated across 19 LLMs under 3 prompt regimes (unguided, little guidance, expert guidance). Measures whether LLM-generated HTML is WCAG-conformant. URL: `https://conesible.de/wab/`. February 2026.

**Integration steps:**

1. Download the 150 task prompts from the benchmark (the paper notes full task list is withheld to prevent overfitting, but the methodology and guidance conditions are public). Reconstruct a representative 30-task subset covering: forms, dialogs, navigation, small stateful widgets — the component types most commonly generated by BEACON's fix pipeline.
2. For each task, generate a fix suggestion using BEACON's current LLM pipeline (Qwen2.5-Coder-32B-Instruct). This is your `unguided` baseline.
3. Run each generated HTML artifact through axe-core. Record error count and zero-error rate.
4. Add the "little guidance" condition: prepend BEACON's existing RAG-retrieved technique context to the fix prompt. Re-run. Measure delta.
5. Store results in `evaluation/results/webaccessbench_beacon_YYYYMMDD.json` using the same schema as the paper (absolute error count, zero-error frequency, normalized error burden).

**Test integration:** No hard pass/fail threshold at this stage — this is establishing a baseline for Phase 3. The only gate condition is that the evaluation pipeline runs end-to-end without errors.

**Expected output:** BEACON fix pipeline's `unguided` vs `guided` error rate delta. This number motivates the AccessGuruLLM prompt work in Phase 3.

---

### 4.4 Resource: WebAIM Screen Reader Survey #10

**What it is:** 1,539 respondents. JAWS 40.5%, NVDA 37.7%, Chrome 52.3%. Top barriers: CAPTCHA (#1), unexpected screen changes, complex/inaccessible PDFs. Heading navigation dominant (71.6%).

**Integration steps:**

1. This is a severity-weight calibration task, not a code integration. Update the severity scoring logic in `app/services/confidence.py` or wherever severity weights are assigned:
   - Heading structure violations (SC 1.3.1, 2.4.6): escalate default severity to `critical` (was `serious`)
   - Landmark/region violations: escalate to `serious`
2. Add a CAPTCHA detection heuristic to `app/services/heuristics.py`:

```python
# Detect CAPTCHA presence — common implementations
CAPTCHA_SIGNALS = [
    "g-recaptcha", "h-captcha", "cf-turnstile",  # widget IDs
    "captcha", "recaptcha",  # class/id substrings
    'iframe[src*="recaptcha"]', 'iframe[src*="hcaptcha"]'  # iframe src patterns
]

def check_captcha_accessibility(dom):
    """
    SC: No direct WCAG mapping — cognitive/barrier finding
    Fires when CAPTCHA is detected without an accessible alternative.
    Reference: WebAIM SR Survey #10, #1 reported barrier.
    """
    ...
```

3. Document the CAPTCHA finding as a `barrier` type in `failure_taxonomy.py` — it does not map cleanly to a single WCAG SC but is a real barrier. Tag it with `survey_evidence: "WebAIM SR Survey 10, rank 1"`.

**Test integration:**

```python
# tests/unit/test_captcha_detection.py
@pytest.mark.parametrize("fixture,should_fire", [
    ("fixtures/captcha/recaptcha_v2_no_alt.html", True),
    ("fixtures/captcha/recaptcha_v2_with_fallback.html", False),
    ("fixtures/captcha/no_captcha.html", False),
])
def test_captcha_heuristic(fixture, should_fire):
    result = run_beacon_fast(fixture)
    captcha_findings = [f for f in result['findings'] if f['rule_id'] == 'captcha-barrier']
    assert bool(captcha_findings) == should_fire
```

**Expected output:** CAPTCHA detection live in fast mode. Severity weights updated. Heading/landmark findings marked critical.

---

### Phase 2 Gate (mandatory before Phase 3)

**Gate 2 conditions — all must be true:**

| Condition                                | Measurement                                     | Pass Threshold                                                             |
| ---------------------------------------- | ----------------------------------------------- | -------------------------------------------------------------------------- |
| WCAG coverage improved                   | `python evaluation/validate_site_archetypes.py` | Implemented (F+P) ≥62% (36/58 SC)                                          |
| New SC rules passing on GenA11y fixtures | `pytest tests/unit/test_new_sc_rules.py`        | ≥4 new SC covered, each with recall ≥0.60 on GenA11y fixtures              |
| Cognitive COGA citations present         | `pytest tests/unit/test_cognitive_coga.py`      | All 7 existing cognitive rules have COGA pattern refs                      |
| CAPTCHA detection live                   | `pytest tests/unit/test_captcha_detection.py`   | 3/3 parametrized cases passing                                             |
| WebAccessBench baseline recorded         | File present                                    | `evaluation/results/webaccessbench_beacon_*.json` written                  |
| No regression on Phase 1 gates           | All Phase 1 tests                               | Still passing                                                              |
| ACCESSIBILITY_COVERAGE.md updated        | Manual review                                   | Version bumped, new SC classifications updated, IBM engine added to matrix |

**Rollback condition:** If new static check rules produce false-positive rate >15% on the GenA11y not-violated fixtures (pages that should not trigger a given SC but do), roll back those rules and re-implement with tighter element scoping before proceeding.

---

## 5. Phase 3 — Fix Quality and Broader Benchmarking

> Duration: Weeks 5–6  
> Objective: Measure and improve fix suggestion quality using pass@k methodology. Expand regression benchmark to 60-project A11YBench suite. Add framework-specific component benchmarking.

### 5.1 Resource: AccessGuruLLM Prompt Templates

**What it is:** Prompt templates and LLM interaction patterns from AccessGuru ASSETS 2025, achieving 84% violation correction. From `NadeenAhmad/AccessGuruLLM`.

**Integration steps:**

1. Clone `NadeenAhmad/AccessGuruLLM`. Read the prompt templates for each violation category: Syntactic, Semantic, Layout.
2. Map AccessGuru's violation categories to BEACON's finding types:
   - Syntactic → static + axe-core findings (structural HTML violations)
   - Layout → color contrast, spacing, visual findings
   - Semantic → cognitive + heuristic findings (meaning, context, alt text quality)
3. For Semantic violations specifically (where BEACON's fix quality is weakest), replace BEACON's current generic RAG-retrieved template with AccessGuru's taxonomy-driven template pattern. The key difference is that AccessGuru provides the LLM with: (a) the violation type, (b) the element HTML, (c) a rendered screenshot for multimodal context, and (d) a correction instruction grounded in the violation category.
4. Implement screenshot injection for Semantic findings in deep/max mode: capture a Playwright screenshot of the violating element's bounding box and include it as a base64 image in the Qwen prompt. This is the multimodal improvement.
5. Run BEACON's updated fix pipeline against the AccessGuru 305-violation evaluation subset. Compare violation score decrease before and after prompt upgrade.

**Test integration:**

```python
# tests/unit/test_fix_quality.py
def test_semantic_fix_includes_element_screenshot():
    finding = make_semantic_finding(sc_id="1.1.1", rule_id="image-alt")
    fix = get_fix_suggestion(finding, scan_mode="deep")
    assert fix['context']['screenshot_included'] == True

def test_fix_pipeline_produces_valid_html():
    # Fix suggestions must produce parseable HTML — no malformed output
    for fixture in SEMANTIC_VIOLATION_FIXTURES:
        fix = get_fix_suggestion(run_beacon_deep(fixture)['findings'][0])
        assert is_valid_html(fix['suggested_html'])
```

**Expected output:** Semantic fix suggestions include element screenshots. Fix text is violation-category-specific rather than generic. Measurable improvement in AccessGuru violation score decrease metric.

---

### 5.2 Resource: microsoft/a11y-llm-eval

**What it is:** Playwright + axe-core harness with pass@k metrics and token/cost tracking. For evaluating whether AI-generated HTML is accessible. MIT license. GitHub: `microsoft/a11y-llm-eval`.

**Integration steps:**

1. Clone `microsoft/a11y-llm-eval`. This is a Python-native evaluation harness — read the README for the eval loop structure.
2. Adapt the harness to measure BEACON's fix pipeline specifically:
   - Input: BEACON finding with suggested HTML fix
   - Evaluation: apply the fix to the source HTML → run axe-core → count remaining violations on the fixed element
   - Metric: pass@1 (violation resolved in one LLM call), pass@2 (resolved after one re-prompt), overall resolution rate
3. Implement the evaluation in `evaluation/fix_quality_eval.py`:

```python
def evaluate_fix_pass_rate(findings_with_fixes: list, k: int = 1) -> dict:
    """
    For each finding, apply the suggested fix and re-scan with axe-core.
    Returns pass@k rate — fraction of violations resolved within k attempts.
    """
    results = []
    for item in findings_with_fixes:
        original_html = item['source_html']
        suggested_fix = item['fix']['suggested_html']
        fixed_html = apply_fix(original_html, suggested_fix)
        post_fix_violations = run_axe_on_html(fixed_html)
        resolved = not any(v['id'] == item['finding']['rule_id']
                           for v in post_fix_violations)
        results.append({'resolved': resolved, 'k': k, 'sc_id': item['finding']['sc_id']})
    pass_rate = sum(r['resolved'] for r in results) / len(results)
    return {'pass_at_k': pass_rate, 'k': k, 'n': len(results), 'by_sc': ...}
```

4. Run against the WebAccessBench 30-task subset from Phase 2. Record pass@1 and pass@2.
5. Record per-SC pass rates — this shows which SC has the worst fix quality and informs RAG improvement priorities.

**Test integration:**

```python
# tests/integration/test_fix_pass_rate.py
def test_fix_pass_rate_meets_threshold():
    results = evaluate_fix_pass_rate(load_fix_eval_fixtures(), k=1)
    assert results['pass_at_k'] >= 0.60, \
        f"Fix pass@1 rate {results['pass_at_k']:.2f} below 60% threshold"
```

**Expected output:** pass@1 ≥ 60% across the evaluation set. Per-SC pass rate table showing where fix quality is worst.

---

### 5.3 Resource: A11YBench

**What it is:** 60 real-world GitHub projects, 147 pages, 8,886 IBM Equal Access-detected violations. React, Next.js, Vue, static-site generators. MIT license. HuggingFace: `LLM4APR/A11YBench`.

**Integration steps:**

1. Download the A11YBench dataset from HuggingFace. The dataset CSV maps projects to violation counts and types.
2. This is a regression benchmark, not a unit test. Write `evaluation/benchmark_a11ybench.py` that:
   - Selects a representative 10-project subset covering React, Next.js, Vue (matching BEACON's dashboard stack)
   - Runs BEACON deep mode on each project's sample pages
   - Compares BEACON's finding count and SC coverage against IBM Equal Access ground truth
   - Records precision and recall per project
3. The IBM Equal Access ground truth from A11YBench gives you a reference to compare Engine 6 (Phase 1) against — this is the validation that your IBM integration is working correctly.
4. Add `make eval-a11ybench` as a Makefile target. This is a monthly regression run, not a per-commit test.

**Test integration:**

```python
# tests/integration/test_a11ybench_regression.py
def test_a11ybench_no_regression_vs_baseline():
    # Run 3 representative projects. BEACON should not miss more findings
    # than the established baseline from Phase 3 initial run.
    for project in A11YBENCH_SAMPLE_3:
        result = run_beacon_deep(project['url'])
        assert result['finding_count'] >= project['baseline_finding_count'] * 0.90, \
            f"Regression: {project['name']} finding count dropped >10% vs baseline"
```

**Expected output:** Regression suite covering 10 A11YBench projects. BEACON recall vs IBM ground truth per project. Framework-specific blind spots identified.

---

### 5.4 Resource: Tabular Accessibility Dataset

**What it is:** Accessible/non-accessible component pairs in PHP, Angular, React, Vue.js. CC BY 4.0. Zenodo. Published September 2025. Focus: tabular components.

**Integration steps:**

1. Download from Zenodo. Extract React and Vue component pairs (skip PHP/Angular for now — lower relevance to BEACON's target stack).
2. For each component pair, render the non-accessible version in a headless browser (Playwright) and run BEACON deep mode. The expected outcome: BEACON should detect a violation on the non-accessible version.
3. Run BEACON on the accessible version. The expected outcome: no violation for the same rule.
4. This is primarily useful for validating false-positive rate on correctly-accessible code. Record false-positive count.

**Test integration:**

```python
# tests/unit/test_tabular_fp_rate.py
def test_accessible_tables_produce_no_false_positives():
    for component in TABULAR_ACCESSIBLE_FIXTURES:
        result = run_beacon_deep(component['html'])
        table_violations = [f for f in result['findings']
                            if f['sc_id'] in ['1.3.1', '4.1.2']]
        assert len(table_violations) == 0, \
            f"False positive on accessible table component: {component['name']}"
```

**Expected output:** False-positive rate on accessible tabular components documented. Any false positives in static checks fixed before Phase 4.

---

### Phase 3 Gate (mandatory before Phase 4)

**Gate 3 conditions — all must be true:**

| Condition                                | Measurement                                             | Pass Threshold                                             |
| ---------------------------------------- | ------------------------------------------------------- | ---------------------------------------------------------- |
| Fix pass@1 rate                          | `pytest tests/integration/test_fix_pass_rate.py`        | ≥60% pass@1                                                |
| A11YBench regression suite green         | `pytest tests/integration/test_a11ybench_regression.py` | No regression >10% on 3-project sample                     |
| False-positive rate on accessible tables | `pytest tests/unit/test_tabular_fp_rate.py`             | 0 false positives on accessible component set              |
| Semantic fixes include screenshots       | `pytest tests/unit/test_fix_quality.py`                 | All semantic findings in deep mode have screenshot context |
| AccessGuru score decrease improvement    | Manual measurement                                      | ≥10 percentage point improvement vs Phase 2 baseline       |
| No regression on Phase 1 + 2 gates       | All previous tests                                      | Still passing                                              |
| WCAG coverage updated                    | `ACCESSIBILITY_COVERAGE.md`                             | Version bumped, fix quality section added                  |

**Rollback condition:** If AccessGuruLLM prompt templates cause fix suggestion latency to increase by more than 40% per finding, revert the screenshot injection step and implement as a background/async enrichment instead.

---

## 6. Phase 4 — Edge Cases, SR Layer, and Standards Readiness

> Duration: Weeks 7–9  
> Objective: Harden ARIA detection with structured fixture ingestion. Add screen reader automation as an experimental max+sr mode. Implement EARL export. Address GTM-relevant standards positioning.

### 6.1 Resource: ARIA APG Structured Fixture Ingestion

**What it is:** 30+ WAI-ARIA design patterns with keyboard interaction specs, ARIA roles/states, and live code examples. GitHub: `w3c/aria-practices`. Currently ingested as prose — this step ingests the structured HTML examples.

**Integration steps:**

1. Clone `w3c/aria-practices`. Pattern examples are in `content/patterns/*/examples/`. Each example is a self-contained HTML page.
2. Write `scripts/ingest_aria_apg.py` that walks the examples directory and for each pattern:
   - Extracts the pattern name and ID (e.g., `accordion`, `dialog`)
   - Parses the required ARIA roles, states, and keyboard interactions from the pattern spec page
   - Creates fixture pairs: the example (accessible reference) + a deliberately broken version (remove one required ARIA attribute)
3. Ingest pattern specs into ChromaDB with metadata `{ source: "aria_apg", pattern_id, required_roles, required_states, keyboard_interactions }`. This enables pattern-level retrieval: when BEACON detects a broken ARIA widget, the RAG query can match it to the APG pattern and retrieve the exact keyboard/role requirements.
4. Use the broken fixtures to validate that BEACON's existing axe-core + browser-probe engines catch the violations.

**Test integration:**

```python
# tests/unit/test_aria_apg_fixtures.py
@pytest.mark.parametrize("pattern", APG_PATTERN_NAMES)
def test_broken_apg_pattern_detected(pattern):
    broken_html = load_broken_apg_fixture(pattern)
    result = run_beacon_deep(broken_html)
    assert len(result['findings']) > 0, \
        f"BEACON missed ARIA violation in broken {pattern} pattern"

def test_apg_fix_suggestion_references_pattern():
    result = run_beacon_deep(load_broken_apg_fixture("dialog"))
    aria_findings = [f for f in result['findings'] if '4.1.2' in f.get('sc_id','')]
    fix = get_fix_suggestion(aria_findings[0])
    assert 'dialog' in fix['fix_text'].lower() or 'APG' in fix['fix_text']
```

**Expected output:** ARIA fix suggestions cite specific APG patterns. Broken APG pattern fixtures covered by existing engines (validation that no regression occurred).

---

### 6.2 Resource: MDN ARIA Reference

**What it is:** MDN Web Docs ARIA roles, properties, states with browser compatibility data and common misuse warnings. URL: `https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles`.

**Integration steps:**

1. Scrape the 6 ARIA role category pages and their child role pages (approximately 70 role pages total). Focus on: widget roles, landmark roles, live region roles — these are the most commonly violated.
2. For each role page, extract: description, required properties, optional properties, prohibited properties, browser support notes, common mistakes section.
3. Ingest into ChromaDB with metadata `{ source: "mdn_aria", role_name, category, required_props, prohibited_props }`.
4. The key value here is the "common mistakes" content — MDN's plain English descriptions produce more readable fix suggestions than W3C spec language. Update the RAG prompt template to prefer MDN chunks for ARIA-related fix suggestions.

**Test integration:**

```python
# tests/unit/test_mdn_aria_rag.py
def test_aria_fix_uses_mdn_language():
    # Fix for a combobox ARIA violation should reference MDN-style guidance
    finding = make_finding(rule_id="aria-required-attr", sc_id="4.1.2")
    fix = get_fix_suggestion(finding)
    # MDN chunks should appear in top-k retrieval for ARIA rules
    assert fix['rag_sources'][0]['source'] in ['mdn_aria', 'aria_apg', 'wcag_techniques']
```

**Expected output:** ARIA fix suggestion readability improved. Fix text is developer-facing rather than spec-language.

---

### 6.3 Resource: Pa11y

**What it is:** HTML CodeSniffer-based Node.js accessibility checker. Third independent rule engine (different from axe-core and IBM). URL: `https://pa11y.org/`. `pa11y-ci` for bulk URL testing.

**Integration steps:**

1. `npm install pa11y --save` in BEACON's Node.js layer.
2. Create `scripts/pa11y_scan.js` analogous to the IBM scan script. Pa11y returns WCAG 2.1 AA findings by default.
3. Add Pa11y as an optional Engine 7, activated only in `max` mode via a feature flag `enable_pa11y=True`. Do not make it default — it adds latency and HTML CodeSniffer has different (sometimes overlapping, sometimes contradictory) rule interpretations vs axe-core.
4. Use Pa11y primarily for cross-validation: when Pa11y and axe-core agree on a finding, escalate confidence. When they disagree, flag for human review rather than auto-suppressing either.
5. Integrate `pa11y-ci` as a standalone audit mode for CI pipeline testing — useful when BEACON is used in a CI context.

**Test integration:**

```python
# tests/unit/test_pa11y_engine.py
def test_pa11y_fires_on_known_violation():
    result = run_beacon_max("fixtures/webaim/low_contrast.html",
                            options={"enable_pa11y": True})
    pa11y_findings = [f for f in result['findings'] if f['engine'] == 'pa11y']
    assert len(pa11y_findings) > 0

def test_pa11y_axe_agreement_boosts_confidence():
    # When Pa11y and axe agree, confidence should be ≥0.95
    result = run_beacon_max("fixtures/webaim/missing_alt.html",
                            options={"enable_pa11y": True})
    agreed_findings = [f for f in result['findings']
                       if 'pa11y' in f.get('confidence_sources', [])
                       and 'axe' in f.get('confidence_sources', [])]
    for f in agreed_findings:
        assert f['confidence'] >= 0.95
```

**Expected output:** Pa11y available as opt-in Engine 7 in max mode. Cross-engine confidence escalation working.

---

### 6.4 Resource: Contrast-Finder

**What it is:** HSL binary search algorithm that finds the nearest passing color combination for any failing contrast pair. LGPL-3.0. GitHub: `Asqatasun/Contrast-Finder`. Live: `https://app.contrast-finder.org`.

**Integration steps:**

1. The algorithm is available via their REST API: `GET https://app.contrast-finder.org/result.json?foreground=<hex>&background=<hex>&ratio=4.5&isBackgroundTested=true`. Alternatively, port the HSL binary search to Python directly — the algorithm is well-documented and short.
2. Implement `app/services/contrast_fixer.py`:

```python
def suggest_contrast_fix(fg_hex: str, bg_hex: str, level: str = "AA") -> dict:
    """
    Given a failing foreground/background pair, return the nearest passing color.
    Uses HSL binary search to minimize perceptual distance from original.
    Returns: { suggested_fg, suggested_bg, new_ratio, delta_e, passes_AA, passes_AAA }
    """
    ...
```

3. Wire into the fix suggestion pipeline: for any SC 1.4.3 or 1.4.11 finding with known fg/bg values, append the contrast fix suggestion to the fix text.
4. The fix suggestion output format: `"Change background from #CCCCCC to #767676 — new contrast ratio 4.6:1 (passes AA). Or change text from #767676 to #595959 for 4.8:1."` — concrete hex values, not generic guidance.

**Test integration:**

```python
# tests/unit/test_contrast_fixer.py
def test_contrast_fix_produces_passing_pair():
    result = suggest_contrast_fix("#767676", "#CCCCCC", level="AA")
    assert result['passes_AA'] == True
    assert result['new_ratio'] >= 4.5

def test_contrast_fix_in_finding_output():
    result = run_beacon_deep("fixtures/webaim/low_contrast.html")
    contrast_findings = [f for f in result['findings'] if f['sc_id'] == '1.4.3']
    for f in contrast_findings:
        if f.get('fg_hex') and f.get('bg_hex'):
            assert 'suggested_fg' in f['fix'] or 'suggested_bg' in f['fix']
```

**Expected output:** SC 1.4.3 findings include concrete hex replacement suggestions. No longer "contrast ratio 2.8:1, fails AA" — now "change to #595959 for 4.8:1 ratio."

---

### 6.5 Resource: Guidepup (Screen Reader Automation)

**What it is:** VoiceOver (macOS) and NVDA (Windows) automation via W3C AT Driver API. GitHub: `guidepup/guidepup`. Catches ARIA live regions, focus management, and dynamic content announcement failures that no static rule detects.

**Integration steps:**

1. This is a new `max+sr` scan mode, not an addition to existing modes. Add `max+sr` as a new scan mode value in `app/audit/scan_mode_runner.py`.
2. `max+sr` is macOS/Windows-only (VoiceOver or NVDA required). Detect OS at startup and emit a capability warning if neither is available. The mode gracefully degrades to `max` if SR is not available.
3. Implement `app/services/sr_probes.py` using Guidepup's API:
   - Navigate to the target URL with SR active
   - Interact with key interactive elements (forms, dialogs, carousels, modals)
   - Record what the SR announces for each interaction
   - Flag cases where: (a) announcement is empty, (b) announcement does not match visible text, (c) focus is lost after action
4. Map SR probe failures to WCAG SC: empty announcement → SC 4.1.3 (Status Messages) or SC 1.3.1; focus loss → SC 2.4.3; mismatched announcement → SC 4.1.2.
5. Mark all SR-probe findings as `engine: "sr_probe"` with `confidence: 0.95` (human-equivalent detection).

**Test integration:**

```python
# tests/integration/test_sr_probes.py
@pytest.mark.skipif(not SR_AVAILABLE, reason="Screen reader not available in this environment")
def test_sr_probe_detects_empty_dialog_announcement():
    result = run_beacon_sr("fixtures/sr/dialog_no_label.html")
    sr_findings = [f for f in result['findings'] if f['engine'] == 'sr_probe']
    assert any(f['sc_id'] in ['4.1.2', '1.3.1'] for f in sr_findings)

def test_max_sr_degrades_to_max_without_sr():
    # If SR is not available, max+sr should behave identically to max
    result_maxsr = run_beacon_scan("fixtures/webaim/missing_alt.html",
                                   mode="max+sr", sr_available=False)
    result_max = run_beacon_scan("fixtures/webaim/missing_alt.html", mode="max")
    assert result_maxsr['findings'] == result_max['findings']
```

**Expected output:** `max+sr` scan mode functional on macOS (CI on macOS runner or documented as local-only). SR probe findings visible in scan results.

---

### 6.6 Resource: EARL 1.0 Schema

**What it is:** W3C standard for expressing accessibility test results as machine-readable JSON-LD. Enables interoperability with compliance management platforms. URL: `https://www.w3.org/TR/EARL10-Schema/`.

**Integration steps:**

1. Implement `app/services/earl_serializer.py` that converts BEACON's internal finding schema to EARL JSON-LD:

```python
def to_earl(audit_result: dict) -> dict:
    """
    Serialize BEACON audit result to EARL 1.0 JSON-LD.
    Spec: https://www.w3.org/TR/EARL10-Schema/
    """
    return {
        "@context": "http://www.w3.org/ns/earl#",
        "@type": "TestReport",
        "assertions": [
            {
                "@type": "Assertion",
                "subject": { "@id": finding['url'], "@type": "earl:TestSubject" },
                "test": { "@id": f"https://act-rules.github.io/rules/{finding['rule_id']}" },
                "result": {
                    "@type": "TestResult",
                    "outcome": "earl:failed" if finding['severity'] != 'pass' else "earl:passed",
                    "info": finding['message']
                }
            }
            for finding in audit_result['findings']
        ]
    }
```

2. Add a `GET /audit/{audit_id}/earl` endpoint to `app/routers/audit.py` that returns EARL JSON-LD with `Content-Type: application/ld+json`.
3. Validate against the EARL schema using `pyld` or equivalent JSON-LD library.

**Test integration:**

```python
# tests/unit/test_earl_export.py
def test_earl_export_validates_against_schema():
    audit_result = run_beacon_deep("fixtures/webaim/missing_alt.html")
    earl_output = to_earl(audit_result)
    assert earl_output['@context'] == 'http://www.w3.org/ns/earl#'
    assert all('outcome' in a['result'] for a in earl_output['assertions'])

def test_earl_endpoint_returns_jsonld():
    response = client.get(f"/audit/{TEST_AUDIT_ID}/earl")
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/ld+json'
```

**Expected output:** EARL export endpoint live. Output validates against EARL 1.0 schema.

---

### 6.7 Resource: Siteimprove Alfa (Engine 8)

**What it is:** Enterprise-grade suite of open-source accessibility conformance testing tools written in TypeScript by Siteimprove. It is built strictly on top of ACT (Accessibility Conformance Testing) Rules definitions. GitHub: `siteimprove/alfa`.

**Integration steps:**

1. Since Alfa is TypeScript-based, integrate it in BEACON's Node.js layer via `npm install @siteimprove/alfa-axe` (or Alfa's core API packages) alongside existing engines.
2. Add Alfa as an optional Engine 8, activated in `max` mode alongside Pa11y (via `enable_alfa=True`).
3. Wire Alfa's output into `app/services/normalizer.py`. Since Alfa is built directly on standard ACT rules, mapping its output to WCAG SC is highly deterministic, offering one of the purest rule-to-SC mappings of any engine.
4. **Use Case (Tie-Breaker):** Alfa's greatest strength is its rigorous, enterprise-tested ACT implementation. Use it to resolve disagreements between axe-core and Pa11y: if axe-core and Pa11y disagree on a finding, rely on Alfa's output as the "tie-breaker" to either boost the confidence score or flag it specifically for human review.

**Test integration:**

```python
# tests/unit/test_alfa_engine.py
def test_alfa_engine_acts_as_tiebreaker():
    # In max mode, we test cross-validation if there's conflict
    result = run_beacon_max("fixtures/webaim/complex_table.html",
                            options={"enable_pa11y": True, "enable_alfa": True})
    alfa_findings = [f for f in result['findings'] if f['engine'] == 'alfa']
    assert len(alfa_findings) > 0
```

**Expected output:** Alfa available as opt-in Engine 8 in max mode, functioning as an ACT-strict tie-breaker between other evaluation engines.

---

### 6.8 GTM Resources: WCAG 3.0, ADA/EAA, WAI Tools List

These are positioning resources, not technical integrations. Complete them as documentation and messaging tasks, not code tasks.

**WCAG 3.0 Working Draft:**

- Add a section to BEACON's public documentation: "WCAG 3.0 Readiness". State: BEACON is WCAG 2.2 AA-aligned. WCAG 3.0 Bronze tier is scoped to approximately WCAG 2.2 AA equivalent — BEACON's coverage directly maps to Bronze compliance preparation. Final WCAG 3.0 recommendation is expected no earlier than 2028. No compliance tools should claim WCAG 3.0 conformance today.
- Add `wcag_3_readiness` field to audit reports: `true` if WCAG 2.2 AA pass rate ≥ 80%, `false` otherwise. This is a positioning field only, documented with the above caveat.

**ADA Title II + European Accessibility Act:**

- Update BEACON's marketing copy and pitch deck: "US government and education sites face ADA Title II WCAG 2.1 AA enforcement (April 2026). EU businesses face EAA enforcement (June 2025). BEACON provides automated detection against WCAG 2.1 and 2.2 AA — the exact standards these laws require."
- Add `compliance_frameworks` to audit report metadata: `["ADA", "EAA", "Section508"]` with `disclaimer: "Automated detection only. Manual audit required for legal compliance certification."`

**W3C WAI Evaluation Tools List:**

- Submit BEACON for listing once Phase 3 gate passes and the tool has measurable precision/recall numbers. The submission requires: tool URL, methodology tags (WCAG 2.2, automated, partially-automated), and a description.

---

### Phase 4 Gate (final)

**Gate 4 conditions — all must be true:**

| Condition                                     | Measurement                                   | Pass Threshold                                                                  |
| --------------------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------- |
| ARIA APG broken fixtures detected             | `pytest tests/unit/test_aria_apg_fixtures.py` | ≥80% of tested APG patterns caught                                              |
| Pa11y cross-validation working                | `pytest tests/unit/test_pa11y_engine.py`      | Both parametrized cases passing                                                 |
| Alfa engine acts as ACT validator             | `pytest tests/unit/test_alfa_engine.py`       | Tie-breaker validation tests passing                                            |
| Contrast hex suggestions in SC 1.4.3 findings | `pytest tests/unit/test_contrast_fixer.py`    | Both cases passing                                                              |
| EARL export validates                         | `pytest tests/unit/test_earl_export.py`       | Schema validation passing                                                       |
| max+sr mode functional (where SR available)   | `pytest tests/integration/test_sr_probes.py`  | SR degrades gracefully test passing; full SR test passing if macOS CI available |
| ACCESSIBILITY_COVERAGE.md final update        | Manual                                        | Version bumped to v3.0, coverage ≥75% documented                                |
| No regression on all prior gates              | Full test suite                               | All Phase 1–3 tests still passing                                               |

---

## 7. Test Gate Specifications

### Gate Test Suite Structure

```
evaluation/
  benchmark_act.py          # Fast 23-case smoke test (per-commit)
  benchmark_act_full.py     # Full ~80 rule ACT suite (weekly)
  benchmark_gena11y.py      # 148-page GenA11y benchmark (weekly)
  benchmark_accessguru.py   # AccessGuru semantic subset (monthly)
  benchmark_a11ybench.py    # 10-project A11YBench regression (monthly)
  fix_quality_eval.py       # pass@k fix evaluation (per-phase)
  validate_site_archetypes.py  # Existing deterministic validation
  results/
    act_23_baseline.json
    gena11y_baseline_YYYYMMDD.json
    act_full_YYYYMMDD.json
    accessguru_semantic_baseline_YYYYMMDD.json
    webaccessbench_beacon_YYYYMMDD.json

tests/
  unit/
    test_webaim_six.py        # Phase 1 — permanent regression
    test_ibm_checker.py       # Phase 1
    test_rag_techniques.py    # Phase 1
    test_new_sc_rules.py      # Phase 2
    test_cognitive_coga.py    # Phase 2
    test_captcha_detection.py # Phase 2
    test_fix_quality.py       # Phase 3
    test_tabular_fp_rate.py   # Phase 3
    test_aria_apg_fixtures.py # Phase 4
    test_mdn_aria_rag.py      # Phase 4
    test_pa11y_engine.py      # Phase 4
    test_alfa_engine.py       # Phase 4
    test_contrast_fixer.py    # Phase 4
    test_earl_export.py       # Phase 4
  integration/
    test_fix_pass_rate.py     # Phase 3 gate
    test_a11ybench_regression.py  # Phase 3
    test_sr_probes.py         # Phase 4
```

### CI Configuration

```yaml
# .github/workflows/beacon_tests.yml (or equivalent)

on: [push, pull_request]

jobs:
  unit_tests:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/unit/ -q

  smoke_benchmark:
    runs-on: ubuntu-latest
    steps:
      - run: python evaluation/benchmark_act.py
        # Must maintain F1=1.00 on original 23 cases

  weekly_benchmarks:
    runs-on: ubuntu-latest
    schedule: "0 2 * * 1" # Every Monday 2am
    steps:
      - run: make eval-gena11y eval-act-full

  monthly_benchmarks:
    runs-on: ubuntu-latest
    schedule: "0 3 1 * *" # First of every month
    steps:
      - run: make eval-accessguru eval-a11ybench
```

---

## 8. Success Metrics Summary

| Metric                         | Phase 1 Target               | Phase 2 Target         | Phase 3 Target           | Phase 4 Target        |
| ------------------------------ | ---------------------------- | ---------------------- | ------------------------ | --------------------- |
| WCAG A/AA implemented (F+P)    | 62.1% (achieved)             | 62.1% (maintained)     | ≥68% (40/58)             | ≥75% (44/58)          |
| ACT benchmark cases            | ~80 (full rule set)          | ~80 (maintained)       | ~80 (maintained)         | ~80 (maintained)      |
| Benchmark datasets active      | 3 (ACT, GenA11y, AccessGuru) | 3 + WebAccessBench     | 5 (+ A11YBench, Tabular) | 5 (maintained)        |
| Detection engines              | 6 (+ IBM)                    | 6 + cognitive hardened | 6 (maintained)           | 8 (+ Pa11y, Alfa opt-in) |
| Fix pass@1 rate                | Unmeasured (baseline)        | Baseline recorded      | ≥60%                     | ≥65%                  |
| Cognitive findings citing COGA | 0%                           | 100% (all 7 rules)     | 100%                     | 100%                  |
| CAPTCHA detection              | No                           | Yes (fast mode)        | Yes                      | Yes                   |
| SR layer                       | No                           | No                     | No                       | Experimental (max+sr) |
| EARL export                    | No                           | No                     | No                       | Yes                   |
| WebAIM Six recall (fast mode)  | 6/6                          | 6/6                    | 6/6                      | 6/6                   |

---

## 9. Risk Register

| Risk                                                             | Likelihood | Impact | Mitigation                                                                                             |
| ---------------------------------------------------------------- | ---------- | ------ | ------------------------------------------------------------------------------------------------------ |
| IBM Equal Access adds >300ms latency per scan                    | Medium     | Medium | Run IBM as async background task alongside axe-core, not blocking                                      |
| AccessGuru prompt templates cause fix regressions                | Medium     | High   | Gate 3 requires pass@1 ≥60% — explicit rollback condition documented                                   |
| GenA11y GPL-3.0 licensing conflicts with BEACON's commercial use | Low        | High   | Use fixtures for internal benchmarking only, do not redistribute                                       |
| Guidepup requires macOS/Windows — CI runs on Linux               | High       | Low    | SR tests are `skipif not SR_AVAILABLE` — graceful degradation documented                               |
| WCAG Techniques scraping blocked by W3C rate limits              | Low        | Low    | Cache full scrape locally; re-run monthly maximum                                                      |
| A11YBench 60-project eval infra is too slow for CI               | High       | Medium | Use 3-project sample for CI; full 60 runs monthly only                                                 |
| Pa11y contradicts axe-core findings, causing user confusion      | Medium     | Medium | Pa11y is opt-in, max-mode only; disagreements flagged for review, not surfaced as conflicting findings |
| Phase 2 new SC rules produce >15% false-positive rate            | Medium     | High   | Explicit rollback condition in Gate 2; use element scoping from GenA11y approach                       |

---

## 10. Dependency Graph

```
Phase 1 (must complete first)
├── GenA11y dataset ──────────────────► feeds Phase 2 new SC rule validation
├── ACT rules expansion ──────────────► establishes full benchmark baseline
├── IBM Equal Access ─────────────────► cross-validates Phase 3 A11YBench ground truth
├── AccessGuru dataset ───────────────► gap table drives Phase 2 detection targets
├── WCAG 2.2 Techniques ─────────────► feeds Phase 1 RAG fix quality immediately
│                                       feeds Phase 3 AccessGuruLLM integration
└── WebAIM Million 2026 ─────────────► permanent regression suite (all phases)

Phase 2 (depends on Phase 1 gap data)
├── GenA11y paper ────────────────────► uses Phase 1 gap table to target new rules
├── COGA-Usable ──────────────────────► uses Phase 1 cognitive baseline to set priorities
├── WebAccessBench ───────────────────► uses Phase 1 RAG corpus to measure guided vs unguided
└── WebAIM SR Survey ─────────────────► uses Phase 1 finding severity weights as baseline

Phase 3 (depends on Phase 2 detection improvements)
├── AccessGuruLLM ────────────────────► depends on Phase 1 Techniques corpus in RAG
├── microsoft/a11y-llm-eval ──────────► depends on Phase 2 WebAccessBench baseline
├── A11YBench ────────────────────────► depends on Phase 1 IBM Equal Access engine
└── Tabular dataset ──────────────────► validates Phase 2 false-positive work

Phase 4 (depends on Phase 3 fix quality stabilization)
├── ARIA APG fixtures ────────────────► extends Phase 1 RAG corpus
├── MDN ARIA ─────────────────────────► extends Phase 1 RAG corpus
├── Pa11y ────────────────────────────► depends on Phase 1 IBM engine (3-engine cross-val)
├── Siteimprove Alfa ─────────────────► depends on ACT expansion; acts as engine tie-breaker
├── Contrast-Finder ──────────────────► depends on Phase 1 Techniques corpus (fix formatting)
├── Guidepup ─────────────────────────► depends on Phase 2 browser probe infrastructure
└── EARL / GTM resources ─────────────► depends on Phase 3 metrics for credible claims
```

---

_This plan was generated from ACCESSIBILITY_COVERAGE v2.7 (2026-04-25) and the BEACON External Resources document. Phase 1 and 2 are confirmed complete at 62.1% coverage._
