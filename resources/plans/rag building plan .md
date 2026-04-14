Here is the complete final plan with every value corrected — only the WCAG count, comments, and target metrics updated, everything else identical.

---

## Phase 0 — Environment & project structure

```bash
python -m venv rag-env && source rag-env/bin/activate
pip install crawl4ai playwright httpx beautifulsoup4 lxml \
            tiktoken sentence-transformers chromadb \
            rank-bm25 scikit-learn tqdm pydantic \
            sentence-transformers[cross-encoder] rich
playwright install chromium
```

```
rag/
├── config.py        ← all constants, source manifest, keyword maps
├── crawl.py         ← Phase 1: fetch raw HTML
├── extract.py       ← Phase 2: clean content
├── chunk.py         ← Phase 3: split into concept chunks
├── filter.py        ← Phase 4: relevance gate
├── dedup.py         ← Phase 5: MD5 + Jaccard
├── tag.py           ← Phase 6: metadata enrichment
├── embed.py         ← Phase 7: vector embeddings
├── store.py         ← Phase 8: ChromaDB ingestion
├── axe_parser.py    ← local axe-core rule extractor
├── query.py         ← online retrieval pipeline
├── verify.py        ← WCAG 2.2 coverage checker
└── data/
    ├── raw/         ← crawled HTML per silo
    ├── extracted/   ← cleaned text
    ├── chunks/      ← chunked JSON
    └── final/       ← tagged, deduped, ready to embed
```

---

## Phase 1 — Crawling

```python
# config.py
SOURCES = [
  { "silo": "wcag",   "url": "https://w3c.github.io/wcag/guidelines/22/",     "depth": 2 },
  { "silo": "wcag",   "url": "https://w3c.github.io/wcag/understanding/22/",  "depth": 3 },
  { "silo": "wcag",   "url": "https://www.w3.org/TR/WCAG22/",                 "depth": 1 },
  { "silo": "aria",   "url": "https://w3c.github.io/aria/",                   "depth": 3 },
  { "silo": "aria",   "url": "https://w3c.github.io/aria-practices/",         "depth": 3 },
  { "silo": "coga",   "url": "https://w3c.github.io/coga/content-usable/",    "depth": 3 },
  { "silo": "mdn",    "url": "https://developer.mozilla.org/en-US/docs/Web/Accessibility", "depth": 2 },
  { "silo": "webaim", "url": "https://webaim.org/",                           "depth": 2 },
]

ALLOWED_DOMAINS = [
  "w3c.github.io", "www.w3.org",
  "developer.mozilla.org", "webaim.org"
]
BLOCKED_DOMAINS = ["github.com"]
```

```python
# crawl.py
import asyncio, hashlib, json
from pathlib import Path
from crawl4ai import AsyncWebCrawler
from urllib.parse import urlparse
from config import SOURCES, ALLOWED_DOMAINS

async def crawl_source(source):
    visited = set()
    queue = [(source["url"], 0)]

    async with AsyncWebCrawler() as crawler:
        while queue:
            url, depth = queue.pop(0)
            if url in visited or depth > source["depth"]:
                continue
            domain = urlparse(url).netloc
            if not any(domain.endswith(d) for d in ALLOWED_DOMAINS):
                continue
            visited.add(url)

            result = await crawler.arun(url=url)
            if not result.success:
                continue

            slug = hashlib.md5(url.encode()).hexdigest()[:10]
            out = Path(f"data/raw/{source['silo']}/{slug}.json")
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({
                "url": url, "silo": source["silo"],
                "html": result.html,
                "links": result.links.get("internal", [])
            }))

            for link in result.links.get("internal", []):
                href = link.get("href", "")
                if href and href not in visited:
                    queue.append((href, depth + 1))
```

```python
# axe_parser.py
import json
from pathlib import Path

def parse_axe_rules(rules_path="./axe-core/lib/rules"):
    chunks = []
    for f in Path(rules_path).glob("*.json"):
        rule = json.loads(f.read_text())
        text = (
            f"Rule: {rule['id']}\n"
            f"Description: {rule.get('description','')}\n"
            f"Help: {rule.get('help','')}\n"
            f"Tags: {', '.join(rule.get('tags',[]))}\n"
            f"Impact: {rule.get('impact','')}\n"
            f"Help URL: {rule.get('helpUrl','')}"
        )
        chunks.append({
            "text": text, "silo": "axe",
            "rule_id": rule["id"],
            "tags": rule.get("tags", []),
            "impact": rule.get("impact", ""),
            "url": rule.get("helpUrl", "")
        })
    return chunks
```

---

## Phase 2 — Extraction

```python
# extract.py
from bs4 import BeautifulSoup

KEEP_TAGS = {
    "main","article","section",
    "h1","h2","h3","h4",
    "p","ul","ol","li",
    "code","pre","blockquote",
    "table","thead","tbody","tr","td","th","caption"
}
STRIP_TAGS = {
    "nav","footer","header","aside",
    "script","style","noscript",
    "form","button","svg","img"
}

def extract_content(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all(list(STRIP_TAGS)):
        tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.find("body")
    if not root:
        return ""

    lines = []
    for elem in root.descendants:
        if elem.name in KEEP_TAGS:
            text = elem.get_text(" ", strip=True)
            if text and len(text) > 10:
                lines.append(text)

    return "\n\n".join(lines)
```

---

## Phase 3 — Chunking

```python
# chunk.py
import re, tiktoken

enc = tiktoken.get_encoding("cl100k_base")
CHUNK_MAX = 400
OVERLAP = 40

def token_len(text):
    return len(enc.encode(text))

def chunk_document(text: str, meta: dict) -> list[dict]:
    sections = re.split(r'\n(?=#{1,4} |\b[A-Z][^\n]{0,60}\n[-=]+)', text)
    chunks = []

    for section in sections:
        tokens = enc.encode(section.strip())
        if not tokens:
            continue
        if len(tokens) <= CHUNK_MAX:
            chunks.append({"text": enc.decode(tokens), **meta})
        else:
            start = 0
            while start < len(tokens):
                end = min(start + CHUNK_MAX, len(tokens))
                chunks.append({"text": enc.decode(tokens[start:end]), **meta})
                start += CHUNK_MAX - OVERLAP

    return [c for c in chunks if c["text"].strip()]
```

---

## Phase 4 — Relevance Filter

```python
# filter.py
import re

REQUIRED_TERMS = [
    "success criterion","wcag","aria","accessibility",
    "role=","alt=","aria-label","screen reader",
    "keyboard","focus","contrast","cognitive",
    "perceivable","operable","understandable","robust",
    "technique","failure","sufficient","advisory",
    "axe","violation","impact","heading","landmark",
    "caption","transcript","skip navigation","tab order",
    "target size","color alone","reflow","zoom","lang attribute",
    "autocomplete","fieldset","legend","aria-live","aria-expanded",
    "aria-describedby","prefers-reduced-motion","focus visible"
]

NOISE_PATTERNS = [
    r"^\s*(changelog|release notes|version \d)",
    r"copyright \d{4}",
    r"subscribe to our newsletter",
    r"^\s*menu\s*$",
    r"^\s*skip to (main )?content\s*$",
]

SAFE_SILOS = {"wcag", "aria", "coga", "axe"}

def passes_filter(chunk: dict) -> bool:
    if chunk.get("silo") in SAFE_SILOS:
        return True

    text = chunk["text"].lower()

    for pat in NOISE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return False

    if len(text.split()) < 20:
        return False

    return any(term in text for term in REQUIRED_TERMS)
```

---

## Phase 5 — Deduplication

```python
# dedup.py
import hashlib

def md5(text):
    return hashlib.md5(text.encode()).hexdigest()

def trigrams(text):
    w = text.lower().split()
    return set(zip(w, w[1:], w[2:]))

def jaccard(a, b):
    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)

def dedup(chunks: list[dict], threshold=0.85) -> list[dict]:
    seen = set()
    unique = []
    for chunk in chunks:
        h = md5(chunk["text"])
        if h in seen:
            continue
        seen.add(h)
        if any(jaccard(chunk["text"], p["text"]) > threshold for p in unique[-200:]):
            continue
        chunk["id"] = h
        unique.append(chunk)
    return unique
```

---

## Phase 6 — Metadata Tagging

```python
# tag.py
import re

WCAG_SC_RE = re.compile(r'\b(\d\.\d+\.\d+)\b')

SEVERITY_MAP = {
    "A":   ["level a","(level a)","level-a","conformance level a"],
    "AA":  ["level aa","(level aa)","level double-a","level-aa"],
    "AAA": ["level aaa","(level aaa)","level triple-a","level-aaa"],
}

ISSUE_TYPES = {
    "images":      ["alt text","non-text content","1.1.1","decorative image","image of text"],
    "keyboard":    ["keyboard","focus","tab order","keyboard trap","tabindex","2.1","focus visible","2.4.7","2.4.11","2.4.12"],
    "color":       ["contrast","color alone","1.4.3","1.4.11","1.4.1","color blindness","4.5:1","3:1","7:1"],
    "structure":   ["heading","landmark","semantic","1.3.1","h1","h2","skip navigation","2.4.1","dom order","reading order"],
    "forms":       ["label","input","error","3.3","fieldset","legend","autocomplete","aria-describedby","3.3.1","3.3.2","3.3.7","3.3.8","3.3.9"],
    "timing":      ["timeout","pause","2.2","time limit","session"],
    "motion":      ["animation","flashing","2.3","prefers-reduced-motion","seizure","three flashes"],
    "cognitive":   ["coga","cognitive","plain language","memory","reading level","unusual terms","abbreviations","3.1.3","3.1.4","3.1.5","3.1.6"],
    "aria":        ["aria-","role=","aria-label","aria-labelledby","aria-live","aria-expanded","aria-selected","aria-hidden","aria-checked"],
    "media":       ["captions","audio description","transcript","1.2","sign language","media alternative"],
    "links":       ["link text","new window","new tab","target size","24px","44px","2.5.8","2.5.5","click here"],
    "language":    ["lang attribute","language of page","3.1.1","3.1.2","foreign phrase"],
    "responsive":  ["reflow","320px","zoom","resize","1.4.10","1.4.4","viewport","horizontal scroll"],
    "appearance":  ["prefers-color-scheme","prefers-contrast","prefers-reduced-transparency","custom fonts","dyslexia"],
    "tables":      ["table","thead","tbody","th scope","caption","tabular data"],
    "navigation":  ["consistent help","3.2.6","redundant entry","3.3.7","dragging","2.5.7"],
    "auth":        ["accessible authentication","3.3.8","3.3.9","cognitive function test","captcha"],
    "focus":       ["focus not obscured","2.4.11","2.4.12","focus appearance","2.4.13","focus indicator"],
    "target":      ["target size","2.5.8","2.5.7","dragging movements","minimum 24px"],
}

USER_IMPACT = {
    "blind":          ["screen reader","alt text","1.1","aria","role=","non-text"],
    "low_vision":     ["contrast","resize","zoom","1.4.3","1.4.4","1.4.10","reflow"],
    "motor":          ["keyboard","pointer","timeout","2.1","2.2","target size","tabindex","dragging","2.5.7","2.5.8"],
    "deaf":           ["captions","transcript","sign language","1.2","audio"],
    "cognitive":      ["coga","plain language","reading level","memory","abbreviation","unusual terms","redundant entry","3.3.7","3.3.8","3.3.9","accessible authentication"],
    "photosensitive": ["flashing","animation","2.3","seizure","three flashes"],
    "dyslexia":       ["custom fonts","dyslexia","reading","spacing","1.4.12"],
}

def tag_chunk(chunk: dict) -> dict:
    text = chunk["text"].lower()
    raw  = chunk["text"]

    chunk["wcag_sc"]     = list(set(WCAG_SC_RE.findall(raw)))
    chunk["issue_types"] = [k for k, kws in ISSUE_TYPES.items() if any(kw in text for kw in kws)]
    chunk["issue_type"]  = chunk["issue_types"][0] if chunk["issue_types"] else "general"
    chunk["user_impact"] = [u for u, kws in USER_IMPACT.items() if any(kw in text for kw in kws)] or ["general"]
    chunk["severity"]    = "unknown"
    for lvl, kws in SEVERITY_MAP.items():
        if any(kw in text for kw in kws):
            chunk["severity"] = lvl
            break

    heading = re.search(r'^#{1,4}\s+(.+)$', raw, re.MULTILINE)
    chunk["topic"] = heading.group(1).strip() if heading else ""
    chunk["token_count"] = len(raw.split())

    return chunk
```

Final chunk schema:

```json
{
  "id": "a3f9c1d2e4",
  "text": "...",
  "silo": "wcag",
  "url": "https://w3c.github.io/wcag/understanding/22/...",
  "severity": "AA",
  "wcag_sc": ["1.4.3", "1.4.11"],
  "issue_type": "color",
  "issue_types": ["color", "appearance"],
  "user_impact": ["blind", "low_vision"],
  "topic": "Contrast (Minimum)",
  "token_count": 312
}
```

---

## Phase 7 — Embedding

```python
# embed.py
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_chunks(chunks: list[dict]) -> list[dict]:
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts, batch_size=64,
        show_progress_bar=True,
        normalize_embeddings=True
    )
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist()
    return chunks
```

---

## Phase 8 — Storage

```python
# store.py
import chromadb

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(
    name="accessibility_kb",
    metadata={"hnsw:space": "cosine"}
)

def store_chunks(chunks: list[dict]):
    for i in range(0, len(chunks), 100):
        batch = chunks[i:i+100]
        collection.add(
            ids        = [c["id"] for c in batch],
            embeddings = [c["embedding"] for c in batch],
            documents  = [c["text"] for c in batch],
            metadatas  = [{
                "silo":        c.get("silo", ""),
                "severity":    c.get("severity", "unknown"),
                "issue_type":  c.get("issue_type", "general"),
                "wcag_sc":     ",".join(c.get("wcag_sc", [])),
                "user_impact": ",".join(c.get("user_impact", [])),
                "topic":       c.get("topic", ""),
                "url":         c.get("url", ""),
                "token_count": str(c.get("token_count", 0)),
            } for c in batch]
        )
    print(f"Stored {len(chunks)} chunks total.")
```

---

## Online Query Pipeline

```python
# query.py
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
import chromadb, functools

embedder  = SentenceTransformer("all-MiniLM-L6-v2", normalize_embeddings=True)
reranker  = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
client    = chromadb.PersistentClient("./chroma_db")
col       = client.get_collection("accessibility_kb")

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
    return tuple(embedder.encode(query).tolist())

def expand_query(issue_id: str, raw: str) -> str:
    return ISSUE_QUERY_MAP.get(issue_id, f"WCAG accessibility: {raw}")

def hybrid_retrieve(query: str, top_k: int = 20) -> list[dict]:
    emb = list(_cached_embed(query))
    vec_results = col.query(
        query_embeddings=[emb], n_results=top_k,
        include=["documents","metadatas","distances"]
    )
    vec_docs  = vec_results["documents"][0]
    vec_metas = vec_results["metadatas"][0]

    all_items   = col.get(include=["documents","metadatas"])
    corpus      = all_items["documents"]
    tokenized   = [d.lower().split() for d in corpus]
    bm25        = BM25Okapi(tokenized)
    bm25_scores = bm25.get_scores(query.lower().split())
    top_bm25_idx = sorted(range(len(bm25_scores)),
                          key=lambda i: bm25_scores[i], reverse=True)[:top_k]
    bm25_docs  = [corpus[i] for i in top_bm25_idx]
    bm25_metas = [all_items["metadatas"][i] for i in top_bm25_idx]

    def rrfScore(rank, k=60): return 1 / (k + rank + 1)

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

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [{"text": doc, "meta": doc_meta.get(doc, {}), "score": sc}
            for doc, sc in ranked]

def rerank(query: str, candidates: list[dict], top_n: int = 3) -> list[dict]:
    if not candidates:
        return []
    pairs  = [(query, c["text"]) for c in candidates]
    scores = reranker.predict(pairs)
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    return [c for _, c in ranked[:top_n]]

def answer(issue_id: str, raw_description: str, element_html: str,
           severity: str = None) -> dict:
    query      = expand_query(issue_id, raw_description)
    candidates = hybrid_retrieve(query)
    top3       = rerank(query, candidates)
    context    = "\n\n---\n\n".join(c["text"] for c in top3)
    sources    = [c["meta"].get("url","") for c in top3]
    wcag_scs   = list({sc for c in top3
                       for sc in c["meta"].get("wcag_sc","").split(",") if sc})
    return {
        "query":        query,
        "context":      context,
        "sources":      sources,
        "wcag_sc":      wcag_scs,
        "element_html": element_html,
    }
```

LLM prompt template:

```python
PROMPT_TEMPLATE = """
You are an accessibility expert. A developer's audit found an issue.

ISSUE: {issue_id}
ELEMENT: {element_html}
WCAG CRITERIA: {wcag_sc}

REFERENCE KNOWLEDGE:
{context}

Your task:
1. Explain WHY this fails accessibility (2-3 sentences, plain language).
2. State which WCAG success criteria are violated and at what level (A/AA/AAA).
3. Describe who is affected and how.
4. Provide the corrected HTML/code with a brief explanation of each change.

Format your response as:
EXPLANATION: ...
WCAG: ...
IMPACT: ...
FIX:
```[html]
...corrected code...
```
"""
```

---

## Coverage verification

```python
# verify.py
# 86 active success criteria in WCAG 2.2
# (78 from WCAG 2.1, minus 4.1.1 Parsing which was removed, plus 9 new in 2.2)
# Note: some tools report 87 if they still count the obsolete 4.1.1

WCAG_22_ALL_SC = [
    # Principle 1 — Perceivable
    "1.1.1",
    "1.2.1","1.2.2","1.2.3","1.2.4","1.2.5","1.2.6","1.2.7","1.2.8","1.2.9",
    "1.3.1","1.3.2","1.3.3","1.3.4","1.3.5","1.3.6",
    "1.4.1","1.4.2","1.4.3","1.4.4","1.4.5","1.4.6","1.4.7","1.4.8","1.4.9",
    "1.4.10","1.4.11","1.4.12","1.4.13",
    # Principle 2 — Operable
    "2.1.1","2.1.2","2.1.3","2.1.4",
    "2.2.1","2.2.2","2.2.3","2.2.4","2.2.5","2.2.6",
    "2.3.1","2.3.2","2.3.3",
    "2.4.1","2.4.2","2.4.3","2.4.4","2.4.5","2.4.6","2.4.7","2.4.8","2.4.9","2.4.10",
    "2.4.11","2.4.12","2.4.13",                         # new in 2.2
    "2.5.1","2.5.2","2.5.3","2.5.4","2.5.5","2.5.6",
    "2.5.7","2.5.8",                                     # new in 2.2
    # Principle 3 — Understandable
    "3.1.1","3.1.2","3.1.3","3.1.4","3.1.5","3.1.6",
    "3.2.1","3.2.2","3.2.3","3.2.4","3.2.5",
    "3.2.6",                                             # new in 2.2
    "3.3.1","3.3.2","3.3.3","3.3.4","3.3.5","3.3.6",
    "3.3.7","3.3.8","3.3.9",                             # new in 2.2
    # Principle 4 — Robust
    # 4.1.1 intentionally excluded — removed/obsolete in WCAG 2.2
    "4.1.2","4.1.3",
]  # 86 total

def verify_coverage(collection):
    all_meta = collection.get(include=["metadatas"])["metadatas"]
    covered  = set()
    for meta in all_meta:
        for sc in meta.get("wcag_sc","").split(","):
            if sc.strip():
                covered.add(sc.strip())

    missing = [sc for sc in WCAG_22_ALL_SC if sc not in covered]
    print(f"\nWCAG 2.2 coverage: {len(WCAG_22_ALL_SC)-len(missing)}/{len(WCAG_22_ALL_SC)}")
    if missing:
        print(f"Missing SC: {missing}")
    else:
        print("Full WCAG 2.2 coverage confirmed (86/86).")
```

---

## Final targets & validation queries

| Metric | Target | How to check |
|---|---|---|
| Total chunks | 800–1200 | `collection.count()` |
| WCAG 2.2 SC coverage | 86/86 | `verify.py` |
| Avg chunk tokens | 80–380 | logged during chunking |
| Noise rate | < 5% | sample 50 random chunks |
| Retrieval precision (top 3) | > 80% | 20 hand-labelled test queries |
| Reranker latency | < 300ms | `time.perf_counter()` around `rerank()` |
| BM25 index rebuild time | < 10s | acceptable for 1200 docs |

Run all 5 of these queries before going live. The top 3 results for each must be on-topic:

1. `"img element missing alt attribute"`
2. `"text fails minimum contrast ratio 4.5:1"`
3. `"form input has no associated label"`
4. `"skip to main content link missing"`
5. `"button has no accessible name aria-label"`

If any return off-topic chunks in position 1–3, tighten `filter.py` or `tag.py` — not the embedding model.