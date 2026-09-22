"""
Dashboard API - projects and scans backed by SQLAlchemy persistence.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import threading
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel

from app.audit.failure_taxonomy import normalize_failure
from app.audit.scan_mode_runner import run_scan_mode_audit
from app.config import (
    resolve_max_pages,
)
from app.db.dashboard_repository import (
    delete_project as delete_project_record,
)
from app.db.dashboard_repository import (
    get_project as get_project_record,
)
from app.db.dashboard_repository import (
    get_scan as get_scan_record,
)
from app.db.dashboard_repository import (
    list_projects as list_project_records,
)
from app.db.dashboard_repository import (
    list_scans as list_scan_records,
)
from app.db.dashboard_repository import (
    upsert_project as upsert_project_record,
)
from app.db.dashboard_repository import (
    upsert_scan as upsert_scan_record,
)
from app.security.jwt_utils import get_current_user_id
from app.services.audit_runner import get_audit_runtime_health, run_audit
from app.services.grouper import group_issues

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Dashboard API"])

SCAN_STALE_TIMEOUT_SECONDS = 15 * 60

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
SCANS_FILE = os.path.join(DATA_DIR, "scans.json")

_legacy_bootstrap_done = False
_legacy_bootstrap_lock = threading.Lock()


def _resolve_site_scan_page_budget(scan_mode: str, user_id: str | None = None) -> int:
    from app.db.repository import get_user_usage_limits
    mode = (scan_mode or "deep").lower()
    mode_ceiling = resolve_max_pages(mode, has_sitemap=False)
    
    user_limits = get_user_usage_limits(user_id) if user_id else {}
    user_max = user_limits.get("max_pages", 10)
    
    return min(mode_ceiling, user_max)


def _extract_page_issue_occurrences(site_payload: dict) -> list[dict]:
    occurrences: list[dict] = []
    for page_result in site_payload.get("results", []):
        if not isinstance(page_result, dict):
            continue
        issues = page_result.get("issues", [])
        if not isinstance(issues, list):
            continue
        for issue in issues:
            if isinstance(issue, dict):
                occurrences.append(issue)
    return occurrences


def _severity_counts(issues: list[dict]) -> dict[str, int]:
    counts = {"critical": 0, "serious": 0, "moderate": 0, "minor": 0}
    for issue in issues:
        severity = str(issue.get("severity") or "").lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def _normalize_site_scan_result(site_payload: dict, scan_mode: str, elapsed_seconds: float) -> dict:
    site_result = site_payload.get("site_result", {}) if isinstance(site_payload.get("site_result"), dict) else {}
    site_failure_profile = (
        site_payload.get("site_failure_profile", {})
        if isinstance(site_payload.get("site_failure_profile"), dict)
        else {}
    )
    crawl_meta = site_payload.get("crawl_meta", {}) if isinstance(site_payload.get("crawl_meta"), dict) else {}

    site_issues = [
        issue for issue in site_result.get("issues", [])
        if isinstance(issue, dict)
    ]
    page_issue_occurrences = _extract_page_issue_occurrences(site_payload)

    summed_element_occurrences = sum(
        max(
            1,
            int(
                issue.get("affected_count")
                or issue.get("count")
                or issue.get("affected_pages")
                or 1
            ),
        )
        for issue in site_issues
    )

    pages_scanned = int(
        site_result.get("pages_audited")
        or site_payload.get("pages_completed")
        or len(site_payload.get("results", []) or [])
        or 1
    )
    pages_discovered = int(
        site_result.get("pages_discovered")
        or site_payload.get("pages_discovered")
        or pages_scanned
    )

    issue_types_count = len(site_issues)
    failing_elements_count = max(len(page_issue_occurrences), summed_element_occurrences)
    if failing_elements_count <= 0 and issue_types_count > 0:
        failing_elements_count = issue_types_count

    severity_source = page_issue_occurrences if page_issue_occurrences else site_issues
    severity_counts = _severity_counts(severity_source)

    raw_score = site_result.get("site_score")
    score = round(float(raw_score), 1) if isinstance(raw_score, (int, float)) else None

    issue_by_rule: dict[str, dict] = {}
    for issue in site_issues:
        rule_id = str(issue.get("rule_id") or "")
        if rule_id and rule_id not in issue_by_rule:
            issue_by_rule[rule_id] = issue

    priority_ranking: list[dict] = []
    for item in site_result.get("priority_ranking", []) if isinstance(site_result.get("priority_ranking"), list) else []:
        if not isinstance(item, dict):
            continue
        rule_id = str(item.get("rule_id") or "")
        source_issue = issue_by_rule.get(rule_id, {})
        affected_pages = int(item.get("affected_pages") or 0)
        priority_ranking.append(
            {
                **item,
                "rule_family": source_issue.get("rule_id") or rule_id,
                "description": source_issue.get("description") or rule_id,
                "severity": source_issue.get("severity"),
                "frequency": affected_pages,
            }
        )

    groups = group_issues(site_issues) if site_issues else []

    engines_policy = site_payload.get("engines_policy", {}) if isinstance(site_payload.get("engines_policy"), dict) else {}
    engines_used = ["site-orchestrator", "crawler-sitemap", "crawler-discovery", "static", "heuristic"]
    if engines_policy.get("playwright"):
        engines_used.append("browser-probe")
    if engines_policy.get("axe"):
        engines_used.append("axe-core")
    if engines_policy.get("cognitive"):
        engines_used.append("cognitive")

    degraded_mode = bool(
        site_payload.get("degraded_mode")
        or site_result.get("degraded_mode")
        or site_payload.get("sla_truncated")
    )
    partial_engine_coverage = bool(
        site_payload.get("partial_engine_coverage")
        or site_result.get("partial_engine_coverage")
    )
    audit_run_id = (
        site_payload.get("audit_run_id")
        or site_result.get("audit_run_id")
        or ""
    )

    top_degraded = site_payload.get("top_degraded_causes", [])
    degraded_reason = normalize_failure(top_degraded[0].get("reason")).value if isinstance(top_degraded, list) and top_degraded and isinstance(top_degraded[0], dict) and top_degraded[0].get("reason") else None

    confidence_score = site_result.get("confidence_score")
    if not isinstance(confidence_score, (int, float)):
        confidence_score = crawl_meta.get("site_confidence_score")
    if not isinstance(confidence_score, (int, float)):
        confidence_score = site_failure_profile.get("site_confidence_score")
    if not isinstance(confidence_score, (int, float)):
        confidence_score = 0.85 if not degraded_mode else 0.55
    confidence_score = round(max(0.0, min(1.0, float(confidence_score))), 4)

    if confidence_score < 0.30:
        score = None

    if confidence_score < 0.30:
        confidence_note = "Low confidence due to degraded or sparse page evidence; score suppressed."
    elif confidence_score < 0.55:
        confidence_note = "Moderate-low confidence; interpret score with caution."
    elif confidence_score < 0.75:
        confidence_note = "Moderate confidence based on sampled crawl evidence."
    else:
        confidence_note = "High confidence from multi-page crawl and consistent signals."

    confidence_values = [float(issue.get("confidence") or 0.0) for issue in site_issues]
    confidence_avg = (sum(confidence_values) / len(confidence_values)) if confidence_values else 0.0

    trust_warnings = []
    if degraded_mode:
        trust_warnings.append("site_scan_degraded_or_truncated")
    if partial_engine_coverage and not degraded_mode:
        # Partial coverage without full degradation: engines ran but not all completed.
        trust_warnings.append("partial_engine_coverage")
    if pages_scanned <= 1:
        trust_warnings.append("single_page_coverage")

    trust_payload = {
        "confidence_avg": round(confidence_avg, 4),
        "suppression_rate": 0.0,
        "data_quality": "medium" if degraded_mode else "high",
        "engines_coverage": {
            "static": True,
            "heuristic": True,
            "browser": bool(engines_policy.get("playwright")),
            "axe": bool(engines_policy.get("axe")),
            "ibm": "ibm" in engines_used or any("ibm" in str(e).lower() for e in engines_used),
            "cognitive": bool(engines_policy.get("cognitive")) or "cognitive" in engines_used,
            "lighthouse": "lighthouse" in engines_used,
        },
        "calibration_warnings": trust_warnings,
        "audit_completeness": "partial" if degraded_mode else "full",
        "low_trust_rules_present": [],
        "score_integrity": {},
    }

    summary = (
        f"Site scan audited {pages_scanned} page(s), discovered {pages_discovered}, "
        f"found {failing_elements_count} failing element(s) across {issue_types_count} issue type(s). "
        f"Score: {'n/a' if score is None else f'{score}/100'}"
    )

    return {
        "url": site_payload.get("seed_url"),
        "scan_mode": scan_mode,
        "score": score,
        "score_raw": raw_score,
        "overall_score": score,
        "total_issues": failing_elements_count,
        "issue_types_count": issue_types_count,
        "failing_elements_count": failing_elements_count,
        "critical_issues": severity_counts["critical"],
        "serious_issues": severity_counts["serious"],
        "moderate_issues": severity_counts["moderate"],
        "minor_issues": severity_counts["minor"],
        "issues": site_issues,
        "groups": groups,
        "priority_ranking": priority_ranking,
        "summary": summary,
        "scan_time_seconds": round(float(elapsed_seconds), 2),
        "engines_used": engines_used,
        "degraded_mode": degraded_mode,
        "partial_engine_coverage": partial_engine_coverage,
        "audit_run_id": audit_run_id,
        "degraded_reason": normalize_failure(degraded_reason).value if degraded_reason else None,
        "skipped_components": [],
        "degradation_reason": degraded_reason,
        "confidence_score": confidence_score,
        "confidence_note": confidence_note,
        "site_failure_profile": site_failure_profile,
        "enrichment_status": "complete",
        "cognitive_scores": None,
        "markdown_report": "",
        "trust": trust_payload,
        "pages_scanned": pages_scanned,
        "pages_discovered": pages_discovered,
        "scraped_pages": site_payload.get("urls_audited") or site_payload.get("scraped_pages") or [],
    }


def _load_legacy_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
            if isinstance(payload, dict):
                return payload
    except Exception as exc:
        logger.warning("Unable to load legacy dashboard file %s: %s", path, exc)

    return {}


def _ensure_legacy_bootstrap() -> None:
    global _legacy_bootstrap_done
    if _legacy_bootstrap_done:
        return

    with _legacy_bootstrap_lock:
        if _legacy_bootstrap_done:
            return

        try:
            if list_project_records() or list_scan_records():
                _legacy_bootstrap_done = True
                return

            projects = _load_legacy_json(PROJECTS_FILE)
            scans = _load_legacy_json(SCANS_FILE)

            imported_projects = 0
            imported_scans = 0

            for project in projects.values():
                if not isinstance(project, dict) or not project.get("id"):
                    continue
                upsert_project_record(project)
                imported_projects += 1

            for scan in scans.values():
                if not isinstance(scan, dict) or not scan.get("id"):
                    continue
                if not scan.get("project_id"):
                    continue
                upsert_scan_record(scan)
                imported_scans += 1

            if imported_projects or imported_scans:
                logger.info(
                    "Imported %s legacy project(s) and %s scan(s) from JSON into SQL storage",
                    imported_projects,
                    imported_scans,
                )
        finally:
            _legacy_bootstrap_done = True


def _utc_now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def _parse_iso(ts: str | None) -> datetime.datetime | None:
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _expire_stale_scans(project_id: str | None = None) -> int:
    """Mark long-running scans as failed so the UI does not spin forever."""
    now = datetime.datetime.utcnow()
    changed = 0

    scans = list_scan_records(project_id=project_id)
    for scan in scans:
        if scan.get("status") != "scanning":
            continue

        created_at = _parse_iso(scan.get("created_at"))
        if not created_at:
            continue

        age_seconds = (now - created_at).total_seconds()
        if age_seconds <= SCAN_STALE_TIMEOUT_SECONDS:
            continue

        scan["status"] = "failed"
        scan["summary"] = "Scan timed out before completion. Please retry."
        scan["ai_analysis"] = "Scan timed out before completion. Please retry."
        scan["completed_at"] = _utc_now_iso()
        upsert_scan_record(scan)
        changed += 1

    if changed:
        logger.warning(
            "Expired %s stale scan(s)%s",
            changed,
            f" for project {project_id}" if project_id else "",
        )

    return changed


def _fail_active_scans_for_project(project_id: str, reason: str) -> int:
    """Ensure only one active scan per project by failing older active jobs."""
    changed = 0
    now_iso = _utc_now_iso()

    scans = list_scan_records(project_id=project_id)
    for scan in scans:
        if scan.get("status") != "scanning":
            continue

        scan["status"] = "failed"
        scan["summary"] = reason
        scan["ai_analysis"] = reason
        scan["completed_at"] = now_iso
        upsert_scan_record(scan)
        changed += 1

    if changed:
        logger.info("Marked %s active scan(s) as failed for project %s", changed, project_id)

    return changed


def _detect_audit_failure(result: dict) -> tuple[bool, str]:
    """Translate partial or fallback audit payloads into a clear failed state."""
    summary = (result.get("summary") or "").strip()
    summary_lc = summary.lower()
    engines_used = result.get("engines_used") or []
    total_issues = int(result.get("total_issues") or 0)
    score = result.get("score")

    if summary_lc.startswith("failed to fetch url"):
        return True, summary

    if total_issues == 0 and (score == 0 or score == 0.0) and len(engines_used) == 0:
        return True, summary or "Scan failed before any audit engines produced results."

    return False, ""


def _recompute_project_summary(project_id: str) -> bool:
    """Update project card stats from latest valid completed scan."""
    project = get_project_record(project_id)
    if not project:
        return False

    before = (
        project.get("latest_score"),
        project.get("total_issues"),
        project.get("last_scan_at"),
    )

    completed_scans = [
        scan for scan in list_scan_records(project_id=project_id)
        if scan.get("status") == "completed"
    ]
    completed_scans = sorted(
        completed_scans,
        key=lambda scan: scan.get("completed_at") or scan.get("created_at") or "",
        reverse=True,
    )

    if completed_scans:
        latest = completed_scans[0]
        project["latest_score"] = latest.get("score")
        project["total_issues"] = latest.get("total_issues", 0)
        project["last_scan_at"] = latest.get("completed_at") or latest.get("created_at")
    else:
        project["latest_score"] = None
        project["total_issues"] = 0
        project["last_scan_at"] = None

    after = (
        project.get("latest_score"),
        project.get("total_issues"),
        project.get("last_scan_at"),
    )

    if before != after:
        upsert_project_record(project)
        return True

    return False


def _repair_invalid_completed_scans(project_id: str | None = None) -> int:
    """Repair legacy records where failed fetches were persisted as completed scans."""
    changed = 0
    touched_projects: set[str] = set()

    scans = list_scan_records(project_id=project_id)
    for scan in scans:
        if scan.get("status") != "completed":
            continue

        summary = (scan.get("summary") or "").strip()
        summary_lc = summary.lower()
        engines_used = scan.get("engines_used") or []
        score = scan.get("score")
        total_issues = int(scan.get("total_issues") or 0)

        looks_like_failed_fetch = summary_lc.startswith("failed to fetch url")
        looks_like_empty_failure = total_issues == 0 and (score == 0 or score == 0.0) and len(engines_used) == 0
        if not (looks_like_failed_fetch or looks_like_empty_failure):
            continue

        reason = summary or "Scan failed before any audit engines produced results."
        scan["status"] = "failed"
        scan["score"] = None
        scan["enrichment_status"] = "failed"
        scan["summary"] = reason
        scan["ai_analysis"] = reason
        scan["completed_at"] = scan.get("completed_at") or _utc_now_iso()
        upsert_scan_record(scan)
        touched_projects.add(scan.get("project_id", ""))
        changed += 1

    if changed:
        for pid in touched_projects:
            if pid:
                _recompute_project_summary(pid)
        logger.info(
            "Repaired %s invalid completed scan record(s)%s",
            changed,
            f" for project {project_id}" if project_id else "",
        )

    return changed


class ProjectCreate(BaseModel):
    name: str
    url: str
    description: str | None = None


class ScanStart(BaseModel):
    project_id: str
    scan_mode: str | None = "fast"


@router.post("/projects/")
async def create_project(
    data: ProjectCreate,
    user_id: str | None = Depends(get_current_user_id),
):
    _ensure_legacy_bootstrap()
    pid = str(uuid.uuid4())[:8]
    project = {
        "id": pid,
        "name": data.name,
        "url": data.url,
        "description": data.description or "",
        "created_at": _utc_now_iso(),
        "last_scan_at": None,
        "latest_score": None,
        "total_issues": 0,
        "user_id": user_id,
    }
    return upsert_project_record(project, user_id=user_id)


@router.get("/projects/")
async def get_projects(user_id: str | None = Depends(get_current_user_id)):
    def _fetch():
        _ensure_legacy_bootstrap()
        _repair_invalid_completed_scans()

        changed = False
        projects = list_project_records(user_id=user_id)
        for project in projects:
            changed = _recompute_project_summary(project["id"]) or changed

        if changed:
            projects = list_project_records(user_id=user_id)

        return sorted(projects, key=lambda project: project.get("created_at", ""), reverse=True)

    return await asyncio.to_thread(_fetch)


@router.get("/projects/{pid}")
async def get_project(
    pid: str,
    user_id: str | None = Depends(get_current_user_id),
):
    def _fetch_one():
        _ensure_legacy_bootstrap()

        project = get_project_record(pid, user_id=user_id)
        if not project:
            raise HTTPException(404, "Project not found or access denied")

        if _recompute_project_summary(pid):
            project = get_project_record(pid, user_id=user_id)

        return project

    return await asyncio.to_thread(_fetch_one)


@router.delete("/projects/{pid}")
async def delete_project(
    pid: str,
    user_id: str | None = Depends(get_current_user_id),
):
    _ensure_legacy_bootstrap()

    deleted = delete_project_record(pid, user_id=user_id)
    if not deleted:
        raise HTTPException(404, "Project not found or access denied")

    return {"status": "deleted"}


@router.post("/scans/")
async def start_scan(
    data: ScanStart,
    user_id: str | None = Depends(get_current_user_id),
):
    _ensure_legacy_bootstrap()

    project = get_project_record(data.project_id, user_id=user_id)
    if not project:
        raise HTTPException(404, "Project not found or access denied")

    _repair_invalid_completed_scans(project_id=data.project_id)
    _expire_stale_scans(project_id=data.project_id)
    _fail_active_scans_for_project(
        project_id=data.project_id,
        reason="Superseded by a newer scan request.",
    )

    scan_id = str(uuid.uuid4())[:8]
    scan_url = project["url"]
    scan_mode = data.scan_mode or "fast"

    if scan_mode in {"deep", "max"}:
        runtime = get_audit_runtime_health()
        active = int(runtime.get("active_audits", 0) or 0)
        maximum = max(1, int(runtime.get("max_concurrent_audits", 1) or 1))
        if active >= maximum:
            raise HTTPException(
                status_code=429,
                detail={
                    "message": "Scanner is saturated. Retry shortly or run in fast mode.",
                    "active_audits": active,
                    "max_concurrent_audits": maximum,
                    "recommended_scan_mode": "fast",
                },
            )

    scan_record: dict = {
        "id": scan_id,
        "project_id": data.project_id,
        "status": "scanning",
        "url": scan_url,
        "scan_mode": scan_mode,
        "score": None,
        "total_issues": 0,
        "issue_types_count": 0,
        "failing_elements_count": 0,
        "critical_issues": 0,
        "serious_issues": 0,
        "moderate_issues": 0,
        "minor_issues": 0,
        "summary": "",
        "ai_analysis": "",
        "issues": [],
        "groups": [],
        "priority_ranking": [],
        "trust": {},
        "engines_used": [],
        "scan_time_seconds": 0,
        "pages_scanned": 1,
        "pages_discovered": 1,
        "scraped_pages": [],
        "degraded_mode": False,
        "degraded_reason": normalize_failure(None).value if False else None,
        "skipped_components": [],
        "degradation_reason": None,
        "confidence_score": None,
        "confidence_note": "",
        "site_failure_profile": {},
        "enrichment_status": "pending",
        "cognitive_scores": None,
        "created_at": _utc_now_iso(),
        "completed_at": None,
        "markdown_report": "",
        "user_id": user_id,
    }
    upsert_scan_record(scan_record)

    async def run_bg_audit():
        try:
            if scan_mode in {"deep", "max"}:
                started = time.perf_counter()
                site_payload = await run_scan_mode_audit(
                    seed_url=scan_url,
                    scan_mode=scan_mode,
                    max_pages=_resolve_site_scan_page_budget(scan_mode, user_id),
                )
                elapsed = time.perf_counter() - started
                result = _normalize_site_scan_result(site_payload, scan_mode, elapsed)

                # If crawl discovery yields only a single page, compare against the
                # direct full-engine audit and keep the richer finding set.
                site_issue_count = int(result.get("total_issues") or 0)
                site_pages_scanned = int(result.get("pages_scanned") or 1)
                if site_pages_scanned <= 1:
                    try:
                        direct_result = await run_audit(
                            url=scan_url,
                            scan_mode=scan_mode,
                            max_pages=1,
                            enable_enrichment=False,
                            use_cache=False,
                            user_id=user_id,
                            is_internal=True,
                        )
                        direct_issue_count = int(direct_result.get("total_issues") or 0)
                        if direct_issue_count > site_issue_count:
                            result = direct_result
                            logger.info(
                                "Using direct full-engine result for single-page scan %s (site=%s, direct=%s)",
                                scan_id,
                                site_issue_count,
                                direct_issue_count,
                            )
                    except Exception as direct_exc:
                        logger.warning("Direct single-page comparison failed for %s: %s", scan_id, direct_exc)
            else:
                result = await run_audit(url=scan_url, scan_mode=scan_mode, user_id=user_id)

            failed, failure_reason = _detect_audit_failure(result)
            if failed:
                scan_record["status"] = "failed"
                scan_record["summary"] = failure_reason
                scan_record["ai_analysis"] = failure_reason
                scan_record["engines_used"] = result.get("engines_used", [])
                scan_record["scan_time_seconds"] = result.get("scan_time_seconds", 0)
                scan_record["pages_scanned"] = int(result.get("pages_scanned") or 1)
                scan_record["pages_discovered"] = int(result.get("pages_discovered") or scan_record["pages_scanned"])
                scan_record["confidence_score"] = result.get("confidence_score")
                scan_record["confidence_note"] = result.get("confidence_note", "")
                scan_record["site_failure_profile"] = result.get("site_failure_profile", {})
                scan_record["enrichment_status"] = "failed"
                trust_payload = dict(result.get("trust", {}) or {})
                trust_payload["confidence_score"] = result.get("confidence_score")
                trust_payload["confidence_note"] = result.get("confidence_note", "")
                trust_payload["site_failure_profile"] = result.get("site_failure_profile", {})
                scan_record["trust"] = trust_payload
                scan_record["completed_at"] = _utc_now_iso()
                upsert_scan_record(scan_record)
                logger.warning("Scan %s failed early: %s", scan_id, failure_reason)
                return

            issues = result.get("issues", [])
            critical = sum(1 for item in issues if item.get("severity") == "critical")
            serious = sum(1 for item in issues if item.get("severity") == "serious")
            moderate = sum(1 for item in issues if item.get("severity") == "moderate")
            minor = sum(1 for item in issues if item.get("severity") == "minor")

            scan_record["status"] = "completed"
            scan_record["score"] = result.get("score", 0)
            scan_record["total_issues"] = result.get("total_issues", 0)
            scan_record["issue_types_count"] = int(result.get("issue_types_count") or len(issues))
            scan_record["failing_elements_count"] = int(result.get("failing_elements_count") or result.get("total_issues", 0))
            scan_record["critical_issues"] = int(result.get("critical_issues") or critical)
            scan_record["serious_issues"] = int(result.get("serious_issues") or serious)
            scan_record["moderate_issues"] = int(result.get("moderate_issues") or moderate)
            scan_record["minor_issues"] = int(result.get("minor_issues") or minor)
            scan_record["summary"] = result.get("summary", "")
            scan_record["ai_analysis"] = "AI engine is generating insights..."
            scan_record["issues"] = issues
            scan_record["groups"] = result.get("groups", [])
            scan_record["priority_ranking"] = result.get("priority_ranking", [])
            scan_record["engines_used"] = result.get("engines_used", [])
            scan_record["scan_time_seconds"] = result.get("scan_time_seconds", 0)
            scan_record["pages_scanned"] = int(result.get("pages_scanned") or 1)
            scan_record["pages_discovered"] = int(result.get("pages_discovered") or scan_record["pages_scanned"])
            scan_record["scraped_pages"] = result.get("scraped_pages", [])
            trust_payload = dict(result.get("trust", {}) or {})
            trust_payload["confidence_score"] = result.get("confidence_score")
            trust_payload["confidence_note"] = result.get("confidence_note", "")
            trust_payload["site_failure_profile"] = result.get("site_failure_profile", {})
            scan_record["trust"] = trust_payload
            scan_record["degraded_mode"] = result.get("degraded_mode", False)
            scan_record["partial_engine_coverage"] = result.get("partial_engine_coverage", False)
            scan_record["audit_run_id"] = result.get("audit_run_id", "")
            scan_record["degraded_reason"] = result.get("degraded_reason")
            scan_record["skipped_components"] = result.get("skipped_components", [])
            scan_record["degradation_reason"] = result.get("degradation_reason")
            scan_record["confidence_score"] = result.get("confidence_score")
            scan_record["confidence_note"] = result.get("confidence_note")
            scan_record["site_failure_profile"] = result.get("site_failure_profile", {})
            scan_record["enrichment_status"] = result.get("enrichment_status", "complete")
            scan_record["cognitive_scores"] = result.get("cognitive_scores")
            scan_record["markdown_report"] = result.get("markdown_report", "")
            scan_record["completed_at"] = _utc_now_iso()

            upsert_scan_record(scan_record)

            # ── Phase 2.5: Lighthouse Enrichment (fire and forget, deep/max only) ──
            if scan_mode in {"deep", "max"}:
                try:
                    from app.audit.scan_mode_runner import _lighthouse_eligible
                    from app.services.audit_runner import _run_lighthouse_background
                    if _lighthouse_eligible(scan_mode):
                        crawl_urls = list(result.get("scraped_pages") or result.get("urls_audited") or [scan_url])
                        beacon_findings = list(result.get("issues") or [])
                        asyncio.create_task(
                            _run_lighthouse_background(
                                scan_id=scan_id,
                                beacon_findings=beacon_findings,
                                crawl_urls=crawl_urls,
                                scan_mode=scan_mode,
                            )
                        )
                        logger.info("Lighthouse enrichment background task dispatched for scan %s", scan_id)
                except Exception as lh_exc:
                    logger.error("Failed to dispatch lighthouse enrichment for scan %s: %s", scan_id, lh_exc)



            fresh_project = get_project_record(data.project_id)
            if fresh_project:
                fresh_project["latest_score"] = scan_record["score"]
                fresh_project["total_issues"] = scan_record["failing_elements_count"]
                fresh_project["last_scan_at"] = scan_record["completed_at"]
                upsert_project_record(fresh_project)

            logger.info("Scan %s marked completed. Phase 2 (AI) starting...", scan_id)

            try:
                from app.config import settings
                from app.services.llm import get_client

                client = get_client()
                degraded_prefix = ""
                if scan_record.get("degraded_mode"):
                    reason = (
                        scan_record.get("degradation_reason")
                        or scan_record.get("degraded_reason")
                        or "Requested engines were unavailable during this run."
                    )
                    degraded_prefix = f"Limited-confidence scan: {reason}\n\n"

                if not issues:
                    if scan_record.get("degraded_mode"):
                        ai_summary = (
                            degraded_prefix
                            + "No blocking issues were detected in static HTML, but browser-level checks did not run. "
                            + "Run deep scan again after browser engines recover."
                        )
                    else:
                        ai_summary = (
                            "Excellent! No accessibility issues were found. "
                            "Your site follows all primary accessibility standards."
                        )
                else:
                    top_issues = [f"{item.get('rule_id')} ({item.get('severity')})" for item in issues[:3]]
                    prompt = (
                        "Write a concise, 2-sentence executive summary of this web accessibility audit. "
                        f"Score: {result.get('score', 0)}/100, "
                        f"Issues found: {result.get('total_issues', 0)}. "
                        f"Top problems: {', '.join(top_issues)}."
                    )

                    ai_model = getattr(settings, "llm_model", "meta/llama-3.2-11b-vision-instruct")
                    response = await client.chat.completions.create(
                        model=ai_model,
                        messages=[
                            {"role": "system", "content": "You are the BEACON AI engine."},
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=150,
                        temperature=0.4,
                        timeout=15.0,
                    )
                    ai_summary = degraded_prefix + response.choices[0].message.content.strip()

                scan_record["ai_analysis"] = ai_summary
                upsert_scan_record(scan_record)
                logger.debug("AI summary generated for scan %s", scan_id)

            except Exception as exc:
                logger.error("Failed to generate top-level AI summary for %s: %s", scan_id, exc)
                err_str = str(exc).lower()
                if "429" in err_str or "insufficient_quota" in err_str or "limit" in err_str:
                    ai_summary = (
                        "[AI ERROR]: API credit limit reached. "
                        f"Please check your NVIDIA NIM API billing. Raw error: {exc}"
                    )
                elif "401" in err_str:
                    ai_summary = f"[AI ERROR]: Authentication failure. Raw error: {exc}"
                elif "timeout" in err_str:
                    ai_summary = f"[AI ERROR]: Request timed out. Raw error: {exc}"
                else:
                    ai_summary = f"[AI ERROR]: System failure. Technical details: {exc}"

                scan_record["ai_analysis"] = ai_summary
                upsert_scan_record(scan_record)

            logger.info(
                "Scan %s completed: score=%s, issues=%s",
                scan_id,
                scan_record["score"],
                scan_record["total_issues"],
            )

        except Exception as exc:
            scan_record["status"] = "failed"
            scan_record["summary"] = f"Scan failed: {exc}"
            scan_record["ai_analysis"] = f"Scan failed: {exc}"
            scan_record["enrichment_status"] = "failed"
            scan_record["trust"] = scan_record.get("trust") or {}
            scan_record["completed_at"] = _utc_now_iso()
            upsert_scan_record(scan_record)
            logger.error("Scan %s failed: %s", scan_id, exc, exc_info=True)

    asyncio.create_task(run_bg_audit())
    return {"scan_id": scan_id, "status": "scanning"}


@router.get("/scans/{pid}")
async def get_scans(pid: str):
    _ensure_legacy_bootstrap()

    _repair_invalid_completed_scans(project_id=pid)
    _expire_stale_scans(project_id=pid)

    if _recompute_project_summary(pid):
        logger.debug("Project %s summary recomputed from scan history", pid)

    scans = list_scan_records(project_id=pid)
    return sorted(scans, key=lambda scan: scan.get("created_at", ""), reverse=True)


@router.get("/profiles")
async def list_regulatory_profiles():
    """Lists all authoritative regulatory compliance control profiles (§25–§30)."""
    from app.profiles.registry import REGULATORY_PROFILES
    return [p.to_dict() for p in REGULATORY_PROFILES.values()]


@router.get("/personas")
async def list_persona_lenses():
    """Lists all user persona lenses (§32–§38)."""
    from app.profiles.registry import PERSONA_LENSES
    return [lens.to_dict() for lens in PERSONA_LENSES.values()]


@router.get("/scans/{pid}/{sid}")
async def get_scan(
    pid: str,
    sid: str,
    profile: str | None = Query(None, description="Regulatory profile ID (e.g. GLOBAL_WCAG_22_AA, US_SECTION_508)"),
    persona: str | None = Query(None, description="Persona lens ID (e.g. SCREEN_READER, KEYBOARD_MOTOR)"),
    view: str | None = Query(None, description="Role view (DEVELOPER, QA_A11Y, COMPLIANCE, EXECUTIVE)"),
):
    _ensure_legacy_bootstrap()

    _repair_invalid_completed_scans(project_id=pid)
    _expire_stale_scans(project_id=pid)

    scan = get_scan_record(sid)
    if not scan:
        raise HTTPException(404, "Scan not found")

    if profile or persona or view:
        try:
            from app.services.role_views import project_scan_view
            return project_scan_view(scan, profile_id=profile, persona_id=persona, view=view)
        except ValueError as e:
            raise HTTPException(400, str(e))

    return scan


@router.get("/scans/{pid}/{sid}/progress")
async def get_scan_progress(pid: str, sid: str):
    _ensure_legacy_bootstrap()

    _repair_invalid_completed_scans(project_id=pid)
    _expire_stale_scans(project_id=pid)

    scan = get_scan_record(sid)
    if not scan:
        raise HTTPException(404, "Scan not found")

    return {
        "status": scan["status"],
        "score": scan.get("score"),
        "total_issues": scan.get("total_issues", 0),
    }


def _issue_dict_to_finding(issue: dict):
    from app.models.contracts import Finding
    confidence_sources = issue.get("confidence_sources") or []
    return Finding(
        id=str(issue.get("id") or issue.get("issue_id") or uuid.uuid4().hex[:8]),
        rule_id=str(issue.get("rule_id") or issue.get("description") or "a11y-violation"),
        engine=str(issue.get("engine") or (confidence_sources[0] if confidence_sources else "beacon")),
        engine_version="3.0.0",
        rule_version="3.0.0",
        beacon_version="3.0.0",
        wcag_criterion=str(issue.get("wcag_criterion") or ""),
        wcag_level=str(issue.get("wcag_level") or "AA"),
        severity=str(issue.get("severity") or "serious").lower(),
        selector=str(issue.get("selector") or issue.get("target_element") or "body"),
        selector_fingerprint=str(issue.get("selector_fingerprint") or ""),
        html_snippet=str(issue.get("html_snippet") or ""),
        message=str(issue.get("description") or issue.get("message") or ""),
        evidence=issue.get("evidence") or {},
        group_id=str(issue.get("group_id") or ""),
        confidence=float(issue.get("confidence") or 0.85),
        scanner_confidence=float(issue.get("scanner_confidence") or issue.get("confidence") or 0.85),
        verification_confidence=float(issue.get("verification_confidence") or 0.85),
        wcag_mapping_confidence=float(issue.get("wcag_mapping_confidence") or 0.90),
        consensus_confidence=float(issue.get("consensus_confidence") or 0.80),
        confidence_breakdown=issue.get("confidence_breakdown") or {},
        agreement_count=int(issue.get("agreement_count") or len(confidence_sources) or 1),
        participating_engines=issue.get("participating_engines") or confidence_sources or ["beacon"],
        act_rule_id=issue.get("act_rule_id"),
        act_adjudicated=bool(issue.get("act_adjudicated") or False),
    )


@router.get("/scans/{pid}/{sid}/export/{fmt}")
async def export_scan_report(pid: str, sid: str, fmt: str):
    """
    Export scan findings to standards-compliant formats:
    - 'sarif': OASIS SARIF 2.1.0 JSON (GitHub Code Scanning)
    - 'earl': W3C EARL 1.0 JSON-LD (EU EAA / ADA regulatory compliance)
    - 'markdown': Formatted markdown report
    - 'json': Raw normalized findings payload
    """
    _ensure_legacy_bootstrap()
    scan = get_scan_record(sid)
    if not scan:
        raise HTTPException(404, "Scan not found")

    url = scan.get("url") or "https://scan.target"
    issues = scan.get("issues") or []
    normalized_format = fmt.lower().strip()

    if normalized_format == "sarif":
        from app.audit.exporters.sarif_exporter import export_to_sarif
        findings = [_issue_dict_to_finding(issue) for issue in issues]
        sarif_data = export_to_sarif(findings, target_url=url, tool_version="3.0.0")
        return Response(
            content=json.dumps(sarif_data, indent=2),
            media_type="application/sarif+json",
            headers={"Content-Disposition": f'attachment; filename="beacon-scan-{sid}.sarif"'},
        )

    elif normalized_format in {"earl", "jsonld", "json-ld"}:
        from app.audit.exporters.earl_exporter import export_to_earl
        findings = [_issue_dict_to_finding(issue) for issue in issues]
        earl_data = export_to_earl(findings, target_url=url, tool_version="3.0.0")
        return Response(
            content=json.dumps(earl_data, indent=2),
            media_type="application/ld+json",
            headers={"Content-Disposition": f'attachment; filename="beacon-scan-{sid}.earl.jsonld"'},
        )

    elif normalized_format in {"markdown", "md"}:
        report_text = scan.get("markdown_report")
        if not report_text:
            from app.services.report import generate_markdown_report
            report_text = generate_markdown_report(
                url=url,
                scan_mode=scan.get("scan_mode", "fast"),
                score=float(scan.get("score") or 0.0),
                issues=issues,
                groups=scan.get("groups", []),
                prioritized_issues=scan.get("priority_ranking", []),
                scan_time=float(scan.get("scan_time_seconds") or 0.0),
                engines_used=scan.get("engines_used", []),
            )
        return Response(
            content=report_text,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="beacon-scan-{sid}.md"'},
        )

    elif normalized_format == "json":
        return Response(
            content=json.dumps(scan, indent=2, default=str),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="beacon-scan-{sid}.json"'},
        )

    elif normalized_format == "csv":
        from app.audit.exporters.csv_exporter import export_to_csv
        csv_text = export_to_csv(issues, target_url=url)
        return Response(
            content=csv_text,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="beacon-scan-{sid}.csv"'},
        )
    else:
        raise HTTPException(
            400,
            f"Unsupported export format: '{fmt}'. Supported formats: sarif, earl, markdown, json, csv.",
        )


@router.get("/scans/{pid}/{sid}/statement")
async def get_accessibility_statement(
    pid: str,
    sid: str,
    org_name: str = Query("[Organization Name]", description="Name of the organization"),
    profile: str = Query("W3C WCAG 2.2 Level AA", description="Target standard/profile"),
):
    """Generate an authoritative accessibility statement draft (§68)."""
    _ensure_legacy_bootstrap()
    scan = get_scan_record(sid)
    if not scan:
        raise HTTPException(404, "Scan not found")
    from app.services.accessibility_statement import generate_accessibility_statement
    statement = generate_accessibility_statement(
        scan,
        organization_name=org_name,
        profile_name=profile,
    )
    return {"statement": statement, "scan_id": sid, "project_id": pid}


