# test_depth.py
import sys, os
sys.path.insert(0, os.path.abspath("rag-pipeline"))
import asyncio
from query import hybrid_retrieve, rerank

async def test_queries():
    queries = [
        "aria-label vs aria-labelledby for complex widgets",
        "accessibility of CSS generated content ::before ::after",
        "WCAG 2.2 touch target spacing 2.5.8",
    ]

    for q in queries:
        print(f"\n--- Testing Query: {q} ---")
        try:
            candidates = hybrid_retrieve(q, top_k=10)
            top = rerank(q, candidates, top_n=3)
            for i, c in enumerate(top):
                meta = c['meta']
                silo = meta.get('source_silo', meta.get('silo', 'unknown'))
                print(f"[{i+1}] SILO: {silo} | URL: {meta.get('url')}")
                print(f"    PREVIEW: {c['text'][:200]}...")
        except Exception as e:
            print(f"Error testing {q}: {e}")

if __name__ == "__main__":
    asyncio.run(test_queries())
