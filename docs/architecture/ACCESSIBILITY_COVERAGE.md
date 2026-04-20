# ACCESSIBILITY_COVERAGE

## 🚀 Quick Summary

- Automated WCAG coverage: ~55% (core detection) + runtime JS enrichment via Lighthouse (deep/max)
- Strong coverage in: semantics, ARIA, keyboard, structure
- Partial coverage in: UX, cognitive, navigation
- Not covered by static scan: advanced media, timing, gestures
- Lighthouse enrichment: supplements detection in deep/max modes — adds runtime JS/performance findings BEACON cannot see with static analysis
- RAG: enrichment only (not detection)

This tool is NOT a full compliance solution.

## 📊 Coverage Overview

| Category    | Coverage |
| ----------- | -------- |
| Full        | 34.5%    |
| Partial     | 20.7%    |
| Not Covered | 44.8%    |

## 1) Scope and Method

This document is generated from implementation evidence in code, not from marketing claims or benchmark assumptions.

Evidence sources analyzed:

- app/services/static_checks.py
- app/services/heuristics.py
- app/services/browser_probes.py
- app/services/cognitive_checks.py
- app/services/normalizer.py (AXE_WCAG_MAP)
- app/services/audit_runner.py
- app/services/llm.py
- app/routers/rag.py
- app/services/lighthouse_runner.py (signal enrichment, deep/max)
- app/services/lighthouse_mapper.py (BEACON schema normalization)
- app/services/lighthouse_enricher.py (deterministic merge engine)
- app/data/lighthouse_mapping.json (versioned audit inclusion list, v1)

Method:

- Step 1: Extract static rules and WCAG mappings from static checker issue builders.
- Step 2: Extract heuristic rules and WCAG mappings.
- Step 3: Extract browser probe rules and WCAG mappings.
- Step 4: Extract cognitive rules and WCAG mappings.
- Step 5: Extract axe-core WCAG mapping from normalizer.
- Step 6: Classify WCAG 2.2 A/AA criteria as Full, Partial, or Not Covered using deterministic-vs-heuristic evidence.

Important constraints:

- Coverage here means implemented detection logic exists in code.
- Coverage here does not mean guaranteed legal conformance for every page type.
- Dynamic checks depend on deep/max mode and Playwright availability.

## 2) Detection Pipeline by Stage

Pipeline sequencing is implemented in app/services/audit_runner.py.

- Stage A: Static and heuristic checks run in parallel (run_static/run_heuristic path).
- Stage B: axe-core runs in deep/max mode only.
- Stage C: Normalization, deduplication, confidence scoring.
- Stage D: Cognitive checks (deep/max when enabled).
- Stage E: RAG enrichment is post-detection enrichment, not primary detection.
- Stage F: Lighthouse enrichment (deep/max only, async). Runs lighthouse_runner → lighthouse_mapper → lighthouse_enricher.
  Lighthouse findings are merged via 5-rule deterministic engine. BEACON primary findings are never overwritten.
  Adds `lighthouse_confirmed`, `lighthouse_score`, `severity_upgraded_by_lighthouse` fields to confirmed findings.
  Adds supplementary/additional_insight findings for Lighthouse-only discoveries.

Key evidence lines:

- Scan mode behavior and engine gating: app/services/audit_runner.py:944
- axe-core deep/max execution path: app/services/audit_runner.py:1249
- Parallel engine execution: app/services/audit_runner.py:1286
- RAG enrichment stage marker: app/services/audit_runner.py:1455

## 3) Engine Types and Trust Posture

| Engine              | Source                               | Base confidence | Default manual review | Detection type                    |
| ------------------- | ------------------------------------ | --------------: | --------------------- | --------------------------------- |
| Static              | app/services/static_checks.py:143    |            0.85 | False                 | Deterministic DOM checks          |
| Heuristic           | app/services/heuristics.py:52        |             0.5 | True                  | Pattern/heuristic signals         |
| Browser probe       | app/services/browser_probes.py:41    |             0.8 | False                 | Runtime interaction probes        |
| Cognitive           | app/services/cognitive_checks.py:110 |             0.6 | True                  | UX/readability heuristics         |
| axe-core normalized | app/services/normalizer.py:24        |             0.9 | False                 | Deterministic axe-core violations |
| Lighthouse          | app/services/lighthouse_enricher.py  | supplementary   | False                 | Runtime JS enrichment (deep/max)  |

Additional confidence governance:

- Heuristic-only findings are forced to needs-review in confidence logic.
- Cross-engine corroboration can boost confidence for the same rule.

Evidence lines:

- Heuristic-only needs-review: app/services/confidence.py:419
- Cross-engine boost: app/services/confidence.py:539

## 4) Rule Inventory (Code-Extracted)

Code-extracted unique rule counts by engine:

- Static: 81
- Heuristic: 23
- Browser probe: 19
- Cognitive: 7
- axe-core mapped rules: 31

Total unique mapped SC identifiers detected across all engines (including AAA and legacy 4.1.1): 38

Notes:

- Rule extraction is literal-call based with dynamic dict key capture.
- Dynamic behavior can still emit additional runtime-specific variants.

### 4.1 Full Rule Lists by Engine

Static rules (81):
apg-dialog-no-name, apg-dialog-not-modal, apg-expanded-missing-controls, apg-tab-broken-controls, apg-tab-missing-controls, apg-tablist-missing-tabs, aria-allowed-attr, aria-allowed-role, aria-hidden-focusable, aria-required-children, aria-required-parent, aria-roles, aria-valid-attr, aria-valid-attr-value, auto-update-no-control, autocomplete-missing, autoplay-media, broken-aria-description, broken-aria-label, button-name, clickable-no-role, color-contrast, css-reordering, div-itis-missing-semantics, duplicate-aria-ref, duplicate-id, duplicate-label, empty-alt, empty-heading, empty-link, error-not-linked, fake-list, focus-management, heading-order, image-redundant-alt, inaccessible-document-link, input-name, invalid-lang, keyboard-trap, landmark-roles, lang-mismatch, link-no-underline, link-purpose, marquee-used, media-alternative, meta-refresh, missing-alt, missing-autocomplete-auth, missing-captions, missing-h1, missing-label, missing-landmark, missing-lang, missing-skip-link, missing-transcript, multiple-h1, no-aria-live, no-fieldset-legend, no-footer-landmark, no-header-landmark, no-headings, no-main-landmark, no-nav-landmark, no-title, placeholder-as-label, positive-tabindex, redundant-entry, role-no-name, semantic-html, small-font-size, svg-no-accessible-name, table-no-caption, table-no-headers, th-no-scope, timeout-no-warning, touch-target-spacing, unlabeled-icon, unsafe-external-link, video-transcript, viewport-zoom-disabled, visibility-aria-mismatch

Heuristic rules (23):
alt-is-filename, alt-quality, alt-too-long, aria-allowed-attr, aria-attribute, aria-roles, aria-valid-attr, aria-valid-attr-value, avoid-inline-spacing, coga-action-fatigue, coga-wall-of-text, keyboard-trap, letter-spacing, missing-landmark, no-main-landmark, semantic-html, sensory-language, short-link-text, svg-no-accessible-name, text-spacing, vague-button-text, vague-label, weak-error-message

Browser probe rules (19):
aria-tree-no-name, autoplay-media, excessive-motion, focus-management, focus-obscured, focus-trap-background, focus-trap-cycling, focus-trap-escape, focus-trap-initial, infinite-scroll-accessibility, keyboard-trap, keyboard-unreachable, lazy-img-missing-alt, no-focus-style, responsive-reflow, skeleton-loading-state, target-size-minimum, text-spacing, zoom-overflow

Cognitive rules (7):
cta-clarity, error-message-quality, form-no-progress, form-usability, jargon, nav-complexity, readability

axe-core mapped rules (31):
area-alt, aria-hidden-focus, aria-required-attr, aria-required-children, aria-required-parent, aria-roles, aria-valid-attr, aria-valid-attr-value, button-name, bypass, color-contrast, color-contrast-enhanced, definition-list, document-title, form-field-multiple-labels, heading-order, html-has-lang, html-lang-valid, image-alt, input-image-alt, label, landmark-one-main, link-name, list, listitem, meta-viewport, region, tabindex, td-headers-attr, th-has-data-cells, video-caption

## 5) Standards Mapping

### 5.1 WCAG Mapping

WCAG SC mapping is explicitly attached in issue objects and/or normalizer mappings.

Examples:

- Static issue schema includes wcag_criterion and wcag_level fields.
- Heuristic, browser, cognitive builders also emit wcag_criterion/wcag_level fields.
- axe-core uses AXE_WCAG_MAP in normalizer.

Evidence lines:

- Static issue schema: app/services/static_checks.py:145
- Heuristic issue schema: app/services/heuristics.py:53
- Browser issue schema: app/services/browser_probes.py:41
- Cognitive issue schema: app/services/cognitive_checks.py:110
- axe-core map: app/services/normalizer.py:24

### 5.2 ARIA and APG

The implementation includes direct ARIA and APG-specific checks, not only generic WCAG labels.

Examples:

- ARIA role/attribute validation in static checks.
- APG pattern checks in static checker modules.

Evidence lines:

- ARIA checks entry: app/services/static_checks.py:2320
- APG pattern check: app/services/static_checks.py:2674

### 5.3 Knowledge-Base Standards Used for Enrichment (Not Detection)

Retrieval trust silos include wcag, aria, coga, axe, toolkit, local_wcag_kb.

Evidence line:

- app/services/retrieval.py:27

## 6) WCAG 2.2 A/AA Coverage Classification

Denominator used in this report:

- 58 WCAG 2.2 A/AA SC identifiers in internal baseline list used for this code analysis.

Classification rule used:

- Full: strong deterministic coverage signal (multiple deterministic engines or dense deterministic rules).
- Partial: only single-engine or mostly heuristic coverage.
- Not Covered: no implemented detector found for that SC.

### 6.1 Full Coverage (20/58)

1.1.1, 1.2.1, 1.2.2, 1.3.1, 1.4.2, 1.4.3, 1.4.4, 1.4.12, 2.1.1, 2.1.2, 2.4.1, 2.4.2, 2.4.3, 2.4.4, 2.5.8, 3.1.1, 3.3.1, 3.3.2, 4.1.2, 4.1.3

### 6.2 Partial Coverage (12/58)

1.3.3, 1.3.5, 1.4.1, 1.4.10, 2.2.1, 2.2.2, 2.4.5, 2.4.6, 2.4.7, 2.4.11, 3.1.2, 3.3.7

### 6.3 Not Covered (26/58)

1.2.3, 1.2.4, 1.2.5, 1.3.2, 1.3.4, 1.4.5, 1.4.11, 1.4.13, 2.1.4, 2.2.6, 2.3.1, 2.3.2, 2.4.12, 2.5.1, 2.5.2, 2.5.3, 2.5.4, 2.5.7, 3.2.1, 3.2.2, 3.2.3, 3.2.4, 3.2.6, 3.3.3, 3.3.4, 3.3.8

## 7) Percentage Estimates (Honest)

Using the 58-item A/AA baseline in this analysis:

- Full: 20/58 = 34.5%
- Partial: 12/58 = 20.7%
- Not covered: 26/58 = 44.8%
- Implemented at least partial: 32/58 = 55.2%

## 💪 Strength Areas

- Semantic structure (WCAG 1.3.1)
- Name, role, value (4.1.2)
- Keyboard accessibility (2.1.x)
- ARIA validation

Additional non-A/AA criteria observed in code mapping:

- AAA signals: 1.4.6, 2.3.3, 3.1.3, 3.1.5, 3.3.9
- Legacy/obsolete in 2.2 context: 4.1.1 still appears in rule mapping path

## 8) Limitations and Non-Coverage Risks

1. Dynamic engine dependency:

- Browser and axe evidence requires deep/max path and Playwright runtime.

2. Heuristic/cognitive reliability:

- Heuristic and cognitive findings are intentionally low-confidence or needs-review by default.

3. Mapping quality caveat:

- A cognitive rule call appears to pass arguments in a mismatched order for form-no-progress, which can distort wcag/level fields.
- Evidence: app/services/cognitive_checks.py:376

4. Enrichment mutation caveat:

- Enrichment can overwrite wcag_criterion from generated text, so compliance accounting should use pre-enrichment detector mapping when auditing raw detector coverage.
- Evidence: app/services/llm.py:452

5. Access and blocked-page degradation:

- For blocked/auth-limited pages, pipeline can degrade and emit availability-focused findings rather than full structural coverage.

## 9) Detection vs RAG Enrichment Separation

This is critical:

Detection engines:

- Static, heuristic, browser-probe, axe-core, cognitive
- These produce the actual issue detections.

Lighthouse enrichment engine (deep/max only):

- Runs Google Lighthouse CLI (headless Chrome) against up to 5 URLs per scan.
- Findings are mapped from Lighthouse audit format into BEACON findings_schema.
- Merged with BEACON findings via 5-rule deterministic engine (lighthouse_enricher.py).
- Lighthouse confirmed = BEACON finding corroborated by Lighthouse runtime.
- Lighthouse-only (score <50): added as supplementary finding.
- Lighthouse-only (score 50-89): added as additional_insight finding.
- Lighthouse-only (score ≥90): dropped silently.
- BEACON findings are NEVER deleted, suppressed, or downgraded by Lighthouse.
- Live integration test (10 sites): +30–50% coverage uplift on reachable sites, 0 BEACON findings lost.

RAG enrichment:

- Happens later and enhances remediation payloads (explanations, steps, code fix suggestions).
- RAG does not create detector reach for missing SC categories.

Evidence:

- Enrichment stage in runner: app/services/audit_runner.py:1455
- Enrichment function: app/services/llm.py:901
- Standalone RAG endpoint for Q/A over knowledge base: app/routers/rag.py:13

## 10) Practical Interpretation

Current implementation has strong depth in core structural/semantics/name-role-value areas (notably 1.3.1 and 4.1.2) and moderate runtime keyboard/focus coverage.

However, a large set of timing, pointer, advanced media, and predictable-input criteria remains uncovered.

Bottom line:

- This is a capable multi-engine accessibility detector with meaningful WCAG breadth.
- It is not full WCAG 2.2 A/AA coverage yet.
- Current honest A/AA implemented coverage estimate is 55.2% (full+partial), with 34.5% in the stronger/full bucket under this report's evidence criteria.

## ⚠️ Disclaimer

This tool provides automated accessibility analysis and does not guarantee full WCAG, ADA, EAA, or Section 508 compliance. Manual audits are required.

## 🔦 Lighthouse Integration Note (Phase 21)

As of April 2026, BEACON integrates Google Lighthouse as a runtime signal-enrichment layer for `deep` and `max` scan modes.

- Lighthouse adds JavaScript-execution-dependent findings that static/heuristic analysis cannot reach (e.g. React-injected ARIA, lazy-loaded image alt attributes, dynamic focus management).
- This integration **does not inflate the core WCAG coverage figures** in this document — those numbers reflect BEACON's own detectors only.
- Lighthouse enrichment provides **additional signals** on top of the 55.2% coverage baseline documented here.
- The live 10-site test showed average +30–50% additional finding uplift on reachable sites, with 0 BEACON findings overwritten.
- Lighthouse coverage is limited to its own audit inclusion list (`app/data/lighthouse_mapping.json`). Not all WCAG criteria are covered by Lighthouse audits.
