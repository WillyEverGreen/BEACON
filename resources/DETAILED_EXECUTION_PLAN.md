# 🚀 Accessibility Intelligence Engine — Detailed Execution Plan

> **Project Goal:** Build a next-gen accessibility auditing platform that combines deterministic rule engines, AI-powered semantic analysis, cognitive UX scoring, and a RAG-backed remediation layer — surpassing Lighthouse and axe-core in coverage, accuracy, and developer experience.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Milestone 1 — Schemas, Contracts & Gates](#2-milestone-1--schemas-contracts--gates)
3. [Milestone 2 — Deterministic Extraction Engine](#3-milestone-2--deterministic-extraction-engine)
4. [Milestone 3 — Confidence & False-Positive Control](#4-milestone-3--confidence--false-positive-control)
5. [Milestone 4 — RAG Upgrade & Remediation Layer](#5-milestone-4--rag-upgrade--remediation-layer)
6. [Milestone 5 — Cognitive & UX Layer](#6-milestone-5--cognitive--ux-layer)
7. [Milestone 6 — Grouping & Developer Outputs](#7-milestone-6--grouping--developer-outputs)
8. [Milestone 7 — Evaluation & Benchmark Proof](#8-milestone-7--evaluation--benchmark-proof)
9. [Milestone 8 — Feedback Intelligence Loop](#9-milestone-8--feedback-intelligence-loop)
10. [WCAG 2.2 Full Checklist Mapping](#10-wcag-22-full-checklist-mapping)
11. [Authoritative Resource Registry](#11-authoritative-resource-registry)
12. [Data Flow Diagram](#12-data-flow-diagram)
13. [File & Module Map](#13-file--module-map)

---

## 1. Architecture Overview

```
URL Input
   │
   ▼
┌──────────────┐
│  Crawl Queue │  ← URL input, depth config, SPA-aware routing
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   Renderer   │  ← Playwright: full DOM snapshot + accessibility tree
└──────┬───────┘
       │
       ├──────────────────┬──────────────────┐
       ▼                  ▼                  ▼
┌────────────┐   ┌──────────────┐   ┌─────────────┐
│ Static HTML│   │ Browser/Dyn. │   │  axe-core   │
│  Checks    │   │   Probes     │   │  Engine     │
└─────┬──────┘   └──────┬───────┘   └──────┬──────┘
      │                 │                   │
      └────────┬────────┴───────────────────┘
               ▼
      ┌─────────────────┐
      │  Join / Dedup /  │  ← Normalize, deduplicate, group, rank
      │  Group / Rank    │
      └────────┬────────┘
               │
               ▼
      ┌─────────────────┐
      │  Confidence &   │  ← Multi-signal scoring, FP filtering
      │  FP Controller  │
      └────────┬────────┘
               │
               ▼
      ┌─────────────────┐
      │  RAG Pipeline   │  ← WCAG corpus + COGA + ARIA APG + AI
      │  (Remediation)  │
      └────────┬────────┘
               │
               ▼
      ┌─────────────────┐
      │  Output Layer   │  ← JSON API + Markdown Report + Fix Snippets
      └─────────────────┘
```

---

## 2. Milestone 1 — Schemas, Contracts & Gates

**Goal:** Define every data structure, API contract, mode of operation, and quality gate up front so that all downstream milestones build on a stable foundation.

### 2.1 Scan Mode Definitions

| Mode | Description | Max Runtime | Use Case |
|------|-------------|-------------|----------|
| **Fast** | Static HTML checks + axe-core only; no Playwright rendering | ≤ 15 seconds | CI/CD pipelines, quick health checks |
| **Deep** | Full Playwright render + browser probes + axe + static + cognitive/UX | ≤ 120 seconds | Pre-release audits, compliance reports |

### 2.2 Quality Gates (Hard Thresholds)

Every audit run **MUST** meet these gates before its results are accepted:

| Gate | Threshold | Enforced By |
|------|-----------|-------------|
| **Runtime** | Fast ≤ 15s, Deep ≤ 120s | `audit_runner.py` — abort & return timeout error if exceeded |
| **Coverage Delta** | ≥ 20% more findings than Lighthouse on reference test suite | Benchmark CI job |
| **Duplicate Rate** | ≤ 5% duplicate issues after dedup pass | `dedup_engine.py` — log warning if exceeded |
| **False-Positive Rate** | ≤ 10% (measured via labeled validation set) | `confidence.py` — auto-downgrade if FP threshold crossed |

### 2.3 Extended Issue Schema

Update `app/models.py` — `AuditIssue` to carry richer metadata:

```python
class AuditIssue(BaseModel):
    # ── Identity ──
    issue_id: str               # Unique hash: SHA256(url + selector + rule_id)
    rule_id: str                # e.g. "color-contrast", "image-alt"
    issue_type: str             # "violation", "needs-review", "best-practice"

    # ── Location ──
    element: str                # CSS selector or XPath
    html_snippet: str           # Offending HTML fragment (≤ 500 chars)
    page_url: str               # Full URL where found

    # ── Classification ──
    severity: str               # critical | serious | moderate | minor
    wcag_criterion: str         # e.g. "1.4.3"
    wcag_level: str             # A | AA | AAA
    category: str               # html | keyboard | forms | color | images | aria | media | cognitive

    # ── Confidence ──
    confidence: float           # 0.0 – 1.0
    confidence_sources: list[str]  # ["axe-core", "heuristic", "browser-probe"]
    needs_manual_review: bool   # True if confidence < 0.6

    # ── Remediation ──
    description: str
    suggested_fix: str
    code_fix: str               # Ready-to-paste code snippet
    fix_effort: str             # low | medium | high

    # ── Grouping ──
    group_id: str               # Groups related issues (e.g., same rule across page)
    domain: str                 # Functional domain: navigation, forms, content, media

    # ── Evidence ──
    evidence: dict              # Screenshots, computed styles, ARIA tree snapshots
    reproducibility: str        # Steps to reproduce for high-priority items
```

### 2.4 RAG Packet Schemas

**Input to RAG (Issue Packet):**
```python
class IssuePacket(BaseModel):
    issue_id: str
    rule_id: str
    wcag_criterion: str
    element: str
    html_snippet: str
    description: str
    severity: str
    confidence: float
```

**Output from RAG (Remediation Packet):**
```python
class RemediationPacket(BaseModel):
    issue_id: str
    explanation: str              # Why this is an issue
    wcag_references: list[WCAGReference]
    code_fix: str                 # Ready-to-use fix
    practical_assets: list[PracticalAsset]
    validation_hint: str          # How to verify the fix
    confidence: float             # RAG's confidence in this remediation
    needs_manual_review: bool     # Flag for human review
    sources: list[RetrievedSource]
```

### Tasks
- [ ] Update `app/models.py` with extended `AuditIssue` schema
- [ ] Add `IssuePacket` and `RemediationPacket` models
- [ ] Add scan mode configuration to `app/config.py`
- [ ] Define quality gate constants in `app/config.py`
- [ ] Write unit tests for schema validation

---

## 3. Milestone 2 — Deterministic Extraction Engine

**Goal:** Build a multi-layered extraction pipeline that runs static HTML checks, browser dynamic probes, and axe-core in parallel, then normalizes and deduplicates findings.

### 3.1 Static HTML Checks (Baseline)

Parse the rendered DOM and check against the **full WCAG 2.2 checklist** (see [Section 10](#10-wcag-22-full-checklist-mapping)):

| Check Category | Specific Rules | WCAG Criterion | Priority |
|----------------|---------------|----------------|----------|
| **HTML Semantics** | `<html lang>` present and valid | 3.1.1 (A) | P0 |
| | Unique `<title>` per page | 2.4.2 (A) | P0 |
| | Semantic landmarks: `<header>`, `<nav>`, `<main>`, `<footer>`, `<aside>` | 1.3.1 (A) | P0 |
| | DOM order matches visual reading order | 1.3.2 (A) | P0 |
| | Viewport meta allows zoom | 1.4.4 (AA) | P0 |
| **Headings** | Single `<h1>` per page | 1.3.1 (A) | P0 |
| | No skipped heading levels | 1.3.1 (A) | P0 |
| | Headings are descriptive (heuristic) | 2.4.6 (AA) | P1 |
| | Skip navigation link as first link | 2.4.1 (A) | P0 |
| **Images** | All `<img>` have `alt` attribute | 1.1.1 (A) | P0 |
| | Decorative images use `alt=""` | 1.1.1 (A) | P0 |
| | Complex images have long descriptions | 1.1.1 (A) | P1 |
| | Images of text flagged | 1.4.5 (AA) | P1 |
| **Links & Buttons** | Links visually distinguishable (not color-only) | 1.4.1 (A) | P0 |
| | No "click here" / "read more" link text | 2.4.4 (A) | P0 |
| | Correct element usage (`<a>` vs `<button>`) | 4.1.2 (A) | P0 |
| | Buttons without text have `aria-label` | 4.1.2 (A) | P0 |
| | Links opening new window identified | 3.2.5 (AA) | P1 |
| | Touch target size ≥ 24px | 2.5.8 (AA) | P1 |
| **Forms** | Every `<input>` has a `<label>` with `for`/`id` | 1.3.1 (A) | P0 |
| | Related fields grouped with `<fieldset>` + `<legend>` | 1.3.1 (A) | P1 |
| | Errors linked via `aria-describedby` | 3.3.1 (A) | P0 |
| | `autocomplete` on relevant inputs | 1.3.5 (AA) | P1 |
| | Focus states visible on controls | 2.4.7 (AA) | P0 |
| **Color Contrast** | Normal text: 4.5:1 ratio | 1.4.3 (AA) | P0 |
| | Large text: 3:1 ratio | 1.4.3 (AA) | P0 |
| | UI components: 3:1 ratio | 1.4.11 (AA) | P0 |
| | Text over images readable | 1.4.3 (AA) | P1 |
| | Icons/graphics: 3:1 ratio | 1.4.11 (AA) | P1 |
| **Media** | No autoplay media | 1.4.2 (A) | P0 |
| | Media controls accessible (ARIA roles) | 4.1.2 (A) | P1 |
| | Video captions present | 1.2.2 (A) | P0 |
| | Audio transcripts available | 1.2.1 (A) | P0 |
| | No seizure triggers (flash rate < 3/sec) | 2.3.1 (A) | P0 |
| **ARIA** | Native HTML preferred over ARIA | Best Practice | P1 |
| | Custom elements have correct ARIA roles | 4.1.2 (A) | P0 |
| | ARIA states dynamically updated | 4.1.2 (A) | P0 |
| | Decorative content uses `aria-hidden` | 4.1.2 (A) | P1 |
| | Dynamic content uses `aria-live` regions | 4.1.3 (AA) | P1 |
| **Tables** | Data tables use `<th>` with `scope` | 1.3.1 (A) | P0 |
| | Tables have `<caption>` | 1.3.1 (A) | P1 |
| **Lists** | Proper list markup (`<ul>`, `<ol>`, `<dl>`) | 1.3.1 (A) | P1 |
| **Content** | No reliance on sensory characteristics | 1.3.3 (A) | P1 |
| | Language changes marked with `lang` attr | 3.1.2 (AA) | P1 |

### 3.2 Quality Heuristic Checks (Beyond axe-core)

These are AI/NLP-augmented checks that no existing tool does well:

| Heuristic | What It Catches | How to Implement |
|-----------|----------------|------------------|
| **Alt Text Quality** | `alt="image"`, `alt="photo.jpg"`, overly generic alts | Regex patterns + LLM semantic scoring against surrounding context |
| **Vague Link Text** | "click here", "read more", "learn more", "here" | Pattern matching + context analysis (does preceding text provide context?) |
| **Vague Button Text** | "submit", "go", "ok" without clear action context | NLP analysis of button text vs form purpose |
| **Weak Error Messaging** | "invalid input", "error" without explaining what's wrong | Parse error containers, score message specificity via LLM |
| **Label Clarity** | Labels like "field1", "input", "enter value" | Semantic analysis: does the label describe the expected input? |

### 3.3 Browser Dynamic Probes (Playwright)

Run in **Deep** scan mode only:

| Probe | Purpose | Implementation |
|-------|---------|----------------|
| **Keyboard Navigation** | Verify all interactive elements are reachable via Tab | Playwright keyboard automation: Tab through page, record focus order |
| **Focus Trap Detection** | Ensure users can always Tab away | Detect if Tab cycles without advancing |
| **Modal Focus Management** | Background elements shouldn't be interactive when modal is open | Open modal, verify `inert` or `aria-hidden` on background |
| **Responsive Reflow** | No horizontal scroll at 320px width | Resize viewport, check for overflow |
| **Zoom Test** | Content usable at 200% zoom | Zoom via viewport, check for overlaps and clipping |
| **Animation Detection** | Check for `prefers-reduced-motion` respect | Toggle media query, verify animations stop |
| **ARIA Tree Snapshot** | Capture full accessibility tree as screen readers see it | `page.accessibility.snapshot()` via Playwright |
| **Focus Style Check** | Interactive elements have visible focus indicators | Tab to each element, capture computed `:focus` styles |

### 3.4 axe-core Integration

```python
# Run axe-core via Playwright
async def run_axe_core(page) -> list[dict]:
    await page.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js")
    results = await page.evaluate("axe.run()")
    return results["violations"]
```

### 3.5 Normalization & Deduplication

```
Raw findings from all 3 engines
         │
         ▼
┌─────────────────────────┐
│  Normalize to AuditIssue│  ← Map axe/static/browser results to unified schema
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Deduplicate             │  ← Key: (url, selector, rule_id)
│  - Same element + same   │     If ≥2 engines find same issue → boost confidence
│    rule = merge findings │     If 1 engine only → keep but flag
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Group by domain         │  ← navigation | forms | content | media | structure
│  + rank by severity      │
└─────────────────────────┘
```

### Tasks
- [ ] Implement static HTML check functions in `app/services/static_checks.py` [NEW]
- [ ] Implement quality heuristic checkers in `app/services/heuristics.py` [NEW]
- [ ] Implement Playwright browser probes in `app/services/browser_probes.py` [NEW]
- [ ] Integrate axe-core execution into `app/services/audit_runner.py` [MODIFY]
- [ ] Build normalization layer in `app/services/normalizer.py` [NEW]
- [ ] Build dedup engine in `app/services/dedup_engine.py` [NEW]
- [ ] Unit tests for each check category

---

## 4. Milestone 3 — Confidence & False-Positive Control

**Goal:** Assign a calibrated confidence score to every finding so that false positives are suppressed and true issues are promoted.

### 4.1 Confidence Formula

```
confidence = (
    0.30 × source_reliability     +  # axe-core=0.9, browser-probe=0.8, heuristic=0.5
    0.25 × signal_strength        +  # How clear-cut is the violation? (0.0–1.0)
    0.25 × cross_engine_agreement +  # Found by 1 engine=0.3, 2=0.7, 3=1.0
    0.20 × evidence_quality          # Has screenshot? DOM proof? Computed styles?
)
```

### 4.2 Rules Engine

| Condition | Action |
|-----------|--------|
| Heuristic-only finding (no axe, no browser) | Auto-set `issue_type = "needs-review"` |
| `confidence < 0.4` | Auto-downgrade severity by 1 level |
| `confidence < 0.2` | Auto-set `needs_manual_review = True`, exclude from score |
| ≥ 2 engines agree on exact same issue | Auto-set `confidence = max(confidence, 0.8)` |
| ≥ 3 engines agree | Auto-confirm: `confidence = 0.95` |

### Tasks
- [ ] Implement `app/services/confidence.py` [NEW] with formula + rules
- [ ] Add confidence calculation to normalization pipeline
- [ ] Write test cases with known FP/TP scenarios
- [ ] Add quality gate enforcement (FP rate tracking)

---

## 5. Milestone 4 — RAG Upgrade & Remediation Layer

**Goal:** Upgrade the existing RAG pipeline to consume structured issue packets and produce structured remediation packets with WCAG, ARIA APG, ACT, and COGA references.

### 5.1 Corpus Expansion

Ingest these authoritative sources into the vector store:

| Source | URL | Purpose | Chunk Strategy |
|--------|-----|---------|----------------|
| **WCAG 2.2 Full Spec** | [w3.org/TR/WCAG22](https://www.w3.org/TR/WCAG22/) | All success criteria definitions | Per criterion |
| **Understanding WCAG 2.2** | [w3.org/WAI/WCAG22/Understanding](https://www.w3.org/WAI/WCAG22/Understanding/) | Detailed explanations per criterion | Per criterion |
| **WCAG 2 at a Glance** | [w3.org/WAI/standards-guidelines/wcag/glance](https://www.w3.org/WAI/standards-guidelines/wcag/glance/) | POUR principles overview | Single doc |
| **What's New in WCAG 2.2** | [w3.org/WAI/standards-guidelines/wcag/new-in-22](https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/) | New criteria context | Single doc |
| **WCAG 3.0 Working Draft** | [w3c.github.io/wcag3/guidelines](https://w3c.github.io/wcag3/guidelines/) | Future-proofing | Per section |
| **WAI-ARIA 1.3 Full Spec** | [w3c.github.io/aria](https://w3c.github.io/aria/) | Roles, states, properties | Per role/pattern |
| **ARIA Authoring Practices Guide** | [w3.org/WAI/ARIA/apg](https://www.w3.org/WAI/ARIA/apg/) | Correct ARIA implementation patterns | Per pattern |
| **COGA — Making Content Usable** | [w3.org/TR/coga-usable](https://www.w3.org/TR/coga-usable/) | Cognitive accessibility patterns | Per objective |
| **COGA Working Draft** | [w3c.github.io/coga/content-usable](https://w3c.github.io/coga/content-usable/) | Live draft with patterns | Per pattern |
| **Cognitive Accessibility at W3C** | [w3.org/WAI/cognitive](https://www.w3.org/WAI/cognitive/) | Research hub | Per section |
| **MDN Accessibility Guide** | [developer.mozilla.org/en-US/docs/Web/Accessibility](https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Information_for_Web_authors) | Practical developer reference | Per guide |
| **axe-core Rules** | [github.com/dequelabs/axe-core](https://github.com/dequelabs/axe-core) | Rule definitions + test cases | Per rule |
| **axe-core API Docs** | [axe-core API.md](https://github.com/dequelabs/axe-core/blob/develop/doc/API.md) | API integration reference | Per section |
| **Playwright A11y Testing** | [playwright.dev/docs/accessibility-testing](https://playwright.dev/docs/accessibility-testing) | Automation patterns | Per section |
| **Playwright ARIA Snapshots** | [playwright.dev/docs/aria-snapshots](https://playwright.dev/docs/aria-snapshots) | A11y tree inspection | Single doc |

### 5.2 Retrieval Expansion Strategy

When an issue arrives, retrieve from **multiple** corpus sections:

```
Issue: "Images missing alt text"
  ├─ WCAG 1.1.1 (criterion definition)
  ├─ Understanding WCAG 1.1.1 (detailed explanation)
  ├─ ARIA APG: img role (correct implementation)
  ├─ COGA: clear labeling objective (cognitive angle)
  └─ axe-core: image-alt rule (how axe detects this)
```

### 5.3 RAG Pipeline Flow

```
IssuePacket
    │
    ▼
┌────────────────┐
│ Query Formatter│  ← Convert issue to natural-language retrieval query
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Hybrid Search  │  ← Semantic (embedding) + keyword (BM25) retrieval
│ Top-K per silo │     from WCAG / ARIA / COGA / axe / MDN silos
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ Reranker       │  ← Cross-encoder reranking for relevance
└───────┬────────┘
        │
        ▼
┌────────────────┐
│ LLM Generation │  ← Structured prompt → RemediationPacket
│ + Grounding    │     Grounded in ONLY the retrieved sources
└───────┬────────┘
        │
        ▼
RemediationPacket
```

### Tasks
- [ ] Add new corpus sources to `app/services/ingestion.py` [MODIFY]
- [ ] Implement multi-silo retrieval in `app/services/retrieval.py` [MODIFY]
- [ ] Add issue-packet → RAG query formatter
- [ ] Update LLM prompt to output `RemediationPacket` schema
- [ ] Add reranker stage (cross-encoder or reciprocal rank fusion)
- [ ] Test RAG accuracy on 20+ known accessibility issues

---

## 6. Milestone 5 — Cognitive & UX Layer

**Goal:** Add checks that no other tool does — cognitive load analysis, readability scoring, CTA/label clarity, navigation complexity, and form usability.

> **Reference:** [Cognitive Accessibility at W3C](https://www.w3.org/WAI/cognitive/) | [COGA — Making Content Usable](https://www.w3.org/TR/coga-usable/)

### 6.1 Cognitive Checks

| Check | What It Measures | Implementation |
|-------|-----------------|----------------|
| **Readability Score** | Flesch-Kincaid, Gunning Fog on visible text | Extract text nodes, compute scores, flag if > Grade 8 |
| **Jargon Scoring** | Technical/domain jargon density | NLP token analysis against common-word corpus |
| **CTA Clarity** | Are call-to-action buttons clear? | LLM evaluation: "Is this CTA unambiguous?" |
| **Label Clarity** | Do form labels describe expected input? | Semantic comparison of label text vs input purpose |
| **Navigation Complexity** | Is the nav structure overwhelming? | Count nav items, nesting depth, assess cognitive load |
| **Form Usability** | Are forms broken into manageable steps? | Count fields per form, check for progress indicators |
| **Error Message Quality** | Are error messages specific and helpful? | NLP analysis: generic "error" vs specific guidance |

### 6.2 File

Create `app/services/cognitive_checks.py` [NEW]:

```python
class CognitiveAnalyzer:
    def analyze_readability(self, text: str) -> dict
    def analyze_jargon(self, text: str) -> dict
    def analyze_cta_clarity(self, buttons: list) -> list[AuditIssue]
    def analyze_label_clarity(self, forms: list) -> list[AuditIssue]
    def analyze_nav_complexity(self, nav_elements: list) -> list[AuditIssue]
    def analyze_form_usability(self, forms: list) -> list[AuditIssue]
    def analyze_error_messages(self, error_elements: list) -> list[AuditIssue]
```

### Tasks
- [ ] Implement `app/services/cognitive_checks.py` [NEW]
- [ ] Add readability and jargon scoring (Flesch-Kincaid, Gunning Fog)
- [ ] Add CTA and label clarity via LLM evaluation
- [ ] Add navigation complexity scoring
- [ ] Add form usability analysis
- [ ] Integrate cognitive findings into main audit pipeline

---

## 7. Milestone 6 — Grouping & Developer Outputs

**Goal:** Group related findings by domain and rule family, then produce multiple output formats optimized for developer consumption.

### 7.1 Grouping Strategy

```
All Deduplicated Issues
         │
         ▼
┌─────────────────────────┐
│ Group by Domain          │
│  ├─ Navigation           │
│  ├─ Forms                │
│  ├─ Content              │
│  ├─ Media                │
│  ├─ Structure            │
│  └─ Cognitive            │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ Sub-group by Rule Family │
│  ├─ color-contrast       │
│  ├─ image-alt            │
│  ├─ aria-roles           │
│  └─ ...                  │
└─────────────────────────┘
```

### 7.2 Output Formats

| Format | Target | Contents |
|--------|--------|----------|
| **JSON API Payload** | VS Code extension, CI integration | Full `AuditResponse` with all issues, groups, scores |
| **Markdown Report** | Human-readable, exportable | Executive summary → grouped findings → fix code blocks |
| **Fix Snippets** | Copy-paste developer workflow | Isolated code diffs: before → after |

### 7.3 Evidence Requirements

For all **critical** and **serious** issues, require:
- HTML snippet of the offending element
- Relevant computed styles (for contrast issues)
- ARIA tree excerpt (for ARIA issues)
- Reproducibility steps (e.g., "Tab to element X, observe no focus indicator")

### Tasks
- [ ] Implement `app/services/grouper.py` [NEW]
- [ ] Implement Markdown report generator in `app/services/report.py` [NEW]
- [ ] Add fix snippet formatter to RAG output
- [ ] Ensure evidence is captured and attached to high-priority issues

---

## 8. Milestone 7 — Evaluation & Benchmark Proof

**Goal:** Prove the engine is better than Lighthouse and axe-core with measurable metrics.

### 8.1 Benchmark Metrics

| Metric | Definition | Target |
|--------|-----------|--------|
| **Coverage Delta** | (Our findings − Lighthouse findings) / Lighthouse findings | ≥ +20% |
| **Precision Proxy** | % of findings verified as true positives by manual review | ≥ 90% |
| **False-Positive Rate** | % of findings marked as FP by reviewers | ≤ 10% |
| **Duplicate Rate** | % of duplicate findings after dedup | ≤ 5% |
| **Runtime** | Time from URL input to final report | Fast ≤ 15s, Deep ≤ 120s |
| **Suggestion Acceptance** | % of fix suggestions accepted by developers | ≥ 60% |

### 8.2 Reference Test Suite

Use these real-world data sources to build the reference test set:

| Source | URL | Purpose |
|--------|-----|---------|
| **WebAIM Screen Reader Survey #10** | [webaim.org/projects/screenreadersurvey10](https://webaim.org/projects/screenreadersurvey10/) | Latest screen reader + browser usage data |
| **WebAIM Survey #9** | [webaim.org/projects/screenreadersurvey9](https://webaim.org/projects/screenreadersurvey9/) | Trend comparison |
| **WebAIM Survey #8** | [webaim.org/projects/screenreadersurvey8](https://webaim.org/projects/screenreadersurvey8/) | Longitudinal analysis |
| **WebAIM Survey #7** | [webaim.org/projects/screenreadersurvey7](https://webaim.org/projects/screenreadersurvey7/) | Historical benchmark |
| **All WebAIM Surveys** | [webaim.org/projects/screenreadersurvey](https://webaim.org/projects/screenreadersurvey/) | Full archive since 2008 |

### 8.3 Comparison Methodology

```
For each URL in test suite:
  1. Run Lighthouse → collect findings
  2. Run axe-core standalone → collect findings
  3. Run OUR engine (Deep) → collect findings
  4. Manual expert review → ground truth
  5. Compute: coverage delta, precision, FP rate, duplicates, runtime
  6. Publish results table
```

### Tasks
- [ ] Build benchmark test suite (10–20 diverse URLs)
- [ ] Implement comparison runner script
- [ ] Implement metrics calculator
- [ ] Generate benchmark report

---

## 9. Milestone 8 — Feedback Intelligence Loop

**Goal:** Learn from developer responses to improve confidence calibration and suggestion quality over time.

### 9.1 Feedback Tracking

For every suggested fix, track:

| State | Meaning |
|-------|---------|
| `accepted` | Developer used the fix as-is |
| `edited` | Developer modified the fix before applying |
| `rejected` | Developer explicitly dismissed the fix |
| `ignored` | Developer took no action |

### 9.2 Confidence Recalibration

```python
# Pseudo-code for periodic recalibration
for rule_id in all_rules:
    accepted = count(feedback[rule_id] == "accepted")
    total = count(feedback[rule_id])
    acceptance_rate = accepted / total

    if acceptance_rate < 0.3:
        lower_default_confidence(rule_id)
    elif acceptance_rate > 0.8:
        raise_default_confidence(rule_id)
```

### 9.3 Version & Recalibrate

- Store feedback in Firebase (or local DB)
- Run recalibration weekly
- Version the confidence model (v1, v2, ...) so regressions can be reverted

### Tasks
- [ ] Add feedback endpoint to `app/routers/audit.py` [MODIFY]
- [ ] Implement feedback storage (Firebase / local DB)
- [ ] Implement recalibration cron job
- [ ] Add confidence model versioning

---

## 10. WCAG 2.2 Full Checklist Mapping

Every item from the accessibility checklist mapped to our engine's detection strategy:

### Level A (Essential) — 40+ checks

| # | Check | WCAG | Engine |
|---|-------|------|--------|
| 1 | Set page language (`<html lang>`) | 3.1.1 | Static |
| 2 | Unique page titles | 2.4.2 | Static |
| 3 | Use semantic HTML landmarks | 1.3.1 | Static |
| 4 | Linear content flow (DOM = visual order) | 1.3.2 | Static + Browser |
| 5 | Keyboard accessible elements | 2.1.1 | Browser (Playwright Tab) |
| 6 | Remove keyboard traps | 2.1.2 | Browser (Tab loop detection) |
| 7 | No positive tabindex | Best Practice | Static |
| 8 | Proper modal focus management | 2.4.3 | Browser (modal probe) |
| 9 | Don't convey info by color alone | 1.4.1 | Static + Heuristic |
| 10 | Subtle animations (no flashing) | 2.3.1 | Browser (animation scan) |
| 11 | Group related form fields | 1.3.1 | Static |
| 12 | Display errors in accessible list | 3.3.1 | Static + Heuristic |
| 13 | Associate errors with inputs | 3.3.1 | Static (aria-describedby) |
| 14 | Associate labels with all inputs | 1.3.1 | Static + axe-core |
| 15 | Don't rely on sensory characteristics | 1.3.3 | Heuristic (NLP) |
| 16 | Make labels unique and descriptive | 2.4.6 | Heuristic |
| 17 | Semantic table elements | 1.3.1 | Static |
| 18 | `<th>` with scope for headers | 1.3.1 | Static |
| 19 | `<caption>` for tables | 1.3.1 | Static |
| 20 | Links visually recognizable | 1.4.1 | Static + Browser |
| 21 | Self-explanatory link text | 2.4.4 | Heuristic (NLP) |
| 22 | Correct element for purpose | 4.1.2 | Static |
| 23 | Label buttons with no text | 4.1.2 | Static + axe-core |
| 24 | Add alt text to all images | 1.1.1 | Static + axe-core |
| 25 | Decorative images: `alt=""` | 1.1.1 | Static |
| 26 | Complex image descriptions | 1.1.1 | Heuristic |
| 27 | Image text in alt | 1.1.1 | Heuristic (OCR potential) |
| 28 | Prevent media autoplay | 1.4.2 | Static + Browser |
| 29 | Media pausable | 2.2.2 | Browser |
| 30 | Accessible media controls | 4.1.2 | Static + axe-core |
| 31 | Video captions | 1.2.2 | Static |
| 32 | Audio transcripts | 1.2.1 | Heuristic |
| 33 | No seizure triggers | 2.3.1 | Browser (flash detection) |
| 34 | No focus-triggered changes | 3.2.1 | Browser |
| 35 | No input-triggered changes | 3.2.2 | Browser |
| 36 | Prefer native HTML over ARIA | Best Practice | Static |
| 37 | ARIA roles for custom elements | 4.1.2 | Static + axe-core |
| 38 | Dynamic ARIA states updated | 4.1.2 | Browser (ARIA tree) |
| 39 | Accessible names for unlabeled elements | 4.1.2 | Static + axe-core |
| 40 | Hide decorative content from SR | 4.1.2 | Static |
| 41 | Only one `<h1>` per page | 1.3.1 | Static |
| 42 | Don't skip heading levels | 1.3.1 | Static |
| 43 | Proper list markup | 1.3.1 | Static |
| 44 | Skip navigation link | 2.4.1 | Static |
| 45 | Use headings to structure content | 1.3.1 | Static |

### Level AA (Standard) — 15+ checks

| # | Check | WCAG | Engine |
|---|-------|------|--------|
| 1 | Ensure zoom functionality (viewport meta) | 1.4.4 | Static |
| 2 | Don't remove focus styles | 2.4.7 | Browser (computed styles) |
| 3 | Support responsive reflow (no horizontal scroll at 320px) | 1.4.10 | Browser (viewport resize) |
| 4 | Support custom fonts | 1.4.12 | Browser |
| 5 | Autocomplete for relevant inputs | 1.3.5 | Static |
| 6 | Focus states on controls | 2.4.7 | Browser |
| 7 | Mark language changes in content | 3.1.2 | Heuristic (language detection) |
| 8 | Links opening new window identified | 3.2.5 | Static |
| 9 | Target size ≥ 24px | 2.5.8 | Browser (computed size) |
| 10 | Normal text contrast 4.5:1 | 1.4.3 | axe-core + Static |
| 11 | Large text contrast 3:1 | 1.4.3 | axe-core + Static |
| 12 | Text over image contrast | 1.4.3 | Browser (overlay analysis) |
| 13 | Contrast on all themes | 1.4.3 | Browser (theme toggle) |
| 14 | Icon contrast 3:1 | 1.4.11 | Browser |
| 15 | UI component contrast 3:1 | 1.4.11 | axe-core + Browser |
| 16 | Multiple ways to find content | 2.4.5 | Heuristic |
| 17 | Descriptive headings | 2.4.6 | Heuristic (NLP) |
| 18 | Avoid images of text | 1.4.5 | Heuristic (OCR) |
| 19 | Announce dynamic content changes (aria-live) | 4.1.3 | Browser (mutation observer) |

### Level AAA (Enhanced) — 5+ checks

| # | Check | WCAG | Engine |
|---|-------|------|--------|
| 1 | Respect `prefers-reduced-motion` | 2.3.3 | Browser |
| 2 | Respect `prefers-color-scheme` | Best Practice | Browser |
| 3 | Respect `prefers-contrast` | Best Practice | Browser |
| 4 | Define unusual terms | 3.1.3 | Cognitive (NLP) |
| 5 | Explain abbreviations | 3.1.4 | Cognitive (NLP) |
| 6 | Enhanced contrast (7:1 / 4.5:1) | 1.4.6 | axe-core |
| 7 | Enhanced target size (44px) | 2.5.5 | Browser |

### Testing & Validation (Meta-Checks)

| # | Check | Tool |
|---|-------|------|
| 1 | Run accessibility audits | Lighthouse + Our Engine |
| 2 | Add linting to build process | `eslint-plugin-jsx-a11y` integration |
| 3 | Validate color contrast | axe-core + manual |
| 4 | Test keyboard-only navigation | Playwright Tab automation |
| 5 | Test with screen readers | Manual (VoiceOver, NVDA, JAWS, TalkBack) |
| 6 | Test at 200% zoom | Playwright viewport |
| 7 | Test with increased font size | Playwright + OS settings |
| 8 | Test color blindness modes | Browser devtools simulation |
| 9 | Test blurry vision simulation | Browser devtools simulation |
| 10 | Verify focus management | Playwright + Manual |
| 11 | Test on mobile devices | Manual touch testing |

---

## 11. Authoritative Resource Registry

All curated resources organized by category, to be used as RAG corpus sources and reference material:

### 🔴 Core Standards (Non-Negotiable)

| Resource | URL | Use In Engine |
|----------|-----|---------------|
| WCAG 2.2 Full Specification | https://www.w3.org/TR/WCAG22/ | RAG corpus: criterion definitions |
| WCAG 2 Overview | https://www.w3.org/WAI/standards-guidelines/wcag/ | RAG corpus: POUR principles |
| What's New in WCAG 2.2 | https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ | RAG corpus: new criteria context |
| WCAG 2 at a Glance | https://www.w3.org/WAI/standards-guidelines/wcag/glance/ | RAG corpus: quick reference |
| Understanding WCAG 2.2 | https://www.w3.org/WAI/WCAG22/Understanding/ | RAG corpus: detailed explanations |
| WCAG 3.0 Working Draft | https://w3c.github.io/wcag3/guidelines/ | RAG corpus: future-proofing |

### 🟠 WAI-ARIA

| Resource | URL | Use In Engine |
|----------|-----|---------------|
| WAI-ARIA Overview | https://www.w3.org/WAI/standards-guidelines/aria/ | RAG corpus: ARIA overview |
| WAI-ARIA 1.3 Full Spec | https://w3c.github.io/aria/ | RAG corpus: roles/states/properties |
| ARIA Authoring Practices Guide | https://www.w3.org/WAI/ARIA/apg/ | RAG corpus: implementation patterns |

### 🟡 Cognitive Accessibility (Differentiator)

| Resource | URL | Use In Engine |
|----------|-----|---------------|
| Cognitive Accessibility at W3C | https://www.w3.org/WAI/cognitive/ | RAG corpus: cognitive research |
| Making Content Usable — COGA | https://www.w3.org/TR/coga-usable/ | RAG corpus: cognitive patterns |
| COGA Working Draft (GitHub) | https://w3c.github.io/coga/content-usable/ | RAG corpus: live draft patterns |
| COGA Task Force Work Statement | https://www.w3.org/WAI/about/groups/task-forces/coga/work-statement/ | Reference: COGA scope |

### 🟢 Testing Tools & Rule Engines

| Resource | URL | Use In Engine |
|----------|-----|---------------|
| axe-core GitHub Repository | https://github.com/dequelabs/axe-core | Rule engine integration |
| axe-core API Documentation | https://github.com/dequelabs/axe-core/blob/develop/doc/API.md | API reference |
| axe-core Developer Guide | https://github.com/dequelabs/axe-core/blob/develop/doc/developer-guide.md | Custom rule development |
| axe DevTools (Deque) | https://www.deque.com/axe/axe-core/ | Commercial reference |
| Playwright Accessibility Testing | https://playwright.dev/docs/accessibility-testing | Browser probe implementation |
| Playwright ARIA Snapshots | https://playwright.dev/docs/aria-snapshots | A11y tree capture |

### 🔵 Real User Research

| Resource | URL | Use In Engine |
|----------|-----|---------------|
| Screen Reader Survey #10 (2024) | https://webaim.org/projects/screenreadersurvey10/ | Priority calibration |
| Screen Reader Survey #9 (2021) | https://webaim.org/projects/screenreadersurvey9/ | Trend comparison |
| Screen Reader Survey #8 (2019) | https://webaim.org/projects/screenreadersurvey8/ | Longitudinal analysis |
| Screen Reader Survey #7 (2017) | https://webaim.org/projects/screenreadersurvey7/ | Historical benchmark |
| All WebAIM Surveys Index | https://webaim.org/projects/screenreadersurvey/ | Full archive |

### 🟣 Reference & Developer Docs

| Resource | URL | Use In Engine |
|----------|-----|---------------|
| MDN Accessibility Guide | https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Information_for_Web_authors | RAG corpus: dev reference |
| Wikipedia — WCAG History | https://en.wikipedia.org/wiki/Web_Content_Accessibility_Guidelines | Context / background |

### ⚪ Regulatory & Legal

| Resource | URL | Use In Engine |
|----------|-----|---------------|
| U.S. Access Board — WCAG 2.2 | https://www.access-board.gov/news/2023/11/27/w3c-wcag-2-2-now-available/ | Compliance context |
| AllAccessible — WCAG 2.2 Guide 2025 | https://www.allaccessible.org/blog/wcag-22-complete-guide-2025 | Practical compliance guide |

---

## 12. Data Flow Diagram

### End-to-End Audit Flow

```
[1] User submits URL + scan mode (Fast/Deep)
         │
         ▼
[2] Crawl Queue: identify pages, handle SPA routing
         │
         ▼
[3] Renderer: Playwright renders full DOM + captures ARIA tree
         │
         ├──────────────────────┬──────────────────────┐
         ▼                      ▼                      ▼
[4a] Static Checks        [4b] Browser Probes     [4c] axe-core
   • HTML semantics           • Keyboard nav          • 80+ rules
   • Headings                 • Focus traps           • Contrast
   • Images/alt               • Modal focus           • ARIA
   • Forms/labels             • Responsive            • Labels
   • Links/buttons            • Zoom/animation        • Structure
   • Tables/lists             • ARIA tree snap
   • Media                    • Focus styles
         │                      │                      │
         └──────────┬───────────┴──────────────────────┘
                    ▼
[5] Normalize → all findings → unified AuditIssue schema
                    │
                    ▼
[6] Deduplicate → key: (url, selector, rule_id)
    • 2+ engines agree → boost confidence
    • 1 engine only → flag for review
                    │
                    ▼
[7] Confidence Scoring → formula: source + signal + agreement + evidence
    • Heuristic-only → "needs-review"
    • Low confidence → auto-downgrade severity
    • Multi-engine → auto-confirm
                    │
                    ▼
[8] (Deep only) Cognitive/UX Checks
    • Readability + jargon
    • CTA + label clarity
    • Nav complexity + form usability
                    │
                    ▼
[9] Group by domain + rule family → rank by severity
                    │
                    ▼
[10] RAG Pipeline: issue packets → retrieval → LLM → remediation packets
     • WCAG + Understanding + ARIA APG + COGA + axe rules
     • Structured remediation with confidence + manual-review flag
                    │
                    ▼
[11] Merge: issues + remediation → final enriched report
                    │
                    ├──────────────────┬──────────────────┐
                    ▼                  ▼                  ▼
            JSON API Payload    Markdown Report    Fix Snippets
            (for extensions)    (human-readable)   (copy-paste)
```

---

## 13. File & Module Map

### Current Project Structure

```
DJ HACK/
├── app/
│   ├── __init__.py
│   ├── config.py              ← Add scan modes, quality gates
│   ├── main.py                ← FastAPI app entry point
│   ├── models.py              ← ★ Extend AuditIssue, add IssuePacket/RemediationPacket
│   ├── data/
│   ├── routers/
│   │   ├── audit.py           ← ★ Add feedback endpoint
│   │   └── rag.py             ← Existing RAG endpoint
│   └── services/
│       ├── audit_runner.py    ← ★ Orchestrate multi-engine pipeline
│       ├── embedding.py       ← Existing embedding service
│       ├── ingestion.py       ← ★ Add new corpus sources
│       ├── llm.py             ← ★ Update prompt for RemediationPacket
│       ├── retrieval.py       ← ★ Add multi-silo hybrid retrieval
│       └── vector_store.py    ← Existing vector store
├── corpus/
│   └── wcag-aaa-web-design/   ← Existing corpus
├── chroma_db/                 ← Vector DB storage
├── resources/
│   ├── plan.txt               ← Original plan
│   ├── accessbility_checklist.txt
│   └── Accessibility_Resource_Master_List.docx
└── requirements.txt
```

### New Files to Create

```
app/services/
├── static_checks.py       [NEW] Static HTML analysis (M2)
├── heuristics.py          [NEW] AI/NLP quality heuristics (M2)
├── browser_probes.py      [NEW] Playwright dynamic probes (M2)
├── normalizer.py          [NEW] Multi-engine result normalization (M2)
├── dedup_engine.py        [NEW] Deduplication engine (M2)
├── confidence.py          [NEW] Confidence scoring & FP control (M3)
├── cognitive_checks.py    [NEW] Cognitive/UX analysis (M5)
├── grouper.py             [NEW] Domain/rule family grouping (M6)
├── report.py              [NEW] Markdown report generator (M6)
└── feedback.py            [NEW] Feedback tracking & recalibration (M8)
```

---

## Summary: What Makes This Better Than Lighthouse

| Capability | Lighthouse | axe-core | **Our Engine** |
|-----------|-----------|---------|----------------|
| WCAG 2.2 A/AA coverage | Partial | Good | **Full (60+ checks)** |
| WCAG AAA coverage | None | None | **Partial (7+ checks)** |
| Cognitive/UX checks | None | None | **✅ (7 checks)** |
| AI-powered alt text quality | None | None | **✅** |
| Vague link/button detection | Basic | Basic | **✅ NLP-enhanced** |
| Browser dynamic probes | Some | None | **✅ Full Playwright** |
| Confidence scoring | None | None | **✅ Multi-signal** |
| False-positive control | None | None | **✅ Auto-downgrade** |
| RAG-backed remediation | None | None | **✅ Grounded in WCAG+COGA+ARIA** |
| Fix code snippets | None | None | **✅ Ready-to-paste** |
| Feedback learning loop | None | None | **✅ Continuous improvement** |
| COGA integration | None | None | **✅ Cognitive accessibility** |
| Multi-format output | Single | JSON | **✅ JSON + MD + Snippets** |
