"""
Dashboard API — projects & scans backed by the real BEACON engine.
Data is persisted to local JSON files in app/data.
"""
import uuid
import datetime
import asyncio
import logging
import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.audit_runner import run_audit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Dashboard API"])

# ── JSON Persistence ──────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

PROJECTS_FILE = os.path.join(DATA_DIR, "projects.json")
SCANS_FILE = os.path.join(DATA_DIR, "scans.json")

def load_data(filepath: str) -> dict:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading {filepath}: {e}")
    return {}

def save_data(filepath: str, data: dict):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error writing to {filepath}: {e}")

# In-memory maps synchronized with disk
DB_PROJECTS: dict[str, dict] = load_data(PROJECTS_FILE)
DB_SCANS: dict[str, dict] = load_data(SCANS_FILE)

SCAN_STALE_TIMEOUT_SECONDS = 15 * 60


def _utc_now_iso() -> str:
    return datetime.datetime.utcnow().isoformat()


def _parse_iso(ts: Optional[str]) -> Optional[datetime.datetime]:
    if not ts:
        return None
    try:
        return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _expire_stale_scans(project_id: Optional[str] = None) -> int:
    """Mark long-running scans as failed so the UI does not spin forever."""
    now = datetime.datetime.utcnow()
    changed = 0

    for scan in DB_SCANS.values():
        if project_id and scan.get("project_id") != project_id:
            continue
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
        scan["ai_analysis"] = "⚠️ Scan timed out before completion. Please retry."
        scan["completed_at"] = _utc_now_iso()
        changed += 1

    if changed:
        save_data(SCANS_FILE, DB_SCANS)
        logger.warning(f"Expired {changed} stale scan(s){' for project ' + project_id if project_id else ''}")

    return changed


def _fail_active_scans_for_project(project_id: str, reason: str) -> int:
    """Ensure only one active scan per project by failing older active jobs."""
    changed = 0
    now_iso = _utc_now_iso()

    for scan in DB_SCANS.values():
        if scan.get("project_id") != project_id:
            continue
        if scan.get("status") != "scanning":
            continue

        scan["status"] = "failed"
        scan["summary"] = reason
        scan["ai_analysis"] = f"⚠️ {reason}"
        scan["completed_at"] = now_iso
        changed += 1

    if changed:
        save_data(SCANS_FILE, DB_SCANS)
        logger.info(f"Marked {changed} active scan(s) as failed for project {project_id}")

    return changed


def _detect_audit_failure(result: dict) -> tuple[bool, str]:
    """Translate partial/fallback audit payloads into a clear failed state."""
    summary = (result.get("summary") or "").strip()
    summary_lc = summary.lower()
    engines_used = result.get("engines_used") or []
    total_issues = int(result.get("total_issues") or 0)
    score = result.get("score")

    if summary_lc.startswith("failed to fetch url"):
        return True, summary

    # Defensive fallback: empty engine execution + zero metrics should not be considered success.
    if total_issues == 0 and (score == 0 or score == 0.0) and len(engines_used) == 0:
        return True, summary or "Scan failed before any audit engines produced results."

    return False, ""


def _recompute_project_summary(project_id: str) -> bool:
    """Update project card stats from latest valid completed scan."""
    project = DB_PROJECTS.get(project_id)
    if not project:
        return False

    before = (
        project.get("latest_score"),
        project.get("total_issues"),
        project.get("last_scan_at"),
    )

    completed_scans = [
        s for s in DB_SCANS.values()
        if s.get("project_id") == project_id and s.get("status") == "completed"
    ]
    completed_scans = sorted(
        completed_scans,
        key=lambda s: s.get("completed_at") or s.get("created_at") or "",
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
    return before != after


def _repair_invalid_completed_scans(project_id: Optional[str] = None) -> int:
    """Repair legacy records where failed fetches were persisted as completed scans."""
    changed = 0
    touched_projects: set[str] = set()

    for scan in DB_SCANS.values():
        if project_id and scan.get("project_id") != project_id:
            continue
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
        scan["ai_analysis"] = f"⚠️ {reason}"
        scan["completed_at"] = scan.get("completed_at") or _utc_now_iso()
        touched_projects.add(scan.get("project_id", ""))
        changed += 1

    if changed:
        for pid in touched_projects:
            if pid:
                _recompute_project_summary(pid)
        save_data(SCANS_FILE, DB_SCANS)
        save_data(PROJECTS_FILE, DB_PROJECTS)
        logger.info(f"Repaired {changed} invalid completed scan record(s){' for project ' + project_id if project_id else ''}")

    return changed


# ── Request Models ────────────────────────────────────────────────
class ProjectCreate(BaseModel):
    name: str
    url: str
    description: Optional[str] = None


class ScanStart(BaseModel):
    project_id: str
    scan_mode: Optional[str] = "fast"


# ── Project Endpoints ─────────────────────────────────────────────
@router.post("/projects/")
async def create_project(data: ProjectCreate):
    pid = str(uuid.uuid4())[:8]
    project = {
        "id": pid,
        "name": data.name,
        "url": data.url,
        "description": data.description or "",
        "created_at": datetime.datetime.utcnow().isoformat(),
        "last_scan_at": None,
        "latest_score": None,
        "total_issues": 0,
    }
    DB_PROJECTS[pid] = project
    save_data(PROJECTS_FILE, DB_PROJECTS)
    return project

@router.get("/projects/")
async def get_projects():
    _repair_invalid_completed_scans()

    changed = False
    for pid in DB_PROJECTS.keys():
        changed = _recompute_project_summary(pid) or changed
    if changed:
        save_data(PROJECTS_FILE, DB_PROJECTS)

    # Sort projects by most recently created
    projs = list(DB_PROJECTS.values())
    return sorted(projs, key=lambda p: p.get("created_at", ""), reverse=True)


@router.get("/projects/{pid}")
async def get_project(pid: str):
    if pid not in DB_PROJECTS:
        raise HTTPException(404, "Project not found")

    if _recompute_project_summary(pid):
        save_data(PROJECTS_FILE, DB_PROJECTS)

    return DB_PROJECTS[pid]


@router.delete("/projects/{pid}")
async def delete_project(pid: str):
    if pid not in DB_PROJECTS:
        raise HTTPException(404, "Project not found")
    del DB_PROJECTS[pid]
    save_data(PROJECTS_FILE, DB_PROJECTS)
    
    # Remove associated scans
    to_remove = [sid for sid, s in DB_SCANS.items() if s["project_id"] == pid]
    for sid in to_remove:
        del DB_SCANS[sid]
    if to_remove:
        save_data(SCANS_FILE, DB_SCANS)
        
    return {"status": "deleted"}


# ── Scan Endpoints ────────────────────────────────────────────────
@router.post("/scans/")
async def start_scan(data: ScanStart):
    if data.project_id not in DB_PROJECTS:
        raise HTTPException(404, "Project not found")

    # Cleanup stale scans and enforce one active scan per project.
    _repair_invalid_completed_scans(project_id=data.project_id)
    _expire_stale_scans(project_id=data.project_id)
    _fail_active_scans_for_project(
        project_id=data.project_id,
        reason="Superseded by a newer scan request.",
    )

    scan_id = str(uuid.uuid4())[:8]
    project = DB_PROJECTS[data.project_id]
    scan_url = project["url"]
    scan_mode = data.scan_mode or "fast"

    scan_record: dict = {
        "id": scan_id,
        "project_id": data.project_id,
        "status": "scanning",
        "url": scan_url,
        "scan_mode": scan_mode,
        "score": None,
        "total_issues": 0,
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
        "degraded_mode": False,
        "degraded_reason": None,
        "skipped_components": [],
        "degradation_reason": None,
        "enrichment_status": "pending",
        "cognitive_scores": None,
        "created_at": datetime.datetime.utcnow().isoformat(),
        "completed_at": None,
    }
    DB_SCANS[scan_id] = scan_record
    save_data(SCANS_FILE, DB_SCANS)

    async def run_bg_audit():
        try:
            result = await run_audit(url=scan_url, scan_mode=scan_mode)

            failed, failure_reason = _detect_audit_failure(result)
            if failed:
                scan_record["status"] = "failed"
                scan_record["summary"] = failure_reason
                scan_record["ai_analysis"] = f"⚠️ {failure_reason}"
                scan_record["engines_used"] = result.get("engines_used", [])
                scan_record["scan_time_seconds"] = result.get("scan_time_seconds", 0)
                scan_record["enrichment_status"] = "failed"
                scan_record["trust"] = result.get("trust", {})
                scan_record["completed_at"] = _utc_now_iso()
                save_data(SCANS_FILE, DB_SCANS)
                logger.warning(f"Scan {scan_id} failed early: {failure_reason}")
                return

            # Count severities from issues
            issues = result.get("issues", [])
            critical = sum(1 for i in issues if i.get("severity") == "critical")
            serious = sum(1 for i in issues if i.get("severity") == "serious")
            moderate = sum(1 for i in issues if i.get("severity") == "moderate")
            minor = sum(1 for i in issues if i.get("severity") == "minor")

            # Phase 1: Update basic metrics and MARK COMPLETED immediately
            scan_record["status"] = "completed"
            scan_record["score"] = result.get("score", 0)
            scan_record["total_issues"] = result.get("total_issues", 0)
            scan_record["critical_issues"] = critical
            scan_record["serious_issues"] = serious
            scan_record["moderate_issues"] = moderate
            scan_record["minor_issues"] = minor
            scan_record["summary"] = result.get("summary", "")
            scan_record["ai_analysis"] = "💡 AI Engine is generating insights..."
            scan_record["issues"] = issues
            scan_record["groups"] = result.get("groups", [])
            scan_record["priority_ranking"] = result.get("priority_ranking", [])
            scan_record["engines_used"] = result.get("engines_used", [])
            scan_record["scan_time_seconds"] = result.get("scan_time_seconds", 0)
            scan_record["trust"] = result.get("trust", {})
            scan_record["degraded_mode"] = result.get("degraded_mode", False)
            scan_record["degraded_reason"] = result.get("degraded_reason")
            scan_record["skipped_components"] = result.get("skipped_components", [])
            scan_record["degradation_reason"] = result.get("degradation_reason")
            scan_record["enrichment_status"] = result.get("enrichment_status", "complete")
            scan_record["cognitive_scores"] = result.get("cognitive_scores")
            scan_record["markdown_report"] = result.get("markdown_report", "")
            scan_record["completed_at"] = _utc_now_iso()

            # Immediate save so UI stops polling/spinning
            save_data(SCANS_FILE, DB_SCANS)

            # Update project summary
            project["latest_score"] = scan_record["score"]
            project["total_issues"] = scan_record["total_issues"]
            project["last_scan_at"] = scan_record["completed_at"]
            save_data(PROJECTS_FILE, DB_PROJECTS)

            logger.info(f"Scan {scan_id} marked COMPLETED. Phase 2 (AI) starting...")

            # Phase 2: Deferred AI Executive Summary
            try:
                from app.services.llm import get_client
                from app.config import settings
                client = get_client()
                degraded_prefix = ""
                if scan_record.get("degraded_mode"):
                    reason = (
                        scan_record.get("degradation_reason")
                        or scan_record.get("degraded_reason")
                        or "Requested engines were unavailable during this run."
                    )
                    degraded_prefix = f"⚠️ Limited-confidence scan: {reason}\n\n"
                
                # Check for empty issues (e.g. clean site)
                if not issues:
                    if scan_record.get("degraded_mode"):
                        ai_summary = (
                            degraded_prefix
                            + "No blocking issues were detected in static HTML, but browser-level checks did not run. "
                            + "Run deep scan again after browser engines recover."
                        )
                    else:
                        ai_summary = "Excellent! No accessibility issues were found. Your site follows all primary accessibility standards."
                else:
                    top_issues = [f"{i.get('rule_id')} ({i.get('severity')})" for i in issues[:3]]
                    prompt = f"Write a concise, 2-sentence executive summary of this web accessibility audit. Score: {result.get('score', 0)}/100, Issues found: {result.get('total_issues', 0)}. Top problems: {', '.join(top_issues)}."
                    
                    resp = await client.chat.completions.create(
                        model=settings.featherless_model,
                        messages=[
                            {"role": "system", "content": "You are the BEACON AI engine."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=150,
                        temperature=0.4,
                        timeout=15.0
                    )
                    ai_summary = degraded_prefix + resp.choices[0].message.content.strip()
                
                scan_record["ai_analysis"] = ai_summary
                save_data(SCANS_FILE, DB_SCANS)
                logger.debug(f"AI summary generated for scan {scan_id}")

            except Exception as e:
                logger.error(f"Failed to generate top-level AI summary for {scan_id}: {e}")
                err_str = str(e).lower()
                if "429" in err_str or "insufficient_quota" in err_str or "limit" in err_str:
                    ai_summary = f"⚠️ [AI ERROR]: API Credit Limit Reached. Please check your Featherless AI billing. Raw Error: {e}"
                elif "401" in err_str:
                    ai_summary = f"⚠️ [AI ERROR]: Authentication Failure. Your API key might be invalid. Raw Error: {e}"
                elif "timeout" in err_str:
                    ai_summary = f"🕒 [AI ERROR]: Request Timed Out. The AI service took too long to respond. Raw Error: {e}"
                else:
                    ai_summary = f"❌ [AI ERROR]: System Failure. Technical details: {e}"
                
                scan_record["ai_analysis"] = ai_summary
                save_data(SCANS_FILE, DB_SCANS)

            logger.info(f"Scan {scan_id} completed: score={scan_record['score']}, issues={scan_record['total_issues']}")

        except Exception as e:
            scan_record["status"] = "failed"
            scan_record["summary"] = f"Scan failed: {str(e)}"
            scan_record["ai_analysis"] = f"❌ Scan failed: {str(e)}"
            scan_record["enrichment_status"] = "failed"
            scan_record["trust"] = scan_record.get("trust") or {}
            scan_record["completed_at"] = _utc_now_iso()
            save_data(SCANS_FILE, DB_SCANS)
            logger.error(f"Scan {scan_id} failed: {e}", exc_info=True)

    asyncio.create_task(run_bg_audit())
    return {"scan_id": scan_id, "status": "scanning"}


@router.get("/scans/{pid}")
async def get_scans(pid: str):
    _repair_invalid_completed_scans(project_id=pid)
    _expire_stale_scans(project_id=pid)

    if _recompute_project_summary(pid):
        save_data(PROJECTS_FILE, DB_PROJECTS)

    scans = [s for s in DB_SCANS.values() if s["project_id"] == pid]
    return sorted(scans, key=lambda s: s.get("created_at", ""), reverse=True)


@router.get("/scans/{pid}/{sid}")
async def get_scan(pid: str, sid: str):
    _repair_invalid_completed_scans(project_id=pid)
    _expire_stale_scans(project_id=pid)
    if sid not in DB_SCANS:
        raise HTTPException(404, "Scan not found")
    return DB_SCANS[sid]


@router.get("/scans/{pid}/{sid}/progress")
async def get_scan_progress(pid: str, sid: str):
    _repair_invalid_completed_scans(project_id=pid)
    _expire_stale_scans(project_id=pid)
    if sid not in DB_SCANS:
        raise HTTPException(404, "Scan not found")
    scan = DB_SCANS[sid]
    return {
        "status": scan["status"],
        "score": scan.get("score"),
        "total_issues": scan.get("total_issues", 0),
    }