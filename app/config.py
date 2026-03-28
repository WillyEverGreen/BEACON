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
