# local_corpus.py
import json
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def process_local_corpus(corpus_dir: str = "../corpus/wcag-aaa-web-design"):
    """
    Reads markdown and JSON files from the given corpus directory.
    Returns a list of dicts that emulate extracted web content,
    to be fed squarely into the `chunk` phase.
    """
    corpus_path = Path(corpus_dir).resolve()
    extracted_docs = []

    if not corpus_path.exists():
        logger.info(f"Local corpus directory {corpus_path} not found. Skipping local corpus.")
        return extracted_docs

    logger.info(f"Ingesting local corpus from {corpus_path}")
    for filepath in corpus_path.rglob("*"):
        if filepath.is_file() and filepath.suffix in [".md", ".json", ".html", ".css", ".js"]:
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                if not content.strip():
                    continue

                rel_path = filepath.relative_to(corpus_path).as_posix()
                
                # Emulate Phase 2 extractor output
                extracted_docs.append({
                    "url": f"local://{rel_path}",
                    "silo": "toolkit",
                    "text": content,
                    "title": rel_path
                })
            except Exception as e:
                logger.error(f"Failed to read {filepath}: {e}")
                
    return extracted_docs
