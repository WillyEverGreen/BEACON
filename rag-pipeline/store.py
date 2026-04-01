"""
ChromaDB storage module — persists embedded chunks to the vector store.

Handles batched upsert to respect ChromaDB's per-call limits.
"""
import logging

import chromadb

logger = logging.getLogger("rag.store")

# ── Configuration ──────────────────────────────────────────────
CHROMA_PERSIST_DIR = "./chroma_db"
CHROMA_COLLECTION_NAME = "accessibility_kb"
BATCH_SIZE = 100


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


def store_chunks(chunks: list[dict]) -> None:
    """
    Store embedded chunks into ChromaDB in batches.
    
    Each chunk must have: id, embedding, text, and metadata fields
    (silo, severity, issue_type, wcag_sc, user_impact, topic, url, token_count).
    
    Args:
        chunks: List of chunk dicts with embeddings
    """
    if not chunks:
        logger.warning("No chunks to store.")
        return

    collection = _get_collection()

    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        try:
            collection.add(
                ids=[c["id"] for c in batch],
                embeddings=[c["embedding"] for c in batch],
                documents=[c["text"] for c in batch],
                metadatas=[{
                    "silo":        c.get("silo", ""),
                    "severity":    c.get("severity", "unknown"),
                    "issue_type":  c.get("issue_type", "general"),
                    "wcag_sc":     ",".join(c.get("wcag_sc", [])),
                    "user_impact": ",".join(c.get("user_impact", [])),
                    "topic":       c.get("topic", ""),
                    "url":         c.get("url", ""),
                    "token_count": str(c.get("token_count", 0)),
                } for c in batch]
            )
        except Exception as e:
            logger.error(f"Failed to store batch {i}-{i+len(batch)}: {e}")
            raise

    logger.info(f"Stored {len(chunks)} chunks total in {CHROMA_COLLECTION_NAME}")
