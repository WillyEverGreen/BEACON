"""
Audit router: run accessibility audits on URLs, submit feedback.
"""
import logging
from fastapi import APIRouter, HTTPException
from app.models import (
    AuditRequest, AuditResponse, AuditIssue, IssueGroup,
    CognitiveScore, FeedbackRequest, FeedbackResponse,
)
from app.services.audit_runner import run_audit
from app.services.feedback import record_feedback, get_feedback_stats

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit", tags=["Audit"])


@router.post("", response_model=AuditResponse)
async def audit_url(request: AuditRequest):
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
            cognitive_scores=cognitive_scores,
            summary=result["summary"],
            markdown_report=result.get("markdown_report", ""),
            scan_time_seconds=result.get("scan_time_seconds", 0),
            engines_used=result.get("engines_used", []),
            quality_gates=result.get("quality_gates", {}),
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
