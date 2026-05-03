# BEACON Testing Toolkit

Hierarchy of tests to ensure production reliability and zero-regression.

## Quick Reference Cheatsheet

| When | Command (Bash/Linux) | Command (Windows/PS) |
|---|---|---|
| Every push | `./testing_toolkit/run_tier_1.sh` | `.\testing_toolkit\run_tier_1.ps1` |
| Every release | `./testing_toolkit/run_tier_2.sh` | `.\testing_toolkit\run_tier_2.ps1` |
| Every Monday | `Tier 3 (Weekly)` | `Tier 3 (Weekly)` |
| First of month | `Tier 4 (Monthly)` | `Tier 4 (Monthly)` |
| After major changes | `Tier 5 (Manual/One-off)` | `Tier 5 (Manual/One-off)` |

## Tiers Breakdown

### Tier 1: Every Push
- **Syntax Checks**: Ensures core modules are valid Python.
- **Unit Tests**: Full `tests/unit/` suite.
- **ACT Benchmark**: 1.00 F1 score verification.
- **WebAIM Six**: Core accessibility detection.
- **Fast Mode Smoke**: ~40s integration test.

### Tier 2: Pre-Release
- **Site Archetypes**: Verification of common layouts (10/10).
- **All Scan Modes**: Full integration coverage.
- **Contrast-Finder**: Mathematical correctness check.
- **IBM/Cognitive**: Engine stability and flag verification.
- **A11YBench**: Regression safety net.

### Tier 3: Weekly
- Full ACT suite (~80 rules).
- GenA11y 148-page benchmark.
- Lighthouse pipeline verification.

### Tier 4: Monthly
- AccessGuru semantic baseline.
- Full A11YBench 60-project suite.
- Production 10-site benchmark.

### Tier 5: Manual / One-off
- Supabase E2E write tests.
- Health endpoint verification.
- RAG/LLM intelligence checks.
