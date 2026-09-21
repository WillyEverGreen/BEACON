"""
BEACON Lightweight Vector Store Architecture.

Pure Python, zero-dependency embedding & vector similarity engine.
- Vector search: NumPy-based normalized cosine similarity (dot product on normalized embeddings).
- Metadata store: JSON metadata serialization.
- Disk persistence: metadata.json + embeddings.npy.
- Rationale: High performance, zero C++ build dependencies, predictable memory footprint.
"""
import json
import logging
import hashlib
from pathlib import Path
from typing import Optional
import numpy as np

from app.config import settings
from app.services.embedding import generate_embeddings, generate_single_embedding

logger = logging.getLogger(__name__)

# Persistent storage directory
STORE_DIR = Path(settings.chroma_persist_dir)

# In-memory store
_store: Optional[dict] = None


def _get_store_path() -> Path:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    return STORE_DIR


def _load_store() -> dict:
    """Load store from disk or initialize empty."""
    global _store
    if _store is not None:
        return _store

    store_path = _get_store_path()
    meta_path = store_path / "metadata.json"
    emb_path = store_path / "embeddings.npy"

    if meta_path.exists() and emb_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            embeddings = np.load(str(emb_path), allow_pickle=False)
            _store = {
                "ids": data["ids"],
                "documents": data["documents"],
                "metadatas": data["metadatas"],
                "embeddings": embeddings,
            }
            logger.info(f"Loaded {len(_store['ids'])} chunks from disk")
        except Exception as e:
            logger.warning(f"Failed to load store: {e}. Starting fresh.")
            _store = {"ids": [], "documents": [], "metadatas": [], "embeddings": np.array([])}
    else:
        _store = {"ids": [], "documents": [], "metadatas": [], "embeddings": np.array([])}

    return _store


def _save_store():
    """Persist store to disk."""
    store = _load_store()
    store_path = _get_store_path()

    meta = {
        "ids": store["ids"],
        "documents": store["documents"],
        "metadatas": store["metadatas"],
    }

    with open(store_path / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)

    if len(store["embeddings"]) > 0:
        np.save(str(store_path / "embeddings.npy"), store["embeddings"])

    logger.info(f"Saved {len(store['ids'])} chunks to disk")


def upsert_chunks(chunks: list[dict]) -> int:
    """
    Upsert chunks into store.
    Each chunk: {"content": str, "metadata": dict}
    Returns number of chunks upserted.
    """
    if not chunks:
        return 0

    store = _load_store()

    # Prepare data
    new_ids = []
    new_docs = []
    new_metas = []

    existing_ids = set(store["ids"])

    # Track existing content hashes
    existing_hashes = set()
    for doc in store["documents"]:
        content_hash = hashlib.sha256(doc.encode("utf-8")).hexdigest()
        existing_hashes.add(content_hash)

    for i, chunk in enumerate(chunks):
        content = chunk["content"]
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

        # Skip explicit ID existing OR content hash existing
        source = chunk["metadata"].get("source", "unknown")
        filename = chunk["metadata"].get("filename", "unknown")
        criterion_id = chunk["metadata"].get("criterion_id", "")
        chunk_idx = chunk["metadata"].get("chunk_index", 0)

        chunk_id = f"{source}_{filename}_{criterion_id}_{chunk_idx}_{i}"

        if chunk_id in existing_ids or content_hash in existing_hashes:
            continue

        existing_hashes.add(content_hash)
        new_ids.append(chunk_id)
        new_docs.append(content)

        # Clean metadata (ensure serializable)
        clean_meta = {}
        for k, v in chunk["metadata"].items():
            if isinstance(v, (str, int, float, bool)):
                clean_meta[k] = v
            else:
                clean_meta[k] = str(v)
        new_metas.append(clean_meta)

    if not new_ids:
        logger.info("No new chunks to upsert")
        return 0

    # Generate embeddings
    logger.info(f"Generating embeddings for {len(new_docs)} chunks...")
    new_embeddings = generate_embeddings(new_docs)
    new_emb_array = np.array(new_embeddings, dtype=np.float32)

    # Append to store
    store["ids"].extend(new_ids)
    store["documents"].extend(new_docs)
    store["metadatas"].extend(new_metas)

    if len(store["embeddings"]) == 0 or store["embeddings"].size == 0:
        store["embeddings"] = new_emb_array
    else:
        store["embeddings"] = np.vstack([store["embeddings"], new_emb_array])

    # Save to disk
    _save_store()

    logger.info(f"Upserted {len(new_ids)} chunks. Total: {len(store['ids'])}")
    return len(new_ids)


def search_similar(
    query: str,
    n_results: int = 15,
    where_filter: Optional[dict] = None,
) -> list[dict]:
    """
    Semantic search: find chunks similar to query using cosine similarity.
    Returns list of {"content", "metadata", "score"}.
    """
    store = _load_store()

    if len(store["ids"]) == 0:
        logger.warning("Store is empty. Run ingestion first.")
        return []

    # Get query embedding
    query_embedding = np.array(generate_single_embedding(query), dtype=np.float32)

    # Apply metadata filters to get candidate indices
    candidate_indices = list(range(len(store["ids"])))
    if where_filter:
        candidate_indices = _apply_filter(store["metadatas"], where_filter)

    if not candidate_indices:
        # Fallback: search all
        candidate_indices = list(range(len(store["ids"])))

    # Get candidate embeddings
    candidate_embeddings = store["embeddings"][candidate_indices]

    # Compute cosine similarity
    # Embeddings are already normalized by sentence-transformers
    similarities = np.dot(candidate_embeddings, query_embedding)

    # Get top-n
    top_k = min(n_results, len(candidate_indices))
    top_indices = np.argsort(similarities)[::-1][:top_k]

    results = []
    for idx in top_indices:
        real_idx = candidate_indices[idx]
        score = float(similarities[idx])
        if score > 0:  # Only positive similarities
            results.append({
                "content": store["documents"][real_idx],
                "metadata": store["metadatas"][real_idx],
                "score": round(score, 4),
            })

    return results


def _apply_filter(metadatas: list[dict], filters: dict) -> list[int]:
    """Apply metadata filters, return matching indices."""
    indices = []

    for i, meta in enumerate(metadatas):
        match = True

        if "topic" in filters and filters["topic"]:
            topic_filter = filters["topic"].lower()
            meta_topic = meta.get("topic", "").lower()
            meta_all_topics = meta.get("all_topics", "").lower()
            if topic_filter not in meta_topic and topic_filter not in meta_all_topics:
                match = False

        if "level" in filters and filters["level"]:
            if meta.get("level", "").upper() != filters["level"].upper():
                # Allow empty levels (repo content matches any level filter)
                if meta.get("level", ""):
                    match = False

        if "chunk_type" in filters and filters["chunk_type"]:
            if meta.get("chunk_type", "") != filters["chunk_type"]:
                match = False

        if match:
            indices.append(i)

    return indices


def get_all_metadata_values() -> dict:
    """Get all unique values for metadata fields."""
    store = _load_store()

    topics = set()
    levels = set()
    chunk_types = set()

    for meta in store["metadatas"]:
        if meta.get("topic"):
            topics.add(meta["topic"])
        if meta.get("all_topics"):
            for t in meta["all_topics"].split(","):
                if t.strip():
                    topics.add(t.strip())
        if meta.get("level") and meta["level"]:
            levels.add(meta["level"])
        if meta.get("chunk_type"):
            chunk_types.add(meta["chunk_type"])

    return {
        "topics": sorted(topics),
        "levels": sorted(levels),
        "chunk_types": sorted(chunk_types),
    }


def get_chunks_count() -> int:
    """Get the total number of chunks in the store."""
    store = _load_store()
    return len(store["ids"])


def get_collection():
    """Compatibility alias — returns the store."""
    return _load_store()


def reset_collection():
    """Delete and recreate the store."""
    global _store
    store_path = _get_store_path()

    for f in ["metadata.json", "embeddings.npy"]:
        fp = store_path / f
        if fp.exists():
            fp.unlink()

    _store = {"ids": [], "documents": [], "metadatas": [], "embeddings": np.array([])}
    logger.info("Store reset")
