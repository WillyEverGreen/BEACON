"""
Configuration settings loaded from .env file.
Includes scan mode definitions and quality gate thresholds.
"""
from pydantic_settings import BaseSettings
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
            "no-headings": ["no-lang", "no-main-landmark", "no-title"],
        },
    },
    # Balanced mode keeps broader recall while still filtering weak findings.
    "balanced": {
        "min_confidence": 0.55,
        "include_needs_review": True,
        "exclude_contextual_single_source": False,
    },
    # Ultra-strict mode: only highest-confidence issues, excludes over-reported page-level checks
    # Used for benchmarking against external sources (reduces false positives from ~4k to ~100)
    "ultra_strict": {
        "min_confidence": 0.95,
        "include_needs_review": False,
        "exclude_contextual_single_source": True,
        "exclude_rules": [
            "no-main-landmark",  # Too aggressive on test fixtures
            "no-headings",       # Page-level check; many valid minimal pages
            "no-title",          # Embedded tests may not have title
            "no-lang",           # Similar page-level context issue
        ],
    },
        # Strict mode: excludes 4 over-reported rules at normal high_precision confidence
        # Aims for ~25-35% precision by removing ~3,900 false positives from page-level WCAG checks
        "strict": {
            "min_confidence": 0.75,
            "include_needs_review": False,
            "exclude_contextual_single_source": True,
            "exclude_rules": [
                "no-main-landmark",
                "no-headings",
                "no-title",
                "no-lang",
            ],
        },
        # Very-high-precision mode: aggressively suppresses historically noisy rules.
        # Intended for production triage where false positives are more costly than misses.
        "very_high_precision": {
            "min_confidence": 0.75,
            "include_needs_review": False,
            "exclude_contextual_single_source": True,
            "exclude_rules": [
                "no-main-landmark",
                "no-headings",
                "no-title",
                "no-lang",
                "missing-captions",
                "autoplay-media",
                "missing-skip-link",
                "th-no-scope",
                "missing-autocomplete",
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
                "missing-captions": 0.92,
                "autoplay-media": 0.92,
                "missing-skip-link": 0.92,
                "th-no-scope": 0.90,
                "missing-autocomplete": 0.90,
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

# ── User Impact Scores per Rule ─────────────────────────────────
# 0.0 – 1.0; higher = blocks more / more-vulnerable user populations.
# Used as the 5th confidence signal so blocking issues surface above noise.
USER_IMPACT_SCORES: dict[str, float] = {
    # Blind / Screen reader users
    "missing-alt":            1.0,
    "empty-alt":              0.9,
    "missing-label":          1.0,
    "button-no-name":         1.0,
    "role-no-name":           0.9,
    "svg-no-accessible-name": 0.85,
    "no-headings":            0.8,
    "no-h1":                  0.7,
    # Keyboard / Motor-impairment users
    "no-focus-style":         0.9,
    "keyboard-unreachable":   1.0,
    "focus-trap":             1.0,
    "positive-tabindex":      0.7,
    # Low-vision users
    "color-contrast":         0.9,
    "color-contrast-enhanced":0.85,
    "small-font-size":        0.7,
    # Cognitive / all users
    "empty-link":             0.8,
    "generic-link-text":      0.7,
    "missing-skip-link":      0.75,
    # Deaf users
    "missing-captions":       0.9,
    "missing-transcript":     0.85,
    "_default":               0.5,   # fallback
}

# ── Human Impact Summaries ──────────────────────────────────────
# Simple, non-technical explanations for product managers/designers.
IMPACT_SUMMARIES: dict[str, str] = {
    # Blind / Screen reader users
    "missing-alt":            "Screen reader users cannot understand this image without a text description.",
    "empty-alt":              "Screen reader users may miss the meaning of this meaningful image, or have to listen to the filename.",
    "missing-label":          "Screen reader users cannot clearly understand what this form input expects.",
    "button-no-name":         "Screen reader users don't know what clicking this button will do.",
    "role-no-name":           "Screen reader users don't know the purpose of this interactive element.",
    "svg-no-accessible-name": "Screen reader users cannot perceive or interact with this SVG graphic.",
    "no-headings":            "Without headings, screen reader users cannot quickly navigate and skim the page.",
    "no-h1":                  "Screen reader users lack the main title context to understand what this page is about.",
    # Keyboard / Motor-impairment users
    "no-focus-style":         "Keyboard-only users (e.g. users with motor impairments) cannot see which element is currently selected.",
    "keyboard-unreachable":   "Keyboard-only users are completely blocked from clicking or reaching this element.",
    "focus-trap":             "Keyboard-only users are trapped here and cannot navigate away without a mouse.",
    "positive-tabindex":      "Keyboard users will jump awkwardly around the page, breaking logical navigation flow.",
    # Low-vision users
    "color-contrast":         "Low-vision users or users in glare will struggle to read this text.",
    "color-contrast-enhanced":"Low-vision users may struggle reading this text without higher contrast.",
    "small-font-size":        "Low-vision users will struggle to read this very small text.",
    # Cognitive / all users
    "empty-link":             "Users don't know where this link goes because there's no visible or screen-reader text.",
    "generic-link-text":      "Users reading out of context (like 'Click here') don't know where this link goes.",
    "missing-skip-link":      "Keyboard users are forced to repeatedly tab through all navigation before reaching content.",
    # Deaf users
    "missing-captions":       "Deaf or hard-of-hearing users cannot consume this video/audio content.",
    "missing-transcript":     "Deaf or hard-of-hearing users cannot consume this audio content.",
    "_default":               "This issue creates friction for users with disabilities interacting with your app.",
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
    "dom_hits":    0,
    "dom_misses":  0,
    "llm_hits":    0,
    "llm_misses":  0,
    "fix_hits":    0,
    "fix_misses":  0,
}


# ── Severity Weights (for scoring) ─────────────────────────────

SEVERITY_WEIGHTS = {
    "critical": 10,
    "serious": 5,
    "moderate": 2,
    "minor": 1,
}

# ── Scoring Configuration ───────────────────────────────────────
# Prevents a single noisy rule (e.g. 'region') from collapsing the
# score to 0 by capping the maximum penalty contribution per rule_id.

SCORING_CONFIG = {
    # Max penalty points any single rule_id can contribute to the score.
    # With 338 region violations at 2 pts each = 676 → score 0. Cap at 15.
    "max_penalty_per_rule": 15,

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

# ── Domain Classification ──────────────────────────────────────

RULE_DOMAIN_MAP = {
    "missing-alt": "content",
    "empty-alt": "content",
    "alt-quality": "content",
    "no-headings": "structure",
    "no-h1": "structure",
    "multiple-h1": "structure",
    "heading-skip": "structure",
    "missing-label": "forms",
    "empty-link": "navigation",
    "generic-link-text": "navigation",
    "unsafe-external-link": "navigation",
    "button-no-name": "forms",
    "button-name": "forms",
    "role-no-name": "aria",
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
    "empty-link": "hard",
    "button-no-name": "hard",
    "button-name": "hard",
    "no-lang": "hard",
    "no-title": "hard",
    "missing-captions": "hard",
    "svg-no-accessible-name": "hard",
    "unsafe-external-link": "hard",
    "no-headings": "hard",
    "no-h1": "hard",
    "multiple-h1": "hard",
    "heading-skip": "hard",

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


class Settings(BaseSettings):
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
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    backend_cors_origins: str = "http://localhost:3000"

    # Firebase
    firebase_project_id: str = ""

    # Scan defaults
    default_scan_mode: str = "fast"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
