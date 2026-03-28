"""
Embedding service using sentence-transformers (local, no API key needed).
"""
import logging
from typing import Optional
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level model cache
_model: Optional[SentenceTransformer] = None


def get_model() -> SentenceTransformer:
    """Get or initialize the embedding model (cached)."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        logger.info(f"Model loaded. Dimension: {_model.get_sentence_embedding_dimension()}")
    return _model


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
