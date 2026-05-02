import argparse
import asyncio
import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# Hotfix to prevent crawl4ai's dotenv load from crashing asynchronously on Windows
import dotenv

dotenv.load_dotenv = lambda *a, **k: True

# Add rag to path so imports work
sys.path.insert(0, os.path.abspath("rag"))

from axe_parser import parse_axe_rules
from chunk import chunk_document
from config import SOURCES
from crawl import crawl_source
from dedup import dedup
from embed import embed_chunks
from extract import extract_content
from filter import passes_filter
from local_corpus import process_local_corpus
from model_registry import invalidate_bm25_cache
from store import get_collection_count, get_existing_ids, store_chunks
from tag import tag_chunk
from verify import get_coverage_details

RAW_DIR = Path("data/raw")
DEFAULT_REPORT_PATH = Path("data/ingestion_report.json")
LOCAL_CORPUS_PATH = "corpus/wcag-aaa-web-design"
AXE_RULES_PATH = "axe-core/lib/rules"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incremental offline RAG ingestion.")
    parser.add_argument(
        "--hard-reset",
        action="store_true",
        help="Delete existing chroma_db before ingestion.",
    )
    parser.add_argument(
        "--skip-crawl",
        action="store_true",
        help="Skip crawling and only ingest existing raw files + local sources.",
    )
    parser.add_argument(
        "--reindex-existing",
        action="store_true",
        help="Re-embed and upsert all chunks, even if IDs already exist.",
    )
    parser.add_argument(
        "--strict-coverage",
        action="store_true",
        help="Exit with non-zero code if source or WCAG coverage has gaps.",
    )
    parser.add_argument(
        "--report-path",
        default=str(DEFAULT_REPORT_PATH),
        help=f"Where to write JSON ingestion report (default: {DEFAULT_REPORT_PATH}).",
    )
    return parser.parse_args()


def _normalize_url(url: str) -> str:
    """Normalize URLs for reliable source-coverage matching."""
    cleaned = (url or "").strip()
    if not cleaned:
        return ""
    try:
        parts = urlsplit(cleaned)
        normalized = urlunsplit(
            (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", "")
        )
        return normalized.rstrip("/")
    except Exception:
        return cleaned.lower().rstrip("/")


def _extract_web_docs(raw_dir: Path) -> tuple[list[dict], set[str], Counter, int]:
    """Extract clean text docs from crawled JSON files."""
    docs: list[dict] = []
    seen_urls: set[str] = set()
    docs_per_silo: Counter = Counter()
    parse_errors = 0

    if not raw_dir.exists():
        return docs, seen_urls, docs_per_silo, parse_errors

    raw_files = list(raw_dir.rglob("*.json"))
    total_files = len(raw_files)
    print(f"Found {total_files} raw files.")

    for i, raw_file in enumerate(raw_files):
        if i % 500 == 0:
            print(f"  Extracting {i}/{total_files}...")
        try:
            data = json.loads(raw_file.read_text(encoding="utf-8", errors="ignore"))
            source_url = data.get("url", "")
            if source_url:
                seen_urls.add(_normalize_url(source_url))

            html = data.get("html", "")
            if not html:
                continue

            text = extract_content(html)
            if not text:
                continue

            silo = data.get("silo", "unknown")
            docs.append(
                {
                    "url": source_url,
                    "silo": silo,
                    "text": text,
                    "title": data.get("url", ""),
                }
            )
            docs_per_silo[silo] += 1
        except Exception:
            parse_errors += 1

    return docs, seen_urls, docs_per_silo, parse_errors


def _compute_source_coverage(seen_urls: set[str]) -> dict:
    """Compare configured source seeds against crawled raw data URLs."""
    found_seed_urls: list[str] = []
    missing_seed_urls: list[str] = []

    for source in SOURCES:
        seed_url = source["url"]
        if _normalize_url(seed_url) in seen_urls:
            found_seed_urls.append(seed_url)
        else:
            missing_seed_urls.append(seed_url)

    return {
        "expected_seed_count": len(SOURCES),
        "found_seed_count": len(found_seed_urls),
        "missing_seed_count": len(missing_seed_urls),
        "missing_seed_urls": missing_seed_urls,
    }


def _write_report(report_path: Path, report: dict) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")


async def run_ingestion(args: argparse.Namespace) -> int:
    print("=" * 60)
    print("  STARTING INCREMENTAL OFFLINE RAG INGESTION")
    print("=" * 60)

    if args.hard_reset:
        print("\n[0] Hard reset requested: deleting existing ChromaDB...")
        shutil.rmtree("chroma_db", ignore_errors=True)

    collection_count_before = get_collection_count()

    crawl_errors: list[dict] = []
    if args.skip_crawl:
        print("\n[1] Skipping crawl (--skip-crawl).")
    else:
        print("\n[1] Crawling configured web sources...")
        crawl_results = await asyncio.gather(
            *(crawl_source(source) for source in SOURCES),
            return_exceptions=True,
        )
        for source, result in zip(SOURCES, crawl_results):
            if isinstance(result, Exception):
                crawl_errors.append({"url": source["url"], "error": str(result)})

    print("\n[2] Extracting web content from raw cache...")
    web_docs, seen_urls, web_docs_per_silo, parse_errors = _extract_web_docs(RAW_DIR)

    print("\n[3] Injecting local engineering corpus...")
    local_docs = process_local_corpus(LOCAL_CORPUS_PATH)

    print("\n[4] Parsing local axe-core rules...")
    axe_chunks = parse_axe_rules(AXE_RULES_PATH)

    docs = web_docs + local_docs
    print(f"\n[5] Chunking {len(docs)} documents...")
    all_chunks: list[dict] = []
    for i, doc in enumerate(docs):
        if i % 500 == 0:
            print(f"  Chunking {i}/{len(docs)}...")
        meta = {
            "url": doc.get("url", ""),
            "silo": doc.get("silo", "unknown"),
            "title": doc.get("title", ""),
        }
        all_chunks.extend(chunk_document(doc.get("text", ""), meta))

    all_chunks.extend(axe_chunks)

    print(f"\n[6] Filtering {len(all_chunks)} chunks for relevance...")
    filtered = [chunk for chunk in all_chunks if passes_filter(chunk)]

    print(f"\n[7] Deduplicating {len(filtered)} chunks...")
    unique = dedup(filtered)

    print(f"\n[8] Tagging metadata on {len(unique)} chunks...")
    tagged = [tag_chunk(chunk) for chunk in unique]

    candidate_ids = [chunk["id"] for chunk in tagged if chunk.get("id")]
    existing_id_hits = 0

    if args.reindex_existing:
        to_embed = [chunk for chunk in tagged if chunk.get("id")]
    else:
        existing_ids = get_existing_ids(candidate_ids)
        existing_id_hits = len(existing_ids)
        to_embed = [chunk for chunk in tagged if chunk.get("id") and chunk["id"] not in existing_ids]

    print(
        f"\n[9] Incremental indexing decision: {len(to_embed)} new chunks, "
        f"{existing_id_hits} already indexed chunks skipped."
    )

    if to_embed:
        print("\n[10] Generating embeddings for new chunks...")
        embedded = embed_chunks(to_embed)

        print("\n[11] Upserting chunks into ChromaDB...")
        written_count = store_chunks(embedded, use_upsert=True)

        # Keep retrieval index synchronized after ingestion updates.
        invalidate_bm25_cache()
    else:
        print("\n[10] No new chunks to embed/upsert.")
        written_count = 0

    collection_count_after = get_collection_count()
    wcag_coverage = get_coverage_details()
    source_coverage = _compute_source_coverage(seen_urls)

    expected_silos = sorted({source["silo"] for source in SOURCES} | {"axe", "toolkit"})
    found_silos = sorted(
        set(web_docs_per_silo.keys())
        | ({"toolkit"} if local_docs else set())
        | ({"axe"} if axe_chunks else set())
    )
    missing_silos = [silo for silo in expected_silos if silo not in found_silos]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": {
            "hard_reset": bool(args.hard_reset),
            "skip_crawl": bool(args.skip_crawl),
            "reindex_existing": bool(args.reindex_existing),
        },
        "vector_store": {
            "count_before": collection_count_before,
            "count_after": collection_count_after,
            "new_chunks_written": written_count,
            "existing_chunk_hits": existing_id_hits,
        },
        "pipeline_counts": {
            "web_docs": len(web_docs),
            "local_docs": len(local_docs),
            "axe_chunks": len(axe_chunks),
            "all_chunks": len(all_chunks),
            "filtered_chunks": len(filtered),
            "unique_chunks": len(unique),
            "new_chunks_embedded": len(to_embed),
            "raw_parse_errors": parse_errors,
        },
        "crawl": {
            "configured_sources": len(SOURCES),
            "crawl_error_count": len(crawl_errors),
            "crawl_errors": crawl_errors,
        },
        "source_coverage": source_coverage,
        "silo_coverage": {
            "expected_silos": expected_silos,
            "found_silos": found_silos,
            "missing_silos": missing_silos,
            "web_docs_per_silo": dict(web_docs_per_silo),
        },
        "wcag_coverage": wcag_coverage,
    }

    report_path = Path(args.report_path)
    _write_report(report_path, report)

    print("\n" + "=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)
    print(f"Vector DB chunks: {collection_count_before} -> {collection_count_after}")
    print(
        "Source seed coverage: "
        f"{source_coverage['found_seed_count']}/{source_coverage['expected_seed_count']}"
    )
    print(
        "WCAG coverage: "
        f"{wcag_coverage['covered_count']}/{wcag_coverage['total']}"
    )
    print(f"Ingestion report written to: {report_path}")

    has_gaps = bool(
        source_coverage["missing_seed_urls"]
        or missing_silos
        or wcag_coverage["missing"]
        or crawl_errors
        or wcag_coverage["error"]
    )
    if has_gaps:
        print("WARNING: Coverage gaps detected. Check ingestion report for details.")

    if args.strict_coverage and has_gaps:
        return 2
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(run_ingestion(args))


if __name__ == "__main__":
    raise SystemExit(main())
