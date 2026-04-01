"""
BEACON Engine Adapter — provides the interface expected by the
Localbros3000 full-stack app's scan_service.py.

Wraps the DJ HACK audit pipeline to expose:
  - scan_page_full(page) → (issues_list, checklist_dict)
  - analyze_page_rag(url, html, layer1_rule_ids) → [RagFinding-compatible]
  - get_rag_status() → {chunks, ready}

This adapter is the primary integration point between the engine and the app.
"""
import logging
from typing import Any, Optional

from app.schema_compat import (
    audit_issue_to_accessibility_issue,
    audit_issue_to_rag_finding,
    checklist_to_app_format,
    get_disability_groups,
)

logger = logging.getLogger(__name__)

# ── Category Mapping (for checklist grouping) ─────────────────

CHECKLIST_CATEGORIES = {
    "HTML & Structure": {
        "html-lang", "page-title", "semantic-landmarks", "meta-viewport",
        "heading-structure", "single-h1", "heading-order", "empty-heading",
        "descriptive-headings", "list-markup", "skip-navigation", "multiple-nav-methods",
    },
    "Keyboard Navigation": {
        "keyboard-accessible", "no-positive-tabindex", "no-keyboard-trap",
        "modal-focus-trap", "focus-visible",
    },
    "Appearance & Animation": {
        "no-color-only", "no-rapid-flash", "responsive-reflow",
        "prefers-reduced-motion", "prefers-color-scheme",
    },
    "Forms": {
        "input-label", "fieldset-legend", "error-association",
        "error-text", "autocomplete-attrs", "form-focus-visible",
    },
    "Links & Buttons": {
        "link-name", "link-purpose", "new-window-label", "button-name",
        "correct-element", "target-size-24", "target-size-44",
    },
    "Content & Language": {
        "no-sensory-only", "unique-labels", "semantic-tables",
        "th-scope", "table-caption", "lang-changes", "abbr-expand",
    },
    "Color Contrast": {
        "contrast-normal", "contrast-large", "contrast-ui", "contrast-enhanced",
    },
    "Images & Media": {
        "image-alt", "decorative-alt", "complex-image-desc", "no-autoplay",
        "media-pausable", "video-captions", "audio-transcript",
        "svg-accessible", "no-images-of-text",
    },
    "ARIA & Widgets": {
        "aria-valid", "aria-required-attr", "aria-allowed-attr",
        "aria-hidden-body", "aria-roles", "aria-live-region",
    },
}


class BeaconEngineAdapter:
    """
    Adapter that exposes the DJ HACK engine through the interface
    expected by the Localbros3000 full-stack application.
    
    Usage:
        adapter = BeaconEngineAdapter()
        issues, checklist = await adapter.scan_page_full(crawled_page)
        rag_findings = await adapter.analyze_page_rag(url, html, layer1_ids)
    """

    def __init__(self):
        self._static_scanner = None
        self._audit_runner = None

    def _get_static_scanner(self):
        """Lazy-load the static checks scanner."""
        if self._static_scanner is None:
            from app.services.static_checks import run_static_checks
            self._static_scanner = run_static_checks
        return self._static_scanner

    async def scan_page_full(
        self,
        page: Any,
        include_rag: bool = False,
    ) -> tuple[list[dict], dict]:
        """
        Full page scan compatible with DJ FR's AccessibilityScanner.scan_page_full().
        
        Args:
            page: CrawledPage-like object with .html and .url attributes
            include_rag: If True, also run RAG Layer 2 analysis
        
        Returns:
            (issues_list, checklist_summary_dict) in AccessibilityIssue format
        """
        html = getattr(page, "html", "") if not isinstance(page, str) else page
        url = getattr(page, "url", "unknown") if not isinstance(page, str) else "unknown"

        try:
            # Run static checks (our engine's Layer 1)
            scanner = self._get_static_scanner()
            raw_issues, check_results = scanner(html, url)

            # Convert to AccessibilityIssue format
            mapped_issues = [
                audit_issue_to_accessibility_issue(issue)
                for issue in raw_issues
            ]

            # Build checklist summary
            checklist = checklist_to_app_format(
                check_results, CHECKLIST_CATEGORIES
            )

            logger.info(
                f"Scan complete: {len(mapped_issues)} issues, "
                f"score={checklist.get('score', 0)}/100 on {url}"
            )

            return mapped_issues, checklist

        except Exception as e:
            logger.error(f"scan_page_full failed for {url}: {e}")
            return [], {"categories": {}, "total_passed": 0, "total_failed": 0, "score": 0}

    async def analyze_page_rag(
        self,
        page_url: str,
        html_content: str,
        layer1_rule_ids: set[str],
    ) -> list[dict]:
        """
        RAG-powered semantic analysis compatible with DJ FR's
        Layer2Scanner.analyze_page().
        
        Returns list of RagFinding-compatible dicts.
        """
        try:
            from app.services.audit_runner import run_audit
            
            result = await run_audit(
                url=page_url,
                html=html_content,
                mode="fast",
            )

            # Filter out issues already found by Layer 1
            rag_issues = [
                audit_issue_to_rag_finding(issue)
                for issue in result.get("issues", [])
                if issue.get("source") == "rag"
                and issue.get("rule_id") not in layer1_rule_ids
            ]

            logger.info(f"RAG Layer 2: {len(rag_issues)} new findings on {page_url}")
            return rag_issues

        except Exception as e:
            logger.error(f"analyze_page_rag failed for {page_url}: {e}")
            return []

    def get_rag_status(self) -> dict:
        """
        RAG health check compatible with DJ FR's /api/wcag/rag/status endpoint.
        """
        try:
            from app.services.vector_store import get_chunks_count
            count = get_chunks_count()
            return {
                "chunks": count,
                "ready": count > 0,
                "engine": "beacon-v2",
            }
        except Exception as e:
            logger.error(f"RAG status check failed: {e}")
            return {"chunks": 0, "ready": False, "engine": "beacon-v2"}
