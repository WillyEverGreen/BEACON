"""
Embedding service using sentence-transformers (local, no API key needed).

Uses the shared model from rag/model_registry.py to avoid
loading the same ~90MB model multiple times.
"""
import logging
import sys
import os
from typing import Optional

from sentence_transformers import SentenceTransformer

# Ensure rag is importable
_rag_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "rag"))
if _rag_path not in sys.path:
    sys.path.insert(0, _rag_path)

from model_registry import get_embedding_model as _get_shared_model

logger = logging.getLogger(__name__)


def get_model() -> SentenceTransformer:
    """Get the shared embedding model (singleton via model_registry)."""
    return _get_shared_model()


def generate_embeddings(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    """
    Generate embeddings for a list of texts.
    Returns list of embedding vectors.
    """
    model = get_model()

    if not texts:
        return []

    logger.info(f"Generating embeddings for {len(texts)} texts...")
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,  # For cosine similarity
    )

    return [emb.tolist() for emb in embeddings]


def generate_single_embedding(text: str) -> list[float]:
    """Generate embedding for a single text."""
    results = generate_embeddings([text])
    return results[0] if results else []


def get_embedding_dimension() -> int:
    """Get the dimension of the embedding model."""
    model = get_model()
    return model.get_sentence_embedding_dimension()
