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
    # Sort projects by most recently created
    projs = list(DB_PROJECTS.values())
    return sorted(projs, key=lambda p: p.get("created_at", ""), reverse=True)


@router.get("/projects/{pid}")
async def get_project(pid: str):
    if pid not in DB_PROJECTS:
        raise HTTPException(404, "Project not found")
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
        "engines_used": [],
        "scan_time_seconds": 0,
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
            scan_record["enrichment_status"] = result.get("enrichment_status", "complete")
            scan_record["cognitive_scores"] = result.get("cognitive_scores")
            scan_record["markdown_report"] = result.get("markdown_report", "")
            scan_record["completed_at"] = datetime.datetime.utcnow().isoformat()

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
                
                # Check for empty issues (e.g. clean site)
                if not issues:
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
                    ai_summary = resp.choices[0].message.content.strip()
                
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
            scan_record["completed_at"] = datetime.datetime.utcnow().isoformat()
            save_data(SCANS_FILE, DB_SCANS)
            logger.error(f"Scan {scan_id} failed: {e}", exc_info=True)

    asyncio.create_task(run_bg_audit())
    return {"scan_id": scan_id, "status": "scanning"}


@router.get("/scans/{pid}")
async def get_scans(pid: str):
    scans = [s for s in DB_SCANS.values() if s["project_id"] == pid]
    return sorted(scans, key=lambda s: s.get("created_at", ""), reverse=True)


@router.get("/scans/{pid}/{sid}")
async def get_scan(pid: str, sid: str):
    if sid not in DB_SCANS:
        raise HTTPException(404, "Scan not found")
    return DB_SCANS[sid]


@router.get("/scans/{pid}/{sid}/progress")
async def get_scan_progress(pid: str, sid: str):
    if sid not in DB_SCANS:
        raise HTTPException(404, "Scan not found")
    scan = DB_SCANS[sid]
    return {
        "status": scan["status"],
        "score": scan.get("score"),
        "total_issues": scan.get("total_issues", 0),
    }