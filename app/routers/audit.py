"""
Audit router: run accessibility audits on URLs, submit feedback.
Includes SSE streaming for real-time audit progress.
"""
import asyncio
import json
import logging
import time
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from app.models import (
    AuditRequest, AuditResponse, AuditIssue, IssueGroup,
    CognitiveScore, FeedbackRequest, FeedbackResponse,
)
from app.services.audit_runner import run_audit
from app.services.feedback import record_feedback, get_feedback_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit"])


def _build_explain_payload(result: dict) -> dict:
    score_distribution = result.get("score_distribution") if isinstance(result.get("score_distribution"), dict) else {}
    score_explanation = result.get("score_explanation") if isinstance(result.get("score_explanation"), dict) else {}
    issues = result.get("issues") if isinstance(result.get("issues"), list) else []

    confidence_summary = {"high": 0, "medium": 0, "low": 0}
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        tier = str(issue.get("confidence_tier") or "").strip().lower()
        if tier not in confidence_summary:
            confidence = issue.get("confidence", 0.0)
            try:
                confidence_value = float(confidence)
            except (TypeError, ValueError):
                confidence_value = 0.0
            if confidence_value >= 0.85:
                tier = "high"
            elif confidence_value >= 0.60:
                tier = "medium"
            else:
                tier = "low"
        confidence_summary[tier] += 1

    top_impact_issues = []
    for item in result.get("priority_ranking", [])[:5]:
        if not isinstance(item, dict):
            continue
        top_impact_issues.append(
            {
                "rule": item.get("rule_id", "unknown"),
                "impact": item.get("severity", "unknown"),
                "occurrences": int(item.get("affected_count") or 1),
            }
        )

    critical_penalty = float(score_distribution.get("critical_penalty", 0.0) or 0.0)
    major_penalty = float(score_distribution.get("major_penalty", 0.0) or 0.0)
    minor_penalty = float(score_distribution.get("minor_penalty", 0.0) or 0.0)
    quality_bonus = float(score_explanation.get("quality_bonus", 0.0) or 0.0)

    return {
        "score_breakdown": {
            "critical_penalty": round(critical_penalty, 3),
            "serious_penalty": round(major_penalty, 3),
            "major_penalty": round(major_penalty, 3),
            "minor_penalty": round(minor_penalty, 3),
            "quality_bonus": round(quality_bonus, 3),
        },
        "top_impact_issues": top_impact_issues,
        "confidence_summary": confidence_summary,
    }


@router.post("", response_model=AuditResponse)
async def audit_url(
    request: AuditRequest,
    explain: bool = Query(default=False, description="Include explainability payload in response"),
):
    """
    Run accessibility audit on a URL.
    
    - **fast** mode: Static HTML + heuristic checks (≤15s)
    - **deep** mode: Full Playwright render + browser probes + axe-core + cognitive analysis (≤120s)
    
    Returns enriched issues with confidence scores, grouped by domain, and a markdown report.
    """
    try:
        result = await run_audit(
            url=request.url,
            scan_mode=request.scan_mode.value,
            checks=request.checks,
            max_pages=request.max_pages,
        )

        # Build issue models
        issues = []
        for issue_data in result.get("issues", []):
            try:
                issues.append(AuditIssue(**issue_data))
            except Exception as e:
                logger.warning(f"Failed to parse issue: {e}")
                # Fallback: create minimal issue
                issues.append(AuditIssue(
                    issue_type=issue_data.get("issue_type", "violation"),
                    severity=issue_data.get("severity", "moderate"),
                    description=issue_data.get("description", ""),
                    element=issue_data.get("element", ""),
                    wcag_criterion=issue_data.get("wcag_criterion", ""),
                    suggested_fix=issue_data.get("suggested_fix", ""),
                ))

        # Build group models
        groups = []
        for group_data in result.get("groups", []):
            group_issues_list = []
            for gi in group_data.get("issues", []):
                try:
                    group_issues_list.append(AuditIssue(**gi))
                except Exception:
                    pass
            groups.append(IssueGroup(
                group_id=group_data.get("group_id", ""),
                domain=group_data.get("domain", ""),
                rule_family=group_data.get("rule_family", ""),
                issues=group_issues_list,
                count=group_data.get("count", 0),
                worst_severity=group_data.get("worst_severity", "minor"),
            ))

        # Build cognitive scores
        cognitive_scores = None
        cog_data = result.get("cognitive_scores")
        if cog_data:
            cog_issues = []
            for ci in cog_data.get("issues", []):
                try:
                    cog_issues.append(AuditIssue(**ci))
                except Exception:
                    pass
            cognitive_scores = CognitiveScore(
                readability_grade=cog_data.get("readability_grade", 0),
                readability_ease=cog_data.get("readability_ease", 100),
                gunning_fog=cog_data.get("gunning_fog", 0),
                jargon_density=cog_data.get("jargon_density", 0),
                nav_complexity=cog_data.get("nav_complexity", "low"),
                form_usability=cog_data.get("form_usability", "good"),
                overall_cognitive_score=cog_data.get("overall_cognitive_score", 100),
                issues=cog_issues,
            )

        return AuditResponse(
            url=result["url"],
            scan_mode=result.get("scan_mode", "fast"),
            total_issues=result["total_issues"],
            issues=issues,
            groups=groups,
            score=result["score"],
            overall_score=result.get("overall_score", result["score"]),
            severity_breakdown=result.get("severity_breakdown", {}),
            score_distribution=result.get("score_distribution", {}),
            priority_score_distribution=result.get("priority_score_distribution", {}),
            top_issue_types=result.get("top_issue_types", []),
            issue_groupings=result.get("issue_groupings", {}),
            score_explanation=result.get("score_explanation", {}),
            cognitive_scores=cognitive_scores,
            summary=result["summary"],
            markdown_report=result.get("markdown_report", ""),
            scan_time_seconds=result.get("scan_time_seconds", 0),
            pages_scanned=int(result.get("pages_scanned") or result.get("pages_audited") or 1),
            engines_used=result.get("engines_used", []),
            quality_gates=result.get("quality_gates", {}),
            trust=result.get("trust", {}),
            browser_probe_metadata=result.get("browser_probe_metadata", {}),
            spa_framework=result.get("spa_framework"),
            is_spa=result.get("is_spa", False),
            spa_classification=result.get(
                "spa_classification",
                {"is_spa": bool(result.get("is_spa", False)), "confidence": "low", "signals": []},
            ),
            enrichment_status=result.get("enrichment_status", "complete"),
            audit_id=result.get("audit_id", ""),
            priority_ranking=result.get("priority_ranking", []),
            prioritized_issues=result.get("prioritized_issues", []),
            recommendations=result.get("recommendations", []),
            cognitive_mode=result.get("cognitive_mode", "off"),
            explain=_build_explain_payload(result) if explain else None,
        )

    except Exception as e:
        logger.error(f"Audit error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Audit failed: {str(e)}")


@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(request: FeedbackRequest):
    """
    Submit developer feedback for a suggested fix.
    
    States: accepted, edited, rejected, ignored
    """
    try:
        result = record_feedback(
            issue_id=request.issue_id,
            state=request.state.value,
            edited_fix=request.edited_fix,
            comment=request.comment,
        )
        return FeedbackResponse(**result)
    except Exception as e:
        logger.error(f"Feedback error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Feedback recording failed: {str(e)}")


@router.get("/feedback/stats")
async def feedback_stats():
    """Get aggregate feedback statistics."""
    try:
        return get_feedback_stats()
    except Exception as e:
        logger.error(f"Feedback stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/enrichment/{audit_id}")
async def get_enrichment(audit_id: str):
    """
    Poll for background RAG enrichment results.
    Returns status: 'pending' | 'complete' | 'failed' | 'not_found'
    """
    from app.services.audit_runner import get_enriched_results
    return get_enriched_results(audit_id)


@router.post("/stream")
async def audit_stream(request: AuditRequest):
    """
    SSE streaming audit endpoint.
    Streams real-time progress events as the audit executes:
      - {"event": "started", "scan_mode": "..."}
      - {"event": "fetching", "progress": 10}
      - {"event": "engines_running", "progress": 30}
      - {"event": "scoring", "progress": 70}
      - {"event": "complete", "progress": 100, "result": {...}}
    """
    async def event_generator():
        try:
            # Phase 1: Started
            yield f"data: {json.dumps({'event': 'started', 'scan_mode': request.scan_mode.value, 'progress': 5})}\n\n"
            await asyncio.sleep(0.05)

            # Phase 2: Fetching
            yield f"data: {json.dumps({'event': 'fetching', 'url': request.url, 'progress': 10})}\n\n"

            # Phase 3: Run the full audit
            yield f"data: {json.dumps({'event': 'engines_running', 'progress': 30})}\n\n"

            start = time.time()
            result = await run_audit(
                url=request.url,
                scan_mode=request.scan_mode.value,
                checks=request.checks,
                max_pages=request.max_pages,
            )
            elapsed = round(time.time() - start, 2)

            # Phase 4: Scoring
            yield f"data: {json.dumps({'event': 'scoring', 'progress': 70, 'issues_found': result.get('total_issues', 0)})}\n\n"
            await asyncio.sleep(0.05)

            # Phase 5: Complete
            yield f"data: {json.dumps({'event': 'complete', 'progress': 100, 'scan_time': elapsed, 'score': result.get('score', 0), 'total_issues': result.get('total_issues', 0), 'enrichment_status': result.get('enrichment_status', 'complete'), 'audit_id': result.get('audit_id', ''), 'summary': result.get('summary', '')})}\n\n"

        except Exception as e:
            logger.error(f"SSE audit error: {e}", exc_info=True)
            yield f"data: {json.dumps({'event': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/cache/stats")
async def cache_stats():
    """
    Returns cache observability telemetry for all 4 tiers:
    - page (URL-level cache)
    - dom  (structural hash cache)
    - llm  (LLM response cache)
    - fix  (Fix Library cache)

    Also returns hit_rate per tier to see if caching is actually working.
    """
    from app.services.fix_cache import get_cache_stats
    from app.config import CACHE_STATS

    fix_stats = get_cache_stats()

    # Build hit-rate summaries per tier
    def hit_rate(hits: int, misses: int) -> float:
        total = hits + misses
        return round(hits / total, 3) if total > 0 else 0.0

    # Sync fix cache counters into CACHE_STATS for unified reporting
    CACHE_STATS["fix_hits"]   = fix_stats.get("hit_count", 0)
    CACHE_STATS["fix_misses"] = fix_stats.get("miss_count", 0)

    return {
        "cache_hit_rates": {
            "page": hit_rate(CACHE_STATS["page_hits"], CACHE_STATS["page_misses"]),
            "dom":  hit_rate(CACHE_STATS["dom_hits"],  CACHE_STATS["dom_misses"]),
            "llm":  hit_rate(CACHE_STATS["llm_hits"],  CACHE_STATS["llm_misses"]),
            "retrieval": hit_rate(
                int(CACHE_STATS.get("retrieval_hits", 0) or 0),
                int(CACHE_STATS.get("retrieval_misses", 0) or 0),
            ),
            "fix":  hit_rate(CACHE_STATS["fix_hits"],  CACHE_STATS["fix_misses"]),
        },
        "raw_counters": CACHE_STATS,
        "fix_library":  fix_stats,
    }
