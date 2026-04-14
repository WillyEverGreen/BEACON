"""
Shared Model Registry — Single SentenceTransformer instance for the entire engine.

Eliminates ~180MB of redundant memory by preventing multiple loads of
'all-MiniLM-L6-v2' across embed.py, query.py, and app/services/embedding.py.

Thread-safe lazy initialization with configurable model name.
"""
import logging
import os
import threading
from typing import Optional

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_NAME = os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL_NAME)

# ── Thread-safe singleton ──────────────────────────────────────
_model: Optional[SentenceTransformer] = None
_lock = threading.Lock()


def get_embedding_model() -> SentenceTransformer:
    """
    Get or initialize the shared embedding model.
    
    Returns the same SentenceTransformer instance across all modules.
    Thread-safe: uses a lock to prevent double-initialization in concurrent contexts.
    """
    global _model
    if _model is not None:
        return _model

    with _lock:
        # Double-check after acquiring lock
        if _model is not None:
            return _model
        logger.info(f"Loading shared embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
        dim = _model.get_sentence_embedding_dimension()
        logger.info(f"Shared model loaded. Dimension: {dim}")
        return _model


def get_model_name() -> str:
    """Return the configured model name."""
    return MODEL_NAME


# ── BM25 Cache Management ─────────────────────────────────────
_bm25_cache: dict = {}
_bm25_lock = threading.Lock()


def get_bm25_cache() -> dict:
    """Get the shared BM25 cache dict."""
    return _bm25_cache


def invalidate_bm25_cache() -> None:
    """Clear the BM25 index cache (call after re-ingestion)."""
    with _bm25_lock:
        _bm25_cache.clear()
        logger.info("BM25 cache invalidated")
# ── CrossEncoder Model (Reranker) ─────────────────────────────
_rerank_model: Optional[SentenceTransformer] = None
_rerank_lock = threading.Lock()

def get_rerank_model() -> SentenceTransformer:
    """Get the shared CrossEncoder re-ranking model."""
    global _rerank_model
    from sentence_transformers import CrossEncoder # Import here to avoid overhead elsewhere
    if _rerank_model is not None:
        return _rerank_model
    with _rerank_lock:
        if _rerank_model is not None:
            return _rerank_model
        logger.info("Loading shared CrossEncoder model: cross-encoder/ms-marco-MiniLM-L-6-v2")
        _rerank_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        return _rerank_model
