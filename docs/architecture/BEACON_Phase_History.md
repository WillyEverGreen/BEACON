# BEACON Development History (Phases 1 ??? 20)

This document provides a cohesive historical context of the BEACON platform???s evolution. It details the journey from our initial pipeline setup (Phase 1) up until the massive pre-production crawler hardening cycle (Phase 20).

---

## Early Pipeline Foundations (Phases 1 ??? 7)
The earliest phases focused on establishing a deterministic baseline for automated accessibility auditing.

*   **Phase 1 & 2 ??? Core Pipeline & Reliability Setup:** Established the foundational backend correctness, defined the pipeline ordering, set scoring constants, created the audit logging mechanism, and generated initial evaluation artifacts.
*   **Phase 3 & 4 ??? Crawler & Rules Baseline:** Expanded rule sets and basic crawling mechanics, laying the groundwork for more complex interactions and UI integrations. 
*   **Phase 5 ??? Deterministic Scoring:** Built out the deterministic scoring and prioritization engine with full validation, ensuring identical DOMs produce identical accessibility scores every single time without flake.
*   **Phase 6 ??? Architecture Stabilization:** Addressed UI transparency, wiring scraped page metrics into the database and early Dashboard APIs.
*   **Phase 7 ??? Async Orchestration:** Completely overhauled the API layer to be fully asynchronous, introducing robust job orchestration, validation, security measures, and concurrent crawl support.

---

## Intelligence & Suppressions (Phases 8 ??? 12)
These phases were transitional periods where we realized raw crawling wasn't enough; we required intelligent filtering and failure handling.

*   **Phases 8 ??? 11 ??? Core Extensions:** Continuous evolution of the audit engines (Axe-core, custom interactive engines) and bringing the Next.js UI up to parity with the backend schema.
*   **Phase 12 ??? Suppression Fixes:** Addressed critically low WCAG ACT (Accessibility Conformance Testing) recall by implementing intelligent suppression fixes to manage false positives and improve scan accuracy.

---

## Engine Consistency & Hardening (Phases 13 ??? 16)
At this point, the platform shifted focus heavily towards production reliability against complex, real-world JavaScript heavy applications.

*   **Phase 13 ??? Failure Normalisation & Mode Consistency:** Addressed significant mode-consistency gaps where `fast` vs `deep` vs `max` modes were returning heavily divergent failures (e.g., `extraction_failure` vs `network_error`). Established the strict rule that CI must fail if modes diverge unexpectedly on test fixtures.
*   **Phase 14 ??? Crawler Production Hardening:** Imposed stability controls on the DOM snapshot routines and internal crawler loops.
*   **Phase 15 ??? ACT Coverage Uplift:** Significantly elevated our coverage of W3C ACT specs with the integration of targeted custom rules.
*   **Phase 16 ??? Operational Hardening (The Great Stack Upgrade):** Swapped out legacy HTTP libraries (`httpx`) for `curl_cffi` to evade basic TLS fingerprinting/bot blocks. Replaced vanilla Playwright Chromium with `Camoufox` to provide high-grade browser stealth capabilities for all dynamic audits.

---

## Runtime Intelligence & Production Readiness (Phases 17 ??? 20)
The final hardening cycle preparing BEACON for untethered public crawling.

*   **Phase 17 ??? Runtime Intelligence & Observability:** Implemented massive runtime intelligence upgrades. Added site-level failure profile aggregations, adaptive crawl strategies based on failure types, a domain-level preflight cache, and laid the initial groundwork for a long-term "Domain Learning System" (slated for Phase 18+).
*   **Phases 18 & 19 ??? Crawler Target Triage:** Fired the newly upgraded crawler against a gauntlet of 30 targets. Achieved a 27/30 pass rate initially, resolving edge cases related to heavy bot-walls (e.g., Etsy). Delineated system crashes from expected operational mitigations (like degraded modes).
*   **Phase 20 ??? Topology & Deep Mode Hardening:** The final production-readiness milestone before Lighthouse integration.
    *   **Site Topology Detection:** Centralised topology logic classifying domains into `single_page`, `thin`, `deep_uniform`, `paginated`, or `multi_template` structures before deciding the crawl budget.
    *   **Unified Limits:** Stripped all hardcoded caps and introduced `resolve_max_pages()` mapped to the `SCAN_MODES` config block.
    *   **Degraded Mode Contract:** Ensured strictly typed graceful failures where unreachable/bot-blocked sites return `degraded_mode=True` featuring explicit `degraded_reason` strings alongside metadata contexts rather than crashing the pipeline.
    *   **Alembic Migration:** Deployed `81e9864e53a7` to register topology metrics (`site_topology`, `templates_found`, `urls_discovered`) firmly into the `scans` table and presented them successfully on the UI interface.

---

*Moving beyond Phase 20, BEACON moved forward to execute __Phase 21__, integrating the Google Lighthouse CI Enrichment Pipeline and fully scrubbing all legacy architectural components (e.g., purging the archaic "BFS" crawler terminology in favor of "Discovery").*
