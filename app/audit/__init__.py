"""Audit orchestration package for page and site pipelines.

This module intentionally uses lazy imports to avoid package-level import
cycles during application bootstrap.
"""

__all__ = [
    "PageAuditResult",
    "PageContext",
    "SiteAuditResult",
    "aggregate_site_results",
    "audit_page",
    "detect_page_type",
    "run_scan_mode_audit",
    "run_site_audit",
]


def __getattr__(name: str):
    if name in {"PageAuditResult", "PageContext", "SiteAuditResult"}:
        from app.audit.models import PageAuditResult, PageContext, SiteAuditResult

        return {
            "PageAuditResult": PageAuditResult,
            "PageContext": PageContext,
            "SiteAuditResult": SiteAuditResult,
        }[name]

    if name == "audit_page":
        from app.audit.page_auditor import audit_page

        return audit_page

    if name == "run_site_audit":
        from app.audit.parallel_runner import run_site_audit

        return run_site_audit

    if name == "run_scan_mode_audit":
        from app.audit.scan_mode_runner import run_scan_mode_audit

        return run_scan_mode_audit

    if name in {"aggregate_site_results", "detect_page_type"}:
        from app.audit.site_aggregator import aggregate_site_results, detect_page_type

        return {
            "aggregate_site_results": aggregate_site_results,
            "detect_page_type": detect_page_type,
        }[name]

    raise AttributeError(f"module 'app.audit' has no attribute '{name}'")
