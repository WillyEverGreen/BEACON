"""
Retrieval service: bridged directly to the new `rag-pipeline/query.py`
Uses identical function signatures so `llm.py` can remain completely unchanged.

Wraps synchronous rag-pipeline calls in asyncio.to_thread() to prevent
blocking the FastAPI event loop.
"""
import asyncio
import logging
import sys
import os
from typing import Optional

# Wire up the new rag-pipeline module
_rag_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "rag-pipeline"))
if _rag_path not in sys.path:
    sys.path.insert(0, _rag_path)

from query import hybrid_retrieve, rerank, expand_query

logger = logging.getLogger(__name__)


async def retrieve(
    query: str,
    filters: Optional[dict] = None,
    n_results: int = 10,
    use_query_expansion: bool = True,
) -> list[dict]:
    """Retrieve exactly as before, but powered by the new engine.
    
    Uses asyncio.to_thread() to run the synchronous hybrid_retrieve
    without blocking the event loop.
    """
    try:
        # Run sync retrieval in a thread pool to avoid blocking the event loop
        candidates = await asyncio.to_thread(hybrid_retrieve, query, n_results * 2)
        top_n = rerank(query, candidates, top_n=n_results)
        
        # Reformats the dict from {"text", "meta", "score"} to the structure LLM.py expects
        formatted = []
        for c in top_n:
            formatted.append({
                "content": c["text"],
                "metadata": c["meta"],
                "score": float(c.get("score", 0.0))
            })
        return formatted
    except Exception as e:
        logger.error(f"Retrieval failed via rag-pipeline bridge: {e}")
        return []


def _issue_to_query(issue: dict) -> str:
    """Helper to convert issue schema to search string."""
    parts = []
    rule_id = issue.get("rule_id", "")
    wcag = issue.get("wcag_criterion", "")
    description = issue.get("description", "")
    element = issue.get("element", "")

    if wcag:
        parts.append(f"WCAG {wcag}")
    if rule_id:
        parts.append(rule_id.replace("-", " "))
    if description:
        parts.append(description[:200])
    if element and element not in ("<body>", "<head>"):
        parts.append(f"element: {element}")

    return " ".join(parts) if parts else "web accessibility issue"


async def retrieve_for_issue(
    issue: dict,
    n_results: int = 8,
) -> list[dict]:
    """
    Called by llm.py when enriching findings.
    Leverages the hybrid retrieval engine with query expansion.
    
    Uses asyncio.to_thread() to prevent event loop blocking.
    """
    rule_id = issue.get("rule_id", "")
    desc = issue.get("description", "")
    
    # We use the pipeline's curated query expander as well
    expanded_str = expand_query(rule_id, desc)
    raw_issue_str = _issue_to_query(issue)
    
    final_query = f"{expanded_str} {raw_issue_str}"[:500]
    
    try:
        candidates = await asyncio.to_thread(hybrid_retrieve, final_query, 20)
        top_n = rerank(final_query, candidates, top_n=n_results)
        
        formatted = []
        for c in top_n:
            formatted.append({
                "content": c["text"],
                "metadata": c["meta"],
                "score": float(c.get("score", 0.0))
            })
        return formatted
    except Exception as e:
        logger.error(f"Issue retrieval failed via rag-pipeline bridge: {e}")
        return []
