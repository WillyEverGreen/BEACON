"""
Fix Cache and Self-Learning Moat.
Stores LLM-generated RAG remediation fixes, tracking success rate and frequency.
Allows the engine to bypass expensive LLM calls for recurring issue patterns.
"""
import hashlib
import json
import logging
from pathlib import Path

from app.config import CACHE_STATS

logger = logging.getLogger(__name__)

# Persistent local cache for the hackathon (could act as Redis fallback)
CACHE_FILE = Path(__file__).resolve().parents[1] / "data" / "fix_library.json"
_fix_library = {}
_cache_stats = {
    "hit_count": 0,
    "miss_count": 0,
}

def _load_cache():
    global _fix_library
    if CACHE_FILE.exists():
        try:
            with CACHE_FILE.open("r", encoding="utf-8") as f:
                _fix_library = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load Fix Library: {e}")
            _fix_library = {}

def _save_cache():
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(_fix_library, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save Fix Library: {e}")

# Initialize on module load
_load_cache()

def normalize_html_pattern(html_snippet: str) -> str:
    """
    Remove dynamic attributes (id, class, src, href, data-*) to create a structural signature.
    E.g. <img src="user_123.jpg" class="avatar"> -> <img>
    """
    import re
    # Very basic normalization for structural cache hits.
    # In production, use BeautifulSoup to strip attributes cleanly.
    pattern = re.sub(r'\s+([a-zA-Z0-9_\-]+)="[^"]*"', '', html_snippet)
    pattern = re.sub(r'\s+([a-zA-Z0-9_\-]+)=\'[^\']*\'', '', pattern)
    return pattern.strip()

def get_cache_key(rule_id: str, html_snippet: str) -> str:
    """Generate stable SHA-256 hash of rule_id + normalized pattern."""
    normalized = normalize_html_pattern(html_snippet)
    key_str = f"{rule_id}::{normalized}"
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

def get_cached_fix(rule_id: str, html_snippet: str) -> dict | None:
    """Retrieve a previously generated fix if it meets the success criteria."""
    key = get_cache_key(rule_id, html_snippet)
    match = _fix_library.get(key)
    
    if not match:
        _cache_stats["miss_count"] += 1
        return None
        
    # Check success threshold before blindly reusing
    times_used = match.get("times_used", 1)
    successes = match.get("successful_fixes", 1)
    success_rate = successes / max(times_used, 1)
    
    # Needs to be a high-confidence fix to bypass LLM
    if success_rate > 0.85:
        _cache_stats["hit_count"] += 1
        # Increment usage
        match["times_used"] = times_used + 1
        # Optimistically assume success unless explicit feedback rejects it
        match["successful_fixes"] = successes + 1
        
        # Async save (fire and forget basically, or just save synchronously for MVP)
        _save_cache()
        return match.get("remediation_data")
        
    _cache_stats["miss_count"] += 1
    return None

def store_fix(rule_id: str, html_snippet: str, remediation_data: dict, confidence: float = 0.9):
    """
    Store a newly generated LLM fix into the library.
    Runs fix validation first — rejects bad patches before they poison the cache.
    """
    from app.services.fix_validator import validate_fix

    key = get_cache_key(rule_id, html_snippet)
    normalized = normalize_html_pattern(html_snippet)
    
    # Validate the fix before storing
    vanilla_fix = ""
    fixes = remediation_data.get("fixes", {})
    if isinstance(fixes, dict):
        vanilla_fix = fixes.get("vanilla", "")
    
    validation = validate_fix(html_snippet, vanilla_fix, rule_id)
    
    if not validation.get("valid", False):
        logger.info(f"Fix rejected for {rule_id}: {validation.get('reason', 'unknown')}")
        # Store with low confidence so it won't be reused
        _fix_library[key] = {
            "rule_id": rule_id,
            "normalized_pattern": normalized,
            "remediation_data": remediation_data,
            "times_used": 1,
            "successful_fixes": 0,  # Zero success = won't pass the 85% gate
            "confidence": validation.get("confidence", 0.0),
            "validated": False,
            "validation_reason": validation.get("reason", ""),
        }
        CACHE_STATS["fix_writes"] = int(CACHE_STATS.get("fix_writes", 0) or 0) + 1
        _save_cache()
        return
    
    _fix_library[key] = {
        "rule_id": rule_id,
        "normalized_pattern": normalized,
        "remediation_data": remediation_data,
        "times_used": 1,
        "successful_fixes": 1,
        "confidence": validation.get("confidence", confidence),
        "validated": True,
        "validation_reason": validation.get("reason", ""),
    }
    CACHE_STATS["fix_writes"] = int(CACHE_STATS.get("fix_writes", 0) or 0) + 1
    _save_cache()


def record_feedback_for_fix(rule_id: str, html_snippet: str, accepted: bool):
    """
    Record developer feedback for a fix. Adjusts success rate to
    self-correct the moat over time.
    """
    key = get_cache_key(rule_id, html_snippet)
    match = _fix_library.get(key)
    if not match:
        return
    
    match["times_used"] = match.get("times_used", 1) + 1
    if accepted:
        match["successful_fixes"] = match.get("successful_fixes", 0) + 1
    # If rejected, times_used goes up but successful_fixes doesn't,
    # naturally degrading its success_rate below 85%
    _save_cache()


def get_cache_stats() -> dict:
    """Return cache telemetry for quality gates."""
    total = len(_fix_library)
    validated = sum(1 for v in _fix_library.values() if v.get("validated"))
    high_confidence = sum(1 for v in _fix_library.values()
                          if v.get("successful_fixes", 0) / max(v.get("times_used", 1), 1) > 0.85)
    return {
        "total_cached_fixes": total,
        "validated_fixes": validated,
        "high_confidence_fixes": high_confidence,
        "hit_count": _cache_stats["hit_count"],
        "miss_count": _cache_stats["miss_count"],
    }

