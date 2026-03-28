"""
Corpus ingestion: loads WCAG criteria JSON, clones/processes the wcag-aaa-web-design repo,
and expands the corpus with WCAG Understanding, ARIA APG, COGA, and MDN sources.
Produces chunked documents with source_silo metadata for multi-silo retrieval.
"""
import json
import os
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ───────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CORPUS_DIR = BASE_DIR / "corpus"
REPO_URL = "https://github.com/simonplmak-cloud/wcag-aaa-web-design.git"

# ── Topic classifier ───────────────────────────────────────────
FILENAME_TOPIC_MAP = {
    "contrast": "contrast",
    "color": "contrast",
    "aria": "aria",
    "form": "forms",
    "navigation": "navigation",
    "nav": "navigation",
    "sidebar": "navigation",
    "security": "security",
    "error": "errors",
    "application-states": "application-states",
    "data-table": "data-presentation",
    "data-presentation": "data-presentation",
    "responsive": "responsive",
    "breakpoint": "responsive",
    "corporate": "design-system",
    "design-system": "design-system",
    "token": "design-system",
    "component": "components",
    "checklist": "checklist",
    "empty-state": "application-states",
    "header": "structure",
    "footer": "structure",
    "base": "structure",
    "main": "interactive",
}

FILETYPE_CHUNK_TYPE_MAP = {
    "templates": "template",
    "references": "guideline-reference",
    "scripts": "script",
}


def _classify_topic(filename: str) -> str:
    """Classify a file's topic from its filename."""
    name_lower = filename.lower()
    for keyword, topic in FILENAME_TOPIC_MAP.items():
        if keyword in name_lower:
            return topic
    return "general"


def _classify_chunk_type(filepath: str) -> str:
    """Classify chunk type from directory path."""
    for dir_name, chunk_type in FILETYPE_CHUNK_TYPE_MAP.items():
        if dir_name in filepath:
            return chunk_type
    # Check content for ARIA patterns
    return "general"


def _simple_token_count(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4


def _chunk_text(text: str, max_tokens: int = 700, overlap_tokens: int = 50) -> list[str]:
    """
    Split text into chunks of approximately max_tokens.
    Uses paragraph/section boundaries when possible.
    """
    if _simple_token_count(text) <= max_tokens:
        return [text.strip()] if text.strip() else []

    # Try to split on headings first (markdown)
    sections = re.split(r'\n(?=#{1,3}\s)', text)
    if len(sections) > 1:
        chunks = []
        current_chunk = ""
        for section in sections:
            if _simple_token_count(current_chunk + section) > max_tokens and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = section
            else:
                current_chunk += "\n" + section if current_chunk else section
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        return chunks

    # Fall back to paragraph splitting
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = ""
    for para in paragraphs:
        if _simple_token_count(current_chunk + para) > max_tokens and current_chunk:
            chunks.append(current_chunk.strip())
            # Keep a small overlap
            overlap_text = current_chunk[-overlap_tokens * 4:] if len(current_chunk) > overlap_tokens * 4 else ""
            current_chunk = overlap_text + "\n\n" + para
        else:
            current_chunk += "\n\n" + para if current_chunk else para
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text.strip()]


# ── WCAG Criteria Loading ──────────────────────────────────────

def load_wcag_criteria() -> list[dict]:
    """
    Load structured WCAG 2.2 criteria from JSON.
    Returns list of chunk dicts with content + metadata.
    """
    json_path = DATA_DIR / "wcag_criteria.json"
    if not json_path.exists():
        logger.error(f"WCAG criteria file not found: {json_path}")
        return []

    with open(json_path, "r", encoding="utf-8") as f:
        criteria = json.load(f)

    chunks = []
    for criterion in criteria:
        # Build rich content string
        techniques_text = "\n".join(f"- {t}" for t in criterion.get("techniques", []))
        content = (
            f"WCAG {criterion['id']}: {criterion['name']} (Level {criterion['level']})\n"
            f"Principle: {criterion['principle']}\n"
            f"Guideline: {criterion['guideline']}\n\n"
            f"Description: {criterion['description']}\n\n"
            f"Techniques:\n{techniques_text}"
        )

        # Infer semantic tags
        issue_type = criterion["topic_tags"][0] if criterion["topic_tags"] else "general"
        user_impact = "all"
        desc_lower = criterion["description"].lower()
        if "vision" in desc_lower or "blind" in desc_lower or "contrast" in desc_lower:
            user_impact = "low_vision"
        elif "keyboard" in desc_lower or "motor" in desc_lower:
            user_impact = "motor"
        elif "cognitive" in desc_lower or "read" in desc_lower or "understand" in desc_lower:
            user_impact = "cognitive"
        elif "hearing" in desc_lower or "audio" in desc_lower or "video" in desc_lower:
            user_impact = "hearing"

        chunks.append({
            "content": content,
            "metadata": {
                "source": "wcag-guideline",
                "source_silo": "wcag",
                "topic": issue_type,
                "issue_type": issue_type,
                "user_impact": user_impact,
                "severity": criterion["level"],
                "all_topics": ",".join(criterion.get("topic_tags", [])),
                "level": criterion["level"],
                "chunk_type": "guideline",
                "criterion_id": criterion["id"],
                "criterion_name": criterion["name"],
                "filename": "wcag_criteria.json",
                "principle": criterion["principle"],
                "guideline_name": criterion["guideline"],
            }
        })

    logger.info(f"Loaded {len(chunks)} WCAG criteria chunks")
    return chunks


# ── Repo Ingestion ─────────────────────────────────────────────

def clone_repo() -> Path:
    """Clone the wcag-aaa-web-design repo into corpus/."""
    repo_dir = CORPUS_DIR / "wcag-aaa-web-design"
    if repo_dir.exists():
        logger.info(f"Repo already cloned at {repo_dir}")
        return repo_dir

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Cloning repo from {REPO_URL}...")

    try:
        import git
        git.Repo.clone_from(REPO_URL, str(repo_dir), depth=1)
        logger.info(f"Repo cloned to {repo_dir}")
    except ImportError:
        # Fallback: use subprocess
        import subprocess
        subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(repo_dir)],
            check=True, capture_output=True
        )
        logger.info(f"Repo cloned via subprocess to {repo_dir}")

    return repo_dir


def _process_file(filepath: Path, repo_root: Path) -> list[dict]:
    """Process a single file into chunks with metadata."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        logger.warning(f"Could not read {filepath}: {e}")
        return []

    if not content.strip():
        return []

    rel_path = str(filepath.relative_to(repo_root))
    filename = filepath.name
    topic = _classify_topic(filename)
    chunk_type = _classify_chunk_type(rel_path)

    # Detect ARIA pattern content
    if "aria" in content.lower() and ("role=" in content.lower() or "aria-" in content.lower()):
        if chunk_type == "guideline-reference":
            chunk_type = "aria-pattern"

    text_chunks = _chunk_text(content)

    results = []
    for i, chunk_content in enumerate(text_chunks):
        # Infer basic user impact from content
        c_lower = chunk_content.lower()
        user_impact = "all"
        if "keyboard" in c_lower or "focus" in c_lower:
            user_impact = "motor"
        elif "screen reader" in c_lower or "aria" in c_lower or "alt=" in c_lower:
            user_impact = "low_vision"
        elif "cognitive" in c_lower or "understand" in c_lower:
            user_impact = "cognitive"

        results.append({
            "content": chunk_content,
            "metadata": {
                "source": f"repo-{chunk_type}",
                "source_silo": "toolkit",
                "topic": topic,
                "issue_type": topic,
                "user_impact": user_impact,
                "severity": "best_practice",
                "all_topics": topic,
                "level": "",  # Repo files don't have specific level
                "chunk_type": chunk_type,
                "criterion_id": "",
                "criterion_name": "",
                "filename": filename,
                "filepath": rel_path,
                "chunk_index": i,
            }
        })

    return results


def ingest_repo(repo_dir: Optional[Path] = None) -> list[dict]:
    """
    Process all relevant files from the repo.
    Returns list of chunk dicts.
    """
    if repo_dir is None:
        repo_dir = CORPUS_DIR / "wcag-aaa-web-design"

    if not repo_dir.exists():
        logger.warning(f"Repo not found at {repo_dir}. Call clone_repo() first.")
        return []

    target_dirs = ["templates", "references", "scripts"]
    # Also include SKILL.md at root
    target_files = ["SKILL.md", "README.md"]

    all_chunks = []

    # Process directories
    for dir_name in target_dirs:
        dir_path = repo_dir / dir_name
        if not dir_path.exists():
            logger.warning(f"Directory not found: {dir_path}")
            continue

        for filepath in dir_path.rglob("*"):
            if filepath.is_file() and filepath.suffix in (".html", ".css", ".js", ".py", ".sh", ".md", ".json"):
                chunks = _process_file(filepath, repo_dir)
                all_chunks.extend(chunks)

    # Process root files
    for filename in target_files:
        filepath = repo_dir / filename
        if filepath.exists():
            chunks = _process_file(filepath, repo_dir)
            all_chunks.extend(chunks)

    logger.info(f"Ingested {len(all_chunks)} chunks from repo")
    return all_chunks


# ── Web Corpus Expansion ───────────────────────────────────────

CORPUS_EXPANSION_SOURCES = [
    # ── 1. Core Standards ──────────────────────────────────────
    {
        "name": "WCAG 2.2 Full Specification",
        "url": "https://www.w3.org/TR/WCAG22/",
        "silo": "wcag",
        "chunk_type": "spec-reference",
    },
    {
        "name": "WCAG 2 Overview",
        "url": "https://www.w3.org/WAI/standards-guidelines/wcag/",
        "silo": "wcag",
        "chunk_type": "guideline-overview",
    },
    {
        "name": "What's New in WCAG 2.2",
        "url": "https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/",
        "silo": "wcag",
        "chunk_type": "guideline-overview",
    },
    {
        "name": "WCAG 2 at a Glance",
        "url": "https://www.w3.org/WAI/standards-guidelines/wcag/glance/",
        "silo": "wcag",
        "chunk_type": "guideline-overview",
    },
    {
        "name": "Understanding WCAG 2.2",
        "url": "https://www.w3.org/WAI/WCAG22/Understanding/",
        "silo": "wcag",
        "chunk_type": "understanding",
    },
    {
        "name": "WCAG 3.0 Working Draft",
        "url": "https://w3c.github.io/wcag3/guidelines/",
        "silo": "wcag",
        "chunk_type": "spec-reference",
    },

    # ── 2. WAI-ARIA ────────────────────────────────────────────
    {
        "name": "WAI-ARIA Overview",
        "url": "https://www.w3.org/WAI/standards-guidelines/aria/",
        "silo": "aria",
        "chunk_type": "guideline-overview",
    },
    {
        "name": "WAI-ARIA 1.3 Full Spec",
        "url": "https://w3c.github.io/aria/",
        "silo": "aria",
        "chunk_type": "spec-reference",
    },
    {
        "name": "ARIA Authoring Practices Guide",
        "url": "https://www.w3.org/WAI/ARIA/apg/",
        "silo": "aria",
        "chunk_type": "aria-pattern",
    },

    # ── 3. Cognitive Accessibility ─────────────────────────────
    {
        "name": "Cognitive Accessibility at W3C",
        "url": "https://www.w3.org/WAI/cognitive/",
        "silo": "coga",
        "chunk_type": "coga-pattern",
    },
    {
        "name": "Making Content Usable — COGA",
        "url": "https://www.w3.org/TR/coga-usable/",
        "silo": "coga",
        "chunk_type": "coga-pattern",
    },
    {
        "name": "COGA Working Draft (GitHub)",
        "url": "https://w3c.github.io/coga/content-usable/",
        "silo": "coga",
        "chunk_type": "coga-pattern",
    },
    {
        "name": "COGA Task Force Work Statement",
        "url": "https://www.w3.org/WAI/about/groups/task-forces/coga/work-statement/",
        "silo": "coga",
        "chunk_type": "coga-pattern",
    },

    # ── 4. Testing Tools & Rule Engines ────────────────────────
    {
        "name": "axe-core API Documentation",
        "url": "https://github.com/dequelabs/axe-core/blob/develop/doc/API.md",
        "silo": "axe",
        "chunk_type": "developer-guide",
    },
    {
        "name": "axe-core Developer Guide",
        "url": "https://github.com/dequelabs/axe-core/blob/develop/doc/developer-guide.md",
        "silo": "axe",
        "chunk_type": "developer-guide",
    },
    {
        "name": "Playwright Accessibility Testing",
        "url": "https://playwright.dev/docs/accessibility-testing",
        "silo": "testing",
        "chunk_type": "developer-guide",
    },
    {
        "name": "Playwright ARIA Snapshots",
        "url": "https://playwright.dev/docs/aria-snapshots",
        "silo": "testing",
        "chunk_type": "developer-guide",
    },

    # ── 5. Real User Research (WebAIM) ─────────────────────────
    {
        "name": "WebAIM Screen Reader Survey #10 (2024)",
        "url": "https://webaim.org/projects/screenreadersurvey10/",
        "silo": "research",
        "chunk_type": "user-research",
    },
    {
        "name": "WebAIM Screen Reader Survey #9 (2021)",
        "url": "https://webaim.org/projects/screenreadersurvey9/",
        "silo": "research",
        "chunk_type": "user-research",
    },

    # ── 6. Reference & Developer Docs ──────────────────────────
    {
        "name": "MDN Accessibility Guide",
        "url": "https://developer.mozilla.org/en-US/docs/Web/Accessibility/Guides/Information_for_Web_authors",
        "silo": "mdn",
        "chunk_type": "developer-guide",
    },
    {
        "name": "Wikipedia — WCAG History",
        "url": "https://en.wikipedia.org/wiki/Web_Content_Accessibility_Guidelines",
        "silo": "reference",
        "chunk_type": "reference",
    },

    # ── 7. Regulatory & Legal Context ──────────────────────────
    {
        "name": "U.S. Access Board — WCAG 2.2",
        "url": "https://www.access-board.gov/news/2023/11/27/w3c-wcag-2-2-now-available/",
        "silo": "regulatory",
        "chunk_type": "regulatory",
    },
    {
        "name": "AllAccessible — WCAG 2.2 Guide 2025",
        "url": "https://www.allaccessible.org/blog/wcag-22-complete-guide-2025",
        "silo": "regulatory",
        "chunk_type": "compliance-guide",
    },
]


def ingest_web_source(url: str, silo: str, chunk_type: str, name: str, max_depth: int = 2) -> list[dict]:
    """
    Fetch and chunk a web-based accessibility reference source.
    Crawls internal links up to max_depth to extract comprehensive documentation.
    Returns list of chunk dicts with source_silo metadata.
    """
    import httpx
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, urlparse

    visited = set()
    all_results = []
    base_domain = urlparse(url).netloc

    def crawl_recursive(current_url: str, current_depth: int):
        if current_depth > max_depth or current_url in visited:
            return
            
        visited.add(current_url)

        try:
            response = httpx.get(current_url, timeout=30.0, follow_redirects=True, verify=False)
            response.raise_for_status()
            html = response.text

            soup = BeautifulSoup(html, "lxml")

            # Extract internal links for next depth
            if current_depth < max_depth:
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    full_link = urljoin(current_url, href).split("#")[0]  # ignore fragments
                    if urlparse(full_link).netloc == base_domain and full_link not in visited:
                        # Simple extension filter to avoid PDFs/ZIPs
                        if not any(full_link.endswith(ext) for ext in [".pdf", ".zip", ".png", ".jpg"]):
                            crawl_recursive(full_link, current_depth + 1)

            # Clean DOM for chunking
            for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            body = soup.find("main") or soup.find("article") or soup.find("body") or soup
            text = body.get_text(separator="\n", strip=True)

            if not text or len(text) < 100:
                return

            text_chunks = _chunk_text(text, max_tokens=600)
            for i, chunk_content in enumerate(text_chunks):
                # Infer basic user impact from content
                c_lower = chunk_content.lower()
                user_impact = "all"
                if "keyboard" in c_lower or "focus" in c_lower:
                    user_impact = "motor"
                elif "screen reader" in c_lower or "aria" in c_lower or "alt=" in c_lower or "vision" in c_lower:
                    user_impact = "low_vision"
                elif "cognitive" in c_lower or "understand" in c_lower or "readability" in c_lower:
                    user_impact = "cognitive"
                    
                all_results.append({
                    "content": chunk_content,
                    "metadata": {
                        "source": name,
                        "source_silo": silo,
                        "topic": "reference",
                        "issue_type": "reference",
                        "user_impact": user_impact,
                        "severity": "info",
                        "all_topics": "reference",
                        "level": "",
                        "chunk_type": chunk_type,
                        "criterion_id": "",
                        "criterion_name": "",
                        "filename": current_url,
                        "chunk_index": i,
                    }
                })

        except Exception as e:
            logger.warning(f"Failed to crawl {current_url}: {e}")

    # Start crawling
    logger.info(f"Starting deep crawl of {url} (depth={max_depth})")
    crawl_recursive(url, 0)
    logger.info(f"Finished crawling {name}. Scraped {len(visited)} pages, generated {len(all_results)} chunks.")
    return all_results


def ingest_expanded_corpus() -> list[dict]:
    """
    Ingest all expanded corpus sources (WCAG Understanding, ARIA APG, COGA, MDN).
    Returns list of chunk dicts with source_silo metadata.
    """
    all_chunks = []
    for source in CORPUS_EXPANSION_SOURCES:
        try:
            chunks = ingest_web_source(
                url=source["url"],
                silo=source["silo"],
                chunk_type=source["chunk_type"],
                name=source["name"],
            )
            all_chunks.extend(chunks)
        except Exception as e:
            logger.warning(f"Corpus expansion source '{source['name']}' failed: {e}")
    logger.info(f"Expanded corpus: {len(all_chunks)} total chunks from {len(CORPUS_EXPANSION_SOURCES)} sources")
    return all_chunks


# ── Full Ingestion Pipeline ────────────────────────────────────

def run_full_ingestion(expand_corpus: bool = False) -> list[dict]:
    """
    Run the complete ingestion pipeline:
    1. Load WCAG criteria
    2. Clone & process repo
    3. (Optional) Expand corpus with web sources (ARIA APG, COGA, MDN)
    4. Return all chunks
    """
    all_chunks = []

    # 1. WCAG criteria
    wcag_chunks = load_wcag_criteria()
    all_chunks.extend(wcag_chunks)

    # 2. Repo content
    try:
        repo_dir = clone_repo()
        repo_chunks = ingest_repo(repo_dir)
        all_chunks.extend(repo_chunks)
    except Exception as e:
        logger.error(f"Repo ingestion failed: {e}. Continuing with WCAG criteria only.")

    # 3. (Optional) Corpus expansion
    if expand_corpus:
        try:
            expanded = ingest_expanded_corpus()
            all_chunks.extend(expanded)
        except Exception as e:
            logger.warning(f"Corpus expansion failed: {e}")

    logger.info(f"Total ingestion: {len(all_chunks)} chunks")
    return all_chunks
