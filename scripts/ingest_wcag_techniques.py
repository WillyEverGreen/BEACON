"""Ingest WCAG 2.2 Techniques into local vector metadata/chunks.

Default behavior writes extracted chunks to JSONL so ingestion can be reviewed
before embedding/upsert.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

PARTIAL_COVERAGE_SC = [
    "1.3.3",
    "1.3.5",
    "1.4.1",
    "1.4.10",
    "2.2.1",
    "2.2.2",
    "2.4.5",
    "2.4.6",
    "2.4.7",
    "2.4.11",
    "3.1.2",
    "3.3.7",
]

_INDEX_URL = "https://www.w3.org/WAI/WCAG22/Techniques/"
_SC_PATTERN = re.compile(r"\b(\d\.\d+\.\d+)\b")
_TECHNIQUE_ID_PATTERN = re.compile(r"\b([A-Z]{1,3}\d{1,3})\b")


def _http_get(url: str, *, timeout: float = 20.0) -> str:
    req = Request(url, headers={"User-Agent": "BEACON-Techniques-Ingest/1.0"})
    with urlopen(req, timeout=timeout) as response:  # nosec B310 - controlled W3C target
        return response.read().decode("utf-8", errors="ignore")


def extract_index_links(index_html: str, *, base_url: str = _INDEX_URL) -> list[str]:
    soup = BeautifulSoup(index_html, "lxml")
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        if not ("Techniques/" in href or href.startswith("./") or href.startswith("http")):
            continue
        absolute = urljoin(base_url, href)
        if "/WAI/WCAG22/Techniques/" not in absolute:
            continue
        if absolute not in links:
            links.append(absolute)
    return links


def _extract_technique_id(url: str, title: str, text: str) -> str:
    basename = Path(urlparse(url).path).name
    stem = Path(basename).stem

    if stem and _TECHNIQUE_ID_PATTERN.match(stem.upper()):
        return stem.upper()

    for source in (title, text):
        match = _TECHNIQUE_ID_PATTERN.search(source or "")
        if match:
            return match.group(1).upper()

    return stem.upper() if stem else "UNKNOWN"


def _extract_sc_id(text: str) -> str:
    match = _SC_PATTERN.search(text or "")
    return match.group(1) if match else ""


def _extract_type(text: str) -> str:
    lowered = (text or "").lower()
    if "failure" in lowered:
        return "failure"
    if "advisory" in lowered:
        return "advisory"
    return "sufficient"


def _extract_level(text: str) -> str:
    lowered = (text or "").lower()
    if "level a" in lowered:
        return "A"
    if "level aa" in lowered:
        return "AA"
    if "level aaa" in lowered:
        return "AAA"
    return ""


def extract_technique_chunk(url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = (soup.title.get_text(" ", strip=True) if soup.title else "").strip()

    main = soup.find("main") or soup.find("article") or soup.find("body") or soup
    text = main.get_text(" ", strip=True)

    technique_id = _extract_technique_id(url, title, text)
    sc_id = _extract_sc_id(text)
    chunk_type = _extract_type(text)
    wcag_level = _extract_level(text)

    content = "\n".join(
        [
            f"Technique {technique_id}",
            f"URL: {url}",
            f"SC: {sc_id}" if sc_id else "SC: unknown",
            text[:4000],
        ]
    )

    return {
        "content": content,
        "metadata": {
            "source": "wcag_techniques",
            "source_silo": "wcag",
            "chunk_type": chunk_type,
            "technique_id": technique_id,
            "sc_id": sc_id,
            "wcag_level": wcag_level,
            "url": url,
            "topic": "wcag-techniques",
        },
    }


def build_chunks_from_documents(documents: Iterable[dict[str, str]]) -> list[dict]:
    chunks: list[dict] = []
    for doc in documents:
        url = str(doc.get("url") or "").strip()
        html = str(doc.get("html") or "")
        if not url or not html:
            continue
        chunks.append(extract_technique_chunk(url, html))
    return chunks


def ingest_wcag_techniques(
    *,
    output_file: Path,
    prioritize_partial: bool = True,
    upsert: bool = False,
    max_pages: int = 0,
) -> dict:
    index_html = _http_get(_INDEX_URL)
    links = extract_index_links(index_html)
    if max_pages > 0:
        links = links[:max_pages]

    chunks: list[dict] = []
    for link in links:
        try:
            page_html = _http_get(link)
        except Exception:
            continue
        chunk = extract_technique_chunk(link, page_html)
        chunks.append(chunk)

    if prioritize_partial:
        partial = [c for c in chunks if c["metadata"].get("sc_id") in PARTIAL_COVERAGE_SC]
        non_partial = [c for c in chunks if c["metadata"].get("sc_id") not in PARTIAL_COVERAGE_SC]
        chunks = [*partial, *non_partial]

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    upserted = 0
    if upsert:
        from app.services.vector_store import upsert_chunks

        upsert_payload = [
            {
                "content": chunk["content"],
                "metadata": chunk["metadata"],
            }
            for chunk in chunks
        ]
        upserted = upsert_chunks(upsert_payload)

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "index_url": _INDEX_URL,
        "chunks": len(chunks),
        "upserted": upserted,
        "output_file": output_file.as_posix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest WCAG techniques")
    parser.add_argument(
        "--out",
        default="data/raw/wcag_techniques.jsonl",
        help="JSONL output path",
    )
    parser.add_argument(
        "--no-prioritize-partial",
        action="store_true",
        help="Disable prioritization of known partial-coverage SC IDs",
    )
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="Also upsert extracted chunks into the local vector store",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=0,
        help="Optional hard cap for fetched technique pages",
    )
    args = parser.parse_args()

    result = ingest_wcag_techniques(
        output_file=Path(args.out),
        prioritize_partial=not args.no_prioritize_partial,
        upsert=args.upsert,
        max_pages=max(0, int(args.max_pages or 0)),
    )

    print("=== WCAG Techniques Ingestion ===")
    print(f"Chunks:  {result['chunks']}")
    print(f"Upserted:{result['upserted']}")
    print(f"Output:  {result['output_file']}")


if __name__ == "__main__":
    main()
