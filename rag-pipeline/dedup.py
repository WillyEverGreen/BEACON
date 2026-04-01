"""
Deduplication module — MD5 exact-match + Jaccard trigram near-duplicate detection.

Processes document chunks to remove exact and near-duplicate content
before embedding and storage, reducing vector store bloat.
"""
import hashlib
import logging

logger = logging.getLogger("rag.dedup")

# ── Constants ──────────────────────────────────────────────────
JACCARD_THRESHOLD = 0.85     # Similarity threshold for near-duplicate detection
DEDUP_WINDOW_SIZE = 200      # Number of recent chunks to compare against
PROGRESS_INTERVAL = 2000     # Log progress every N chunks


def md5(text: str) -> str:
    """Compute MD5 hash of text for exact dedup."""
    return hashlib.md5(text.encode()).hexdigest()


def trigrams(text: str) -> set[tuple[str, ...]]:
    """Generate word-level trigram set for Jaccard similarity."""
    w = text.lower().split()
    return set(zip(w, w[1:], w[2:]))


def jaccard(a: str, b: str) -> float:
    """Compute Jaccard similarity between two texts using trigrams."""
    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def dedup(chunks: list[dict], threshold: float = JACCARD_THRESHOLD) -> list[dict]:
    """
    Remove duplicate chunks using two-pass deduplication:
    1. Exact MD5 hash match (fast O(1) lookup)
    2. Jaccard trigram similarity within a sliding window (near-duplicate detection)
    
    Args:
        chunks: List of chunk dicts with 'text' key
        threshold: Jaccard similarity threshold (0.0–1.0). Default: 0.85
    
    Returns:
        Deduplicated list of chunks with 'id' field added (MD5 hash)
    """
    seen: set[str] = set()
    unique: list[dict] = []

    for i, chunk in enumerate(chunks):
        if i % PROGRESS_INTERVAL == 0:
            logger.info(f"Dedup processing {i}/{len(chunks)}...")

        h = md5(chunk["text"])
        if h in seen:
            continue
        seen.add(h)

        tc = trigrams(chunk["text"])
        if not tc:
            continue

        len_tc = len(tc)

        is_dup = False
        for p in unique[-DEDUP_WINDOW_SIZE:]:
            tp = p.get("_trigrams", set())
            if not tp:
                continue
            intersect = len(tc & tp)
            union = len_tc + len(tp) - intersect
            if intersect / union > threshold:
                is_dup = True
                break

        if not is_dup:
            chunk["id"] = h
            chunk["_trigrams"] = tc
            unique.append(chunk)

    for c in unique:
        c.pop("_trigrams", None)

    logger.info(f"Dedup complete: {len(chunks)} → {len(unique)} chunks ({len(chunks) - len(unique)} removed)")
    return unique
