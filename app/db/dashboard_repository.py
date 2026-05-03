"""Repository helpers for dashboard projects and scans persistence."""

from __future__ import annotations

import os
import datetime as dt
from typing import Any, Optional

from app.audit.failure_taxonomy import normalize_failure
from app.audit.failure_taxonomy import normalize_failure


def _to_iso(value: dt.datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _from_iso(value: Any) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def _serialize_project(record: DashboardProjectRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "name": record.name,
        "url": record.url,
        "description": record.description or "",
        "created_at": _to_iso(record.created_at),
        "last_scan_at": _to_iso(record.last_scan_at),
        "latest_score": float(record.latest_score) if record.latest_score is not None else None,
        "total_issues": int(record.total_issues or 0),
    }


def _serialize_scan(record: DashboardScanRecord) -> dict[str, Any]:
    trust_payload = dict(record.trust or {})
    return {
        "id": record.id,
        "project_id": record.project_id,
        "status": record.status,
        "url": record.url,
        "scan_mode": record.scan_mode,
        "score": float(record.score) if record.score is not None else None,
        "total_issues": int(record.total_issues or 0),
        "issue_types_count": int(record.issue_types_count or 0),
        "failing_elements_count": int(record.failing_elements_count or 0),
        "critical_issues": int(record.critical_issues or 0),
        "serious_issues": int(record.serious_issues or 0),
        "moderate_issues": int(record.moderate_issues or 0),
        "minor_issues": int(record.minor_issues or 0),
        "summary": record.summary or "",
        "ai_analysis": record.ai_analysis or "",
        "issues": list(record.issues or []),
        "groups": list(record.groups or []),
        "priority_ranking": list(record.priority_ranking or []),
        "trust": trust_payload,
        "confidence_score": trust_payload.get("confidence_score"),
        "confidence_note": trust_payload.get("confidence_note", ""),
        "site_failure_profile": trust_payload.get("site_failure_profile", {}),
        "engines_used": list(record.engines_used or []),
        "scan_time_seconds": float(record.scan_time_seconds or 0.0),
        "pages_scanned": int(record.pages_scanned or 1),
        "pages_discovered": int(record.pages_discovered or 1),
        "scraped_pages": list(record.scraped_pages or []),
        "degraded_mode": bool(record.degraded_mode),
        "degraded_reason": normalize_failure(record.degraded_reason).value if record.degraded_reason else None,
        "skipped_components": list(record.skipped_components or []),
        "degradation_reason": record.degradation_reason,
        "enrichment_status": record.enrichment_status or "pending",
        "cognitive_scores": record.cognitive_scores,
        "markdown_report": record.markdown_report or "",
        # Phase 20: topology fields
        "site_topology": record.site_topology,
        "templates_found": int(record.templates_found) if record.templates_found is not None else None,
        "urls_discovered": int(record.urls_discovered) if record.urls_discovered is not None else None,
        "created_at": _to_iso(record.created_at),
        "completed_at": _to_iso(record.completed_at),
    }


def _apply_project_record(record: DashboardProjectRecord, payload: dict[str, Any]) -> None:
    record.name = str(payload.get("name") or "")
    record.url = str(payload.get("url") or "")
    record.description = str(payload.get("description") or "")
    record.created_at = _from_iso(payload.get("created_at")) or dt.datetime.utcnow()
    record.last_scan_at = _from_iso(payload.get("last_scan_at"))

    latest_score = payload.get("latest_score")
    record.latest_score = float(latest_score) if latest_score is not None else None
    record.total_issues = int(payload.get("total_issues") or 0)


def _apply_scan_record(record: DashboardScanRecord, payload: dict[str, Any]) -> None:
    record.project_id = str(payload.get("project_id") or "")
    record.status = str(payload.get("status") or "scanning")
    record.url = str(payload.get("url") or "")
    record.scan_mode = str(payload.get("scan_mode") or "fast")

    score = payload.get("score")
    record.score = float(score) if score is not None else None

    record.total_issues = int(payload.get("total_issues") or 0)
    record.issue_types_count = int(payload.get("issue_types_count") or 0)
    record.failing_elements_count = int(payload.get("failing_elements_count") or record.total_issues)
    record.critical_issues = int(payload.get("critical_issues") or 0)
    record.serious_issues = int(payload.get("serious_issues") or 0)
    record.moderate_issues = int(payload.get("moderate_issues") or 0)
    record.minor_issues = int(payload.get("minor_issues") or 0)
    record.summary = str(payload.get("summary") or "")
    record.ai_analysis = str(payload.get("ai_analysis") or "")
    record.issues = list(payload.get("issues") or [])
    record.groups = list(payload.get("groups") or [])
    record.priority_ranking = list(payload.get("priority_ranking") or [])
    trust_payload = dict(payload.get("trust") or {})
    if "confidence_score" in payload:
        trust_payload["confidence_score"] = payload.get("confidence_score")
    if "confidence_note" in payload:
        trust_payload["confidence_note"] = payload.get("confidence_note")
    if "site_failure_profile" in payload:
        trust_payload["site_failure_profile"] = payload.get("site_failure_profile") or {}
    record.trust = trust_payload
    record.engines_used = list(payload.get("engines_used") or [])
    record.scan_time_seconds = float(payload.get("scan_time_seconds") or 0.0)
    record.pages_scanned = int(payload.get("pages_scanned") or 1)
    record.pages_discovered = int(payload.get("pages_discovered") or record.pages_scanned)
    record.scraped_pages = list(payload.get("scraped_pages") or [])
    record.degraded_mode = bool(payload.get("degraded_mode", False))
    record.degraded_reason = normalize_failure(payload.get("degraded_reason")).value if payload.get("degraded_reason") else None
    record.skipped_components = list(payload.get("skipped_components") or [])
    record.degradation_reason = payload.get("degradation_reason")
    record.enrichment_status = str(payload.get("enrichment_status") or "pending")
    record.cognitive_scores = payload.get("cognitive_scores")
    record.markdown_report = str(payload.get("markdown_report") or "")
    # Phase 20: topology fields
    _topo = payload.get("site_topology")
    record.site_topology = str(_topo) if _topo is not None else None
    _tf = payload.get("templates_found")
    record.templates_found = int(_tf) if _tf is not None else None
    _ud = payload.get("urls_discovered")
    record.urls_discovered = int(_ud) if _ud is not None else None
    record.created_at = _from_iso(payload.get("created_at")) or dt.datetime.utcnow()
    record.completed_at = _from_iso(payload.get("completed_at"))


from app.db.supabase_client import get_supabase

def list_projects() -> list[dict[str, Any]]:
    sb = get_supabase()
    res = sb.table("projects").select("*").order("created_at", desc=True).execute()
    return res.data if res.data else []


def get_project(project_id: str) -> dict[str, Any] | None:
    sb = get_supabase()
    res = sb.table("projects").select("*").eq("id", project_id).maybe_single().execute()
    return res.data if res.data else None


def upsert_project(project: dict[str, Any], user_id: Optional[str] = None) -> dict[str, Any]:
    project_id = str(project.get("id") or "").strip()
    if not project_id:
        raise ValueError("project id is required")
    
    if user_id:
        project["user_id"] = user_id
    elif not project.get("user_id"):
        if os.environ.get("ENVIRONMENT") == "production":
            raise ValueError("user_id is required in production")

    sb = get_supabase()
    res = sb.table("projects").upsert(project).execute()
    return res.data[0] if res.data else {}


def delete_project(project_id: str) -> bool:
    sb = get_supabase()
    res = sb.table("projects").delete().eq("id", project_id).execute()
    return len(res.data) > 0 if res.data else True


def list_scans(project_id: str | None = None) -> list[dict[str, Any]]:
    sb = get_supabase()
    query = sb.table("scans").select("*")
    if project_id:
        query = query.eq("project_id", project_id)
    
    res = query.order("created_at", desc=True).execute()
    return res.data if res.data else []


def get_scan(scan_id: str) -> dict[str, Any] | None:
    sb = get_supabase()
    res = sb.table("scans").select("*").eq("id", scan_id).maybe_single().execute()
    return res.data if res.data else None


def upsert_scan(scan: dict[str, Any], user_id: Optional[str] = None) -> dict[str, Any]:
    scan_id = str(scan.get("id") or "").strip()
    if not scan_id:
        raise ValueError("scan id is required")
    
    if user_id:
        scan["user_id"] = user_id
    elif not scan.get("user_id"):
        if os.environ.get("ENVIRONMENT") == "production":
            raise ValueError("user_id is required in production")

    sb = get_supabase()
    # Handle nested objects/lists by ensuring they are serializable (Supabase SDK does this)
    res = sb.table("scans").upsert(scan).execute()
    return res.data[0] if res.data else {}


def delete_scans_for_project(project_id: str) -> int:
    sb = get_supabase()
    res = sb.table("scans").delete().eq("project_id", project_id).execute()
    return len(res.data) if res.data else 0
