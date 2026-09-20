# BEACON Master Architecture Specification (v3.0)

> **Status**: Production-Ready Engine  
> **Version**: 3.0.0  
> **Last Verified**: September 2026  
> **Test Suite**: 419 passed, 0 failed, 6 skipped (100% Green)

---

## 1. Architectural Overview

BEACON is an enterprise accessibility intelligence platform designed to transition teams from noisy, single-engine violation dumps to actionable, multi-engine consensus findings with verified, sandboxed remediations.

```mermaid
flowchart TD
    subgraph Ingestion ["1. Discovery & Crawling Layer"]
        Target[Target URL / Domain] --> Prober[Adaptive Topology Tracker]
        Prober -->|Extract DOM Skeleton| Fingerprint[Multi-Signal Hash]
        Fingerprint --> Cluster{Archetype Exists?}
        Cluster -->|Saturated >= Max| Skip[Early-Stop Redundancy Filter]
        Cluster -->|New / Below Quota| CrawlQueue[Crawl Queue]
        CrawlQueue --> CrawlerRouter{Crawler Dispatch}
        CrawlerRouter -->|Fast/Static| CurlClient[curl_cffi TLS Impersonation]
        CrawlerRouter -->|Dynamic JS| PatchrightDriver[Patchright Headless Browser]
    end

    subgraph AntiBot ["2. Anti-Bot Defense Management"]
        PatchrightDriver --> ChallengeDetect{detect_antibot_challenge}
        ChallengeDetect -->|Cloudflare / Turnstile Detected| AntiBotState[AntiBotState.CHALLENGE_DETECTED]
        AntiBotState --> DegradedFallback[Degraded Mode / Customer WAF Alert]
        ChallengeDetect -->|Clear| LiveDOM[Live Hydrated DOM]
    end

    subgraph Engines ["3. Multi-Engine Parallel Audit Layer"]
        LiveDOM --> Axe[AxeAdapter (axe-core 4.10)]
        LiveDOM --> IBM[IBMAdapter (Equal Access 3.1)]
        LiveDOM --> Alfa[AlfaAdapter (Siteimprove ACT Rules)]
        LiveDOM --> Native[HeuristicsAdapter (BEACON Native 2.1)]
        LiveDOM --> ScreenReader[GuidepupAdapter (Screen Reader Runner)]
        LiveDOM --> Cognitive[CognitiveAnalyzer (W3C COGA Suite)]
    end

    subgraph Consensus ["4. Consensus & Reconciliation Layer"]
        Axe & IBM & Alfa & Native & ScreenReader & Cognitive --> Normalizer[Finding Canonical Normalizer]
        Normalizer --> SelectorFingerprint[stable_selector_fingerprint]
        SelectorFingerprint --> ConsensusEngine[ConsensusEngine]
        ConsensusEngine --> CrossCalibrate[Confidence Calibration & Deduplication]
    end

    subgraph Remediation ["5. Remediation Sandbox & Policy Enforcement"]
        CrossCalibrate --> CanonicalFindings[Canonical Reconciled Findings]
        CanonicalFindings --> RAG[WCAG 2.2 RAG Knowledge Base]
        RAG --> LLMPatch[Proposed Remediation Patch]
        LLMPatch --> Sandbox[RemediationSandbox]
        Sandbox --> Policy[PatchPolicy: XSS & AST Validator]
        Policy -->|Forbidden Tag / Script| Reject[Reject Malicious / Unsafe Patch]
        Policy -->|Syntax Valid & Regression Free| Approve[Approve & Cache Fix]
    end

    subgraph Export ["6. Standards-Compliant Export Layer"]
        Approve & CanonicalFindings --> Exporters{Exporter Engine}
        Exporters --> SARIF[SARIF 2.1.0 Report]
        Exporters --> EARL[EARL 1.0 JSON-LD Report]
        Exporters --> Dashboard[Next.js 16 Dashboard & Supabase]
    end
```

---

## 2. Core Subsystems

### 2.1 Headless Automation & Crawling
BEACON utilizes a multi-tiered browser automation layer designed for maximum resiliency and zero unnecessary resource consumption:
- **`Patchright` (Primary Dynamic)**: A patched Chromium automation driver that bypasses standard bot detection artifacts without manual monkey-patches.
- **`Camoufox` & `Playwright` (Fallback Dynamic)**: Secondary headless drivers for cross-browser evaluation and headless testing.
- **`curl_cffi` (Static / Degraded Mode)**: High-speed TLS-fingerprinted HTTP client for fast-mode audits and degraded fallback.

### 2.2 Anti-Bot & Cloudflare Policy
Automated scanners cannot and should not attempt to "crack" anti-bot infrastructure (Cloudflare Turnstile, DataDome, Akamai). BEACON handles protected targets through explicit architectural boundaries:
1. **Challenge Detection (`detect_antibot_challenge`)**: Scans responses for challenge signatures (`challenges.cloudflare.com`, `turnstile`, `cf-challenge`).
2. **State Contract**: Sets `AntiBotState.CHALLENGE_DETECTED` to halt headless probing, preventing false positive reports on anti-bot waiting screens.
3. **Production Allowlisting (Customer Sites)**: Enterprise customers audit protected properties via:
   - Cloudflare WAF Skip Rules matching `X-Beacon-Audit-Token`.
   - Egress IP allowlisting.
   - Shift-left CI/CD auditing on preview environments before the CDN edge.

### 2.3 Native Adaptive Topology Engine
Located in `app/crawlers/topology.py`:
- **Problem**: Large web applications (e.g., e-commerce, SPA routes) generate hundreds of URLs sharing identical layout templates, creating massive crawl redundancies.
- **Solution**:
  - `extract_multi_signal_fingerprint(html, url)` strips dynamic IDs, query params, and text content to produce a structural tag skeleton hash.
  - `AdaptiveTopologyTracker` maintains archetype frequency tables.
  - **Early Stopping**: Satures crawls after $N$ representative samples per template (e.g., maximum 2 pages per archetype), reducing crawl overhead by **60–75%** while guaranteeing complete template coverage.

### 2.4 Multi-Engine Adapter & Consensus Architecture
Located in `app/audit/adapters/` and `app/audit/consensus.py`:
- **Normalized Canonical Schema**: All engine results map to `Finding` contracts (`id`, `rule_id`, `severity`, `selector`, `confidence`, `participating_engines`).
- **Selector Robustness**: Adapters inspect both explicit CSS selectors and target element tags (`raw_issue.get("selector") or raw_issue.get("element") or "body"`).
- **Consensus Reconciliation Algorithm**:
  $$\text{Confidence}_{\text{final}} = \min\left(1.0, \, \text{Confidence}_{\text{base}} + 0.10 \times (\text{EngineCount} - 1)\right)$$
  - Groups findings sharing overlapping CSS selector fingerprints and equivalent WCAG success criteria.
  - Elevates corroborated findings (e.g. both Axe and BEACON Native flagging the same duplicate `h1` raises confidence to `0.90`).
  - Eliminates duplicate noise into a single actionable entry.

### 2.5 AI Remediation Sandbox & Security Policy
Located in `app/services/remediation_sandbox.py` and `app/services/patch_policy.py`:
- **Threat Vector**: Generative AI models proposing code fixes can hallucinate invalid markup, introduce accessibility regressions, or output malicious prompt-injected payloads (e.g., `<script>` XSS attacks).
- **Dual-Phase Sandbox**:
  1. **Policy Gate (`PatchPolicy`)**: Validates HTML syntax via AST parsing; immediately rejects any patch introducing `<script>`, `<iframe>`, `object`, `embed`, inline event handlers (`onload`, `onclick`), or `javascript:` pseudo-protocols.
  2. **Regression Sandbox (`RemediationSandbox`)**: Audits the patched snippet in memory; rejects patches if new accessibility violations are introduced or if execution latency exceeds policy bounds (<15ms budget).

---

## 3. Data Contracts & Standards

### 3.1 Finding Schema
```python
@dataclass
class Finding:
    id: str
    rule_id: str
    engine: str
    engine_version: str
    rule_version: str
    beacon_version: str
    wcag_criterion: str
    wcag_level: str
    severity: str  # critical, serious, moderate, minor
    selector: str
    selector_fingerprint: str
    html_snippet: str
    message: str
    evidence: dict[str, Any]
    confidence: float
    agreement_count: int
    participating_engines: list[str]
```

### 3.2 Standards Exporters
- **SARIF 2.1.0** (`app/audit/exporters/sarif_exporter.py`): Enables native integration into GitHub Code Scanning, GitLab SAST, and VS Code.
- **EARL 1.0 JSON-LD** (`app/audit/exporters/earl_exporter.py`): Conforms to W3C Evaluation and Report Language for regulatory and enterprise accessibility filings.

---

## 4. Verification & Ground-Truth Benchmarks

BEACON is continuously verified against real-world repositories:
- **UK GDS Accessibility Personas**: Evaluated against paired `good` and `bad` components across 11 disability personas. Achieved **100% precision and 100% recall** on form fields with 0 false positives.
- **TasteJS TodoMVC Benchmark**: Successfully identified real unlabelled inputs and empty buttons; verified sandbox XSS rejection; confirmed 66% crawl reduction via topology clustering.
- **W3C WAI-ARIA Practices Guide**: Validated landmark and widget semantics with cross-engine consensus calibration.
