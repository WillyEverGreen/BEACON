"""
Retrieval service: bridged directly to the new `rag-pipeline/query.py`
Uses identical function signatures so `llm.py` can remain completely unchanged.
"""
import logging
import sys
import os
from typing import Optional

# Wire up the new rag-pipeline module
sys.path.insert(0, os.path.abspath("rag-pipeline"))
from query import hybrid_retrieve, rerank, expand_query

logger = logging.getLogger(__name__)

async def retrieve(
    query: str,
    filters: Optional[dict] = None,
    n_results: int = 10,
    use_query_expansion: bool = True,
) -> list[dict]:
    """Retrieve exactly as before, but powered by the new engine."""
    try:
        candidates = hybrid_retrieve(query, top_k=n_results * 2)
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
    """Helper to convert issue schema to search string"""
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
    Leverages CrossEncoder reranking from the new engine.
    """
    rule_id = issue.get("rule_id", "")
    desc = issue.get("description", "")
    
    # We use the pipeline's curated query expander as well
    expanded_str = expand_query(rule_id, desc)
    raw_issue_str = _issue_to_query(issue)
    
    final_query = f"{expanded_str} {raw_issue_str}"[:500]
    
    try:
        candidates = hybrid_retrieve(final_query, top_k=20)
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
