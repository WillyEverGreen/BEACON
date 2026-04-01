"""
Clean ingestion service — wraps rag-pipeline modules for the FastAPI app.

Replaces the 22KB legacy ingestion_old.py with a thin delegation layer
that properly calls the rag-pipeline's crawl → extract → chunk → tag → filter → dedup → embed → store pipeline.
"""
import logging
import sys
import os
import json
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Ensure rag-pipeline is importable
_rag_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "rag-pipeline"))
if _rag_path not in sys.path:
    sys.path.insert(0, _rag_path)


# ── WCAG Criteria Loader ──────────────────────────────────────

def _load_wcag_criteria() -> list[dict]:
    """Load WCAG 2.2 criteria from local JSON data file."""
    data_path = Path(__file__).parent.parent / "data" / "wcag_criteria.json"
    if not data_path.exists():
        logger.warning(f"WCAG criteria file not found: {data_path}")
        return []

    try:
        with open(data_path, "r", encoding="utf-8") as f:
            criteria = json.load(f)
        logger.info(f"Loaded {len(criteria)} WCAG criteria from {data_path.name}")
        return criteria if isinstance(criteria, list) else []
    except Exception as e:
        logger.error(f"Failed to load WCAG criteria: {e}")
        return []


def _criteria_to_chunks(criteria: list[dict]) -> list[dict]:
    """Convert WCAG criteria JSON into ingestible text chunks."""
    chunks = []
    for sc in criteria:
        sc_id = sc.get("id", sc.get("num", ""))
        title = sc.get("title", sc.get("handle", ""))
        level = sc.get("level", "")
        text_parts = [
            f"# WCAG {sc_id}: {title}",
            f"Level: {level}",
        ]
        if sc.get("description"):
            text_parts.append(f"\n{sc['description']}")
        if sc.get("intent"):
            text_parts.append(f"\nIntent: {sc['intent']}")
        if sc.get("benefits"):
            text_parts.append(f"\nBenefits: {sc['benefits']}")
        if sc.get("techniques"):
            text_parts.append(f"\nTechniques: {sc['techniques']}")

        text = "\n".join(text_parts)
        chunks.append({
            "text": text,
            "silo": "wcag",
            "url": sc.get("url", f"https://www.w3.org/WAI/WCAG22/Understanding/{sc_id.replace('.', '')}"),
            "wcag_sc": [sc_id] if sc_id else [],
            "severity": level if level else "unknown",
            "issue_type": "guideline",
            "topic": title,
            "user_impact": [],
            "token_count": len(text.split()),
        })
    return chunks


# ── Corpus Expansion Sources ──────────────────────────────────

CORPUS_EXPANSION_SOURCES = [
    {"url": "https://www.w3.org/WAI/WCAG22/quickref/", "silo": "wcag", "depth": 2},
    {"url": "https://www.w3.org/WAI/ARIA/apg/", "silo": "aria", "depth": 2},
    {"url": "https://www.w3.org/WAI/WCAG22/Techniques/", "silo": "wcag", "depth": 2},
]


# ── Main Ingestion Entry Point ────────────────────────────────

def run_full_ingestion(expand_corpus: bool = False) -> list[dict]:
    """
    Run the full ingestion pipeline:
    1. Load WCAG criteria from local JSON
    2. Convert to text chunks
    3. Tag chunks with metadata (WCAG SC, severity, issue type, user impact)
    4. Filter noise
    5. Deduplicate
    6. Generate embeddings

    Args:
        expand_corpus: If True, also crawl web sources (slower, requires crawl4ai)

    Returns:
        List of chunks ready for vector store upsert (with embeddings)
    """
    from tag import tag_chunk
    from filter import passes_filter
    from dedup import dedup
    from embed import embed_chunks

    all_chunks = []

    # Step 1: Local WCAG criteria
    criteria = _load_wcag_criteria()
    if criteria:
        wcag_chunks = _criteria_to_chunks(criteria)
        logger.info(f"Generated {len(wcag_chunks)} chunks from WCAG criteria")
        all_chunks.extend(wcag_chunks)

    # Step 2: Optional corpus expansion (web crawl)
    if expand_corpus:
        try:
            from chunk import chunk_document
            from extract import extract_content

            raw_dir = Path("rag-pipeline/data/raw")
            if raw_dir.exists():
                for silo_dir in raw_dir.iterdir():
                    if not silo_dir.is_dir():
                        continue
                    for json_file in silo_dir.glob("*.json"):
                        try:
                            data = json.loads(json_file.read_text(encoding="utf-8"))
                            html = data.get("html", "")
                            if not html:
                                continue
                            content = extract_content(html)
                            if not content:
                                continue
                            meta = {
                                "silo": data.get("silo", silo_dir.name),
                                "url": data.get("url", ""),
                            }
                            chunks = chunk_document(content, meta)
                            all_chunks.extend(chunks)
                        except Exception as e:
                            logger.debug(f"Failed to process {json_file}: {e}")
                logger.info(f"Loaded {len(all_chunks)} total chunks (including web sources)")
        except ImportError as e:
            logger.warning(f"Corpus expansion requires crawl4ai: {e}")

    if not all_chunks:
        logger.warning("No chunks produced during ingestion")
        return []

    # Step 3: Tag
    logger.info("Tagging chunks with metadata...")
    all_chunks = [tag_chunk(c) for c in all_chunks]

    # Step 4: Filter
    before = len(all_chunks)
    all_chunks = [c for c in all_chunks if passes_filter(c)]
    logger.info(f"Filtered: {before} → {len(all_chunks)} chunks")

    # Step 5: Dedup
    all_chunks = dedup(all_chunks)

    # Step 6: Embed
    logger.info(f"Generating embeddings for {len(all_chunks)} chunks...")
    all_chunks = embed_chunks(all_chunks)

    logger.info(f"Ingestion complete: {len(all_chunks)} chunks ready for storage")
    return all_chunks
