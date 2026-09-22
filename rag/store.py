"""
ChromaDB storage module — persists embedded chunks to the vector store.

Handles batched upsert to respect ChromaDB's per-call limits.
"""
import logging
from collections.abc import Iterable

try:
    import chromadb
except ImportError:
    chromadb = None

logger = logging.getLogger("rag.store")

# ── Configuration ──────────────────────────────────────────────
CHROMA_PERSIST_DIR = "./chroma_db"
CHROMA_COLLECTION_NAME = "accessibility_kb"
BATCH_SIZE = 100
LOOKUP_BATCH_SIZE = 500


def _get_collection():
    """Get or create the ChromaDB collection."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
        return client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    except Exception as e:
        logger.error(f"Failed to connect to ChromaDB at {CHROMA_PERSIST_DIR}: {e}")
        raise


def _batched(values: list[str], batch_size: int) -> Iterable[list[str]]:
    """Yield lists in fixed-size batches."""
    for i in range(0, len(values), batch_size):
        yield values[i:i + batch_size]


def _flatten_ids(raw_ids: object) -> set[str]:
    """Normalize Chroma ID payload shape into a flat string set."""
    found: set[str] = set()
    if isinstance(raw_ids, str):
        return {raw_ids}
    if isinstance(raw_ids, list):
        for item in raw_ids:
            found.update(_flatten_ids(item))
    return found


def get_collection_count() -> int:
    """Return total number of chunks currently in the vector collection."""
    try:
        return int(_get_collection().count())
    except Exception as e:
        logger.warning(f"Could not read collection count: {e}")
        return 0


def get_existing_ids(candidate_ids: list[str]) -> set[str]:
    """Return the subset of IDs that already exist in the collection."""
    if not candidate_ids:
        return set()

    collection = _get_collection()
    existing: set[str] = set()

    for subset in _batched(candidate_ids, LOOKUP_BATCH_SIZE):
        try:
            # include=[] is supported by newer Chroma; fallback keeps compatibility.
            result = collection.get(ids=subset, include=[])
        except TypeError:
            result = collection.get(ids=subset)
        existing.update(_flatten_ids(result.get("ids", [])))

    return existing


def store_chunks(chunks: list[dict], use_upsert: bool = True) -> int:
    """
    Store embedded chunks into ChromaDB in batches.
    
    Each chunk must have: id, embedding, text, and metadata fields
    (silo, severity, issue_type, wcag_sc, user_impact, topic, url, token_count).
    
    Args:
        chunks: List of chunk dicts with embeddings

    Returns:
        Number of chunks written (added or upserted)
    """
    if not chunks:
        logger.warning("No chunks to store.")
        return 0

    collection = _get_collection()

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        payload = {
            "ids": [c["id"] for c in batch],
            "embeddings": [c["embedding"] for c in batch],
            "documents": [c["text"] for c in batch],
            "metadatas": [{
                "silo":        c.get("silo", ""),
                "severity":    c.get("severity", "unknown"),
                "issue_type":  c.get("issue_type", "general"),
                "wcag_sc":     ",".join(c.get("wcag_sc", [])),
                "user_impact": ",".join(c.get("user_impact", [])),
                "topic":       c.get("topic", ""),
                "url":         c.get("url", ""),
                "token_count": str(c.get("token_count", 0)),
            } for c in batch],
        }
        try:
            if use_upsert and hasattr(collection, "upsert"):
                collection.upsert(**payload)
            else:
                collection.add(**payload)
        except Exception as e:
            logger.error(f"Failed to store batch {i}-{i+len(batch)}: {e}")
            raise

    logger.info(f"Stored {len(chunks)} chunks total in {CHROMA_COLLECTION_NAME}")
    return len(chunks)
