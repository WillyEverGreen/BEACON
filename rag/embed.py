"""
Embedding module — generates vector embeddings for document chunks.

Uses the shared model from model_registry to avoid redundant memory usage.
"""
from model_registry import get_embedding_model


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """
    Generate normalized embeddings for a list of text chunks.
    
    Each chunk must have a 'text' key. The 'embedding' key is added in-place.
    Returns the same list with embeddings attached.
    """
    model = get_embedding_model()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts, batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True
    )
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist()
    return chunks
