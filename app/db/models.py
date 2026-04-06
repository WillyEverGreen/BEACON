"""Database table models for BEACON audit persistence."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
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
