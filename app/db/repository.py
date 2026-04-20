"""Persistence helpers for audit payloads and telemetry metadata."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import CACHE_STATS, settings
from app.db.base import get_session
from app.db.models import (
    AuditRecord,
    CacheMetaRecord,
    EnrichmentRecord,
    IssueRecord,
    PageRecord,
)


def _audit_id(payload: dict[str, Any]) -> str:
    value = str(payload.get("audit_id") or "").strip()
    return value or uuid.uuid4().hex


def _upsert_cache_meta(session: Session) -> None:
    tiers = ("page", "dom", "llm", "fix")
    for tier in tiers:
        record = session.get(CacheMetaRecord, tier)
        if record is None:
            record = CacheMetaRecord(tier=tier)
            session.add(record)

        record.hits = int(CACHE_STATS.get(f"{tier}_hits", 0) or 0)
        record.misses = int(CACHE_STATS.get(f"{tier}_misses", 0) or 0)
        record.writes = int(CACHE_STATS.get(f"{tier}_writes", 0) or 0)


def persist_audit_payload(payload: dict[str, Any], *, status: str = "completed") -> str:
    """Persist an audit payload to SQLite using SQLAlchemy models."""
    aid = _audit_id(payload)
    issues = list(payload.get("issues") or [])

    with get_session() as session:
        audit = session.get(AuditRecord, aid)
        if audit is None:
            audit = AuditRecord(id=aid)
            session.add(audit)

        audit.url = str(payload.get("url") or "")
        audit.scan_mode = str(payload.get("scan_mode") or settings.default_scan_mode)
        audit.site_score = float(payload.get("score") or 0.0)
        audit.status = status
        audit.pages_audited = int(payload.get("pages_audited") or 1)
        audit.pages_discovered = int(payload.get("pages_discovered") or audit.pages_audited)
        audit.total_duration_ms = int(float(payload.get("scan_time_seconds") or 0.0) * 1000)
        audit.degraded_mode = bool(payload.get("degraded_mode", False))
        audit.enrichment_status = str(payload.get("enrichment_status") or "pending")
        audit.schema_version = str(getattr(settings, "schema_version", "3.1"))
        audit.summary = str(payload.get("summary") or "")

        # Keep this write idempotent for repeated updates of the same audit id.
        session.query(IssueRecord).filter(IssueRecord.audit_id == aid).delete(synchronize_session=False)
        session.query(PageRecord).filter(PageRecord.audit_id == aid).delete(synchronize_session=False)
        session.query(EnrichmentRecord).filter(EnrichmentRecord.audit_id == aid).delete(synchronize_session=False)

        page = PageRecord(
            audit_id=aid,
            url=str(payload.get("url") or ""),
            score=float(payload.get("score") or 0.0),
            degraded_mode=bool(payload.get("degraded_mode", False)),
            engine_timings=dict(payload.get("quality_gates") or {}),
        )
        session.add(page)
        session.flush()

        for issue in issues:
            issue_row = IssueRecord(
                page_id=page.id,
                audit_id=aid,
                rule_id=str(issue.get("rule_id") or ""),
                wcag_criterion=str(issue.get("wcag_criterion") or ""),
                severity=str(issue.get("severity") or "moderate"),
                confidence=float(issue.get("confidence") or 0.0),
                affected_pages=int(issue.get("affected_pages") or 1),
                enrichment_source=str(issue.get("_enrichment_source") or issue.get("enrichment_source") or "pending"),
                fix=dict(issue.get("fix") or {}),
            )
            session.add(issue_row)
            session.flush()

            session.add(
                EnrichmentRecord(
                    issue_id=issue_row.id,
                    audit_id=aid,
                    source=issue_row.enrichment_source,
                    latency_ms=int(issue.get("enrichment_latency_ms") or 0),
                )
            )

        _upsert_cache_meta(session)

    return aid


def persist_enrichment_payload(
    audit_id: str,
    enrichment_issues: list[dict[str, Any]],
    enrichment_meta: Optional[dict[str, Any]] = None,
    *,
    status: str = "complete",
) -> None:
    """Update persisted enrichment details after background enrichment completes."""
    if not audit_id:
        return

    with get_session() as session:
        audit = session.get(AuditRecord, audit_id)
        if audit is None:
            return

        audit.enrichment_status = str(status)

        # Refresh issue-level enrichment source/fix data.
        session.query(IssueRecord).filter(IssueRecord.audit_id == audit_id).delete(synchronize_session=False)
        session.query(EnrichmentRecord).filter(EnrichmentRecord.audit_id == audit_id).delete(synchronize_session=False)

        page = (
            session.query(PageRecord)
            .filter(PageRecord.audit_id == audit_id)
            .order_by(PageRecord.id.asc())
            .first()
        )

        page_id = page.id if page else None

        latency_ms = 0
        if isinstance(enrichment_meta, dict):
            llm_meta = enrichment_meta.get("llm", {})
            calls = int(llm_meta.get("calls", 0) or 0)
            retries = int(llm_meta.get("retries", 0) or 0)
            latency_ms = max(0, (calls + retries) * 100)

        for issue in enrichment_issues:
            issue_row = IssueRecord(
                page_id=page_id,
                audit_id=audit_id,
                rule_id=str(issue.get("rule_id") or ""),
                wcag_criterion=str(issue.get("wcag_criterion") or ""),
                severity=str(issue.get("severity") or "moderate"),
                confidence=float(issue.get("confidence") or 0.0),
                affected_pages=int(issue.get("affected_pages") or 1),
                enrichment_source=str(issue.get("_enrichment_source") or issue.get("enrichment_source") or "pending"),
                fix=dict(issue.get("fix") or {}),
            )
            session.add(issue_row)
            session.flush()

            session.add(
                EnrichmentRecord(
                    issue_id=issue_row.id,
                    audit_id=audit_id,
                    source=issue_row.enrichment_source,
                    latency_ms=latency_ms,
                )
            )

        _upsert_cache_meta(session)


def get_audit_history(url: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return latest persisted audits for a URL."""
    limit = max(1, min(int(limit), 100))
    with get_session() as session:
        rows = (
            session.query(AuditRecord)
            .filter(AuditRecord.url == url)
            .order_by(AuditRecord.created_at.desc())
            .limit(limit)
            .all()
        )

        history = []
        for row in rows:
            issues = (
                session.query(IssueRecord)
                .filter(IssueRecord.audit_id == row.id, IssueRecord.severity == "critical")
                .count()
            )
            history.append(
                {
                    "timestamp": row.created_at.isoformat() if row.created_at else "",
                    "score": float(row.site_score or 0.0),
                    "scan_mode": row.scan_mode,
                    "pages_audited": int(row.pages_audited or 0),
                    "critical_issues": int(issues or 0),
                }
            )
        return history


def persist_lighthouse_enrichment(scan_id: str, enrichment_block: dict[str, Any]) -> None:
    """Atomic write of the lighthouse_enrichment field on an existing DashboardScanRecord.

    Called once, after the full Lighthouse batch completes (or fails). Never called
    mid-run or interleaved with BEACON's core findings write.

    Args:
        scan_id: The scan record primary key (DashboardScanRecord.id).
        enrichment_block: The complete lighthouse_enrichment dict, including status,
            scores, findings, failure_reason, and batch telemetry metrics.
    """
    if not scan_id or not isinstance(enrichment_block, dict):
        return

    try:
        from app.db.models import DashboardScanRecord
        with get_session() as session:
            scan = session.get(DashboardScanRecord, str(scan_id))
            if scan is None:
                return
            scan.lighthouse_enrichment = enrichment_block
    except Exception:
        # Never let enrichment persistence failure surface to callers.
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "persist_lighthouse_enrichment failed for scan_id=%s", scan_id
        )

