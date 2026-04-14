"""Database table models for BEACON audit persistence."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditRecord(Base):
    __tablename__ = "audits"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    scan_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    site_score: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    pages_audited: Mapped[int] = mapped_column(Integer, default=1)
    pages_discovered: Mapped[int] = mapped_column(Integer, default=1)
    total_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    degraded_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    enrichment_status: Mapped[str] = mapped_column(String(32), default="pending")
    schema_version: Mapped[str] = mapped_column(String(16), default="3.1")
    summary: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    pages: Mapped[list[PageRecord]] = relationship("PageRecord", back_populates="audit", cascade="all, delete-orphan")
    issues: Mapped[list[IssueRecord]] = relationship("IssueRecord", back_populates="audit", cascade="all, delete-orphan")
    enrichments: Mapped[list[EnrichmentRecord]] = relationship("EnrichmentRecord", back_populates="audit", cascade="all, delete-orphan")


class PageRecord(Base):
    __tablename__ = "pages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(String(64), ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    degraded_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    engine_timings: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    audit: Mapped[AuditRecord] = relationship("AuditRecord", back_populates="pages")
    issues: Mapped[list[IssueRecord]] = relationship("IssueRecord", back_populates="page", cascade="all, delete-orphan")


class IssueRecord(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    page_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("pages.id", ondelete="CASCADE"), nullable=True)
    audit_id: Mapped[str] = mapped_column(String(64), ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(128), default="")
    wcag_criterion: Mapped[str] = mapped_column(String(64), default="")
    severity: Mapped[str] = mapped_column(String(32), default="moderate")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    affected_pages: Mapped[int] = mapped_column(Integer, default=1)
    enrichment_source: Mapped[str] = mapped_column(String(64), default="pending")
    fix: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    audit: Mapped[AuditRecord] = relationship("AuditRecord", back_populates="issues")
    page: Mapped[PageRecord | None] = relationship("PageRecord", back_populates="issues")


class EnrichmentRecord(Base):
    __tablename__ = "enrichments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("issues.id", ondelete="SET NULL"), nullable=True)
    audit_id: Mapped[str] = mapped_column(String(64), ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="unknown")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    audit: Mapped[AuditRecord] = relationship("AuditRecord", back_populates="enrichments")


class CacheMetaRecord(Base):
    __tablename__ = "cache_meta"

    tier: Mapped[str] = mapped_column(String(32), primary_key=True)
    hits: Mapped[int] = mapped_column(Integer, default=0)
    misses: Mapped[int] = mapped_column(Integer, default=0)
    writes: Mapped[int] = mapped_column(Integer, default=0)
    last_reset: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class DashboardProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, index=True)
    last_scan_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    latest_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_issues: Mapped[int] = mapped_column(Integer, default=0)

    scans: Mapped[list[DashboardScanRecord]] = relationship(
        "DashboardScanRecord",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class DashboardScanRecord(Base):
    __tablename__ = "scans"
    __table_args__ = (
        Index("ix_scans_project_scan", "project_id", "id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="scanning", index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    scan_mode: Mapped[str] = mapped_column(String(32), default="fast")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_issues: Mapped[int] = mapped_column(Integer, default=0)
    issue_types_count: Mapped[int] = mapped_column(Integer, default=0)
    failing_elements_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_issues: Mapped[int] = mapped_column(Integer, default=0)
    serious_issues: Mapped[int] = mapped_column(Integer, default=0)
    moderate_issues: Mapped[int] = mapped_column(Integer, default=0)
    minor_issues: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    ai_analysis: Mapped[str] = mapped_column(Text, default="")
    issues: Mapped[list] = mapped_column(JSON, default=list)
    groups: Mapped[list] = mapped_column(JSON, default=list)
    priority_ranking: Mapped[list] = mapped_column(JSON, default=list)
    trust: Mapped[dict] = mapped_column(JSON, default=dict)
    engines_used: Mapped[list] = mapped_column(JSON, default=list)
    scan_time_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    pages_scanned: Mapped[int] = mapped_column(Integer, default=1)
    pages_discovered: Mapped[int] = mapped_column(Integer, default=1)
    degraded_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    degraded_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    skipped_components: Mapped[list] = mapped_column(JSON, default=list)
    degradation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    enrichment_status: Mapped[str] = mapped_column(String(32), default="pending")
    cognitive_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    markdown_report: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow, index=True)
    completed_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    project: Mapped[DashboardProjectRecord] = relationship("DashboardProjectRecord", back_populates="scans")
