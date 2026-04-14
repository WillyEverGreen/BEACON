"""
Content chunking module — splits documents into token-bounded chunks
with overlap for context preservation.

Uses tiktoken (cl100k_base) for accurate token counting.
Splits on heading boundaries for semantic coherence.
"""
import re
from typing import Any

import tiktoken

enc = tiktoken.get_encoding("cl100k_base")

# ── Configuration ──────────────────────────────────────────────
CHUNK_MAX_TOKENS: int = 400    # Maximum tokens per chunk
OVERLAP_TOKENS: int = 40      # Token overlap between consecutive chunks
MIN_TEXT_LENGTH: int = 1       # Minimum non-empty text to keep


def token_len(text: str) -> int:
    """Count the number of tokens in a text string."""
    return len(enc.encode(text))


def chunk_document(text: str, meta: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Split a document into token-bounded chunks with overlap.

    Attempts to split on heading boundaries first for semantic coherence.
    Falls back to sliding-window token chunking for long sections.

    Args:
        text: Full document text to chunk
        meta: Metadata dict to attach to each chunk (silo, url, etc.)

    Returns:
        List of chunk dicts with 'text' key and all meta fields
    """
    sections: list[str] = re.split(r'\n(?=#{1,4} |\b[A-Z][^\n]{0,60}\n[-=]+)', text)
    chunks: list[dict[str, Any]] = []

    for section in sections:
        tokens = enc.encode(section.strip())
        if not tokens:
            continue
        if len(tokens) <= CHUNK_MAX_TOKENS:
            chunks.append({"text": enc.decode(tokens), **meta})
        else:
            start = 0
            while start < len(tokens):
                end = min(start + CHUNK_MAX_TOKENS, len(tokens))
                chunks.append({"text": enc.decode(tokens[start:end]), **meta})
                start += CHUNK_MAX_TOKENS - OVERLAP_TOKENS

    return [c for c in chunks if c["text"].strip()]
