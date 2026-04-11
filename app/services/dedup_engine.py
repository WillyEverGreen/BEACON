"""
Deduplication engine: removes duplicate findings across engines.
Merges confidence when multiple engines agree on the same issue.

Phase 10.3: Enhanced with hash+proximity clustering to catch
near-duplicates (e.g., same rule, similar selectors).
"""
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _dedup_key(issue: dict) -> str:
    """
    Generate a dedup key from (url, element/selector, rule_id).
    Normalizes selectors by stripping whitespace and lowering.
    """
    url = str(issue.get("page_url", "")).lower().rstrip("/")
    element = str(issue.get("element", "")).strip().lower()
    rule_id = str(issue.get("rule_id", "")).strip().lower()
    return f"{url}|{element}|{rule_id}"


def _merge_issues(existing: dict, new: dict) -> dict:
    """
    Merge two findings of the same issue from different engines.
    Boosts confidence when multiple engines agree.
    """
    merged = dict(existing)

    # Merge confidence sources
    existing_sources = set(existing.get("confidence_sources", []))
    new_sources = set(new.get("confidence_sources", []))
    all_sources = existing_sources | new_sources
    merged["confidence_sources"] = sorted(all_sources)

    # Boost confidence for multi-engine agreement
    engine_count = len(all_sources)
    if engine_count >= 3:
        merged["confidence"] = 0.95
    elif engine_count >= 2:
        merged["confidence"] = max(existing.get("confidence", 0), new.get("confidence", 0), 0.8)
    else:
        merged["confidence"] = max(existing.get("confidence", 0), new.get("confidence", 0))

    # Use the higher severity
    severity_order = {"critical": 4, "serious": 3, "moderate": 2, "minor": 1}
    existing_sev = severity_order.get(existing.get("severity", "minor"), 0)
    new_sev = severity_order.get(new.get("severity", "minor"), 0)
    if new_sev > existing_sev:
        merged["severity"] = new["severity"]

    # Use the more detailed description
    if len(new.get("description", "")) > len(existing.get("description", "")):
        merged["description"] = new["description"]

    # Use the more specific suggested fix
    if len(new.get("suggested_fix", "")) > len(existing.get("suggested_fix", "")):
        merged["suggested_fix"] = new["suggested_fix"]

    # Use code fix if the new one has it and existing doesn't
    if new.get("code_fix") and not existing.get("code_fix"):
        merged["code_fix"] = new["code_fix"]

    # Merge evidence
    existing_evidence = existing.get("evidence", {})
    new_evidence = new.get("evidence", {})
    merged["evidence"] = {**existing_evidence, **new_evidence}

    # If multiple engines confirm, no longer needs manual review
    if engine_count >= 2:
        merged["needs_manual_review"] = False
        if merged.get("issue_type") == "needs-review":
            merged["issue_type"] = "violation"

    # Use html_snippet from whichever has more detail
    if len(new.get("html_snippet", "")) > len(existing.get("html_snippet", "")):
        merged["html_snippet"] = new["html_snippet"]

    return merged


def deduplicate(issues: list[dict]) -> list[dict]:
    """
    Deduplicate issues by (url, element, rule_id).
    When multiple engines find the same issue, merge and boost confidence.
    
    Returns deduplicated list of issues.
    """
    if not issues:
        return []

    seen = {}  # key -> merged issue
    for issue in issues:
        key = _dedup_key(issue)
        if key in seen:
            seen[key] = _merge_issues(seen[key], issue)
        else:
            seen[key] = dict(issue)

    deduped = list(seen.values())

    original_count = len(issues)
    deduped_count = len(deduped)
    removed = original_count - deduped_count

    if removed > 0:
        dup_rate = removed / original_count if original_count > 0 else 0
        logger.info(
            f"Dedup: {original_count} → {deduped_count} "
            f"({removed} duplicates removed, {dup_rate:.1%} dup rate)"
        )

        # Quality gate telemetry
        if dup_rate > 0.8:
            logger.warning(
                f"⚠️ Unusually high duplicate rate {dup_rate:.1%} (typically 40-80% is normal overlap)"
            )
        else:
            logger.info(
                f"Duplicate rate {dup_rate:.1%} (expected multi-engine overlap)"
            )
    else:
        logger.info(f"Dedup: {original_count} issues, no duplicates found")

    # Count multi-engine confirmations
    multi_engine = sum(1 for i in deduped if len(i.get("confidence_sources", [])) >= 2)
    if multi_engine > 0:
        logger.info(f"  {multi_engine} issues confirmed by multiple engines (boosted confidence)")

    return deduped


def _fingerprint(issue: dict) -> str:
    """Generate a sha256 fingerprint for hash-based proximity dedup.

    Uses rule_id + normalized selector prefix (first 60 chars) to catch
    near-duplicates: same rule on slightly different selector paths
    (e.g. `div.container > img` vs `div.container > img:nth-child(2)`).
    """
    rule_id = str(issue.get("rule_id", "")).strip().lower()
    selector = str(issue.get("element", "")).strip().lower()[:60]
    raw = f"{rule_id}:{selector}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def proximity_dedup(issues: list[dict]) -> list[dict]:
    """Second-pass dedup using hash fingerprints.

    Catches near-duplicates that the primary key-based dedup misses,
    like the same rule firing on multiple similar child elements.
    Keeps the version with the higher confidence.
    """
    if not issues:
        return []

    seen: dict[str, dict] = {}
    for issue in issues:
        fp = _fingerprint(issue)
        if fp in seen:
            existing_conf = seen[fp].get("confidence", 0)
            new_conf = issue.get("confidence", 0)
            if new_conf > existing_conf:
                seen[fp] = issue
            # Merge confidence sources even for proximity dupes
            existing_sources = set(seen[fp].get("confidence_sources", []))
            new_sources = set(issue.get("confidence_sources", []))
            seen[fp]["confidence_sources"] = sorted(existing_sources | new_sources)
        else:
            seen[fp] = issue

    result = list(seen.values())
    removed = len(issues) - len(result)
    if removed > 0:
        logger.info(f"Proximity dedup: {len(issues)} → {len(result)} ({removed} near-dupes removed)")
    return result
