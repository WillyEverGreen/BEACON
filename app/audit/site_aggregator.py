"""Site-level aggregation for multi-page audit results."""

from __future__ import annotations

from collections import defaultdict
import logging
from typing import Any, Iterable

from app.audit.fingerprint import stable_selector_fingerprint
from app.audit.models import PageAuditResult, SiteAuditResult


logger = logging.getLogger(__name__)


def detect_page_type(url: str, dom: str) -> str:
    """Classify page type using URL and rendered DOM hints."""
    lower_url = (url or "").lower()
    lower_dom = (dom or "").lower()

    trimmed = lower_url.rstrip("/")
    if trimmed.endswith(":") or trimmed.count("/") <= 2:
        return "homepage"

    if any(k in lower_url for k in ("/login", "/signin", "/auth", "/register", "/signup")):
        return "auth"

    if "<form" in lower_dom and "<input" in lower_dom:
        return "form"

    if "add to cart" in lower_dom or "add-to-cart" in lower_dom:
        return "product"

    if "pagination" in lower_dom or "filter" in lower_dom or "sort by" in lower_dom:
        return "listing"

    if "<article" in lower_dom or "blog" in lower_url:
        return "article"

    return "unknown"


def _severity_impact(severity: str) -> float:
    mapping = {
        "critical": 1.0,
        "serious": 0.75,
        "moderate": 0.45,
        "minor": 0.25,
    }
    return mapping.get((severity or "").lower(), 0.35)


def _issue_key(issue: dict[str, Any]) -> tuple[str, str, str]:
    selector = (
        issue.get("element_selector_fingerprint")
        or issue.get("selector")
        or issue.get("element")
        or ""
    )
    stable_selector = stable_selector_fingerprint(str(selector))
    return (
        str(issue.get("rule_id", "")),
        str(issue.get("wcag_criterion", "")),
        stable_selector,
    )


def _page_weight(page_type: str) -> float:
    return 2.0 if page_type in {"auth", "form", "product"} else 1.0


def _as_page_result(item: PageAuditResult | dict[str, Any]) -> PageAuditResult:
    if isinstance(item, PageAuditResult):
        return item

    return PageAuditResult(
        url=str(item.get("url", "")),
        score=float(item.get("score", 0.0)),
        issues=list(item.get("issues", [])),
        engine_timings=dict(item.get("engine_timings", {})),
        degraded_mode=bool(item.get("degraded_mode", False)),
        degraded_reason=str(item.get("degraded_reason", "") or ""),
        skipped_engines=list(item.get("skipped_engines", [])),
        hydration_status=str(item.get("hydration_status", "unknown")),
        enrichment_status=str(item.get("enrichment_status", "pending")),
        states_meta=list(item.get("states_meta", [])),
        page_dom=str(item.get("page_dom", "")),
    )


def _build_priority_ranking(
    deduped_issues: Iterable[dict[str, Any]],
    total_pages: int,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for issue in deduped_issues:
        frequency = float(issue.get("frequency", 0.0))
        confidence = float(issue.get("confidence", 0.5))
        visibility = 1.0 if issue.get("severity", "").lower() in {"critical", "serious"} else 0.7
        impact = _severity_impact(str(issue.get("severity", "moderate")))

        priority_score = impact * frequency * visibility * confidence
        affected_pages = int(issue.get("affected_pages", 0))

        ranked.append(
            {
                "rule_id": issue.get("rule_id", ""),
                "wcag_criterion": issue.get("wcag_criterion", ""),
                "priority_score": round(priority_score, 4),
                "affected_pages": affected_pages,
                "fix_once_fixes_all": affected_pages == total_pages and total_pages > 0,
                "estimated_score_gain": round(priority_score * max(1, affected_pages) * 10.0, 2),
            }
        )

    ranked.sort(key=lambda item: (-item["priority_score"], -item["affected_pages"], item["rule_id"]))
    return ranked[:5]


def aggregate_site_results(page_results: list[PageAuditResult | dict[str, Any]], scan_mode: str) -> SiteAuditResult:
    """Aggregate page-level results into a site-level result with cross-page deduplication."""
    pages = [_as_page_result(item) for item in page_results]
    if not pages:
        empty_summary = {
            "site_score": 0.0,
            "worst_page": {"url": "", "score": 0.0},
            "best_page": {"url": "", "score": 0.0},
            "critical_issues": 0,
            "pages_audited": 0,
            "pages_discovered": 0,
            "top_fix": "",
        }
        return SiteAuditResult(
            scan_mode=scan_mode,
            site_score=0.0,
            worst_page_score=0.0,
            worst_page=empty_summary["worst_page"],
            best_page=empty_summary["best_page"],
            pages_audited=0,
            pages_discovered=0,
            issues=[],
            priority_ranking=[],
            executive_summary=empty_summary,
        )

    weighted_total = 0.0
    total_weight = 0.0

    worst_page = min(pages, key=lambda page: page.score)
    best_page = max(pages, key=lambda page: page.score)

    for page in pages:
        page_type = detect_page_type(page.url, page.page_dom)
        weight = _page_weight(page_type)
        weighted_total += float(page.score) * weight
        total_weight += weight

    total_pages = len(pages)
    site_score = round(weighted_total / total_weight, 1) if total_weight > 0 else 0.0
    worst_page_score = round(float(worst_page.score), 1)

    # Invariant guard: non-empty page results must never emit a non-positive site score.
    if total_pages > 0 and site_score <= 0:
        logger.error(
            "Invariant violation: site_score<=0 with %s pages. Applying safe fallback score.",
            total_pages,
        )
        total_issue_count = sum(len(page.issues) for page in pages)
        if total_issue_count == 0:
            site_score = 95.0
        else:
            site_score = round(
                max(15.0, sum(max(float(page.score), 15.0) for page in pages) / total_pages),
                1,
            )

    deduped_issues: list[dict[str, Any]] = []

    # Preserve full per-element density on single-page audits.
    # Cross-page deduplication is only needed when aggregating multiple pages.
    if total_pages == 1:
        single_page = pages[0]
        for issue in single_page.issues:
            item = dict(issue)
            item["affected_pages"] = 1
            item["affected_urls"] = [single_page.url]
            item["frequency"] = 1.0
            deduped_issues.append(item)
    else:
        issue_buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
        issue_urls: dict[tuple[str, str, str], set[str]] = defaultdict(set)

        for page in pages:
            for issue in page.issues:
                key = _issue_key(issue)
                existing = issue_buckets.get(key)
                if existing is None:
                    existing = dict(issue)
                    issue_buckets[key] = existing

                issue_urls[key].add(page.url)

                if float(issue.get("confidence", 0.0)) > float(existing.get("confidence", 0.0)):
                    keep_urls = issue_urls[key]
                    replacement = dict(issue)
                    issue_buckets[key] = replacement
                    issue_urls[key] = keep_urls

        for key, issue in issue_buckets.items():
            urls = sorted(issue_urls[key])
            affected_pages = len(urls)
            frequency = affected_pages / total_pages if total_pages else 0.0

            item = dict(issue)
            item["affected_pages"] = affected_pages
            item["affected_urls"] = urls[:10]
            item["frequency"] = round(frequency, 4)
            deduped_issues.append(item)

    priority_ranking = _build_priority_ranking(deduped_issues, total_pages)

    critical_issues = sum(1 for issue in deduped_issues if str(issue.get("severity", "")).lower() == "critical")
    degraded_reason_counts: dict[str, int] = {}
    for page in pages:
        if not page.degraded_mode:
            continue
        reason = (page.degraded_reason or "unknown").strip() or "unknown"
        degraded_reason_counts[reason] = degraded_reason_counts.get(reason, 0) + 1

    top_degraded_causes = [
        {"reason": reason, "count": count}
        for reason, count in sorted(degraded_reason_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ][:5]

    top_fix = ""
    if priority_ranking:
        top = priority_ranking[0]
        top_fix = f"Fix {top['rule_id']} across {top['affected_pages']} page(s)"

    executive_summary = {
        "site_score": site_score,
        "worst_page": {"url": worst_page.url, "score": worst_page_score},
        "best_page": {"url": best_page.url, "score": round(float(best_page.score), 1)},
        "critical_issues": critical_issues,
        "pages_audited": total_pages,
        "pages_discovered": total_pages,
        "top_fix": top_fix,
        "top_degraded_causes": top_degraded_causes,
    }

    return SiteAuditResult(
        scan_mode=scan_mode,
        site_score=site_score,
        worst_page_score=worst_page_score,
        worst_page=executive_summary["worst_page"],
        best_page=executive_summary["best_page"],
        pages_audited=total_pages,
        pages_discovered=total_pages,
        issues=deduped_issues,
        priority_ranking=priority_ranking,
        executive_summary=executive_summary,
    )
