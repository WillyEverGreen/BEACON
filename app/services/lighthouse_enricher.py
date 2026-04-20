"""
app/services/lighthouse_enricher.py

Single responsibility: orchestrate the full Lighthouse enrichment pipeline for
one scan, then merge the results into BEACON's findings list.

Pipeline:
  1. URL selection (≤5 URLs: homepage → template reps → priority pages)
  2. Per-URL runner (semaphore-controlled, timeout-bounded, retryable)
  3. Per-URL mapper (raw JSON → normalized findings)
  4. Merge (BEACON primary findings + Lighthouse findings → enriched list)
  5. Return atomic enrichment block for DB write

Merge rules (do not change without updating test_lighthouse_enricher.py):

  Rule 1 — BEACON + Lighthouse share same normalized_issue_key (rule_id):
    → Keep BEACON finding as primary.
    → Set lighthouse_confirmed = True.
    → If lighthouse_score < 50: upgrade severity one level (minor→moderate→serious→critical)
      and set severity_upgraded_by_lighthouse = True.
    → If lighthouse_score >= 50: severity unchanged.

  Rule 2 — Lighthouse-only finding, score < 50:
    → Add as new finding: source = "lighthouse", confidence = "supplementary".

  Rule 3 — Lighthouse-only finding, score 50–89:
    → Add as new finding: source = "lighthouse", confidence = "additional_insight".
      (Lower display priority — "Deep Insights" section.)

  Rule 4 — Lighthouse-only finding, score >= 90:
    → Drop silently. (Mapper already handles this, enricher never sees them.)

  Rule 5 — BEACON findings are NEVER deleted, suppressed, or downgraded.
    This rule has no exceptions.
"""
from __future__ import annotations

import datetime
import logging
import time
from typing import Any
from urllib.parse import urlparse

from app.config import (
    LIGHTHOUSE_MAX_URLS_PER_SCAN,
    _LIGHTHOUSE_ELIGIBLE_MODES,
)
from app.config import CRAWLER_URL_RULES
from app.services.lighthouse_runner import ChromeLaunchError, run_lighthouse_for_url
from app.services.lighthouse_mapper import (
    extract_category_scores,
    get_lighthouse_version,
    get_mapping_version,
    map_lighthouse_report,
)

logger = logging.getLogger(__name__)

# ── Severity upgrade ladder ───────────────────────────────────────────────────
_SEVERITY_UPGRADE: dict[str, str] = {
    "minor": "moderate",
    "moderate": "serious",
    "serious": "critical",
    "critical": "critical",  # already at top — no change
}

# Priority path keywords used for URL prioritization (from config, no duplication).
_PRIORITY_PATH_KEYWORDS: list[str] = CRAWLER_URL_RULES.get("priority_path_keywords", [])


# ── URL selection ─────────────────────────────────────────────────────────────

def select_urls_for_lighthouse(
    crawl_urls: list[str],
    *,
    max_urls: int = LIGHTHOUSE_MAX_URLS_PER_SCAN,
) -> list[str]:
    """Select ≤ max_urls URLs for Lighthouse enrichment.

    Priority order:
      1. Homepage — always first, 1 URL.
      2. Template representative URLs (from crawl_urls, cap at 3).
      3. Priority-tagged pages matching CRAWLER_URL_RULES["priority_path_keywords"]
         (login, checkout, signup, etc.) — cap at 2, only if not already selected.

    Hard ceiling: max_urls (default LIGHTHOUSE_MAX_URLS_PER_SCAN = 5).
    """
    if not crawl_urls:
        return []

    selected: list[str] = []
    seen: set[str] = set()

    def _add(url: str) -> bool:
        u = str(url or "").strip()
        if not u or u in seen or len(selected) >= max_urls:
            return False
        selected.append(u)
        seen.add(u)
        return True

    def _is_homepage(url: str) -> bool:
        path = urlparse(url).path
        return path in ("", "/", "/index.html", "/index.htm")

    # Step 1: Homepage
    homepage: str | None = None
    for url in crawl_urls:
        if _is_homepage(url):
            homepage = url
            break
    if homepage is None and crawl_urls:
        homepage = crawl_urls[0]
    if homepage:
        _add(homepage)

    # Step 2: Template representatives — up to 3 from crawl_urls (already diverse)
    template_budget = 3
    for url in crawl_urls:
        if template_budget <= 0:
            break
        if _add(url):
            template_budget -= 1

    # Step 3: Priority-tagged pages — up to 2 not already selected
    priority_budget = 2
    for url in crawl_urls:
        if priority_budget <= 0:
            break
        url_lower = url.lower()
        is_priority = any(kw.lower() in url_lower for kw in _PRIORITY_PATH_KEYWORDS)
        if is_priority and _add(url):
            priority_budget -= 1

    return selected[:max_urls]


# ── Merge engine ──────────────────────────────────────────────────────────────

def merge_findings(
    beacon_findings: list[dict[str, Any]],
    lighthouse_findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Apply merge rules (documented in module docstring).

    Args:
        beacon_findings: BEACON's primary findings list (never modified in place).
        lighthouse_findings: Normalized findings from lighthouse_mapper.

    Returns:
        (enriched_findings, merge_telemetry)
        enriched_findings: BEACON findings (possibly with lighthouse_confirmed=True)
            PLUS Lighthouse-only findings (source='lighthouse').
        merge_telemetry: Counts of confirmations, upgrades, new additions, drops.
    """
    # Index BEACON findings by rule_id for O(1) lookup.
    beacon_by_key: dict[str, list[dict[str, Any]]] = {}
    for finding in beacon_findings:
        key = str(finding.get("rule_id") or "")
        if key:
            beacon_by_key.setdefault(key, []).append(finding)

    # Work on copies so we never mutate the caller's list.
    enriched = [dict(f) for f in beacon_findings]
    # Build index into enriched list for direct mutation.
    enriched_by_key: dict[str, list[dict[str, Any]]] = {}
    for finding in enriched:
        key = str(finding.get("rule_id") or "")
        if key:
            enriched_by_key.setdefault(key, []).append(finding)

    telemetry: dict[str, Any] = {
        "confirmed_count": 0,
        "severity_upgraded_count": 0,
        "new_supplementary_count": 0,
        "new_additional_insight_count": 0,
        "dropped_count": 0,
    }

    for lh_finding in lighthouse_findings:
        key = str(lh_finding.get("rule_id") or "")
        lh_score = lh_finding.get("lighthouse_score")  # already 0–100

        matching = enriched_by_key.get(key)
        if matching:
            # Rule 1 — BEACON finding confirmed by Lighthouse.
            for beacon_f in matching:
                beacon_f["lighthouse_confirmed"] = True
                beacon_f["lighthouse_score"] = lh_score
                beacon_f["lighthouse_audit_id"] = lh_finding.get("lighthouse_audit_id", "")
                beacon_f["severity_upgraded_by_lighthouse"] = False

                if lh_score is not None and lh_score < 50:
                    old_sev = str(beacon_f.get("severity") or "minor")
                    new_sev = _SEVERITY_UPGRADE.get(old_sev, old_sev)
                    if new_sev != old_sev:
                        beacon_f["severity"] = new_sev
                        beacon_f["severity_upgraded_by_lighthouse"] = True
                        telemetry["severity_upgraded_count"] += 1

            telemetry["confirmed_count"] += 1

        else:
            # Rules 2 & 3 — Lighthouse-only finding.
            confidence = str(lh_finding.get("confidence", "supplementary"))
            if confidence == "supplementary":
                telemetry["new_supplementary_count"] += 1
            else:
                telemetry["new_additional_insight_count"] += 1

            new_finding = {**lh_finding}
            enriched.append(new_finding)
            enriched_by_key.setdefault(key, []).append(new_finding)

    return enriched, telemetry


# ── Full enrichment pipeline ──────────────────────────────────────────────────

async def run_lighthouse_enrichment(
    scan_id: str,
    beacon_findings: list[dict[str, Any]],
    crawl_urls: list[str],
    scan_mode: str,
) -> dict[str, Any]:
    """Full Lighthouse enrichment pipeline for one scan.

    This function is designed to run inside a FastAPI BackgroundTask and is wrapped
    in an outer global timeout by the caller. All failures are handled internally —
    a dict with status='failed' is returned rather than raising.

    Args:
        scan_id: ID of the scan being enriched (for logging only — DB write is done
            by the caller via persist_lighthouse_enrichment).
        beacon_findings: BEACON's core resolved findings list.
        crawl_urls: Template-diverse URL list from topology detection.
        scan_mode: Must be 'deep' or 'max'. Caller is responsible for the mode gate.

    Returns:
        Complete lighthouse_enrichment block dict ready for DB write.
    """
    if str(scan_mode).lower() not in _LIGHTHOUSE_ELIGIBLE_MODES:
        return {
            "status": "skipped",
            "failure_reason": f"scan_mode '{scan_mode}' is not Lighthouse-eligible",
            "urls_audited": [],
        }

    mapping_version = get_mapping_version()
    lighthouse_version = get_lighthouse_version()
    t_batch_start = time.monotonic()

    selected_urls = select_urls_for_lighthouse(crawl_urls)
    if not selected_urls:
        return {
            "status": "skipped",
            "failure_reason": "no_urls_selected",
            "lighthouse_version": lighthouse_version,
            "mapping_version": mapping_version,
            "urls_audited": [],
            "aggregate_scores": {},
            "findings": [],
            "ran_at": datetime.datetime.utcnow().isoformat() + "Z",
            "duration_seconds": 0.0,
        }

    logger.info(
        "lighthouse_enricher starting scan_id=%s urls=%d mode=%s",
        scan_id, len(selected_urls), scan_mode,
    )

    # ── Run Lighthouse per URL ────────────────────────────────────────────────
    per_url_results: dict[str, Any] = {}
    all_lighthouse_findings: list[dict[str, Any]] = []
    all_category_scores: list[dict[str, int | None]] = []

    # Batch telemetry counters.
    total_urls_attempted = 0
    success_count = 0
    failure_count = 0
    cache_hit_count = 0
    total_duration = 0.0

    chrome_failed = False

    for url in selected_urls:
        total_urls_attempted += 1
        try:
            url_result = await run_lighthouse_for_url(
                url,
                lighthouse_version=lighthouse_version,
                mapping_version=mapping_version,
            )
        except ChromeLaunchError as exc:
            # Infrastructure failure — abort the entire batch immediately.
            logger.error(
                "lighthouse_enricher chrome_launch_failed scan_id=%s. Aborting batch. error=%s",
                scan_id, exc,
            )
            chrome_failed = True
            for remaining_url in selected_urls[total_urls_attempted:]:
                per_url_results[remaining_url] = {
                    "status": "failed",
                    "failure_reason": "chrome_launch_failed",
                    "cache_hit": False,
                    "scores": {},
                }
                failure_count += 1
            break
        except Exception as exc:
            logger.error(
                "lighthouse_enricher unexpected_error url=%s scan_id=%s error=%s",
                url, scan_id, exc,
            )
            per_url_results[url] = {
                "status": "failed",
                "failure_reason": "lighthouse_parse_error",
                "cache_hit": False,
                "scores": {},
            }
            failure_count += 1
            total_duration += 0.0
            continue

        duration = float(url_result.get("duration_seconds", 0.0))
        total_duration += duration
        is_cache_hit = bool(url_result.get("cache_hit", False))
        if is_cache_hit:
            cache_hit_count += 1

        failure_reason = url_result.get("failure_reason")
        raw_report = url_result.get("raw_report")

        if failure_reason or raw_report is None:
            per_url_results[url] = {
                "status": "failed",
                "failure_reason": failure_reason or "unknown",
                "cache_hit": is_cache_hit,
                "scores": {},
            }
            failure_count += 1
            continue

        # Success path — map and collect.
        try:
            category_scores = extract_category_scores(raw_report)
            url_findings = map_lighthouse_report(raw_report, page_url=url)
        except Exception as exc:
            logger.error(
                "lighthouse_enricher mapper_error url=%s scan_id=%s error=%s",
                url, scan_id, exc,
            )
            per_url_results[url] = {
                "status": "failed",
                "failure_reason": "lighthouse_parse_error",
                "cache_hit": is_cache_hit,
                "scores": {},
            }
            failure_count += 1
            continue

        per_url_results[url] = {
            "status": "completed",
            "failure_reason": None,
            "cache_hit": is_cache_hit,
            "duration_seconds": duration,
            "scores": category_scores,
        }
        all_category_scores.append(category_scores)
        all_lighthouse_findings.extend(url_findings)
        success_count += 1

    # ── Aggregate category scores across URLs ─────────────────────────────────
    aggregate_scores: dict[str, int | None] = {}
    if all_category_scores:
        for key in ("performance", "accessibility", "seo", "best_practices"):
            values = [s[key] for s in all_category_scores if s.get(key) is not None]
            aggregate_scores[key] = round(sum(values) / len(values)) if values else None
    else:
        aggregate_scores = {
            "performance": None,
            "accessibility": None,
            "seo": None,
            "best_practices": None,
        }

    # ── Merge with BEACON findings ────────────────────────────────────────────
    try:
        enriched_findings, merge_telemetry = merge_findings(beacon_findings, all_lighthouse_findings)
    except Exception as exc:
        logger.error(
            "lighthouse_enricher merge_error scan_id=%s error=%s", scan_id, exc
        )
        enriched_findings = list(beacon_findings)
        merge_telemetry = {"error": str(exc)}

    batch_duration = round(time.monotonic() - t_batch_start, 2)
    avg_duration = round(total_duration / total_urls_attempted, 2) if total_urls_attempted else 0.0

    overall_status: str
    overall_failure_reason: str | None = None
    if chrome_failed:
        overall_status = "failed"
        overall_failure_reason = "chrome_launch_failed"
    elif success_count == 0 and failure_count > 0:
        overall_status = "failed"
        overall_failure_reason = "all_urls_failed"
    else:
        overall_status = "completed"

    enrichment_block = {
        "status": overall_status,
        "failure_reason": overall_failure_reason,
        "lighthouse_version": lighthouse_version,
        "mapping_version": mapping_version,
        "urls_audited": selected_urls,
        "per_url_results": per_url_results,
        "aggregate_scores": aggregate_scores,
        "findings": enriched_findings,
        "merge_telemetry": merge_telemetry,
        "batch_metrics": {
            "total_urls_attempted": total_urls_attempted,
            "success_count": success_count,
            "failure_count": failure_count,
            "cache_hit_count": cache_hit_count,
            "avg_duration_seconds": avg_duration,
        },
        "ran_at": datetime.datetime.utcnow().isoformat() + "Z",
        "duration_seconds": batch_duration,
    }

    logger.info(
        "lighthouse_enricher complete scan_id=%s status=%s success=%d fail=%d "
        "cache_hits=%d duration=%.1fs",
        scan_id, overall_status, success_count, failure_count,
        cache_hit_count, batch_duration,
    )
    return enrichment_block
