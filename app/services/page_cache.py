"""
Page-Level and DOM-Level Caching.
Short-circuits repeated and unchanged page audits to eliminate redundant processing.
"""
import hashlib
import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

from app.config import CACHE_STATS

logger = logging.getLogger(__name__)

CACHE_FILE = Path(__file__).resolve().parents[1] / "data" / "page_cache.json"
_page_cache = {}
_MAX_CACHE_ENTRIES = 100

def _load_cache():
    global _page_cache
    if CACHE_FILE.exists():
        try:
            with CACHE_FILE.open("r", encoding="utf-8") as f:
                _page_cache = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load Page Cache: {e}")
            _page_cache = {}

def _save_cache():
    """Persist cache to disk with file-level locking for multi-worker safety."""
    lock_path = CACHE_FILE.with_suffix(".lock")
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Use OS-level file lock to prevent concurrent writes
        with open(lock_path, "w") as lock_f:
            try:
                import msvcrt
                msvcrt.locking(lock_f.fileno(), msvcrt.LK_NBLCK, 1)
            except (ImportError, OSError):
                pass  # Non-Windows or lock contention — proceed best-effort
            with CACHE_FILE.open("w", encoding="utf-8") as f:
                json.dump(_page_cache, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save Page Cache: {e}")

def _evict_oldest():
    """Evict oldest entries when cache exceeds max size."""
    if len(_page_cache) <= _MAX_CACHE_ENTRIES:
        return
    # Sort by timestamp, evict oldest
    sorted_keys = sorted(
        _page_cache.keys(),
        key=lambda k: _page_cache[k].get("timestamp", 0)
    )
    evict_count = len(_page_cache) - _MAX_CACHE_ENTRIES
    for key in sorted_keys[:evict_count]:
        _page_cache.pop(key, None)
    logger.info(f"Page Cache evicted {evict_count} oldest entries (max {_MAX_CACHE_ENTRIES})")

_load_cache()

def get_url_hash(url: str, scan_mode: str, precision_profile: str = "balanced") -> str:
    """Hash the URL, scan mode, and precision profile."""
    key = f"{url}::{scan_mode}::{precision_profile}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()

def clean_html_for_hash(html: str) -> str:
    """
    Remove volatile content (scripts, styles, dynamic IDs, CSRF tokens, timestamps)
    to generate a stable structural hash of the page.
    """
    if not html:
        return ""
    
    # Remove scripts and styles entirely
    cleaned = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', '', html, flags=re.IGNORECASE)
    cleaned = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', '', cleaned, flags=re.IGNORECASE)
    
    # Remove dynamic attributes: id, value, data-*, nonce, token
    cleaned = re.sub(r'\s+(id|value|data-[a-zA-Z0-9\-]+|nonce|token)=("[^"]*"|\'[^\']*\')', '', cleaned, flags=re.IGNORECASE)
    
    # Remove timestamps/numbers
    cleaned = re.sub(r'\b\d{10,}\b', '', cleaned)
    
    # Remove excessive whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def get_dom_hash(cleaned_html: str, scan_mode: str, precision_profile: str = "balanced") -> str:
    """Hash the cleaned DOM structure, scan mode, and precision profile."""
    key = f"{cleaned_html}::{scan_mode}::{precision_profile}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()

def check_cache(cache_key: str, max_age_seconds: int = 86400) -> Optional[dict]:
    """Retrieve result if it exists and is fresh."""
    entry = _page_cache.get(cache_key)
    if not entry:
        # Determine tier from caller context (best-effort key prefix heuristic)
        CACHE_STATS["page_misses"] += 1
        return None

    age = time.time() - entry.get("timestamp", 0)
    if age > max_age_seconds:
        _page_cache.pop(cache_key, None)
        CACHE_STATS["page_misses"] += 1
        return None

    CACHE_STATS["page_hits"] += 1
    return entry.get("result")

def save_to_cache(url_hash: str, dom_hash: str, result: dict):
    """Store audit result under both URL and DOM hashes."""
    entry = {
        "timestamp": time.time(),
        "result": result
    }
    _page_cache[url_hash] = entry
    if dom_hash:
        _page_cache[dom_hash] = entry
    
    _evict_oldest()
    _save_cache()
