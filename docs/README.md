# BEACON Documentation

This directory contains all technical documentation for the BEACON Accessibility Intelligence Engine.

---

## Structure

`
docs/
├── README.md                        <- You are here
├── ROADMAP.md                       <- Planned improvements and future work
├── detailed_cli_audit.md            <- Full CLI flag reference
└── architecture/
    ├── master_architecture.md       <- Full system architecture (v2.5)
    ├── ACCESSIBILITY_COVERAGE.md    <- WCAG 2.2 A/AA criterion coverage breakdown
    ├── BEACON_Phase_History.md      <- Development history across all phases
    ├── phase20_rule_distribution.md <- Rule diversity analysis across production sites
    └── beacon_unified_engine.svg    <- System architecture diagram
`

---

## Where to Start

| Goal | Document |
|---|---|
| Understand the full system | [architecture/master_architecture.md](architecture/master_architecture.md) |
| Check WCAG 2.2 coverage | [architecture/ACCESSIBILITY_COVERAGE.md](architecture/ACCESSIBILITY_COVERAGE.md) |
| Use the CLI audit tool | [detailed_cli_audit.md](detailed_cli_audit.md) |
| See development history | [architecture/BEACON_Phase_History.md](architecture/BEACON_Phase_History.md) |
| See what is planned next | [ROADMAP.md](ROADMAP.md) |
| Reference links and tools | [resources.md](resources.md) |

---

## Related

- [Main README](../README.md) - project overview, quick start, API reference
- [Release Notes](../RELEASE_NOTES.md) - per-phase release notes
- [Evaluation suite](../evaluation/) - ACT benchmarks, production benchmarks, site archetype validation
