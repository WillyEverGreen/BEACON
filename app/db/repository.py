from __future__ import annotations

import logging
import os
import uuid
from typing import Any

logger = logging.getLogger(__name__)

from app.config import settings


def _audit_id(payload: dict[str, Any]) -> str:
    value = str(payload.get("audit_id") or "").strip()
    return value or uuid.uuid4().hex



from app.db.supabase_client import get_supabase


def persist_audit_payload(payload: dict[str, Any], *, status: str = "completed", user_id: str | None = None) -> str:
    """Persist an audit payload directly to Supabase using the SDK."""
    if user_id is None:
        if os.environ.get("ENVIRONMENT") == "production":
            raise ValueError("user_id is required in production")
        logger.warning("persist_audit_payload called without user_id — row will be hidden by RLS")

    aid = _audit_id(payload)
    issues = list(payload.get("issues") or [])
    sb = get_supabase()

    # 1. Persist Audit Master Record
    audit_data = {
        "id": aid,
        "url": str(payload.get("url") or ""),
        "scan_mode": str(payload.get("scan_mode") or settings.default_scan_mode),
        "site_score": float(payload.get("score") or 0.0),
        "status": status,
        "pages_audited": int(payload.get("pages_audited") or 1),
        "pages_discovered": int(payload.get("pages_discovered") or int(payload.get("pages_audited") or 1)),
        "total_duration_ms": int(float(payload.get("scan_time_seconds") or 0.0) * 1000),
        "degraded_mode": bool(payload.get("degraded_mode", False)),
        "enrichment_status": str(payload.get("enrichment_status") or "pending"),
        "schema_version": str(getattr(settings, "schema_version", "3.1")),
        "summary": str(payload.get("summary") or ""),
        "earl_report": dict(payload.get("earl_report") or {}),
        "user_id": user_id,
    }
    sb.table("audits").upsert(audit_data).execute()

    # 2. Cleanup old associated data (Idempotency)
    sb.table("issues").delete().eq("audit_id", aid).execute()
    sb.table("pages").delete().eq("audit_id", aid).execute()
    sb.table("enrichments").delete().eq("audit_id", aid).execute()

    # 3. Persist Page Record
    page_data = {
        "audit_id": aid,
        "url": str(payload.get("url") or ""),
        "score": float(payload.get("score") or 0.0),
        "degraded_mode": bool(payload.get("degraded_mode", False)),
        "engine_timings": dict(payload.get("quality_gates") or {}),
        "user_id": user_id,
    }
    page_res = sb.table("pages").insert(page_data).execute()
    page_id = page_res.data[0]["id"] if page_res.data else None

    # 4. Persist Issues in bulk if possible, but keep it simple for now
    for issue in issues:
        issue_data = {
            "page_id": page_id,
            "audit_id": aid,
            "rule_id": str(issue.get("rule_id") or ""),
            "wcag_criterion": str(issue.get("wcag_criterion") or ""),
            "severity": str(issue.get("severity") or "moderate"),
            "confidence": float(issue.get("confidence") or 0.0),
            "affected_pages": int(issue.get("affected_pages") or 1),
            "enrichment_source": str(issue.get("_enrichment_source") or issue.get("enrichment_source") or "pending"),
            "fix": dict(issue.get("fix") or {}),
            "user_id": user_id,
        }
        issue_res = sb.table("issues").insert(issue_data).execute()
        issue_row_id = issue_res.data[0]["id"] if issue_res.data else None

        # 5. Persist Enrichment Metadata
        enrich_data = {
            "issue_id": issue_row_id,
            "audit_id": aid,
            "source": issue_data["enrichment_source"],
            "latency_ms": int(issue.get("enrichment_latency_ms") or 0),
            "user_id": user_id,
        }
        sb.table("enrichments").insert(enrich_data).execute()

    return aid


def persist_enrichment_payload(
    audit_id: str,
    enrichment_issues: list[dict[str, Any]],
    enrichment_meta: dict[str, Any] | None = None,
    *,
    status: str = "complete",
    user_id: str | None = None,
) -> None:
    """Update persisted enrichment details after background enrichment completes."""
    if not audit_id:
        return

    sb = get_supabase()
    
    # 1. Update audit status
    sb.table("audits").update({"enrichment_status": status}).eq("id", audit_id).execute()

    # 2. Cleanup old associated data (Idempotency)
    sb.table("issues").delete().eq("audit_id", audit_id).execute()
    sb.table("enrichments").delete().eq("audit_id", audit_id).execute()

    # 3. Get the first page for this audit to associate issues
    page_res = sb.table("pages").select("id").eq("audit_id", audit_id).order("id").limit(1).execute()
    page_id = page_res.data[0]["id"] if page_res.data else None

    latency_ms = 0
    if isinstance(enrichment_meta, dict):
        llm_meta = enrichment_meta.get("llm", {})
        calls = int(llm_meta.get("calls", 0) or 0)
        retries = int(llm_meta.get("retries", 0) or 0)
        latency_ms = max(0, (calls + retries) * 100)

    for issue in enrichment_issues:
        issue_data = {
            "page_id": page_id,
            "audit_id": audit_id,
            "rule_id": str(issue.get("rule_id") or ""),
            "wcag_criterion": str(issue.get("wcag_criterion") or ""),
            "severity": str(issue.get("severity") or "moderate"),
            "confidence": float(issue.get("confidence") or 0.0),
            "affected_pages": int(issue.get("affected_pages") or 1),
            "enrichment_source": str(issue.get("_enrichment_source") or issue.get("enrichment_source") or "pending"),
            "fix": dict(issue.get("fix") or {}),
            "user_id": user_id,
        }
        issue_res = sb.table("issues").insert(issue_data).execute()
        issue_row_id = issue_res.data[0]["id"] if issue_res.data else None

        enrich_data = {
            "issue_id": issue_row_id,
            "audit_id": audit_id,
            "source": issue_data["enrichment_source"],
            "latency_ms": latency_ms,
            "user_id": user_id,
        }
        sb.table("enrichments").insert(enrich_data).execute()


def get_audit_history(url: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return latest persisted audits for a URL from Supabase."""
    limit = max(1, min(int(limit), 100))
    sb = get_supabase()
    
    res = sb.table("audits").select("*").eq("url", url).order("created_at", desc=True).limit(limit).execute()
    rows = res.data if res.data else []

    history = []
    for row in rows:
        # Count critical issues for this audit
        issue_res = sb.table("issues").select("id", count="exact").eq("audit_id", row["id"]).eq("severity", "critical").execute()
        critical_count = issue_res.count if issue_res.count is not None else 0
        
        history.append(
            {
                "timestamp": row.get("created_at", ""),
                "score": float(row.get("site_score") or 0.0),
                "scan_mode": row.get("scan_mode"),
                "pages_audited": int(row.get("pages_audited") or 0),
                "critical_issues": int(critical_count),
            }
        )
    return history


def persist_lighthouse_enrichment(scan_id: str, enrichment_block: dict[str, Any]) -> None:
    """Atomic write of the lighthouse_enrichment field using Supabase SDK."""
    if not scan_id or not isinstance(enrichment_block, dict):
        return

    try:
        sb = get_supabase()
        sb.table("scans").update({"lighthouse_enrichment": enrichment_block}).eq("id", str(scan_id)).execute()
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "persist_lighthouse_enrichment failed for scan_id=%s", scan_id
        )

def get_user_usage_limits(user_id: str) -> dict[str, Any]:
    """Fetch plan-based limits for a user. Defaults to 'free' if not found."""
    if not user_id:
        from app.config import PLAN_TIERS
        return PLAN_TIERS["free"]

    try:
        sb = get_supabase()
        res = sb.table("usage_limits").select("*").eq("user_id", user_id).maybe_single().execute()
        if res.data:
            return {
                "plan": res.data.get("plan", "free"),
                "max_pages": res.data.get("pages_per_audit", 10),
                "ai_budget": res.data.get("ai_budget_per_audit", 5),
            }
    except Exception:
        pass
    
    from app.config import PLAN_TIERS
    return PLAN_TIERS["free"]

