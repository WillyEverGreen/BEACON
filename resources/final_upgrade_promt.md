# 🚀 BEACON — ELITE PRODUCTION UPGRADE PROMPT (Phase 9 & 10)

> **Copy this entire prompt into a fresh AI chat. Say: "Start Production Upgrade Execution"**

---

## 🧠 ROLE & SYSTEM PHILOSOPHY

You are a **Principal Engineer & AI Systems Architect** building BEACON into a **self-calibrating, production-grade Accessibility Intelligence Platform**. You do not write one-off patches. You build systems that improve themselves.

**Core Philosophy:**
> Every fix must make the system smarter for the **next** unknown site, not just the current test set.

We do not hardcode rule suppressions. We build an **evidence-based trust layer** that learns from real benchmark truth (ACT) and recalibrates automatically. This is the architectural difference between a demo and a production AI engine.

---

## 📊 CURRENT BASELINE (Fresh ACT + 50-Site Run)

```yaml
# ✅ PASSING
regression_tests:          50/50 passed
fast_p95_time:             8.18s  (target <10s)
timeout_rate:              0.0%
reliability:               92.0%  (target ≥90%)
spa_precision:             100%
spa_recall:                100%

# 🚨 CRITICAL FAILURES (BLOCKERS)
act_micro_precision:       6.60%   (target ≥45%)  ← catastrophic
act_micro_recall:          35.00%  (target ≥50%)  ← significant gap
act_f1:                    11.11%
expectation_alignment:     26.0%   (target ≥70%)  ← 33/50 sites wrong tier

# 🔍 ROOT CAUSE DIAGNOSIS
top_unexpected_rules:      [landmark-one-main, page-has-heading-one, no-headings, target-size-minimum]
top_missing_rules:         [focus-management (dominant), semantic-html]
```

**Key Insight:** The 6.6% precision collapse tells us our confidence scoring is decoupled from real-world evidence. We are not suppressing *wrong rules* — we are failing to *score rules by their proven track record*.

---

## 🏗️ ARCHITECTURAL DIRECTIVE: Build a Self-Improving Audit Engine

Before writing a single line of code, internalize this design constraint:

```
❌ Wrong approach: "Suppress landmark-one-main because it caused FPs today"
✅ Right approach: "landmark-one-main has a 0.22 precision score on ACT truth —
                   downgrade its confidence proportionally and require corroboration"
```

The system must be able to answer: *"Why did we report this issue?"* with a quantifiable trust chain.

---

## 🛠️ PHASE 9: Adaptive Precision & Recall Calibration

### 9.1 — Adaptive Rule Trust Registry **(CORE CHANGE)**

Create `app/data/rule_trust_registry.json`. This becomes the **single source of truth** for how much BEACON trusts each rule, computed from ACT ground truth:

```json
{
  "landmark-one-main": {
    "precision_score": 0.22,
    "recall_score": 0.61,
    "trust_score": 0.35,
    "last_calibrated": "2026-04-10",
    "calibration_source": "ACT-subset-v1",
    "verdict": "noisy",
    "required_engines": 2
  },
  "focus-management": {
    "precision_score": 0.91,
    "recall_score": 0.28,
    "trust_score": 0.48,
    "last_calibrated": "2026-04-10",
    "calibration_source": "ACT-subset-v1",
    "verdict": "underdetected",
    "required_engines": 1
  }
}
```

**Trust Score tiers drive behavior automatically:**
```python
if rule.trust_score < 0.20:
    suppress_entirely()            # Evidence is too weak to report
elif rule.trust_score < 0.40:
    downgrade_confidence(factor=0.6)  # Report but heavily penalize confidence
elif rule.trust_score < 0.60:
    require_multi_engine_corroboration(min_engines=2)
else:
    pass  # Trusted — report normally
```

This means when ACT data says `landmark-one-main` has 22% precision, the system **automatically** becomes skeptical of it — no human needed to hardcode a suppression.

---

### 9.2 — Continuous ACT Feedback Loop **(SELF-IMPROVEMENT)**

Create `app/services/rule_calibrator.py`. After every ACT benchmark run, this module auto-updates `rule_trust_registry.json`:

```python
def recalibrate_from_act_results(act_results: dict):
    """
    Ingests ACT benchmark output and updates rule trust scores.
    This is the core self-improvement loop.
    """
    for rule_id, metrics in act_results["per_rule_metrics"].items():
        tp = metrics["tp"]
        fp = metrics["fp"]
        fn = metrics["fn"]

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0

        # Harmonic trust: weights precision 2x because FPs destroy user trust faster
        trust_score = (3 * precision * recall) / (2 * precision + recall + 1e-9)

        update_registry(rule_id, precision, recall, trust_score)
        log_calibration_event(rule_id, precision, recall, trust_score)
```

**Result:** Every ACT run makes the system smarter. No human patch cycle needed for known rules.

---

### 9.3 — Confidence Rebalancing Layer **(FIXES PRECISION COLLAPSE)**

Replace the current flat confidence scoring in `app/services/confidence.py`. Confidence must be a **multi-signal product**, not a single static value:

```python
def compute_final_confidence(
    base_confidence: float,
    rule_id: str,
    engine_agreement: float,   # 0.0–1.0, how many engines agree
    behavioral_signal: float,  # 0.0–1.0, from browser probes
) -> float:
    """
    Final confidence is a calibrated, evidence-weighted score.
    This prevents both under-reporting and noisy over-reporting.
    """
    trust = get_rule_trust_score(rule_id)  # from rule_trust_registry

    final = (
        base_confidence
        * (0.4 + 0.6 * engine_agreement)   # Engine disagreement is a red flag
        * (0.5 + 0.5 * trust)              # Low trust = automatic confidence penalty
        * (0.7 + 0.3 * behavioral_signal)  # Behavioral probe corroborates or not
    )
    return round(min(final, 0.99), 4)
```

**Why this fixes everything:**
- A `landmark-one-main` found only by the static engine with trust=0.22 gets a confidence of ~0.28. It will fail the `min_confidence=0.62` gate automatically.  
- A `focus-management` issue found by both browser probe AND static with trust=0.48 gets a confidence of ~0.71. It passes the gate.
- No rules need to be manually excluded ever again.

---

### 9.4 — Hybrid Multi-Signal Detection for Critical Rules **(RECALL FIX)**

For high-priority but under-detected rules (recall < 0.40 in the trust registry — currently `focus-management`, `semantic-html`), implement a **mandatory corroboration strategy** in `app/services/browser_probes.py`:

```python
HYBRID_REQUIRED_RULES = {
    "focus-management": ["static_check", "behavioral_probe", "dom_interaction"],
    "semantic-html":    ["static_check", "dom_structure_heuristic"],
}
```

For each of these rules, ALL listed signal types must be checked and merged before reporting. This prevents both false positives (one noisy signal fires) and false negatives (only checking one channel).

**Specific probes to add for `focus-management`:**
1. Interactive elements with `onclick` but no `tabindex` or role.
2. Modals that don't trap focus (Tab cycles out of the dialog).
3. Custom `<div role="button">` without `keyboard-accessible` event handlers.
4. Hidden elements (`display:none`) receiving `focus()` calls via JS.

---

### 9.5 — Score Integrity & Anti-Gaming Guard **(CREATIVE ADDITION)**

Prevent artificially inflated perfect scores from the production pipeline:

```python
SCORE_INTEGRITY_RULES = {
    # A site can only score 100 if ALL of these pass:
    "perfect_score_conditions": [
        "engines_used_count >= 2",
        "suppression_rate < 0.50",
        "no degraded_mode",
        "avg_confidence > 0.75",
    ],
    # A site with partial audit (403, CSP block) is score-capped:
    "partial_audit_max_score": 82,
    # A site with active low_issue_guard is score-capped:
    "low_signal_max_score": 90,
}
```

**Result:** Amazon can no longer score 100 when we only had 1 issue and suppressed it. It gets capped at 82 because it was a partial audit.

---

### 9.6 — Structured Observability Payloads **(CREATIVE ADDITION)**

Every audit response must include a machine-readable `"trust"` block so callers know exactly what to trust:

```json
{
  "score": 87.3,
  "issues": [...],
  "trust": {
    "confidence_avg": 0.76,
    "suppression_rate": 0.42,
    "data_quality": "high",
    "engines_coverage": {"static": true, "browser": true, "axe": true},
    "calibration_warnings": ["landmark-one-main has low trust (0.35) — treat with caution"],
    "audit_completeness": "full",
    "low_trust_rules_present": ["landmark-one-main"]
  }
}
```

---

## 🔥 PHASE 10: Validation, Scale & Production Gate

### 10.1 — Mandatory Re-Validation Protocol

After Phase 9 code is written, the agent must run this exact sequence before declaring readiness:

```
Step 1: python -m pytest tests/calibration/ -v          # Must stay 50/50
Step 2: python evaluation/benchmark_act.py              # Target: Precision >45%, Recall >50%
Step 3: python evaluation/rule_level_metrics.py         # Top-FP rules must change
Step 4: python evaluation/benchmark_production.py       # 10-site, expectation alignment >70%
```

**Hard gates — do NOT proceed past any failure:**

| Gate | Target | Blocker? |
|------|--------|----------|
| ACT Micro Precision | ≥ 45% | 🚨 YES |
| ACT Micro Recall | ≥ 50% | 🚨 YES |
| ACT F1 | ≥ 48% | 🚨 YES |
| Expectation Alignment | ≥ 70% | 🚨 YES |
| Suppression Warnings | ≤ 2/10 sites | ⚠️ Soft |
| Regression Tests | 50/50 | 🚨 YES |
| Structural FP in output | 0 | 🚨 YES |

### 10.2 — Crawl Reliability Hardening

Fix the 4 partial_load failures from the 50-site run with a robust multi-layer fetch strategy:

```python
# In app/services/fetcher.py (or equivalent)
async def fetch_with_fallback(url: str) -> FetchResult:
    for strategy in [browser_fetch, static_fetch, fallback_api_fetch]:
        try:
            result = await strategy(url)
            result.coverage_strategy = strategy.__name__
            return result
        except (BlockedError, TimeoutError, ProtocolError):
            continue
    return FetchResult(status="failed", coverage_strategy="none")
```

Include user-agent rotation and a `"partial_audit"` status in the response when engines were skipped.

### 10.3 — Deduplication Upgrade

Upgrade to hash+proximity clustering in `app/services/dedup_engine.py`:

```python
def deduplicate_issues(issues: list[dict]) -> list[dict]:
    seen = {}
    for issue in issues:
        cluster_key = f"{issue['rule_id']}:{issue.get('selector', '')[:60]}"
        fingerprint = hashlib.sha256(cluster_key.encode()).hexdigest()[:12]
        if fingerprint not in seen:
            seen[fingerprint] = issue
        else:
            # Keep higher-confidence version
            if issue['confidence'] > seen[fingerprint]['confidence']:
                seen[fingerprint] = issue
    return list(seen.values())
```

---

## 🚦 EXECUTION PROTOCOL

Execute **strictly in this order**. Do not skip ahead:

1. **Create `app/data/rule_trust_registry.json`** — seed it from the ACT per-rule metrics already in `evaluation/retest_act_latest.json`.
2. **Create `app/services/rule_calibrator.py`** — the self-improvement feedback loop.
3. **Update `app/services/confidence.py`** — wire in the multi-signal confidence formula.
4. **Update `app/services/browser_probes.py`** — add the 4 hybrid focus-management probes.
5. **Update `app/services/audit_runner.py`** — apply score integrity caps + trust block output.
6. **Run regression tests.** Must stay at 50/50. Fix any regressions before continuing.
7. **Run `evaluation/benchmark_act.py`.** Report Precision/Recall Delta vs baseline.
8. **Run `evaluation/benchmark_production.py`.** Report Expectation Alignment Delta.
9. **Only then** report a new Go / No-Go verdict.

**Hard Constraints:**
- We do not hardcode rule exclusions as a primary strategy. Every behavioral change must be evidence-driven through the trust registry.
- After Phase 9, every audit issue MUST include a `rule_trust_score` in its metadata.
- The `rule_trust_registry.json` must be updated automatically after each ACT run, not manually.
- Structural FP count in final output must remain 0.

---

## 🎯 DEFINITION OF DONE

We are production-ready when ALL of the following are simultaneously true:

```yaml
act_micro_precision:    ≥ 45%
act_micro_recall:       ≥ 50%
regression_tests:       50/50
expectation_alignment:  ≥ 70%
structural_fp:          0
runtime_success:        ≥ 92%
suppression_warnings:   ≤ 2/10 sites
rule_trust_registry:    exists, auto-updated, seeded from ACT
confidence_formula:     multi-signal, not flat
```

When this state is reached: promote `production` profile to default. Not before.