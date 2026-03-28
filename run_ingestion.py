import asyncio
import sys
import os
import shutil
import json
from pathlib import Path

# Hotfix to prevent crawl4ai's dotenv load from crashing asynchronously on Windows
import dotenv
dotenv.load_dotenv = lambda *a, **k: True

# Add rag-pipeline to path so imports work
sys.path.insert(0, os.path.abspath("rag-pipeline"))

from config import SOURCES
from crawl import crawl_source
from extract import extract_content
from local_corpus import process_local_corpus
from chunk import chunk_document
from filter import passes_filter
from dedup import dedup
from tag import tag_chunk
from embed import embed_chunks
from store import store_chunks
from axe_parser import parse_axe_rules

async def main():
    print("=" * 60)
    print("  🚀 STARTING HARD RESET: CLEAN OFFLINE RAG INGESTION 🚀")
    print("=" * 60)
    
    print("\n[1] Deleting old ChromaDB... (Hard Reset)")
    shutil.rmtree("chroma_db", ignore_errors=True)
    
    print("\n[2] Crawling web sources (WCAG, ARIA, COGA, etc)...")
    await asyncio.gather(*(crawl_source(s) for s in SOURCES))
    
    print("\n[3] Extracting web content...")
    docs = []
    raw_dir = Path("data/raw")
    if raw_dir.exists():
        raw_files = list(raw_dir.rglob("*.json"))
        total_files = len(raw_files)
        print(f"Found {total_files} raw files.")
        for i, f in enumerate(raw_files):
            if i % 500 == 0: print(f"  Extracting {i}/{total_files}...")
            try:
                data = json.loads(f.read_text(encoding='utf-8', errors='ignore'))
                if "html" in data:
                    text = extract_content(data["html"])
                    if text:
                        docs.append({
                            "url": data.get("url", ""),
                            "silo": data.get("silo", "unknown"),
                            "text": text,
                            "title": data.get("url", "")
                        })
            except Exception as e:
                pass
                
    print(f"\n[4] Injecting local engineering corpus...")
    local_docs = process_local_corpus("corpus/wcag-aaa-web-design")
    docs.extend(local_docs)
    
    print(f"\n[5] Parsing local axe-core rules...")
    axe_chunks = parse_axe_rules("axe-core/lib/rules")
    
    print(f"\n[6] Chunking {len(docs)} large documents...")
    all_chunks = []
    for i, doc in enumerate(docs):
        if i % 500 == 0: print(f"  Chunking {i}/{len(docs)}...")
        meta = {
            "url": doc["url"],
            "silo": doc["silo"],
            "title": doc.get("title", "")
        }
        all_chunks.extend(chunk_document(doc["text"], meta))
        
    all_chunks.extend(axe_chunks)
        
    print(f"\n[7] Filtering {len(all_chunks)} chunks for relevance...")
    filtered = [c for c in all_chunks if passes_filter(c)]
    
    print(f"\n[8] Deduplicating {len(filtered)} chunks...")
    unique = dedup(filtered)
    
    print(f"\n[9] Tagging metadata on {len(unique)} chunks...")
    tagged = [tag_chunk(c) for c in unique]
    
    print(f"\n[10] Generating Embeddings via all-MiniLM-L6-v2...")
    embedded = embed_chunks(tagged)
    
    print(f"\n[11] Storing mapped chunks into fresh ChromaDB...")
    store_chunks(embedded)
    
    print("=" * 60)
    print("✅ FREH INGESTION COMPLETE. RUN `python rag-pipeline/verify.py` to check coverage.")

if __name__ == "__main__":
    asyncio.run(main())
