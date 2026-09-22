"""
HTML content extractor — strips navigation, ads, and boilerplate from HTML,
preserving only the main semantic content for RAG ingestion.

Uses BeautifulSoup with a tag whitelist/blocklist strategy.
"""

from bs4 import BeautifulSoup

# ── HTML tags to preserve content from ────────────────────────
KEEP_TAGS: set[str] = {
    "main", "article", "section",
    "h1", "h2", "h3", "h4",
    "p", "ul", "ol", "li",
    "code", "pre", "blockquote",
    "table", "thead", "tbody", "tr", "td", "th", "caption"
}

# ── HTML tags to completely remove (with children) ────────────
STRIP_TAGS: set[str] = {
    "nav", "footer", "header", "aside",
    "script", "style", "noscript",
    "form", "button", "svg", "img"
}

# ── Minimum text length to include ────────────────────────────
MIN_TEXT_LENGTH: int = 10


def extract_content(html: str) -> str:
    """
    Extract clean text content from raw HTML.
    
    Removes navigation, scripts, styles, and other boilerplate.
    Preserves semantic content elements (headings, paragraphs, lists, tables).
    
    Args:
        html: Raw HTML string
    
    Returns:
        Cleaned text with double-newline paragraph separation.
        Returns empty string if no content found.
    """
    soup: BeautifulSoup = BeautifulSoup(html, "lxml")

    # Remove noise tags entirely
    for tag in soup.find_all(list(STRIP_TAGS)):
        tag.decompose()

    # Find the main content root
    root: BeautifulSoup | None = (
        soup.find("main") or soup.find("article") or soup.find("body")
    )
    if not root:
        return ""

    # Extract text from semantic elements only
    lines: list[str] = []
    for elem in root.descendants:
        if elem.name in KEEP_TAGS:
            text: str = elem.get_text(" ", strip=True)
            if text and len(text) > MIN_TEXT_LENGTH:
                lines.append(text)

    return "\n\n".join(lines)
