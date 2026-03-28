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
