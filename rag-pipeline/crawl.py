# crawl.py
import asyncio, hashlib, json
from pathlib import Path
from crawl4ai import AsyncWebCrawler
from urllib.parse import urlparse
from config import SOURCES, ALLOWED_DOMAINS

from collections import deque

async def crawl_source(source):
    visited = set()
    queue = deque([(source["url"], 0)])

    async with AsyncWebCrawler() as crawler:
        while queue:
            url, depth = queue.popleft()
            if url in visited or depth > source["depth"]:
                continue
            domain = urlparse(url).netloc
            if not any(domain.endswith(d) for d in ALLOWED_DOMAINS):
                continue
            visited.add(url)

            slug = hashlib.md5(url.encode()).hexdigest()[:10]
            out = Path(f"data/raw/{source['silo']}/{slug}.json")

            if out.exists():
                try:
                    data = json.loads(out.read_text(encoding="utf-8", errors="ignore"))
                    print(f"  [SKIP] {url}")
                    for link in data.get("links", []):
                        href = link.get("href", "")
                        if href and href not in visited:
                            queue.append((href, depth + 1))
                    continue
                except Exception:
                    pass

            result = await crawler.arun(url=url)
            if not result.success:
                continue

            out.parent.mkdir(parents=True, exist_ok=True)
            links = result.links.get("internal", [])
            try:
                out.write_text(json.dumps({
                    "url": url, "silo": source["silo"],
                    "html": result.html,
                    "links": links
                }, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

            for link in links:
                href = link.get("href", "")
                if href and href not in visited:
                    queue.append((href, depth + 1))
