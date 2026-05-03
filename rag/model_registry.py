"""
Shared Model Registry — Single SentenceTransformer instance for the entire engine.

Elimates ~180MB of redundant memory by preventing multiple loads of
'all-MiniLM-L6-v2' across embed.py, query.py, and app/services/embedding.py.

Thread-safe lazy initialization with configurable model name.
"""
import logging
import os
import threading
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────
DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_NAME = os.environ.get("EMBEDDING_MODEL", DEFAULT_MODEL_NAME)

# ── Thread-safe singleton ──────────────────────────────────────
_model: Optional[Any] = None
_lock = threading.Lock()


def get_embedding_model() -> Any:
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
        
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading shared embedding model: {MODEL_NAME}")
            _model = SentenceTransformer(MODEL_NAME)
            dim = _model.get_sentence_embedding_dimension()
            logger.info(f"Shared model loaded. Dimension: {dim}")
        except Exception as e:
            logger.error("Failed to load SentenceTransformer: %s", e)
            raise
            
        return _model


def get_model_name() -> str:
    """Returns the name of the model currently configured."""
    return MODEL_NAME


# ── Reranking Model (Lazy) ─────────────────────────────────────
_reranker: Optional[Any] = None
_rerank_lock = threading.Lock()

def get_rerank_model() -> Any:
    """Get the shared CrossEncoder re-ranking model."""
    global _reranker
    if _reranker is not None:
        return _reranker

    with _rerank_lock:
        if _reranker is not None:
            return _reranker
            
        try:
            from sentence_transformers import CrossEncoder
            logger.info("Loading shared re-ranking model: BAAI/bge-reranker-base")
            _reranker = CrossEncoder("BAAI/bge-reranker-base", max_length=512)
        except Exception as e:
            logger.error("Failed to load CrossEncoder: %s", e)
            raise
            
        return _reranker


# ── BM25 Cache ────────────────────────────────────────────────
_bm25_cache: dict[str, Any] = {}

def get_bm25_cache() -> dict[str, Any]:
    """Get the shared BM25 index cache."""
    return _bm25_cache
