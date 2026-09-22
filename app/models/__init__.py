"""
Pydantic request/response models for the Accessibility Intelligence Engine.
Extended schemas for multi-engine auditing, RAG remediation, feedback, and error handling.
"""
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.models.errors import (
    AuditError,
    AuthenticationError,
    AuthorizationError,
    BeaconError,
    BrowserError,
    ConfigurationError,
    DatabaseError,
    ErrorDetail,
    ErrorResponse,
    ExternalServiceError,
    RateLimitError,
    ResourceNotFoundError,
    ValidationError,
    ValidationErrorDetail,
)
from app.security.url_validator import URLValidationError, validate_public_url

# ── Enums ───────────────────────────────────────────────────────

class ScanMode(str, Enum):
    MINIMAL = "minimal"  # Static + basic heuristics only. Fastest, most debuggable.
    FAST = "fast"
    DEEP = "deep"
    MAX = "max"


class Severity(str, Enum):
    CRITICAL = "critical"
    SERIOUS = "serious"
    MODERATE = "moderate"
    MINOR = "minor"


class IssueType(str, Enum):
    VIOLATION = "violation"
    NEEDS_REVIEW = "needs-review"
    BEST_PRACTICE = "best-practice"


class FixEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FeedbackState(str, Enum):
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    IGNORED = "ignored"


# ── Request Models ──────────────────────────────────────────────

class RAGRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Accessibility question or issue description")
    filters: dict | None = Field(
        default=None,
        description="Optional filters: {topic: str, level: str, chunk_type: str}",
        json_schema_extra={"example": {"topic": "contrast", "level": "AA"}}
    )


class AuditRequest(BaseModel):
    url: str = Field(
        ...,
        max_length=2048,
        description="URL to audit for accessibility",
    )
    scan_mode: ScanMode = Field(
        default=ScanMode.FAST,
        description="Scan mode: 'fast', 'deep', or 'max'"
    )
    max_pages: int | None = Field(
        default=None,
        ge=1,
        le=200,
        description="Optional page cap for multi-page scan orchestration",
    )
    checks: list[str] | None = Field(
        default=None,
        description="Specific checks to run: contrast, aria, headings, forms, etc."
    )

    @field_validator("url")
    @classmethod
    def validate_audit_url(cls, value: str) -> str:
        try:
            return validate_public_url(value)
        except URLValidationError as exc:
            raise ValueError(str(exc)) from exc


class FeedbackRequest(BaseModel):
    issue_id: str = Field(..., description="ID of the issue this feedback is for")
    state: FeedbackState = Field(..., description="Developer response to the fix")
    edited_fix: str | None = Field(default=None, description="If edited, the modified fix")
    comment: str | None = Field(default=None, description="Optional developer comment")


# ── Core Issue & Remediation Schemas ────────────────────────────

class WCAGReference(BaseModel):
    criterion_id: str = Field(..., description="e.g. '1.4.3'")
    name: str = Field(..., description="e.g. 'Contrast Minimum'")
    level: str = Field(..., description="A, AA, or AAA")
    description: str = Field(default="", description="Brief description of the criterion")


class PracticalAsset(BaseModel):
    asset_type: str = Field(..., description="template | aria-pattern | script | reference")
    name: str = Field(..., description="Filename or asset name")
    content: str = Field(..., description="The actual code/content snippet")


class RetrievedSource(BaseModel):
    content: str
    source: str
    chunk_type: str
    relevance_score: float


class ConfidenceBreakdown(BaseModel):
    """Calibrated multi-signal confidence breakdown."""
    scanner_confidence: float = Field(default=0.5, description="Initial scanner certainty [0.0 - 1.0]")
    verification_confidence: float = Field(default=0.5, description="AI adjudication certainty [0.0 - 1.0]")
    wcag_mapping_confidence: float = Field(default=0.5, description="WCAG SC mapping certainty [0.0 - 1.0]")
    consensus_confidence: float = Field(default=0.5, description="Cross-engine/method agreement certainty [0.0 - 1.0]")
    final_confidence: float = Field(default=0.5, description="Calibrated final confidence [0.0 - 1.0]")


class VerificationResult(BaseModel):
    """Structured verdict from independent AI/context adjudication."""
    verdict: Literal["pass", "fail", "needs_review"] = Field(
        default="needs_review",
        description="Whether DOM evidence proves WCAG failure, pass, or requires review"
    )
    confidence: float = Field(default=0.5, description="Adjudication confidence [0.0 - 1.0]")
    wcag_applicable: bool = Field(default=True, description="Whether the mapped WCAG criterion applies in this context")
    wcag_criterion: str | None = Field(default=None, description="Corrected or confirmed WCAG criterion, e.g. '2.4.4'")
    evidence_for: list[str] = Field(default_factory=list, description="Concrete evidence points supporting failure")
    evidence_against: list[str] = Field(default_factory=list, description="Concrete evidence points supporting compliance/pass")
    missing_evidence: list[str] = Field(default_factory=list, description="Ambiguous or missing signals requiring review")
    reasoning_summary: str = Field(default="", description="Structured reasoning for the verdict")
    user_impact: str = Field(default="", description="Real user impact in this specific context")
    recommended_action: str = Field(default="", description="Recommended action or verification step")


class AuditIssue(BaseModel):
    """Extended issue schema with full metadata for multi-engine auditing."""
    # ── Identity ──
    issue_id: str = Field(default="", description="Unique hash: SHA256(url + selector + rule_id)")
    rule_id: str = Field(default="", description="e.g. 'color-contrast', 'image-alt'")
    issue_type: str = Field(default="violation", description="violation | needs-review | best-practice")

    # ── Location ──
    element: str = Field(default="", description="CSS selector or XPath")
    html_snippet: str = Field(default="", description="Offending HTML fragment (≤500 chars)")
    page_url: str = Field(default="", description="Full URL where found")

    # ── Classification ──
    severity: str = Field(default="moderate", description="critical | serious | moderate | minor")
    wcag_criterion: str = Field(default="", description="e.g. '1.4.3'")
    wcag_level: str = Field(default="", description="A | AA | AAA")
    category: str = Field(default="", description="html | keyboard | forms | color | images | aria | media | cognitive")

    # ── Confidence ──
    confidence: float = Field(default=0.5, description="Calibrated final confidence [0.0 – 1.0]")
    scanner_confidence: float = Field(default=0.5, description="Scanner engine certainty [0.0 - 1.0]")
    verification_confidence: float = Field(default=0.5, description="AI adjudication certainty [0.0 - 1.0]")
    wcag_mapping_confidence: float = Field(default=0.5, description="Success criterion mapping certainty [0.0 - 1.0]")
    consensus_confidence: float = Field(default=0.5, description="Cross-engine/method agreement certainty [0.0 - 1.0]")
    confidence_breakdown: ConfidenceBreakdown | None = None
    verification_result: VerificationResult | None = None
    confidence_sources: list[str] = Field(default_factory=list, description="e.g. ['axe-core', 'heuristic']")
    confidence_reason: str = Field(default="", description="Human-readable reason for the confidence score")
    needs_manual_review: bool = Field(default=False, description="True if confidence < 0.6")
    rule_trust_score: float = Field(default=0.5, description="ACT-calibrated trust score for this rule")
    rule_trust_verdict: str = Field(default="uncalibrated", description="trust verdict: suppress|noisy|moderate|trusted")
    required_signals: list[str] = Field(default_factory=list, description="Hybrid corroboration signals required for this rule")
    observed_signals: list[str] = Field(default_factory=list, description="Signals observed for this specific issue/rule")
    missing_signals: list[str] = Field(default_factory=list, description="Required hybrid signals that were not observed")
    hybrid_enforcement: str = Field(default="", description="Hybrid enforcement status, if applied")
    coga_pattern_ref: str = Field(default="", description="COGA Usable pattern citation")

    # ── Remediation ──
    description: str = Field(default="", description="Technical description or 'What is broken' in plain English")
    impact_summary: str = Field(default="", description="Simple, non-technical explanation of why this matters to the user")
    human_impact: str = Field(default="", description="Who it affects and how (human-centric story)")
    wcag_intent: str = Field(default="", description="Why this criterion exists and its importance")
    test_procedure: str = Field(default="", description="Step-by-step verification procedure")
    suggested_fix: str = Field(default="")
    code_fix: str = Field(default="", description="Ready-to-paste Vanilla HTML/CSS/JS fix")
    framework_fixes: dict[str, str] = Field(default_factory=dict, description="Fixes for React, Vue, Angular")
    structured_fix: dict[str, Any] = Field(
        default_factory=dict,
        description="Standardized fix packet: explanation, fix_steps, code_example, impact",
    )
    quality_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Per-fix quality signals: usefulness_score, correctness_score, acceptance_rate",
    )
    fix: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured fix object containing description, before/after diff, and framework hints",
    )
    fix_effort: str = Field(default="medium", description="low | medium | high")

    # ── Grouping & Clustering ──
    group_id: str = Field(default="", description="Groups related issues")
    domain: str = Field(default="", description="navigation | forms | content | media | structure | cognitive")
    root_cause_id: str = Field(default="", description="Primary root-cause cluster ID if grouped")
    is_root_cause_primary: bool = Field(default=True, description="True if primary representative of clustered issue")
    contributing_rules: list[str] = Field(default_factory=list, description="Rules contributing to this root-cause cluster")

    # ── Evidence ──
    evidence: dict = Field(default_factory=dict, description="Screenshots, computed styles, ARIA tree")
    reproducibility: str = Field(default="", description="Legacy field for validation hints")


class IssuePacket(BaseModel):
    """Input to the RAG remediation pipeline."""
    issue_id: str
    rule_id: str
    wcag_criterion: str
    element: str
    html_snippet: str
    description: str
    severity: str
    confidence: float


class RemediationPacket(BaseModel):
    """Output from the RAG remediation pipeline (Audit Mastery schema)."""
    issue_id: str
    explanation: dict[str, str] = Field(
        default_factory=dict, 
        description="Nested 6-part explanation: what_is_broken, impact, wcag_sc, intent, verification"
    )
    fixes: dict[str, str] = Field(
        default_factory=dict, 
        description="vanilla, react, vue, angular"
    )
    practical_assets: list[PracticalAsset] = Field(default_factory=list)
    confidence: float = Field(default=0.0, description="RAG's confidence in this remediation")
    needs_manual_review: bool = Field(default=False)
    sources: list[RetrievedSource] = Field(default_factory=list)


# ── Response Models ─────────────────────────────────────────────

class IssueGroup(BaseModel):
    """A group of related issues by domain and rule family."""
    group_id: str
    domain: str
    rule_family: str = ""
    issues: list[AuditIssue] = Field(default_factory=list)
    count: int = 0
    worst_severity: str = "minor"


class CognitiveScore(BaseModel):
    """Cognitive/UX analysis scores."""
    readability_grade: float = Field(default=0.0, description="Flesch-Kincaid grade level")
    readability_ease: float = Field(default=0.0, description="Flesch reading ease (0-100)")
    gunning_fog: float = Field(default=0.0, description="Gunning Fog index")
    jargon_density: float = Field(default=0.0, description="Technical jargon percentage")
    nav_complexity: str = Field(default="low", description="low | medium | high")
    form_usability: str = Field(default="good", description="good | fair | poor")
    overall_cognitive_score: float = Field(default=100.0, description="0-100 cognitive accessibility score")
    issues: list[AuditIssue] = Field(default_factory=list)


class RAGResponse(BaseModel):
    explanation: str = Field(..., description="Why this is an issue and what it means")
    wcag_references: list[WCAGReference] = Field(default_factory=list)
    code_fix: str = Field(default="", description="Ready-to-use code snippet fix")
    practical_assets: list[PracticalAsset] = Field(default_factory=list)
    validation_hint: str = Field(default="")
    sources: list[RetrievedSource] = Field(default_factory=list)


class AuditResponse(BaseModel):
    """Full audit response with enriched metadata."""
    url: str
    scan_mode: str = "fast"
    cognitive_mode: str = Field(default="off", description="off | on")
    total_issues: int
    issues: list[AuditIssue]
    priority_ranking: list[dict] = Field(
        default_factory=list,
        description="Top-5 rule groups to fix first, ranked by impact × frequency × visibility"
    )
    prioritized_issues: list[dict] = Field(default_factory=list, description="Ranked issue summaries for fix-first decisions")
    recommendations: list[str] = Field(default_factory=list, description="Deterministic fix-order recommendations")
    groups: list[IssueGroup] = Field(default_factory=list)
    score: float | None = Field(default=None, description="Accessibility score 0-100 (nullable when confidence is low)")
    overall_score: float | None = Field(default=None, description="Deterministic overall accessibility score")
    severity_breakdown: dict = Field(default_factory=dict, description="Critical / major / minor counts")
    score_distribution: dict = Field(default_factory=dict, description="Score penalty distribution")
    priority_score_distribution: dict = Field(default_factory=dict, description="Priority score distribution")
    top_issue_types: list[dict] = Field(default_factory=list, description="Top issue types by count")
    issue_groupings: dict = Field(default_factory=dict, description="Issue groupings by type, component, and pattern")
    score_explanation: dict = Field(default_factory=dict, description="Score calculation details")
    score_display_context: str = Field(default="", description="Important caveat for perfect scores")
    expected_score_after_fix: float | None = Field(default=None, description="Score if top priorities are fixed")
    score_improvement: float | None = Field(default=None, description="Potential score boost")
    degraded_mode: bool = Field(default=False, description="True if one or more requested engines failed or skipped")
    degraded_reason: str | None = Field(default=None, description="Machine-readable degradation reason code")
    skipped_components: list[str] = Field(default_factory=list, description="e.g., ['playwright', 'llm']")
    degradation_reason: str | None = Field(default=None, description="Reason for degradation")
    confidence_score: float = Field(default=0.0, description="0-1 confidence in score reliability")
    confidence_note: str = Field(default="", description="Human-readable confidence interpretation")
    cognitive_scores: CognitiveScore | None = None
    summary: str = ""
    markdown_report: str = Field(default="", description="Full markdown report")
    scan_time_seconds: float = Field(default=0.0)
    pages_scanned: int = Field(default=1, description="Number of pages scanned in this audit run")
    engines_used: list[str] = Field(default_factory=list)
    quality_gates: dict = Field(default_factory=dict)
    trust: dict = Field(default_factory=dict, description="Machine-readable trust/calibration payload")
    browser_probe_metadata: dict = Field(default_factory=dict, description="Browser runtime metadata from Playwright probes")
    spa_framework: str | None = Field(default=None, description="Detected SPA framework, if available")
    is_spa: bool = Field(default=False, description="Final SPA classification decision")
    spa_classification: dict = Field(
        default_factory=lambda: {"is_spa": False, "confidence": "low", "signals": []},
        description="Explainable SPA classification payload",
    )
    enrichment_status: str = Field(default="complete", description="complete | pending | failed")
    audit_id: str = Field(default="", description="Unique ID for this audit run to poll for enrichment")
    explain: dict | None = Field(default=None, description="Optional explainability breakdown returned when explain=true")


class FeedbackResponse(BaseModel):
    status: str = "recorded"
    issue_id: str = ""
    message: str = ""


class HealthResponse(BaseModel):
    status: str
    vector_store: str
    chunks_count: int
    llm_model: str


class TopicsResponse(BaseModel):
    topics: list[str]
    levels: list[str]
    chunk_types: list[str]


from app.models.contracts import (
    AntiBotState,
    Finding,
    FindingNormalizer,
    Fingerprint,
    PatchResult,
)

__all__ = [
    "ScanMode",
    "Severity",
    "AuditRequest",
    "AuditResponse",
    "AuditStreamEvent",
    "EnrichmentPollResponse",
    "FeedbackRequest",
    "FeedbackResponse",
    "HealthResponse",
    "Issue",
    "IssueGroup",
    "RAGQueryRequest",
    "RAGQueryResponse",
    "TopicsResponse",
    "AuditError",
    "AuthenticationError",
    "AuthorizationError",
    "BeaconError",
    "BrowserError",
    "ConfigurationError",
    "DatabaseError",
    "ErrorDetail",
    "ErrorResponse",
    "ExternalServiceError",
    "RateLimitError",
    "ResourceNotFoundError",
    "ValidationError",
    "ValidationErrorDetail",
    "URLValidationError",
    "validate_public_url",
    "AntiBotState",
    "Finding",
    "FindingNormalizer",
    "Fingerprint",
    "PatchResult",
]

