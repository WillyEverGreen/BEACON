from rank_bm25 import BM25Okapi
import chromadb, functools, time, logging, re

from model_registry import get_embedding_model, get_bm25_cache, get_rerank_model

logger = logging.getLogger("rag-query")

# ── Named Constants ───────────────────────────────────────────
RRF_K = 60
NOISE_GUARD_MIN_WORD_LEN = 3
CONFIDENCE_CONSENSUS_THRESHOLD = 0.40
LOW_CONFIDENCE_CHUNK_LIMIT = 1
MAX_CONTEXT_CHUNKS = 5          # Hard cap: prevents latency/cost/hallucination from over-long prompts
CHROMA_PERSIST_DIR = "./chroma_db"
CHROMA_COLLECTION = "accessibility_kb"

# ── Lazy ChromaDB connection ──────────────────────────────────
_chroma_client = None
_chroma_col = None


def _get_chroma_collection():
    """Lazy-init ChromaDB collection with error recovery."""
    global _chroma_client, _chroma_col
    if _chroma_col is not None:
        return _chroma_col
    try:
        _chroma_client = chromadb.PersistentClient(CHROMA_PERSIST_DIR)
        _chroma_col = _chroma_client.get_collection(CHROMA_COLLECTION)
        return _chroma_col
    except Exception as e:
        logger.error(f"ChromaDB connection failed: {e}")
        return None


# ── CACHED BM25 INDEX (built ONCE, not per query) ────────────
_bm25_cache = get_bm25_cache()

def _get_bm25():
    """Load corpus + build BM25 index exactly once, then cache."""
    if "index" not in _bm25_cache:
        col = _get_chroma_collection()
        if col is None:
            logger.warning("ChromaDB unavailable — BM25 index empty")
            return None, [], []
        t0 = time.time()
        all_items = col.get(include=["documents", "metadatas"])
        corpus = all_items["documents"]
        metas  = all_items["metadatas"]
        tokenized = [d.lower().split() for d in corpus]
        _bm25_cache["index"]  = BM25Okapi(tokenized)
        _bm25_cache["corpus"] = corpus
        _bm25_cache["metas"]  = metas
        logger.info(f"BM25 Index built: {len(corpus)} docs in {time.time()-t0:.2f}s (cached)")
    return _bm25_cache["index"], _bm25_cache["corpus"], _bm25_cache["metas"]


ISSUE_QUERY_MAP = {
    # HTML / structure
    "missing_lang":          "WCAG 3.1.1 lang attribute html page language",
    "missing_title":         "WCAG 2.4.2 unique descriptive page title",
    "non_semantic_html":     "WCAG 1.3.1 semantic HTML header nav main footer aside",
    "content_order":         "WCAG 1.3.2 meaningful sequence DOM reading order",
    "zoom_disabled":         "WCAG 1.4.4 resize text viewport meta zoom",
    # Keyboard
    "keyboard_inaccessible": "WCAG 2.1.1 keyboard accessible all functionality",
    "keyboard_trap":         "WCAG 2.1.2 no keyboard trap focus escape",
    "positive_tabindex":     "WCAG 2.4.3 focus order tabindex positive avoid",
    "modal_focus":           "WCAG 2.1.1 modal dialog focus management trap",
    "missing_focus_style":   "WCAG 2.4.7 2.4.11 focus visible indicator style",
    "focus_obscured":        "WCAG 2.4.11 2.4.12 focus not obscured component sticky header",
    "focus_appearance":      "WCAG 2.4.13 focus appearance indicator size contrast",
    # Appearance / animation
    "color_only":            "WCAG 1.4.1 color not sole means conveying information",
    "flashing":              "WCAG 2.3.1 three flashes animation seizure trigger",
    "no_reflow":             "WCAG 1.4.10 reflow 320px horizontal scroll",
    "custom_fonts":          "WCAG 1.4.12 text spacing custom font override",
    "prefers_motion":        "WCAG 2.3.3 prefers-reduced-motion animation",
    # Forms
    "missing_label":         "WCAG 1.3.1 3.3.2 form input label for id association",
    "inaccessible_errors":   "WCAG 3.3.1 error identification accessible list text",
    "error_not_linked":      "WCAG 3.3.1 aria-describedby error message input link",
    "no_autocomplete":       "WCAG 1.3.5 autocomplete attribute input field",
    "no_focus_on_input":     "WCAG 2.4.7 interactive controls visible focus state",
    "redundant_entry":       "WCAG 3.3.7 redundant entry auto-populate previously entered information",
    "auth_cognitive":        "WCAG 3.3.8 3.3.9 accessible authentication no cognitive function test",
    # Content
    "sensory_only":          "WCAG 1.3.3 sensory characteristics instruction color position",
    "non_unique_labels":     "WCAG 2.4.6 descriptive unique labels headings",
    "table_no_semantic":     "WCAG 1.3.1 table thead tbody tr td semantic markup",
    "table_no_scope":        "WCAG 1.3.1 th scope header cell association",
    "table_no_caption":      "WCAG 1.3.1 caption table description",
    "lang_change":           "WCAG 3.1.2 lang attribute inline foreign language phrase",
    "unexplained_jargon":    "WCAG 3.1.3 unusual words jargon definition",
    "unexplained_abbrev":    "WCAG 3.1.4 abbreviations expansion first use",
    # Links & buttons
    "non_descriptive_link":  "WCAG 2.4.4 link purpose descriptive text click here",
    "no_underline_link":     "WCAG 1.4.1 link visually distinguishable underline",
    "wrong_element":         "WCAG 4.1.2 anchor button correct semantic element purpose",
    "unlabeled_button":      "WCAG 4.1.2 button no text aria-label accessible name",
    "no_new_tab_warning":    "WCAG 3.2.2 opens new window tab warning icon",
    "small_target":          "WCAG 2.5.8 target size minimum 24px touch",
    "no_dragging_alt":       "WCAG 2.5.7 dragging movements alternative single pointer",
    # Color contrast
    "low_contrast_normal":   "WCAG 1.4.3 contrast ratio 4.5:1 normal text",
    "low_contrast_large":    "WCAG 1.4.3 contrast 3:1 large text bold 19px 24px",
    "low_contrast_image":    "WCAG 1.4.3 text over image contrast readable",
    "low_contrast_icon":     "WCAG 1.4.11 non-text contrast icon graphic 3:1",
    "low_contrast_ui":       "WCAG 1.4.11 UI component border button focus ring 3:1",
    # Headings
    "wrong_heading_use":     "WCAG 1.3.1 2.4.6 heading structure semantic not style",
    "multiple_h1":           "WCAG 1.3.1 single h1 per page",
    "skipped_heading":       "WCAG 1.3.1 heading levels h2 h3 no skip",
    "no_list_markup":        "WCAG 1.3.1 list ul ol dl semantic markup",
    "no_skip_link":          "WCAG 2.4.1 skip navigation first link bypass blocks",
    "no_multiple_nav":       "WCAG 2.4.5 multiple ways search sitemap navigation",
    "no_consistent_help":    "WCAG 3.2.6 consistent help location contact support",
    # Images
    "missing_alt":           "WCAG 1.1.1 img alt attribute non-text content",
    "decorative_no_empty":   "WCAG 1.1.1 decorative image alt empty string",
    "complex_image_no_desc": "WCAG 1.1.1 complex image chart graph long description",
    "image_text_no_alt":     "WCAG 1.1.1 image containing text alt attribute include",
    "image_of_text":         "WCAG 1.4.5 avoid images of text CSS instead",
    # Media
    "media_autoplay":        "WCAG 1.4.2 audio video autoplay control prevent",
    "media_no_pause":        "WCAG 2.2.2 pause stop hide moving media",
    "inaccessible_player":   "WCAG 4.1.2 custom media player ARIA roles keyboard",
    "no_captions":           "WCAG 1.2.2 captions prerecorded video synchronized",
    "no_transcript":         "WCAG 1.2.1 audio transcript text alternative",
    "seizure_trigger":       "WCAG 2.3.1 flashing content three times per second",
    # ARIA
    "focus_triggers_change": "WCAG 3.2.1 focus change context unexpected",
    "input_triggers_submit": "WCAG 3.2.2 on input change no auto submit",
    "native_over_aria":      "WCAG 4.1.2 prefer native HTML elements over ARIA",
    "missing_aria_role":     "WCAG 4.1.2 custom widget ARIA role button tab",
    "static_aria_state":     "WCAG 4.1.3 ARIA state dynamic aria-expanded aria-selected",
    "no_accessible_name":    "WCAG 4.1.2 element no visible label aria-label labelledby",
    "decorative_not_hidden": "WCAG 1.1.1 aria-hidden decorative content screen reader",
    "missing_aria_live":     "WCAG 4.1.3 dynamic content aria-live polite assertive",
}

@functools.lru_cache(maxsize=256)
def _cached_embed(query: str):
    """Cache embedding vectors to avoid re-encoding repeated queries."""
    model = get_embedding_model()
    return tuple(model.encode(query, normalize_embeddings=True).tolist())

def expand_query(issue_id: str, raw: str) -> str:
    return ISSUE_QUERY_MAP.get(issue_id, f"WCAG accessibility: {raw}")


def is_code_query(query: str) -> bool:
    """Detect if a query is a structural code snippet (CSS, HTML tags, JS)."""
    code_symbols = ["{", "}", ";", ":", "()", "<", ">", "=\"", "alt="]
    return any(sym in query for sym in code_symbols)


def hybrid_retrieve(query: str, top_k: int = 15) -> list[dict]:
    """
    OPTION A: Pure Bi-Encoder + Score Fusion.
    We pull the top_k from Vector search and top_k from BM25,
    fuse them together strictly mathematically using Reciprocal Rank Fusion,
    and return the top 5 without any heavy CrossEncoder processing.
    """
    # ── Vector search (fast: ChromaDB ANN) ──
    col = _get_chroma_collection()
    if col is None:
        logger.warning("ChromaDB unavailable — returning empty results")
        return []

    emb = list(_cached_embed(query))
    try:
        vec_results = col.query(
            query_embeddings=[emb], n_results=top_k,
            include=["documents","metadatas","distances"]
        )
    except Exception as e:
        logger.error(f"ChromaDB query failed: {e}")
        return []

    if not vec_results["documents"] or not vec_results["documents"][0]:
        return []
        
    vec_docs  = vec_results["documents"][0]
    vec_metas = vec_results["metadatas"][0]

    # ── BM25 search (cached index) ──
    bm25, corpus, metas = _get_bm25()
    bm25_scores = bm25.get_scores(query.lower().split())
    
    # Fast top-K sort for the BM25 float array
    top_bm25_idx = sorted(range(len(bm25_scores)),
                          key=lambda i: bm25_scores[i], reverse=True)[:top_k]
    bm25_docs  = [corpus[i] for i in top_bm25_idx]
    bm25_metas = [metas[i] for i in top_bm25_idx]

    # ── Option A: Reciprocal Rank Fusion (RRF) ──
    # The math that makes the Bi-Encoder so powerful without a reranker
    def rrfScore(rank, k=RRF_K): return 1 / (k + rank + 1)

    scores = {}
    for rank, doc in enumerate(vec_docs):
        scores[doc] = scores.get(doc, 0) + rrfScore(rank)
    for rank, doc in enumerate(bm25_docs):
        scores[doc] = scores.get(doc, 0) + rrfScore(rank)

    doc_meta = {}
    for doc, meta in zip(vec_docs, vec_metas):
        doc_meta[doc] = meta
    for doc, meta in zip(bm25_docs, bm25_metas):
        if doc not in doc_meta:
            doc_meta[doc] = meta

    # Sort strictly by RRF Score and slice the absolute best
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    
    results = [{"text": doc, "meta": doc_meta.get(doc, {}), "score": sc}
               for doc, sc in ranked]
               
    # ── Option B: Token-Level Noise Guard (Keyword Overlap) ──
    # Guard against LLM or hardware hallucinated queries
    # BYPASS if this is a structural code query (CSS, HTML, etc.)
    if is_code_query(query):
        return results

    words = [w.lower() for w in query.split() if len(w) > NOISE_GUARD_MIN_WORD_LEN]
    if words:
        has_overlap = False
        query_words = set(words)
        for res in results[:3]:  # Check top 3 chunks
            # High-performance regex cleaning for token-level matching
            text_lower = res["text"].lower()
            clean_text = re.sub(r'[^\w\s]', ' ', text_lower)
            text_words = set(clean_text.split())
            if query_words & text_words:  # Fast token-level overlap
                has_overlap = True
                break
        if not has_overlap:
            logger.warning(f"Noise Guard rejected query '{query}' due to 0% keyword overlap.")
            return []

    return results


def rerank(query: str, candidates: list[dict], top_n: int = 5) -> list[dict]:
    """
    Rerank candidates using a heavy CrossEncoder.
    Fuses bi-encoder retrieval results with lexical BM25, then re-orders them
    to put the absolute most relevant at position #1.
    """
    if not candidates:
        return []
    try:
        reranker = get_rerank_model()
        # Form (query, document) pairs for the model
        pairs = [(query, c["text"]) for c in candidates]
        scores = reranker.predict(pairs)
        
        # Zip scores with candidates and sort by score descending
        ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
        return [c for _, c in ranked[:top_n]]
    except Exception as e:
        logger.error(f"Reranking failed: {e}. Falling back to default top-N.")
        return candidates[:top_n]


def answer(issue_id: str, raw_description: str, element_html: str,
           severity: str = None) -> dict:
    query      = expand_query(issue_id, raw_description)
    candidates = hybrid_retrieve(query)
    top_n      = rerank(query, candidates)
    
    # ── Option C & D: Calibrated Confidence + Safe Fallback ──
    confidence = "HIGH"
    if not top_n:
        confidence = "ZERO (REJECTED)"
    else:
        # Normalize confidence: the share of score held by the top result
        sum_scores = sum(c["score"] for c in top_n)
        norm_score = top_n[0]["score"] / sum_scores if sum_scores else 0
        
        # Calibration: 0.25 is a strict heuristic for significant ranking consensus
        if norm_score < CONFIDENCE_CONSENSUS_THRESHOLD:
            confidence = "LOW"
            logger.warning(f"Low retrieval confidence ({norm_score:.2f}). Falling back to safe {LOW_CONFIDENCE_CHUNK_LIMIT}-chunk limit.")
            top_n = top_n[:LOW_CONFIDENCE_CHUNK_LIMIT]
        
    # Enforce max context limit: too many chunks = latency + cost + hallucination risk
    if top_n:
        top_n = top_n[:MAX_CONTEXT_CHUNKS]

    context    = "\n\n---\n\n".join(c["text"] for c in top_n)
    sources    = [c["meta"].get("url","") for c in top_n]
    wcag_scs   = list({sc for c in top_n
                       for sc in c["meta"].get("wcag_sc","").split(",") if sc})
    return {
        "query":        query,
        "confidence":   confidence,
        "context":      context,
        "sources":      sources,
        "wcag_sc":      wcag_scs,
        "element_html": element_html,
        "raw_chunks":   [{"content": c["text"], "metadata": c["meta"], "score": float(c["score"])} for c in top_n]
    }
