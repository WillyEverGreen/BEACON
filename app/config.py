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
        # Medium-precision mode: higher confidence threshold without rule exclusions
        # Aims for ~30-50% precision by raising min_confidence from 0.75 to 0.85
        "medium_precision": {
            "min_confidence": 0.85,
            "include_needs_review": False,
            "exclude_contextual_single_source": True,
        },
}

# ── Confidence Weights ──────────────────────────────────────────

CONFIDENCE_WEIGHTS = {
    "source_reliability": 0.30,
    "signal_strength": 0.25,
    "cross_engine_agreement": 0.25,
    "evidence_quality": 0.20,
}

SOURCE_RELIABILITY_SCORES = {
    "axe-core": 0.9,
    "static": 0.85,
    "browser-probe": 0.8,
    "heuristic": 0.5,
    "cognitive": 0.6,
}

# ── Severity Weights (for scoring) ─────────────────────────────

SEVERITY_WEIGHTS = {
    "critical": 10,
    "serious": 5,
    "moderate": 2,
    "minor": 1,
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
