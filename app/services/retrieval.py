"""
Retrieval service: bridge to rag with Phase 4 guardrails.

Goals:
- prioritize WCAG-aligned chunks
- filter irrelevant/noisy context
- cap context chunk count to control token/cost
- cache repeated retrieval queries
- fall back to local WCAG corpus when primary retrieval is weak
"""
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Optional

from app.config import CACHE_STATS, settings

# Wire up the new rag module
_rag_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "rag"))
if _rag_path not in sys.path:
    sys.path.insert(0, _rag_path)

from query import hybrid_retrieve, rerank, expand_query  # noqa: E402

logger = logging.getLogger(__name__)

_TRUSTED_SILOS = {"wcag", "aria", "coga", "axe", "toolkit", "local_wcag_kb"}
_RELEVANCE_TERMS = {
    "wcag",
    "accessibility",
    "aria",
    "screen reader",
    "keyboard",
    "focus",
    "contrast",
    "success criterion",
    "non-text",
    "landmark",
    "label",
    "caption",
    "reflow",
    "target size",
    "name role value",
}
_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "have",
    "into",
    "about",
    "when",
    "where",
    "rule",
    "issue",
    "wcag",
}

_retrieval_cache: dict[str, list[dict[str, Any]]] = {}
_local_wcag_chunks: list[dict[str, Any]] | None = None


def _extract_wcag_reference(raw: str) -> str:
    match = re.search(r"\b(\d\.\d+\.\d+)\b", str(raw or ""))
    return match.group(1) if match else ""


def _bounded_chunk_limit(requested: int) -> int:
    cap = max(1, int(getattr(settings, "retrieval_max_chunks", 5) or 5))
    return max(1, min(int(requested or cap), cap))


def _candidate_window(limit: int) -> int:
    multiplier = max(2, int(getattr(settings, "retrieval_candidate_multiplier", 3) or 3))
    return max(limit * multiplier, limit + 4)


def _clone_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "content": str(chunk.get("content", "")),
            "metadata": dict(chunk.get("metadata", {}) or {}),
            "score": float(chunk.get("score", 0.0) or 0.0),
        }
        for chunk in chunks
    ]


def _cache_key(
    query: str,
    filters: Optional[dict],
    limit: int,
    wcag_reference: str,
    issue_type: str,
) -> str:
    payload = {
        "q": str(query or "")[:700],
        "filters": filters or {},
        "limit": int(limit),
        "wcag": str(wcag_reference or ""),
        "issue_type": str(issue_type or "").strip().lower(),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_enabled() -> bool:
    return bool(getattr(settings, "retrieval_enable_cache", True))


def _record_cache_stat(hit: bool) -> None:
    if hit:
        CACHE_STATS["retrieval_hits"] = int(CACHE_STATS.get("retrieval_hits", 0) or 0) + 1
    else:
        CACHE_STATS["retrieval_misses"] = int(CACHE_STATS.get("retrieval_misses", 0) or 0) + 1


def _cache_get(key: str) -> list[dict[str, Any]] | None:
    if not _cache_enabled():
        return None
    hit = _retrieval_cache.get(key)
    if hit is None:
        _record_cache_stat(hit=False)
        return None
    _record_cache_stat(hit=True)
    return _clone_chunks(hit)


def _cache_put(key: str, value: list[dict[str, Any]]) -> None:
    if not _cache_enabled():
        return
    max_entries = max(50, int(getattr(settings, "retrieval_cache_max_entries", 1500) or 1500))
    if len(_retrieval_cache) >= max_entries and key not in _retrieval_cache:
        oldest_key = next(iter(_retrieval_cache), None)
        if oldest_key:
            _retrieval_cache.pop(oldest_key, None)
    _retrieval_cache[key] = _clone_chunks(value)


def _normalize_metadata(meta: dict[str, Any] | None) -> dict[str, Any]:
    src = meta if isinstance(meta, dict) else {}
    source_silo = str(src.get("source_silo") or src.get("silo") or "").lower().strip()
    return {
        **src,
        "source_silo": source_silo,
    }


def _extract_query_terms(query: str) -> set[str]:
    terms = set()
    for token in re.findall(r"[a-zA-Z0-9_.-]+", str(query or "").lower()):
        if len(token) < 3:
            continue
        if token in _STOP_WORDS:
            continue
        terms.add(token)
    return terms


def _keyword_overlap_ratio(query_terms: set[str], text: str) -> float:
    if not query_terms:
        return 0.0
    text_terms = set(re.findall(r"[a-zA-Z0-9_.-]+", str(text or "").lower()))
    if not text_terms:
        return 0.0
    overlap = len(query_terms & text_terms)
    return overlap / max(1, len(query_terms))


def _chunk_has_signal(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(term in lowered for term in _RELEVANCE_TERMS)


def _metadata_wcag_tokens(meta: dict[str, Any]) -> set[str]:
    tokens: set[str] = set()
    for key in ("wcag_sc", "criterion_id", "wcag_reference"):
        raw = str(meta.get(key, "") or "")
        for match in re.findall(r"\b\d\.\d+\.\d+\b", raw):
            tokens.add(match)
    return tokens


def _matches_filters(meta: dict[str, Any], filters: Optional[dict]) -> bool:
    if not isinstance(filters, dict) or not filters:
        return True
    for key, expected in filters.items():
        if expected in (None, ""):
            continue
        expected_str = str(expected).strip().lower()
        if not expected_str:
            continue

        if key == "level":
            actual = str(meta.get("severity", "") or "").lower()
        elif key == "topic":
            actual = str(meta.get("topic", "") or "").lower()
        elif key == "chunk_type":
            actual = str(meta.get("chunk_type", "") or "").lower()
        else:
            actual = str(meta.get(key, "") or "").lower()

        if expected_str not in actual:
            return False
    return True


def _chunk_is_wcag_aligned(chunk: dict[str, Any], wcag_reference: str) -> bool:
    if not wcag_reference:
        return False
    metadata = _normalize_metadata(chunk.get("metadata", {}))
    text = str(chunk.get("content", "") or "")
    return wcag_reference in _metadata_wcag_tokens(metadata) or wcag_reference in text


def _merge_unique(
    primary: list[dict[str, Any]],
    secondary: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for chunk in [*primary, *secondary]:
        content = str(chunk.get("content", "") or "").strip()
        if not content:
            continue
        fingerprint = hashlib.sha1(content[:500].encode("utf-8", errors="ignore")).hexdigest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        merged.append(chunk)
        if len(merged) >= limit:
            break
    return merged


def _split_local_text(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    chunks: list[str] = []
    for part in parts:
        normalized = re.sub(r"\s+", " ", str(part or "")).strip()
        if len(normalized) < 120:
            continue
        if len(normalized) > 900:
            normalized = normalized[:900]
        chunks.append(normalized)
    return chunks


def _load_local_wcag_chunks() -> list[dict[str, Any]]:
    global _local_wcag_chunks
    if _local_wcag_chunks is not None:
        return _local_wcag_chunks

    root = Path(__file__).resolve().parents[2]
    corpus_dir = root / "corpus" / "wcag-aaa-web-design"
    if not corpus_dir.exists():
        logger.warning("Local WCAG corpus directory not found: %s", corpus_dir)
        _local_wcag_chunks = []
        return _local_wcag_chunks

    max_local_chunks = max(200, int(getattr(settings, "retrieval_local_max_chunks", 2500) or 2500))
    loaded: list[dict[str, Any]] = []
    valid_ext = {".md", ".txt", ".html", ".json"}

    try:
        for path in corpus_dir.rglob("*"):
            if len(loaded) >= max_local_chunks:
                break
            if not path.is_file() or path.suffix.lower() not in valid_ext:
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            if not text.strip():
                continue

            rel_path = path.relative_to(corpus_dir).as_posix()
            for chunk in _split_local_text(text):
                loaded.append(
                    {
                        "content": chunk,
                        "metadata": {
                            "source": "local_wcag_corpus",
                            "source_silo": "local_wcag_kb",
                            "chunk_type": "fallback",
                            "filename": rel_path,
                            "url": f"local://{rel_path}",
                        },
                    }
                )
                if len(loaded) >= max_local_chunks:
                    break
    except Exception as exc:
        logger.warning("Failed loading local WCAG corpus: %s", exc)

    _local_wcag_chunks = loaded
    return _local_wcag_chunks


def _local_wcag_fallback(
    query: str,
    wcag_reference: str,
    issue_type: str,
    limit: int,
) -> list[dict[str, Any]]:
    chunks = _load_local_wcag_chunks()
    if not chunks:
        return []

    query_terms = _extract_query_terms(query)
    issue_type_term = str(issue_type or "").strip().lower()

    ranked: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        content = str(chunk.get("content", "") or "")
        if not content:
            continue

        overlap = _keyword_overlap_ratio(query_terms, content)
        wcag_match = bool(wcag_reference and wcag_reference in content)
        issue_match = bool(issue_type_term and issue_type_term in content.lower())

        if not wcag_match and overlap <= 0.0:
            continue

        score = overlap
        if wcag_match:
            score += 0.9
        if issue_match:
            score += 0.2

        ranked.append(
            (
                score,
                {
                    "content": content,
                    "metadata": _normalize_metadata(chunk.get("metadata", {})),
                    "score": float(score),
                },
            )
        )

    ranked.sort(key=lambda row: row[0], reverse=True)
    return [item for _, item in ranked[:limit]]


def _select_relevant_chunks(
    query: str,
    candidates: list[dict[str, Any]],
    *,
    wcag_reference: str,
    issue_type: str,
    limit: int,
    filters: Optional[dict] = None,
) -> list[dict[str, Any]]:
    if not candidates:
        return []

    min_relevance = float(getattr(settings, "retrieval_min_relevance", 0.15) or 0.15)
    query_terms = _extract_query_terms(query)
    issue_type_norm = str(issue_type or "").strip().lower()
    ranked: list[tuple[float, dict[str, Any]]] = []

    for candidate in candidates:
        text = str(candidate.get("text", "") or "").strip()
        if not text:
            continue

        raw_meta = candidate.get("meta", {})
        meta = _normalize_metadata(raw_meta if isinstance(raw_meta, dict) else {})
        if not _matches_filters(meta, filters):
            continue

        source_silo = str(meta.get("source_silo", "") or "").lower()
        trusted = source_silo in _TRUSTED_SILOS
        base_score = float(candidate.get("score", 0.0) or 0.0)
        overlap = _keyword_overlap_ratio(query_terms, text)
        wcag_match = bool(
            wcag_reference
            and (
                wcag_reference in _metadata_wcag_tokens(meta)
                or wcag_reference in text
            )
        )
        issue_match = bool(
            issue_type_norm
            and issue_type_norm in str(meta.get("issue_type", "") or "").strip().lower()
        )

        if not trusted and not wcag_match and overlap <= 0.0:
            continue
        if not trusted and not _chunk_has_signal(text):
            continue
        if base_score < min_relevance and not wcag_match and overlap < 0.15:
            continue

        adjusted = base_score
        if trusted:
            adjusted += 0.35
        if wcag_match:
            adjusted += 0.45
        if issue_match:
            adjusted += 0.15
        adjusted += min(0.25, overlap * 0.5)

        ranked.append(
            (
                adjusted,
                {
                    "content": text,
                    "metadata": meta,
                    "score": float(adjusted),
                },
            )
        )

    ranked.sort(key=lambda row: row[0], reverse=True)
    selected = [item for _, item in ranked[: max(limit * 2, limit + 2)]]

    # Keep result set compact and deterministic.
    deduped = _merge_unique(selected, [], limit=limit)

    # If WCAG criterion exists, ensure at least one aligned chunk if possible.
    if wcag_reference and deduped and not any(_chunk_is_wcag_aligned(c, wcag_reference) for c in deduped):
        aligned = [item for _, item in ranked if _chunk_is_wcag_aligned(item, wcag_reference)]
        if aligned:
            deduped = _merge_unique(aligned[:1], deduped, limit=limit)

    return deduped[:limit]


async def _retrieve_primary_candidates(query: str, window: int) -> list[dict[str, Any]]:
    try:
        candidates = await asyncio.to_thread(hybrid_retrieve, query, window)
        if not candidates:
            return []
        reranked = rerank(query, candidates, top_n=window)
        return reranked if isinstance(reranked, list) else []
    except Exception as exc:
        logger.error("Primary retrieval failed: %s", exc)
        return []


async def retrieve(
    query: str,
    filters: Optional[dict] = None,
    n_results: int = 10,
    use_query_expansion: bool = True,
) -> list[dict]:
    """Retrieve filtered, WCAG-aligned context chunks with cache and fallback."""
    del use_query_expansion  # Reserved for future parity with issue retrieval.

    limit = _bounded_chunk_limit(n_results)
    issue_type = str((filters or {}).get("issue_type", "") or "")
    wcag_reference = _extract_wcag_reference(str((filters or {}).get("wcag_reference", "") or query))
    key = _cache_key(query=query, filters=filters, limit=limit, wcag_reference=wcag_reference, issue_type=issue_type)

    cached = _cache_get(key)
    if cached is not None:
        return cached

    primary = await _retrieve_primary_candidates(query, _candidate_window(limit))
    selected = _select_relevant_chunks(
        query,
        primary,
        wcag_reference=wcag_reference,
        issue_type=issue_type,
        limit=limit,
        filters=filters,
    )

    # Force WCAG alignment supplement when we can identify a criterion.
    if wcag_reference and (not selected or not any(_chunk_is_wcag_aligned(c, wcag_reference) for c in selected)):
        supplemental = _local_wcag_fallback(query, wcag_reference, issue_type, limit=1)
        selected = _merge_unique(supplemental, selected, limit=limit)

    if not selected and bool(getattr(settings, "retrieval_local_fallback_enabled", True)):
        selected = _local_wcag_fallback(query, wcag_reference, issue_type, limit=limit)

    _cache_put(key, selected)
    return selected


def _issue_to_query(issue: dict) -> str:
    """Convert issue schema into retrieval search terms."""
    parts = []
    rule_id = issue.get("rule_id", "")
    wcag = _extract_wcag_reference(issue.get("wcag_criterion", ""))
    description = issue.get("description", "")
    element = issue.get("element", "")

    if wcag:
        parts.append(f"WCAG {wcag}")
    if rule_id:
        parts.append(str(rule_id).replace("-", " "))
    if description:
        parts.append(str(description)[:220])
    if element and element not in ("<body>", "<head>"):
        parts.append(f"element: {element}")

    return " ".join(parts) if parts else "web accessibility issue"


async def retrieve_for_issue(
    issue: dict,
    n_results: int = 8,
) -> list[dict]:
    """
    Called by llm.py when enriching findings.
    Uses constrained retrieval + fallback to keep context precise and low-noise.
    """
    limit = _bounded_chunk_limit(n_results)
    rule_id = str(issue.get("rule_id", "") or "")
    description = str(issue.get("description", "") or "")
    wcag_reference = _extract_wcag_reference(str(issue.get("wcag_criterion", "") or ""))
    issue_type = str(issue.get("issue_type", "") or "")

    expanded_query = expand_query(rule_id, description)
    issue_query = _issue_to_query(issue)
    final_query = f"{expanded_query} {issue_query}"[:700]

    cache_filters = {
        "wcag_reference": wcag_reference,
        "issue_type": issue_type,
    }
    key = _cache_key(
        query=final_query,
        filters=cache_filters,
        limit=limit,
        wcag_reference=wcag_reference,
        issue_type=issue_type,
    )

    cached = _cache_get(key)
    if cached is not None:
        return cached

    primary = await _retrieve_primary_candidates(final_query, _candidate_window(limit))
    selected = _select_relevant_chunks(
        final_query,
        primary,
        wcag_reference=wcag_reference,
        issue_type=issue_type,
        limit=limit,
        filters=None,
    )

    if wcag_reference and (not selected or not any(_chunk_is_wcag_aligned(c, wcag_reference) for c in selected)):
        supplemental = _local_wcag_fallback(final_query, wcag_reference, issue_type, limit=1)
        selected = _merge_unique(supplemental, selected, limit=limit)

    if not selected and bool(getattr(settings, "retrieval_local_fallback_enabled", True)):
        selected = _local_wcag_fallback(final_query, wcag_reference, issue_type, limit=limit)

    _cache_put(key, selected)
    return selected
