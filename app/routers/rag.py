"""
RAG router: query the WCAG knowledge base.
"""
import logging
import re

from fastapi import APIRouter, HTTPException

from app.models import (
    PracticalAsset,
    RAGRequest,
    RAGResponse,
    RetrievedSource,
    TopicsResponse,
    WCAGReference,
)
from app.services.llm import generate_rag_response
from app.services.retrieval import retrieve
from app.services.vector_store import get_all_metadata_values

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG"])


def _explanation_to_text(raw: object) -> str:
    if isinstance(raw, str):
        return raw

    if isinstance(raw, dict):
        ordered_keys = ("what_is_broken", "impact", "wcag_sc", "intent", "verification")
        parts: list[str] = []
        for key in ordered_keys:
            value = str(raw.get(key, "") or "").strip()
            if value:
                parts.append(value)
        return "\n\n".join(parts)

    return str(raw or "")


def _extract_sc_id(text: str) -> str:
    match = re.search(r"\b(\d\.\d+\.\d+)\b", str(text or ""))
    if not match:
        return ""
    return match.group(1)


@router.post("", response_model=RAGResponse)
async def query_rag(request: RAGRequest):
    """
    Query the WCAG RAG knowledge base.
    Returns explanation, WCAG references, code fix, practical assets, and validation hints.
    """
    try:
        merged_filters = dict(request.filters or {})
        if not merged_filters.get("sc_id"):
            query_sc = _extract_sc_id(request.query)
            if query_sc:
                merged_filters["sc_id"] = query_sc
                merged_filters.setdefault("wcag_reference", query_sc)

        # 1. Retrieve relevant chunks
        chunks = await retrieve(
            query=request.query,
            filters=merged_filters,
        )

        if not chunks:
            raise HTTPException(
                status_code=404,
                detail="No relevant content found. Try rephrasing your query or check that ingestion has been run."
            )

        # 2. Generate response with LLM
        llm_response = await generate_rag_response(
            query=request.query,
            context_chunks=chunks,
        )

        explanation_text = _explanation_to_text(llm_response.get("explanation", ""))
        code_fix = str(llm_response.get("code_fix", "") or "")
        if not code_fix:
            fixes = llm_response.get("fixes")
            if isinstance(fixes, dict):
                code_fix = str(fixes.get("vanilla", "") or "")

        # 3. Build response
        return RAGResponse(
            explanation=explanation_text,
            wcag_references=[
                WCAGReference(**ref) for ref in llm_response.get("wcag_references", [])
            ],
            code_fix=code_fix,
            practical_assets=[
                PracticalAsset(**asset) for asset in llm_response.get("practical_assets", [])
            ],
            validation_hint=llm_response.get("validation_hint", ""),
            sources=[
                RetrievedSource(
                    content=c["content"][:500],  # Truncate for response
                    source=c["metadata"].get("source", "unknown"),
                    chunk_type=c["metadata"].get("chunk_type", "unknown"),
                    relevance_score=c.get("score", 0.0),
                )
                for c in chunks[:5]
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"RAG query error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal error: {e!s}")


@router.get("/topics", response_model=TopicsResponse)
async def get_topics():
    """List available topics, levels, and chunk types for filtering."""
    try:
        metadata = get_all_metadata_values()
        return TopicsResponse(
            topics=metadata["topics"],
            levels=metadata["levels"],
            chunk_types=metadata["chunk_types"],
        )
    except Exception as e:
        logger.error(f"Error getting topics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
