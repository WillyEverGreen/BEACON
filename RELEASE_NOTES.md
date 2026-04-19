# BEACON Release Notes

## Phase 20 — Production Hardening (April 20, 2026)

### Status: production-ready ✅

### What's New

- **Site topology detection** (`app/services/topology_detector.py`) classifies crawls as
  `single_page`, `thin`, `deep_uniform`, `paginated`, or `multi_template` before page selection.
- **Centralised scan-mode page limits** via `app/config.py::resolve_max_pages()` — all hardcoded
  `max_pages` literals removed from application code.
- **Degraded-mode hardening** — unreachable / bot-blocked sites return `degraded_mode=True` with
  a non-empty `degraded_reason` and all E2 contract fields (`http_client`, `browser_engine`).
- **Alembic migration `81e9864e53a7`** adds `site_topology`, `templates_found`, `urls_discovered`
  columns to the `scans` table.
- **Dashboard observability** — `pages_scanned`, `pages_discovered`, topology label surfaced in
  the Next.js dashboard UI.

### Real-Site Validation

30-run all-modes suite (10 sites × fast / deep / max):

| Mode | PASS | DEGRADED | FAIL |
|------|-----:|---------:|-----:|
| fast |    8 |        2 |    0 |
| deep |    9 |        1 |    0 |
| max  |    9 |        1 |    0 |
| **Total** | **26** | **4** | **0** |

The 4 DEGRADED results (nab.org.in × 3 modes, tiss.edu fast) are expected:
`nab.org.in` is unreachable from this network; `tiss.edu` blocks fast-mode HTTP
but is successfully audited under deep and max modes.

### Rule Diversity

See `docs/phase20_rule_distribution.md`:
- 8 unique rule IDs across the 10 passing sites (gate: ≥5) ✅
- Most dominant rule `heading-order` at 25.0% (gate: ≤70%) ✅

---

## Phase 17-19 — Crawler Stack Hardening (April 2026)

- Status: production-ready for non-blocked / public targets.
- Validation: real-site benchmark 27/30 pass; remaining 3 are confirmed external bot-wall blocks.
- Timeout, retry, and probe hardening for heavy JS sites.
- Etsy / similar bot-walled failures require operational mitigations (egress allowlisting, partner
  proxy pools, or session-cookie injection) — not code-level issues.
