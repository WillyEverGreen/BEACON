"""
Configuration settings loaded from .env file.
Includes scan mode definitions and quality gate thresholds.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AliasChoices, Field
from typing import Optional



# ── Quality Gate Constants ──────────────────────────────────────

QUALITY_GATES = {
    "runtime": {
        "fast_max_seconds": 15,
        "deep_max_seconds": 120,
    },
    "coverage_delta_min": 0.20,       # ≥20% more findings than Lighthouse
    "duplicate_rate_max": 0.05,       # ≤5% duplicate issues after dedup
    "false_positive_rate_max": 0.10,  # ≤10% FP rate
}


# ── Crawler Discovery Configuration ───────────────────────────

CRAWLER_URL_RULES = {
    "binary_extensions": [
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".mp4", ".mp3",
        ".zip", ".gz", ".tar", ".woff", ".woff2", ".ttf", ".eot", ".ico",
    ],
    "tracking_params": [
        "fbclid", "gclid", "mc_eid", "_ga", "ref", "source",
    ],
    "skip_href_prefixes": [
        "mailto:", "tel:", "javascript:", "data:", "#",
    ],
    "skip_path_fragments": [
        "/cdn-cgi/", "/__webpack/", "/static/chunk", "/node_modules/", "/.well-known/",
    ],
    "priority_path_keywords": [
        "/checkout", "/cart", "/basket", "/payment", "/order",
        "/login", "/signin", "/signup", "/register", "/auth",
        "/contact", "/help", "/support", "/accessibility", "/faq",
        "/search", "/results", "/product", "/item", "/listing",
        "/form", "/apply", "/booking", "/schedule", "/subscribe",
        "/dashboard", "/account", "/profile", "/settings",
    ],
}


# ── Scan Mode Runtime Profiles ───────────────────────────────

SCAN_MODE_CONFIG = {
    "fast": {
        "max_pages": 1,
        "crawl_cap": 10,
        "bfs_depth": 1,
        "bfs_pages": 10,
        "dom_pages": 0,
        "stage1_timeout": 12,
        "stage2_timeout": 4,
        "global_sla": 35,
        "concurrency": 5,
    },
    "deep": {
        "max_pages": 12,
        "crawl_cap": 30,
        "bfs_depth": 3,
        "bfs_pages": 30,
        "dom_pages": 0,
        "stage1_timeout": 25,
        "stage2_timeout": 12,
        "global_sla": 120,
        "concurrency": 3,
    },
    "max": {
        "max_pages": 25,
        "crawl_cap": 70,
        "bfs_depth": 4,
        "bfs_pages": 60,
        "dom_pages": 15,
        "stage1_timeout": 40,
        "stage2_timeout": 18,
        "global_sla": 240,
        "concurrency": 2,
    },
}

# Backward-compatible alias expected in some planning/debug paths.
scan_modes = SCAN_MODE_CONFIG

# Global hard caps for stability.
MAX_SCAN_GLOBAL_CAP = 80
MAX_CONCURRENT_SITE_AUDITS = 3

# Dashboard cap defaults (can be overridden by env).
DASHBOARD_DEEP_SCAN_MAX_PAGES = 12
DASHBOARD_MAX_SCAN_MAX_PAGES = 25


# ── Lighthouse Enrichment Constants ────────────────────────────────────────────
# All Lighthouse operational limits live here.
# Nothing is hardcoded in lighthouse_runner.py, lighthouse_mapper.py, or
# lighthouse_enricher.py. When tuning infrastructure, change only this block.
#
# LIGHTHOUSE_MAX_URLS_PER_SCAN    Max URLs per enrichment batch. Hard ceiling.
# LIGHTHOUSE_PER_URL_TIMEOUT_SECONDS  Chrome CLI timeout per individual URL.
# LIGHTHOUSE_GLOBAL_TIMEOUT_SECONDS   Outer safety net for the whole batch.
# LIGHTHOUSE_MAX_CONCURRENT_RUNS  Semaphore bound — prevents Chrome OOM on lean VPS.
# LIGHTHOUSE_CACHE_TTL_SECONDS    In-process result cache TTL.
# LIGHTHOUSE_RETRY_COUNT          Retries allowed for network_unreachable + parse_error only.
# LIGHTHOUSE_RETRY_DELAY_SECONDS  Fixed delay between retry attempts.

LIGHTHOUSE_MAX_URLS_PER_SCAN: int = 5
LIGHTHOUSE_PER_URL_TIMEOUT_SECONDS: int = 90
LIGHTHOUSE_GLOBAL_TIMEOUT_SECONDS: int = 300
LIGHTHOUSE_MAX_CONCURRENT_RUNS: int = 2
LIGHTHOUSE_CACHE_TTL_SECONDS: int = 3600
LIGHTHOUSE_RETRY_COUNT: int = 1
LIGHTHOUSE_RETRY_DELAY_SECONDS: int = 5

# Hard gate: Lighthouse enrichment runs only in these scan modes.
# This is an architectural constraint, not a feature flag.
_LIGHTHOUSE_ELIGIBLE_MODES: frozenset[str] = frozenset({"deep", "max"})


CRAWLER_CONFIG = {
    "sitemap": {
        "timeout_seconds": 8,
        "default_max_pages": 200,
        "fallback_paths": [
            "/sitemap.xml",
            "/sitemap_index.xml",
            "/sitemap-index.xml",
            "/sitemaps/sitemap.xml",
        ],
        "default_priority": 0.5,
        "priority_boost": 0.3,
    },
    "bfs": {
        "default_max_depth": 3,
        "default_max_pages": 100,
        "default_concurrency": 5,
        "timeout_seconds": 15,
        "default_priority": 0.5,
    },
    "dom": {
        "default_max_pages": 30,
        "concurrency": 2,
        "page_timeout_seconds": 20,
        "network_idle_timeout_ms": 12000,
        "ready_state_timeout_ms": 5000,
        "interaction_budget_per_page": 5,
        "early_stop_min_interactions": 2,
        "scroll_steps": 2,
        "interaction_wait_ms": 800,
        "scroll_wait_ms": 1000,
        "max_click_candidates": 10,
        "default_priority": 0.5,
    },
    "orchestrator": {
        "scan_modes": {
            "fast": {
                "cap": int(SCAN_MODE_CONFIG["fast"]["crawl_cap"]),
                "sitemap_max_pages": int(SCAN_MODE_CONFIG["fast"]["crawl_cap"]),
                "sitemap_timeout_seconds": 8,
                "bfs_max_depth": int(SCAN_MODE_CONFIG["fast"]["bfs_depth"]),
                "bfs_max_pages": int(SCAN_MODE_CONFIG["fast"]["bfs_pages"]),
                "dom_max_pages": int(SCAN_MODE_CONFIG["fast"]["dom_pages"]),
                "use_dom": bool(SCAN_MODE_CONFIG["fast"]["dom_pages"] > 0),
            },
            "deep": {
                "cap": int(SCAN_MODE_CONFIG["deep"]["crawl_cap"]),
                "sitemap_max_pages": int(SCAN_MODE_CONFIG["deep"]["crawl_cap"]),
                "bfs_max_depth": int(SCAN_MODE_CONFIG["deep"]["bfs_depth"]),
                "bfs_max_pages": int(SCAN_MODE_CONFIG["deep"]["bfs_pages"]),
                "dom_max_pages": int(SCAN_MODE_CONFIG["deep"]["dom_pages"]),
                "use_dom": bool(SCAN_MODE_CONFIG["deep"]["dom_pages"] > 0),
            },
            "max": {
                "cap": int(SCAN_MODE_CONFIG["max"]["crawl_cap"]),
                "sitemap_max_pages": int(SCAN_MODE_CONFIG["max"]["crawl_cap"]),
                "bfs_max_depth": int(SCAN_MODE_CONFIG["max"]["bfs_depth"]),
                "bfs_max_pages": int(SCAN_MODE_CONFIG["max"]["bfs_pages"]),
                "dom_max_pages": int(SCAN_MODE_CONFIG["max"]["dom_pages"]),
                "use_dom": bool(SCAN_MODE_CONFIG["max"]["dom_pages"] > 0),
            },
        },
        "cross_crawler_agreement_boost": 0.2,
        "shallow_depth_boost": 0.1,
        "shallow_depth_threshold": 2,
    },
}


SITEMAP_MAX_DEPTH = 5

# ── Degraded mode scoring contract ─────────────────────────────────────
# Execution order is STRICT: raw_score → multiply → cap.
# NEVER apply both as additive penalties — they compose, not add.
#   Step 1: raw_score  computed by build_scoring_summary()
#   Step 2: raw_score * DEGRADED_MODE_MULTIPLIER   (in prioritizer.py)
#   Step 3: min(result, DEGRADED_MODE_MAX_SCORE)    (cap in _apply_score_integrity_caps)
# Edge cases:
#   raw_score < DEGRADED_MODE_MAX_SCORE already → multiplier still applies, cap is a no-op.
#   multiplier brings score below 0 → max(0.0, score) guard in build_scoring_summary.
#   e.g. raw=95 → 95*0.85=80.75 → cap no-op → penalty=14.25
#   e.g. raw=100 → 100*0.85=85 → cap to 82.0 → penalty=18.0
DEGRADED_MODE_MULTIPLIER: float = 0.85
DEGRADED_MODE_MAX_SCORE: float = 82.0

# Alias: MAX_SITEMAP_DEPTH mirrors SITEMAP_MAX_DEPTH for forward-compatibility.
MAX_SITEMAP_DEPTH: int = SITEMAP_MAX_DEPTH

CRAWL_ADAPTIVE_STRATEGY = {
    "rate_limit_backoff_seconds": 5.0,
    "max_consecutive_failures": 3,
    "csp_static_fallback_enabled": True,
    "bot_wall_immediate_stop": True,
}

LLM_FIRE_BUDGET_PER_AUDIT = 5
AUDIT_CONCURRENCY_LIMIT = 4


# ── Site Crawl Runtime Limits (Phase 6) ───────────────────────
# These keys are read directly by the Phase 6 crawler orchestration layer.
CRAWL_MAX_PAGES_PER_SITE = 15
CRAWL_MAX_DEPTH = 3
CRAWL_TIMEOUT_PER_PAGE_S = 15
CRAWL_CONCURRENCY = 2


# ── Audit Pipeline Configuration ──────────────────────────────

AUDIT_PIPELINE_CONFIG = {
    "parallel_runner": {
        "concurrency_by_mode": {
            "fast": int(SCAN_MODE_CONFIG["fast"]["concurrency"]),
            "deep": int(SCAN_MODE_CONFIG["deep"]["concurrency"]),
            "max": int(SCAN_MODE_CONFIG["max"]["concurrency"]),
        },
        "max_concurrent_site_audits": int(MAX_CONCURRENT_SITE_AUDITS),
        "page_timeout_stage1_seconds": {
            "fast": int(SCAN_MODE_CONFIG["fast"]["stage1_timeout"]),
            "deep": int(SCAN_MODE_CONFIG["deep"]["stage1_timeout"]),
            "max": int(SCAN_MODE_CONFIG["max"]["stage1_timeout"]),
        },
        "page_timeout_stage2_seconds": {
            "fast": int(SCAN_MODE_CONFIG["fast"]["stage2_timeout"]),
            "deep": int(SCAN_MODE_CONFIG["deep"]["stage2_timeout"]),
            "max": int(SCAN_MODE_CONFIG["max"]["stage2_timeout"]),
        },
        "global_sla_seconds": {
            "fast": int(SCAN_MODE_CONFIG["fast"]["global_sla"]),
            "deep": int(SCAN_MODE_CONFIG["deep"]["global_sla"]),
            "max": int(SCAN_MODE_CONFIG["max"]["global_sla"]),
        },
        "partial_summary_every_pages": 1,
        "event_buffer_max": 1000,
    },
    "journey_simulation": {
        "max_journeys": 3,
        "max_steps_per_journey": 4,
        "max_candidate_urls": 200,
    },
}

# ── Precision Profiles ─────────────────────────────────────────

PRECISION_PROFILES = {
    # Best for production reporting where wrong issues are costly.
    "high_precision": {
        "min_confidence": 0.75,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
    },
    # Tuned balanced profile: preserve high_precision recall while reducing common co-reported FP bundles.
    "tuned_balanced": {
        "min_confidence": 0.75,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
        # If a structural trigger rule is present, suppress noisy companion rules.
        "suppress_when_present": {
            "no-headings": ["no-lang", "missing-lang", "no-main-landmark", "no-title"],
        },
    },
    # Balanced mode keeps broader recall while still filtering weak findings.
    "balanced": {
        "min_confidence": 0.55,
        "include_needs_review": True,
        "exclude_contextual_single_source": False,
    },
    # Ultra-strict mode: only highest-confidence issues.
    # Page-level rules are now handled by the fragment detector instead of hard exclusion.
    "ultra_strict": {
        "min_confidence": 0.95,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
    },
    # Strict mode: high confidence, page-level FPs handled by fragment detector dynamically.
    "strict": {
        "min_confidence": 0.75,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
    },
    # Very-high-precision mode: aggressively filters but lets fragment detector handle page-level rules.
    "very_high_precision": {
        "min_confidence": 0.75,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
        "exclude_rules": [
            "missing-captions",
            "autoplay-media",
            "missing-skip-link",
            "th-no-scope",
            "missing-autocomplete",
            "autocomplete-missing",
        ],
    },
    # High-precision-plus: reduce dominant false positives with per-rule confidence caps
    # while keeping recall-critical rules available.
    "high_precision_plus": {
        "min_confidence": 0.75,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
        # Keep hard exclusions to the worst page-level noise generators only.
        "exclude_rules": [
            "no-main-landmark",
            "no-title",
        ],
        # Require stronger evidence for historically noisy rules instead of full exclusion.
        "per_rule_min_confidence": {
            "no-lang": 0.95,
            "missing-lang": 0.95,
            "missing-captions": 0.92,
            "autoplay-media": 0.92,
            "missing-skip-link": 0.92,
            "th-no-scope": 0.90,
            "missing-autocomplete": 0.90,
            "autocomplete-missing": 0.90,
        },
    },
    # High-precision-recall-boost: remove biggest structural FP generators
    # while lowering thresholds on top FN-heavy rules.
    "high_precision_recall_boost": {
        "min_confidence": 0.75,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
        "exclude_rules": [
            "no-main-landmark",
            "no-title",
        ],
        "per_rule_confidence_override": {
            "text-spacing": 0.55,
            "video-transcript": 0.55,
            "svg-no-accessible-name": 0.55,
            "svg-accessible-name": 0.55,
            "semantic-html": 0.55,
            "link-purpose": 0.55,
            "empty-link": 0.55,
            "aria-valid-attr-value": 0.60,
        },
    },
    # Second-pass profile family:
    # strict/balanced/exploratory are tuned via app/data/rule_quality_policy.json.
    "high_precision_recall_strict": {
        "min_confidence": 0.75,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
    },
    "high_precision_recall_balanced": {
        "min_confidence": 0.75,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
    },
    "high_precision_recall_exploratory": {
        "min_confidence": 0.75,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
    },
    # Medium-precision mode: higher confidence threshold without rule exclusions
    # Aims for ~30-50% precision by raising min_confidence from 0.75 to 0.85
    "medium_precision": {
        "min_confidence": 0.85,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
    },
    # Production profile: tuned for trust via rule_quality_policy.json.
    # Phase 1: opt-in only. Phase 2: A/B test. Phase 3: default.
    "production": {
        "min_confidence": 0.75,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
    },
}

# ── Confidence Weights ──────────────────────────────────────────
# Source reliability reduced to 35% (was 40%) to accommodate user_impact (5%).
# This ensures high-disability-impact issues (e.g. missing-alt for blind users)
# consistently score higher than lower-impact noise.

CONFIDENCE_WEIGHTS = {
    "source_reliability":     0.35,
    "signal_strength":        0.25,
    "cross_engine_agreement": 0.15,
    "evidence_quality":       0.20,
    "user_impact":            0.05,   # NEW: boosts life-critical disability issues
}


SOURCE_RELIABILITY_SCORES = {
    "axe-core":      0.95,
    "static":        0.90,
    "browser-probe": 0.85,
    "heuristic":     0.50,
    "cognitive":     0.60,  # Experimental — lower baseline, isolated to deep mode
}

# ── Cache Observability Counters ────────────────────────────────
# Real-time hit/miss tracking per cache tier. Exposed via GET /audit/cache/stats.
# Without this, you cannot verify that caching is actually working at scale.
CACHE_STATS: dict[str, int] = {
    "page_hits":   0,
    "page_misses": 0,
    "page_writes": 0,
    "dom_hits":    0,
    "dom_misses":  0,
    "dom_writes":  0,
    "cache_evictions": 0,
    "cache_stale_purges": 0,
    "cache_corrupt_entries": 0,
    "llm_hits":    0,
    "llm_misses":  0,
    "llm_writes":  0,
    "retrieval_hits": 0,
    "retrieval_misses": 0,
    "fix_hits":    0,
    "fix_misses":  0,
    "fix_writes":  0,
}


# ── Severity Weights (for scoring) ─────────────────────────────

SEVERITY_WEIGHTS = {
    "critical": 3.0,
    "serious": 2.5,
    "moderate": 1.5,
    "minor": 1.0,
}

# ── Scoring Configuration ───────────────────────────────────────
# Prevents a single noisy rule (e.g. 'region') from collapsing the
# score to 0 by capping the maximum penalty contribution per rule_id.

SCORING_CONFIG = {
    # Max penalty points any single rule_id can contribute to the score.
    # With 338 region violations at 2 pts each = 676 → score 0. Cap at 15.
    "max_penalty_per_rule": 4.0,

    # Max total penalty per severity tier across ALL rules.
    "max_penalty_per_severity": {
        "critical": 30,
        "serious": 25,
        "moderate": 20,
        "minor": 10,
    },

    # Grouped axe issues (is_grouped=True) count as 1 finding for scoring
    # regardless of affected_count.
    "grouped_issue_weight": 1.0,

    # Starting score ceiling (before penalties)
    "score_max": 100,
}

# ── Trust Calibration (Phase 10) ─────────────────────────────
# Config-driven calibration knobs to tune score behavior without rewriting
# detector logic or API contracts.
TRUST_CALIBRATION = {
    "min_confidence_for_scoring": 0.60,
    "min_confidence_for_summary": 0.60,
    "penalty_exponent": 0.65,              # was 0.70 — more aggressive diminishing returns
    "repeat_instance_weight": 0.20,
    "hidden_element_penalty_multiplier": 0.30,
    "above_fold_penalty_multiplier": 1.50,
    "category_base_weights": {
        "critical": 4.0,
        "major": 2.1,
        "minor": 0.8,
    },
    "category_penalty_caps": {
        "critical": 22.0,
        "major": 14.0,
        "minor": 8.0,
    },
    "high_quality_floor": {
        "enabled": True,
        "signal_threshold": 0.85,
        "score_floor": 75.0,
        "max_critical_issues": 0,
        "max_scorable_issues": 8,
        "min_high_confidence_ratio": 0.70,
    },
}

# ── Domain Classification ──────────────────────────────────────

RULE_DOMAIN_MAP = {
    "missing-alt": "content",
    "empty-alt": "content",
    "alt-quality": "content",
    "svg-accessible-name": "content",
    "no-headings": "structure",
    "no-h1": "structure",
    "multiple-h1": "structure",
    "heading-skip": "structure",
    "missing-lang": "structure",
    "missing-label": "forms",
    "input-label": "forms",
    "form-label-missing": "forms",
    "label": "forms",
    "input-name": "forms",
    "autocomplete-missing": "forms",
    "duplicate-label": "forms",
    "empty-link": "navigation",
    "generic-link-text": "navigation",
    "unsafe-external-link": "navigation",
    "clickable-no-role": "aria",
    "button-no-name": "forms",
    "button-name": "forms",
    "role-no-name": "aria",
    "aria-required-parent": "aria",
    "aria-required-children": "aria",
    "aria-allowed-role": "aria",
    "aria-role": "aria",
    "no-lang": "structure",
    "no-title": "structure",
    "no-main-landmark": "structure",
    "no-nav-landmark": "navigation",
    "table-no-headers": "content",
    "table-no-caption": "content",
    "color-contrast": "content",
    "missing-skip-link": "navigation",
    "viewport-zoom": "content",
    "autoplay-media": "media",
    "missing-captions": "media",
    "missing-transcript": "media",
    "media-alternative": "media",
    "letter-spacing": "content",
    "line-height": "content",
    "avoid-inline-spacing": "content",
    "focus-trap": "keyboard",
    "no-focus-style": "keyboard",
    "keyboard-unreachable": "keyboard",
    "positive-tabindex": "keyboard",
    "readability": "cognitive",
    "jargon": "cognitive",
    "cta-clarity": "cognitive",
    "label-clarity": "cognitive",
    "nav-complexity": "cognitive",
    "form-usability": "cognitive",
    "error-message-quality": "cognitive",
}

# ── Rule Type Calibration ─────────────────────────────────────

# hard: deterministic, objective checks
# visual: requires computed styles / rendered browser context
# contextual: language/UX interpretation often requiring manual judgment
RULE_TYPE_MAP = {
    # Hard/static checks
    "missing-alt": "hard",
    "empty-alt": "hard",
    "missing-label": "hard",
    "input-label": "hard",
    "form-label-missing": "hard",
    "label": "hard",
    "input-name": "hard",
    "autocomplete-missing": "hard",
    "duplicate-label": "hard",
    "empty-link": "hard",
    "clickable-no-role": "hard",
    "button-no-name": "hard",
    "button-name": "hard",
    "aria-required-parent": "hard",
    "aria-required-children": "hard",
    "aria-allowed-role": "hard",
    "aria-role": "hard",
    "no-lang": "hard",
    "missing-lang": "hard",
    "no-title": "hard",
    "missing-captions": "hard",
    "media-alternative": "hard",
    "svg-no-accessible-name": "hard",
    "svg-accessible-name": "hard",
    "unsafe-external-link": "hard",
    "no-headings": "hard",
    "no-h1": "hard",
    "multiple-h1": "hard",
    "heading-skip": "hard",
    "letter-spacing": "hard",
    "line-height": "hard",
    "avoid-inline-spacing": "hard",

    # Visual checks
    "color-contrast": "visual",
    "color-contrast-enhanced": "visual",
    "no-focus-style": "visual",
    "small-font-size": "visual",
    "responsive-reflow": "visual",
    "zoom-overflow": "visual",

    # Contextual checks
    "placeholder-as-label": "contextual",
    "readability": "contextual",
    "generic-link-text": "contextual",
    "cta-clarity": "contextual",
    "label-clarity": "contextual",
    "form-usability": "contextual",
    "error-message-quality": "contextual",
    "jargon": "contextual",
    "nav-complexity": "contextual",
}

# ── Page-Level Rules (Fragment Detector) ──────────────────────────
# These rules expect a complete HTML document. When scanning fragments
# (test fixtures, components, embeds), they generate massive false positives.
# The confidence engine applies a penalty when the document is incomplete.

PAGE_LEVEL_RULES = {
    "no-lang", "missing-lang", "no-title", "no-headings", "no-main-landmark",
    "no-h1", "no-nav-landmark", "no-header-landmark", "no-footer-landmark",
    "missing-skip-link",
}

# ── Structural FP Rules (Production Readiness) ──────────────────
# Rules that generate technically-correct but contextually-irrelevant findings.
# Suppressed via weight-based filtering in _apply_precision_profile, NOT by
# reducing confidence (confidence ≠ visibility — see design constraints).
STRUCTURAL_FP_RULES = {
    "landmark-roles", "no-main-landmark", "region",
    "no-nav-landmark", "no-header-landmark", "no-footer-landmark",
    "no-headings",
}

# ── Canonical Metric Definitions ─────────────────────────────────
# Ensures p95 is calculated identically across all benchmark suites.
METRIC_DEFINITIONS = {
    "fast_mode_p95_time": {
        "scope": "successful_audits_only",
        "exclude_degraded": True,
        "exclude_timeouts": True,
        "timeout_threshold_seconds": 30,
    },
}

# ── User Impact Scores ─────────────────────────────────────────────
# How blocking is this issue for affected disability groups? (0.0–1.0)
# Used in the 5-signal confidence formula.

USER_IMPACT_SCORES = {
    # Critical: completely blocks a user group
    "missing-alt": 1.0,
    "missing-label": 1.0,
    "input-label": 0.95,
    "form-label-missing": 1.0,
    "label": 0.95,
    "input-name": 0.95,
    "autocomplete-missing": 0.65,
    "duplicate-label": 0.55,
    "button-name": 0.95,
    "clickable-no-role": 0.85,
    "empty-link": 0.9,
    "aria-hidden-focusable": 0.95,
    "aria-required-parent": 0.9,
    "aria-required-children": 0.9,
    "aria-allowed-role": 0.85,
    "aria-role": 0.85,
    "no-lang": 0.85,
    "missing-lang": 0.85,
    "missing-captions": 0.9,
    "media-alternative": 0.9,
    "keyboard-unreachable": 1.0,
    "no-focus-style": 0.8,
    "viewport-zoom-disabled": 0.9,

    # Serious: significant barrier
    "no-title": 0.7,
    "no-headings": 0.7,
    "no-main-landmark": 0.6,
    "svg-no-accessible-name": 0.85,
    "svg-accessible-name": 0.85,
    "color-contrast": 0.8,
    "heading-skip": 0.6,
    "table-no-headers": 0.7,
    "broken-aria-label": 0.8,
    "placeholder-as-label": 0.75,

    # Moderate: degraded experience
    "link-purpose": 0.5,
    "unsafe-external-link": 0.3,
    "alt-quality": 0.4,
    "positive-tabindex": 0.5,
    "text-spacing": 0.4,
    "letter-spacing": 0.4,
    "line-height": 0.45,
    "avoid-inline-spacing": 0.35,
    "responsive-reflow": 0.6,

    # Default fallback
    "_default": 0.5,
}

# ── Impact Summaries (Plain English) ──────────────────────────────
# Short human-readable descriptions of who is blocked and why.

IMPACT_SUMMARIES = {
    "missing-alt": "Blind users cannot perceive this image at all. Screen readers will either skip it or announce the file name.",
    "missing-label": "Screen reader users cannot identify this form field. They will hear 'edit text' with no context.",
    "input-label": "Without an associated label element, users can struggle to identify the field purpose consistently.",
    "form-label-missing": "Form controls without labels are difficult or impossible to understand for screen reader users.",
    "label": "Assistive technologies require robust label associations to announce field purpose consistently.",
    "input-name": "Assistive technologies cannot announce a clear purpose when an input has no programmatic name.",
    "autocomplete-missing": "Users with cognitive and motor disabilities may lose helpful autofill support for personal data fields.",
    "duplicate-label": "Duplicate labels can cause repeated or confusing announcements for the same input control.",
    "button-name": "Screen reader users hear 'button' with no description. They cannot determine what this control does.",
    "clickable-no-role": "Mouse-only click handlers on generic elements can block keyboard and assistive technology users.",
    "aria-required-parent": "Assistive technologies may misinterpret orphaned ARIA widget roles, breaking expected navigation and announcements.",
    "aria-required-children": "Composite widgets without required child roles are not exposed correctly, so users cannot operate or understand them.",
    "aria-allowed-role": "Incompatible ARIA role overrides can hide native semantics and produce incorrect behavior for assistive technologies.",
    "aria-role": "Invalid or mismatched ARIA roles can break announcements and expected assistive-technology behavior.",
    "empty-link": "Screen reader users hear 'link' with no destination. Keyboard users cannot determine where this navigates.",
    "no-lang": "Screen readers may use the wrong pronunciation language, making all content unintelligible.",
    "missing-lang": "Screen readers may use the wrong pronunciation language, making all content unintelligible.",
    "missing-captions": "Deaf and hard-of-hearing users cannot access video content without captions.",
    "media-alternative": "Users cannot access media content when captions or transcripts are missing.",
    "keyboard-unreachable": "Users who cannot use a mouse are completely blocked from reaching this interactive element.",
    "no-focus-style": "Keyboard users cannot see which element is currently focused, making navigation impossible.",
    "viewport-zoom-disabled": "Users with low vision cannot zoom in to read content.",
    "no-title": "Screen readers announce nothing when the page loads. Users cannot identify which page they are on.",
    "no-headings": "Screen reader users cannot navigate by headings, forcing them to listen to the entire page linearly.",
    "color-contrast": "Users with low vision or color blindness may not be able to read this text.",
    "letter-spacing": "Hard-coded letter spacing can prevent users from applying readable spacing settings.",
    "line-height": "Rigid line-height settings can reduce readability when users need custom spacing.",
    "avoid-inline-spacing": "Inline spacing styles can block user style overrides needed for readability.",
    "svg-no-accessible-name": "Blind users cannot perceive SVG graphics without an accessible name.",
    "svg-accessible-name": "Blind users cannot perceive SVG graphics without an accessible name.",
    "heading-skip": "Screen reader users may miss content sections when heading levels are skipped.",
    "link-purpose": "Users cannot determine where a link goes without reading surrounding context.",
    "_default": "This issue may create a barrier for users with disabilities.",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    schema_version: str = "3.1"

    # Featherless AI (OpenAI-compatible API)
    featherless_api_key: str = ""
    featherless_model: str = "Qwen/Qwen2.5-Coder-32B-Instruct"
    featherless_base_url: str = "https://api.featherless.ai/v1"

    # Embedding model (local sentence-transformers)
    embedding_model: str = "all-MiniLM-L6-v2"

    # Vector store
    vector_store: str = "chromadb"  # chromadb (local)
    chroma_persist_dir: str = "./chroma_db"

    # Backend
    backend_host: str = "0.0.0.0"  # nosec B104
    backend_port: int = 8000
    backend_cors_origins: str = "http://localhost:3000"
    backend_log_level: str = "INFO"

    # Firebase
    firebase_project_id: str = ""

    # Database
    db_url: str = Field(
        default="sqlite:///./beacon.db",
        validation_alias=AliasChoices("DATABASE_URL", "DB_URL"),
    )
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_pool_timeout_seconds: int = 30
    db_pool_recycle_seconds: int = 1800
    db_auto_create: bool = False

    # Observability + telemetry
    metrics_window_size: int = 1000
    logs_dir: str = "./logs"
    telemetry_filename: str = "telemetry.jsonl"
    app_log_filename: str = "app.log"

    # Alerting
    alert_webhook_url: str = ""
    timeout_spike_threshold: float = 0.02
    enrichment_fallback_spike_threshold: float = 0.10
    long_running_audit_seconds: float = 180.0
    llm_failure_burst_count: int = 3
    llm_failure_burst_window_seconds: int = 300

    # API authentication
    auth_enabled: bool = True
    auth_key_store_path: str = "./app/data/api_keys.json"
    bootstrap_viewer_api_key: str = "beacon-viewer-dev"
    bootstrap_auditor_api_key: str = "beacon-auditor-dev"
    bootstrap_admin_api_key: str = "beacon-admin-dev"

    # Feature flags
    beacon_ai_enabled: bool = False

    # Scan defaults
    default_scan_mode: str = "fast"

    # Scan limits + caps
    max_scan_global_cap: int = Field(
        default=MAX_SCAN_GLOBAL_CAP,
        validation_alias=AliasChoices("MAX_SCAN_GLOBAL_CAP"),
    )
    max_concurrent_site_audits: int = Field(
        default=MAX_CONCURRENT_SITE_AUDITS,
        validation_alias=AliasChoices("MAX_CONCURRENT_SITE_AUDITS"),
    )
    dashboard_deep_scan_max_pages: int = Field(
        default=DASHBOARD_DEEP_SCAN_MAX_PAGES,
        validation_alias=AliasChoices("DASHBOARD_DEEP_SCAN_MAX_PAGES"),
    )
    dashboard_max_scan_max_pages: int = Field(
        default=DASHBOARD_MAX_SCAN_MAX_PAGES,
        validation_alias=AliasChoices("DASHBOARD_MAX_SCAN_MAX_PAGES"),
    )

    # Phase 6 crawl defaults
    crawl_max_pages_per_site: int = CRAWL_MAX_PAGES_PER_SITE
    crawl_max_depth: int = CRAWL_MAX_DEPTH
    crawl_timeout_per_page_s: int = CRAWL_TIMEOUT_PER_PAGE_S
    crawl_concurrency: int = CRAWL_CONCURRENCY

    # Enrichment + RAG controls
    enrichment_enable_llm_cache: bool = True
    llm_cache_max_entries: int = 2000
    enrichment_max_concurrency: int = 2
    enrichment_batch_max_issues: int = 6
    enrichment_retry_attempts: int = 3
    enrichment_retry_base_delay_seconds: float = 0.4
    enrichment_retry_max_delay_seconds: float = 3.0
    retrieval_enable_cache: bool = True
    retrieval_cache_max_entries: int = 1500
    retrieval_max_chunks: int = 5
    retrieval_candidate_multiplier: int = 3
    retrieval_min_relevance: float = 0.15
    retrieval_local_fallback_enabled: bool = True
    retrieval_local_max_chunks: int = 2500
    max_tokens_per_audit: int = 12000
    max_llm_cost_per_audit: float = 2.5
    llm_prompt_cost_per_1k_tokens: float = 0.0
    llm_completion_cost_per_1k_tokens: float = 0.0
    llm_fire_budget_per_audit: int = Field(
        default=LLM_FIRE_BUDGET_PER_AUDIT,
        validation_alias=AliasChoices("LLM_FIRE_BUDGET"),
    )
    audit_concurrency_limit: int = Field(
        default=AUDIT_CONCURRENCY_LIMIT,
        validation_alias=AliasChoices("AUDIT_CONCURRENCY"),
    )
    sitemap_max_depth: int = Field(
        default=SITEMAP_MAX_DEPTH,
        validation_alias=AliasChoices("SITEMAP_MAX_DEPTH"),
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",")]


settings = Settings()


# Runtime-resolved mode caps (env-configurable via Settings).
MAX_SCAN_GLOBAL_CAP = max(1, int(settings.max_scan_global_cap or MAX_SCAN_GLOBAL_CAP))
MAX_CONCURRENT_SITE_AUDITS = max(1, int(settings.max_concurrent_site_audits or MAX_CONCURRENT_SITE_AUDITS))
DASHBOARD_DEEP_SCAN_MAX_PAGES = max(
    1,
    min(int(settings.dashboard_deep_scan_max_pages or DASHBOARD_DEEP_SCAN_MAX_PAGES), MAX_SCAN_GLOBAL_CAP),
)
DASHBOARD_MAX_SCAN_MAX_PAGES = max(
    1,
    min(int(settings.dashboard_max_scan_max_pages or DASHBOARD_MAX_SCAN_MAX_PAGES), MAX_SCAN_GLOBAL_CAP),
)

for _mode_name, _mode_cfg in SCAN_MODE_CONFIG.items():
    _crawl_cap = min(int(_mode_cfg["crawl_cap"]), MAX_SCAN_GLOBAL_CAP)
    _orchestrator_mode = CRAWLER_CONFIG["orchestrator"]["scan_modes"][_mode_name]
    _orchestrator_mode["cap"] = _crawl_cap
    _orchestrator_mode["sitemap_max_pages"] = _crawl_cap
    _orchestrator_mode["bfs_max_depth"] = int(_mode_cfg["bfs_depth"])
    _orchestrator_mode["bfs_max_pages"] = min(int(_mode_cfg["bfs_pages"]), _crawl_cap)
    _orchestrator_mode["dom_max_pages"] = min(int(_mode_cfg["dom_pages"]), _crawl_cap)
    _orchestrator_mode["use_dom"] = bool(int(_mode_cfg["dom_pages"]) > 0)

_parallel = AUDIT_PIPELINE_CONFIG["parallel_runner"]
_parallel["concurrency_by_mode"] = {
    mode_name: max(1, int(mode_cfg["concurrency"]))
    for mode_name, mode_cfg in SCAN_MODE_CONFIG.items()
}
_parallel["page_timeout_stage1_seconds"] = {
    mode_name: max(1, int(mode_cfg["stage1_timeout"]))
    for mode_name, mode_cfg in SCAN_MODE_CONFIG.items()
}
_parallel["page_timeout_stage2_seconds"] = {
    mode_name: max(1, int(mode_cfg["stage2_timeout"]))
    for mode_name, mode_cfg in SCAN_MODE_CONFIG.items()
}
_parallel["global_sla_seconds"] = {
    mode_name: max(1, int(mode_cfg["global_sla"]))
    for mode_name, mode_cfg in SCAN_MODE_CONFIG.items()
}
_parallel["max_concurrent_site_audits"] = MAX_CONCURRENT_SITE_AUDITS


# Runtime-resolved crawl limits (env-configurable via Settings).
CRAWL_MAX_PAGES_PER_SITE = int(settings.crawl_max_pages_per_site or CRAWL_MAX_PAGES_PER_SITE)
CRAWL_MAX_DEPTH = int(settings.crawl_max_depth or CRAWL_MAX_DEPTH)
CRAWL_TIMEOUT_PER_PAGE_S = int(settings.crawl_timeout_per_page_s or CRAWL_TIMEOUT_PER_PAGE_S)
CRAWL_CONCURRENCY = int(settings.crawl_concurrency or CRAWL_CONCURRENCY)
SITEMAP_MAX_DEPTH = max(1, int(settings.sitemap_max_depth or SITEMAP_MAX_DEPTH))
LLM_FIRE_BUDGET_PER_AUDIT = max(0, int(settings.llm_fire_budget_per_audit or LLM_FIRE_BUDGET_PER_AUDIT))
AUDIT_CONCURRENCY_LIMIT = max(1, int(settings.audit_concurrency_limit or AUDIT_CONCURRENCY_LIMIT))


# ── Phase 20: Scan Mode Page Count Envelope ──────────────────────────────────
# SCAN_MODES is a new, additive dict that exposes three page-count values per
# mode. The existing SCAN_MODE_CONFIG (crawl_cap, bfs_depth, etc.) is unchanged.
# Call resolve_max_pages(scan_mode, has_sitemap) everywhere instead of
# hardcoding a page count.

from typing import Final  # noqa: E402  (needed here after module-level code)
from enum import Enum      # noqa: E402

SCAN_MODES: Final[dict] = {
    "fast": {
        "max_pages_default":  5,
        "max_pages_sitemap":  8,
        "max_pages_ceiling":  10,
        "max_depth":          2,
        "timeout_ms":         15_000,
        "enable_enrichment":  False,
        "enable_cognitive":   False,
    },
    "deep": {
        "max_pages_default":  15,
        "max_pages_sitemap":  25,
        "max_pages_ceiling":  30,
        "max_depth":          4,
        "timeout_ms":         30_000,
        "enable_enrichment":  True,
        "enable_cognitive":   False,
    },
    "max": {
        "max_pages_default":  40,
        "max_pages_sitemap":  60,
        "max_pages_ceiling":  75,
        "max_depth":          6,
        "timeout_ms":         60_000,
        "enable_enrichment":  True,
        "enable_cognitive":   True,
    },
}


def resolve_max_pages(scan_mode: str, has_sitemap: bool) -> int:
    """Return effective max_pages for a scan mode.

    Callers should never set max_pages directly — always call this helper
    after the sitemap crawler finishes so ``has_sitemap`` is accurate.

    Args:
        scan_mode:   One of "fast", "deep", "max".  Unknown modes fall back
                     to "fast".
        has_sitemap: True if the sitemap crawler returned at least one URL.

    Returns:
        Effective page ceiling, never exceeding ``max_pages_ceiling``.
    """
    mode = SCAN_MODES.get(scan_mode, SCAN_MODES["fast"])
    if has_sitemap:
        return min(mode["max_pages_sitemap"], mode["max_pages_ceiling"])
    return min(mode["max_pages_default"], mode["max_pages_ceiling"])


# ── Phase 20: Site Topology ──────────────────────────────────────────────────
# Used by app/services/topology_detector.py (created in Phase 20).
# SiteTopology is a str-Enum so it serialises cleanly to JSON / DB columns.

class SiteTopology(str, Enum):
    SINGLE_PAGE    = "single_page"
    THIN           = "thin"
    PAGINATED      = "paginated"
    DEEP_UNIFORM   = "deep_uniform"
    MULTI_TEMPLATE = "multi_template"


# How many pages to sample per template group for each topology class.
# THIN: 99 = effectively unlimited — thin brochure sites have few unique pages
#            and every one should be audited (no template deduplication needed).
# SINGLE_PAGE: exactly 1 — SPA root is the only auditable route discovered.
# PAGINATED: 2 — sample two paginated variants to check consistency.
# DEEP_UNIFORM: 2 — sample two instances of the dominant template.
# MULTI_TEMPLATE: 3 — representative sample across each template section.
TOPOLOGY_PAGES_PER_TEMPLATE: Final[dict] = {
    SiteTopology.SINGLE_PAGE:    1,
    SiteTopology.THIN:           99,  # audit everything — thin sites are small
    SiteTopology.PAGINATED:      2,
    SiteTopology.DEEP_UNIFORM:   2,
    SiteTopology.MULTI_TEMPLATE: 3,
}

