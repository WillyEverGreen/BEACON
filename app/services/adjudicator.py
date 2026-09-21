"""
AI Adjudication & Verification Service.

Independently evaluates scanner assertions against concrete DOM context
and retrieved WCAG / ARIA APG standards before any finding is declared a violation.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.models import VerificationResult
from app.services.dom_context import DOMContextExtractor
from app.services.llm import get_client

logger = logging.getLogger(__name__)

ADJUDICATION_SYSTEM_PROMPT = """You are an impartial, standards-rigorous Web Accessibility Adjudicator.
Your job is to independently verify whether a scanner-detected accessibility concern is an ACTUAL WCAG failure in its concrete DOM context.

EVIDENCE CONTRACT:
1. Do NOT assume the scanner's conclusion is correct. Automated scanners are detectors, NOT ground-truth compliance verdicts.
2. Distinguish:
   - actual WCAG failure
   - valid implementation
   - best practice
   - ambiguous/context-dependent case
3. Explicitly distinguish:
   scanner detection
   vs
   WCAG conformance determination
4. Use ONLY:
   - supplied element
   - supplied DOM context
   - supplied page structure
   - supplied accessibility metadata
   - retrieved standards evidence
5. Do NOT invent missing DOM elements, attributes, or user behaviors.
6. If evidence is insufficient or truncated, return "needs_review".
7. Determine whether the evidence supports one of three verdicts:
   - "fail": Concrete violation established by both the element and its surrounding DOM context.
   - "pass": The surrounding context (e.g. enclosing sentence, proximate heading, ARIA attributes, wrapping labels) satisfies the WCAG success criterion.
   - "needs_review": Evidence is ambiguous, partial, or requires human tester interaction.

Output MUST be a single strict JSON object matching this schema:
{
  "verdict": "fail" | "pass" | "needs_review",
  "confidence": 0.0 - 1.0,
  "wcag_applicable": true | false,
  "wcag_criterion": "e.g. 2.4.4",
  "evidence_for": ["List of facts proving failure"],
  "evidence_against": ["List of facts showing compliance or contextual clarity"],
  "missing_evidence": ["Missing information preventing definitive verdict"],
  "reasoning_summary": "Concise technical explanation",
  "user_impact": "Real user impact in this specific context",
  "recommended_action": "Actionable developer guidance"
}
Return JSON only."""

ADJUDICATION_USER_PROMPT = """DETECTED ACCESSIBILITY CONCERN:
- Rule ID: {rule_id}
- Scanner Engine: {engine}
- Proposed WCAG Criterion: {wcag_criterion}
- Scanner Description: {description}
- HTML Snippet: {html_snippet}

EXTRACTED DOM & ACCESSIBILITY CONTEXT:
{dom_context_json}

RETRIEVED STANDARDS & GUIDELINES:
{standards_context}

Perform independent adjudication. Return JSON object only."""


INJECTION_PATTERN = re.compile(
    r"(?i)(ignore\s+(all\s+)?(previous\s+)?(instructions|rules|guidelines)|"
    r"disregard\s+(all\s+)?(previous\s+)?(instructions|rules|guidelines)|"
    r"system\s+(prompt\s+)?override|"
    r"(?:system|assistant|human)\s*:|"
    r"<\|im_start\|>|<\|im_end\|>|"
    r"```(?:json)?|```|"
    r'\{"verdict"|'
    r"override\s+mode|"
    r"mark\s+all\s+findings\s+as|"
    r"output\s*:\s*\{|"
    r"return\s+verdict)"
)


def _is_suspicious_or_injection(text: str) -> bool:
    """Detect if text contains prompt injection delimiters, JSON payloads, or code fence attempts."""
    if not text:
        return False
    return bool(INJECTION_PATTERN.search(str(text)))


def _sanitize_prompt_input(text: str) -> str:
    """Sanitize user/scanner input strings against prompt injection attempts."""
    if not text:
        return ""
    cleaned = INJECTION_PATTERN.sub("[filtered]", str(text))
    return cleaned[:1000]


def _pre_adjudicate_fast_path(issue: dict, dom_context: dict) -> Optional[VerificationResult]:
    """Fast deterministic adjudication for well-defined DOM context patterns without LLM latency."""
    from app.services.dom_context import GENERIC_LINK_TEXTS
    rule_id = str(issue.get("rule_id", "")).lower()

    # 1. Link Purpose in Context (WCAG 2.4.4)
    link_ctx = dom_context.get("link_context")
    if (
        link_ctx
        and ("link" in rule_id or "2.4.4" in str(issue.get("wcag_criterion", "")))
        and not any(s in rule_id for s in ("skip", "bypass"))
        and str(issue.get("wcag_criterion", "")) != "2.4.1"
    ):
        link_text = str(link_ctx.get("link_text", "") or "").strip()
        link_lower = link_text.lower()
        sentence = str(link_ctx.get("enclosing_sentence", "") or "").strip()
        preceding_h = link_ctx.get("preceding_heading") or {}
        h_text = str(preceding_h.get("text", "") or "").strip() if isinstance(preceding_h, dict) else ""
        aria_label = str(link_ctx.get("aria_label", "") or "").strip()
        resolved_labelledby_text = str(link_ctx.get("resolved_labelledby_text", "") or "").strip()

        # Security check: if link text or issue contains injection/delimiter payload, reject fast-path pass
        if (
            _is_suspicious_or_injection(link_text)
            or _is_suspicious_or_injection(issue.get("description", ""))
            or _is_suspicious_or_injection(issue.get("html_snippet", ""))
        ):
            return VerificationResult(
                verdict="fail",
                confidence=0.95,
                wcag_applicable=True,
                wcag_criterion="2.4.4",
                evidence_for=["Link text contains malformed markup, code block delimiters, or prompt injection payloads."],
                reasoning_summary="Malformed or injection link text does not describe a valid destination.",
                user_impact="Screen reader users hear confusing syntax rather than destination info.",
                recommended_action="Replace with valid, descriptive natural language link text.",
            )

        # Case 1: Empty link with no accessible name -> FAIL
        if not link_text and not aria_label and not resolved_labelledby_text:
            return VerificationResult(
                verdict="fail",
                confidence=0.96,
                wcag_applicable=True,
                wcag_criterion="2.4.4",
                evidence_for=["Link contains no discernible text, image alt, aria-label, or aria-labelledby accessible name."],
                reasoning_summary="WCAG 2.4.4 / 4.1.2 requires every link to have a discernible accessible name.",
                user_impact="Screen reader users hear 'link' with no indication of destination.",
                recommended_action="Add visible descriptive text or an aria-label to the link.",
            )

        # Case 2: Descriptive link text -> PASS
        if link_lower not in GENERIC_LINK_TEXTS and len(link_text) > 3:
            return VerificationResult(
                verdict="pass",
                confidence=0.95,
                wcag_applicable=True,
                wcag_criterion="2.4.4",
                evidence_against=[f"Link text is descriptive and conveys purpose: '{link_text[:80]}'"],
                reasoning_summary="Link purpose is programmatically determinable from the link text alone.",
                user_impact="Accessible name clearly conveys destination to all users.",
                recommended_action="No change required; element is compliant.",
            )

        # For generic link text ('Learn more', 'Read more', etc.), evaluate context:
        # Case 3: Valid ARIA label -> PASS
        if aria_label and (len(aria_label) > len(link_text) + 3 or aria_label.lower() not in GENERIC_LINK_TEXTS):
            return VerificationResult(
                verdict="pass",
                confidence=0.96,
                wcag_applicable=True,
                wcag_criterion="2.4.4",
                evidence_against=[f"Link has descriptive aria-label: '{aria_label}'"],
                reasoning_summary="Link purpose is programmatically determinable via aria-label.",
                user_impact="Accessible name clearly conveys destination to screen readers.",
                recommended_action="No change required; element is compliant.",
            )

        # Case 4: Resolved aria-labelledby -> PASS
        if resolved_labelledby_text and len(resolved_labelledby_text) > 3:
            return VerificationResult(
                verdict="pass",
                confidence=0.95,
                wcag_applicable=True,
                wcag_criterion="2.4.4",
                evidence_against=[f"Link is programmatically labeled by referenced element: '{resolved_labelledby_text[:80]}'"],
                reasoning_summary="Link purpose is programmatically determinable via resolved aria-labelledby.",
                user_impact="Screen reader users hear unambiguous destination via referenced label.",
                recommended_action="No change required; element is compliant.",
            )

        # Case 5: Semantic enclosing sentence context -> PASS (Technique G53)
        # Evaluates semantic information instead of arbitrary character length
        has_semantic_sentence = bool(
            link_ctx.get("has_context")
            or (sentence and any(w not in GENERIC_LINK_TEXTS for w in re.findall(r"\b[a-zA-Z0-9_-]+\b", re.sub(re.escape(link_text), "", sentence, flags=re.IGNORECASE).lower())))
        )
        if sentence and has_semantic_sentence:
            return VerificationResult(
                verdict="pass",
                confidence=0.92,
                wcag_applicable=True,
                wcag_criterion="2.4.4",
                evidence_against=[f"Enclosing sentence provides clear programmatic context: '{sentence[:120]}'"],
                reasoning_summary="WCAG 2.4.4 allows link purpose to be determined from the enclosing sentence (Technique G53).",
                user_impact="Screen reader users reading paragraph context can determine link destination.",
                recommended_action="Optional best practice: consider adding aria-label for users navigating via link list.",
            )

        # Case 6: Proximate preceding heading clarifies destination -> PASS (Technique H80)
        if h_text and len(h_text) > 3 and preceding_h.get("proximate", True):
            return VerificationResult(
                verdict="pass",
                confidence=0.90,
                wcag_applicable=True,
                wcag_criterion="2.4.4",
                evidence_against=[f"Preceding heading provides programmatic context: '{h_text[:80]}'"],
                reasoning_summary="WCAG 2.4.4 allows link purpose to be determined from preceding heading (Technique G53 / H80).",
                user_impact="Contextual heading clarifies the link destination.",
                recommended_action="Compliant with WCAG 2.4.4 via heading context.",
            )

        # Case 7: Generic link text with NO clarifying context
        # Distinguish complete DOM available (FAIL) vs incomplete evidence (NEEDS_REVIEW)
        dom_complete = bool(link_ctx.get("dom_is_complete", dom_context.get("dom_is_complete", False)))
        if dom_complete:
            return VerificationResult(
                verdict="fail",
                confidence=0.88,
                wcag_applicable=True,
                wcag_criterion="2.4.4",
                evidence_for=[
                    f"Generic link text '{link_text}' has no proximate heading, informative enclosing sentence, or descriptive ARIA attribute in page DOM."
                ],
                reasoning_summary="Link text is generic and surrounding page DOM does not programmatically determine destination.",
                user_impact="Screen reader users cannot determine where this generic link leads without broader context.",
                recommended_action="Make link text descriptive (e.g. 'Learn more about pricing') or add aria-label.",
            )
        else:
            return VerificationResult(
                verdict="needs_review",
                confidence=0.60,
                wcag_applicable=True,
                wcag_criterion="2.4.4",
                missing_evidence=["Surrounding page DOM context was not provided; cannot verify if enclosing sentence or heading clarifies purpose."],
                reasoning_summary="Generic link text cannot be verified without surrounding page DOM context.",
                user_impact="May impact screen reader users if no context exists on the host page.",
                recommended_action="Verify manually on the live page or supply complete page DOM.",
            )

    # 2. Form Labels (WCAG 1.3.1 / 4.1.2)
    form_ctx = dom_context.get("form_context")
    if form_ctx and ("label" in rule_id or "form" in rule_id or "input" in rule_id or "button-name" in rule_id):
        resolved_name = str(
            form_ctx.get("resolved_accessible_name")
            or form_ctx.get("label_text")
            or ""
        ).strip()
        accessible_source = form_ctx.get("accessible_name_source", "none")
        if form_ctx.get("has_label") and resolved_name:
            lbl_type = (
                "aria-label" if (accessible_source == "aria-label" or form_ctx.get("aria_label"))
                else "aria-labelledby" if (accessible_source == "aria-labelledby" or form_ctx.get("resolved_labelledby_text"))
                else f"<label for='{form_ctx.get('label_for')}'>" if (accessible_source == "label_for" or form_ctx.get("associated_label"))
                else "wrapping <label>" if (accessible_source == "wrapping_label" or form_ctx.get("enclosing_label") or form_ctx.get("wrapping_label"))
                else "title attribute" if form_ctx.get("title")
                else "programmatic label"
            )
            return VerificationResult(
                verdict="pass",
                confidence=0.96,
                wcag_applicable=True,
                wcag_criterion="1.3.1",
                evidence_against=[f"Control is programmatically labeled by {lbl_type}: '{resolved_name[:60]}'"],
                reasoning_summary=f"Input has a valid programmatic label via {lbl_type}.",
                user_impact="Screen reader users hear appropriate control label on focus.",
                recommended_action="No fix required; input label is programmatically determinable.",
            )
        elif not form_ctx.get("has_label") and not resolved_name:
            dom_complete = bool(form_ctx.get("dom_is_complete", dom_context.get("dom_is_complete", False)))
            if dom_complete:
                return VerificationResult(
                    verdict="fail",
                    confidence=0.95,
                    wcag_applicable=True,
                    wcag_criterion="1.3.1",
                    evidence_for=["Form control has no associated <label>, wrapping label with text, aria-label, or title."],
                    reasoning_summary="WCAG 1.3.1 / 4.1.2 requires form controls to have programmatically determined accessible names.",
                    user_impact="Screen reader users cannot identify the purpose of this input field.",
                    recommended_action="Add an explicit <label for='...'> or aria-label attribute.",
                )
            else:
                return VerificationResult(
                    verdict="needs_review",
                    confidence=0.60,
                    wcag_applicable=True,
                    wcag_criterion="1.3.1",
                    missing_evidence=["Isolated input snippet provided without surrounding form/label DOM context."],
                    reasoning_summary="Cannot confirm label association without full DOM context.",
                    user_impact="Screen reader users need accessible names for inputs.",
                    recommended_action="Verify associated label in full DOM.",
                )

    # 3. Bypass Blocks (WCAG 2.4.1)
    lm_ctx = dom_context.get("landmark_context")
    if lm_ctx and ("bypass" in rule_id or "skip" in rule_id or "2.4.1" in str(issue.get("wcag_criterion", ""))):
        if not lm_ctx.get("has_repeated_blocks", True):
            return VerificationResult(
                verdict="pass",
                confidence=0.94,
                wcag_applicable=False,
                wcag_criterion="2.4.1",
                evidence_against=["Page has no repeated navigation blocks; bypass block mechanism not required."],
                reasoning_summary="WCAG 2.4.1 only applies to pages with repeated blocks of content.",
                user_impact="Users do not have to tab through repetitive navigation blocks on this page.",
                recommended_action="Bypass link not required on pages without repetitive navigation.",
            )
        if lm_ctx.get("has_bypass_mechanism", False):
            return VerificationResult(
                verdict="pass",
                confidence=0.91,
                wcag_applicable=True,
                wcag_criterion="2.4.1",
                evidence_against=["Bypass blocks requirement satisfied via structural landmarks or headings."],
                reasoning_summary="Mechanism to bypass blocks is provided via main landmark and heading structure.",
                user_impact="Keyboard and screen reader users can jump directly to primary content.",
                recommended_action="Compliant with WCAG 2.4.1.",
            )
        dom_complete = bool(lm_ctx.get("dom_is_complete", dom_context.get("dom_is_complete", False)))
        if dom_complete:
            return VerificationResult(
                verdict="fail",
                confidence=0.92,
                wcag_applicable=True,
                wcag_criterion="2.4.1",
                evidence_for=["Page contains repeated navigation blocks but lacks skip links, <main> landmark, or heading structure."],
                reasoning_summary="WCAG 2.4.1 requires a mechanism to bypass repeated navigation blocks.",
                user_impact="Keyboard users must repeatedly tab through navigation links on every page view.",
                recommended_action="Add a skip link at the start of the page or wrap content in a <main> landmark.",
            )
        else:
            return VerificationResult(
                verdict="needs_review",
                confidence=0.60,
                wcag_applicable=True,
                wcag_criterion="2.4.1",
                missing_evidence=["Isolated header/nav fragment provided without complete document context."],
                reasoning_summary="Cannot verify skip link or main landmark bypass on incomplete page snippet.",
                user_impact="Users may be impacted if full host page lacks bypass mechanisms.",
                recommended_action="Verify bypass mechanisms on full page DOM.",
            )

    # 4. Landmark Structural Integrity (WCAG 1.3.1)
    if lm_ctx and ("landmark" in rule_id or "region" in rule_id or ("1.3.1" in str(issue.get("wcag_criterion", "")) and "main" in rule_id)):
        if "main" in rule_id:
            if lm_ctx.get("main_count", 0) >= 1:
                return VerificationResult(
                    verdict="pass",
                    confidence=0.95,
                    wcag_applicable=True,
                    wcag_criterion="1.3.1",
                    evidence_against=[f"Page contains primary main landmark: {lm_ctx.get('main_landmarks')}"],
                    reasoning_summary="Page contains valid <main> or role='main' landmark.",
                    user_impact="Screen reader users can locate the primary content region.",
                    recommended_action="Compliant with WCAG 1.3.1.",
                )
            else:
                return VerificationResult(
                    verdict="fail",
                    confidence=0.95,
                    wcag_applicable=True,
                    wcag_criterion="1.3.1",
                    evidence_for=["Page DOM does not contain a <main> or role='main' landmark."],
                    reasoning_summary="WCAG 1.3.1 requires information, structure, and relationships to be programmatically determined.",
                    user_impact="Assistive technology users cannot easily navigate directly to main content.",
                    recommended_action="Wrap the primary page content in a <main> element.",
                )

    # 5. Non-Text Content / Images (WCAG 1.1.1)
    if "image" in rule_id or "alt" in rule_id or "1.1.1" in str(issue.get("wcag_criterion", "")):
        snippet = str(issue.get("html_snippet", "") or "")
        alt_match = re.search(r'alt=(["\'])(.*?)\1', snippet)
        if alt_match:
            alt_val = alt_match.group(2)
            return VerificationResult(
                verdict="pass",
                confidence=0.96,
                wcag_applicable=True,
                wcag_criterion="1.1.1",
                evidence_against=[f"Image has valid alt attribute: alt='{alt_val[:60]}'"],
                reasoning_summary="WCAG 1.1.1 is satisfied by text alternative or empty alt for decorative image.",
                user_impact="Screen readers convey image purpose or ignore decorative graphic.",
                recommended_action="No change required; element is compliant.",
            )
        elif "<img" in snippet or str(issue.get("element", "")).startswith("img"):
            dom_complete = bool(dom_context.get("dom_is_complete", False))
            if dom_complete:
                return VerificationResult(
                    verdict="fail",
                    confidence=0.96,
                    wcag_applicable=True,
                    wcag_criterion="1.1.1",
                    evidence_for=["Image element lacks 'alt' attribute."],
                    reasoning_summary="WCAG 1.1.1 requires all non-text content to have an accessible text alternative.",
                    user_impact="Screen reader users cannot perceive the content or purpose of the image.",
                    recommended_action="Add alt attribute with descriptive text or alt='' if decorative.",
                )

    # 6. Color Contrast (WCAG 1.4.3)
    if "color" in rule_id or "contrast" in rule_id or "1.4.3" in str(issue.get("wcag_criterion", "")):
        itype = str(issue.get("issue_type", "")).lower()
        if itype in ("pass", "fail"):
            return VerificationResult(
                verdict=itype,
                confidence=0.95,
                wcag_applicable=True,
                wcag_criterion="1.4.3",
                evidence_for=["Text contrast ratio fails minimum 4.5:1 requirement."] if itype == "fail" else [],
                evidence_against=["Text contrast ratio meets or exceeds 4.5:1 requirement."] if itype == "pass" else [],
                reasoning_summary="Deterministic color contrast evaluation.",
                user_impact="Low contrast impairs readability for users with low vision." if itype == "fail" else "Text is legible.",
                recommended_action="Adjust text or background color to achieve 4.5:1 contrast ratio." if itype == "fail" else "No change required.",
            )

    return None


async def verify_finding(
    issue: dict,
    dom_context: dict,
    standards_chunks: list[dict],
) -> VerificationResult:
    """Verify a single finding using DOM context and strict adjudication."""
    # Try fast deterministic path first
    fast_result = _pre_adjudicate_fast_path(issue, dom_context)
    if fast_result is not None:
        return fast_result

    # If LLM API key not available, fallback to cautious review
    if not settings.llm_api_key or settings.llm_api_key == "test-key":
        return VerificationResult(
            verdict="needs_review" if issue.get("needs_manual_review") else "fail",
            confidence=float(issue.get("confidence") or 0.6),
            wcag_applicable=True,
            wcag_criterion=str(issue.get("wcag_criterion") or ""),
            evidence_for=["Scanner detected issue; LLM adjudication unavailable."],
            reasoning_summary="Standard rule evaluation without LLM adjudication.",
            user_impact=issue.get("description", ""),
            recommended_action=issue.get("suggested_fix", ""),
        )

    # Prepare retrieved standards context string
    standards_parts = []
    for c in standards_chunks[:3]:
        meta = c.get("metadata", {})
        framework = meta.get("framework", meta.get("silo", "WCAG"))
        criterion = meta.get("criterion", meta.get("wcag_sc", ""))
        header = f"[{framework} | {criterion}]" if criterion else f"[{framework}]"
        standards_parts.append(f"{header}\n{c.get('content', '')}")
    standards_str = "\n\n---\n\n".join(standards_parts) if standards_parts else "No specific standard retrieved."

    user_content = ADJUDICATION_USER_PROMPT.format(
        rule_id=_sanitize_prompt_input(issue.get("rule_id", "")),
        engine=_sanitize_prompt_input(issue.get("engine", issue.get("confidence_sources", ["scanner"])[0] if issue.get("confidence_sources") else "scanner")),
        wcag_criterion=_sanitize_prompt_input(issue.get("wcag_criterion", "Unspecified")),
        description=_sanitize_prompt_input(issue.get("description", "")),
        html_snippet=_sanitize_prompt_input(issue.get("html_snippet", "")[:400]),
        dom_context_json=json.dumps(dom_context, indent=2),
        standards_context=standards_str,
    )

    client = get_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": ADJUDICATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=800,
            temperature=0.1,
            timeout=25.0,
        )

        text = response.choices[0].message.content.strip()
        json_text = text
        if "```" in text:
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
            if match:
                json_text = match.group(1).strip()

        obj_match = re.search(r"\{[\s\S]*\}", json_text)
        if obj_match:
            parsed = json.loads(obj_match.group())
            raw_verdict = str(parsed.get("verdict", "needs_review")).lower().strip()
            verdict = raw_verdict if raw_verdict in ("pass", "fail", "needs_review") else "needs_review"
            return VerificationResult(
                verdict=verdict,
                confidence=float(parsed.get("confidence", 0.7)),
                wcag_applicable=bool(parsed.get("wcag_applicable", True)),
                wcag_criterion=parsed.get("wcag_criterion") or issue.get("wcag_criterion"),
                evidence_for=parsed.get("evidence_for") or [],
                evidence_against=parsed.get("evidence_against") or [],
                missing_evidence=parsed.get("missing_evidence") or [],
                reasoning_summary=str(parsed.get("reasoning_summary") or ""),
                user_impact=str(parsed.get("user_impact") or ""),
                recommended_action=str(parsed.get("recommended_action") or ""),
            )

    except Exception as exc:
        logger.warning(f"Adjudication LLM call failed: {exc}")

    return VerificationResult(
        verdict="needs_review",
        confidence=0.5,
        wcag_applicable=True,
        wcag_criterion=issue.get("wcag_criterion"),
        missing_evidence=["LLM adjudication timed out or failed to parse."],
        reasoning_summary="Fallback to needs_review due to adjudication error.",
        user_impact="",
        recommended_action="Inspect element manually.",
    )


async def adjudicate_issues(
    issues: list[dict],
    html: str,
    max_adjudications: int = 15,
) -> Tuple[list[dict], list[dict], list[dict]]:
    """Adjudicate candidate issues using DOM context extraction and verification.
    
    Returns:
        (verified_failures, verified_passes, needs_review_issues)
    """
    from app.services.retrieval import retrieve

    extractor = DOMContextExtractor(html)
    verified_failures: list[dict] = []
    verified_passes: list[dict] = []
    needs_review_issues: list[dict] = []

    # Filter candidates: prioritize high-FP rules and ambiguous issues
    HIGH_FP_CANDIDATE_RULES = {
        "landmark-one-main", "landmark-roles", "region", "aria_content_in_landmark",
        "no-main-landmark", "missing-skip-link", "bypass", "generic-link-text",
        "empty-link", "link-name", "missing-label", "color-contrast"
    }

    adjudication_tasks = []
    issue_candidates = []

    for issue in issues:
        rule_id = str(issue.get("rule_id", "")).lower()
        needs_adj = (
            rule_id in HIGH_FP_CANDIDATE_RULES
            or issue.get("needs_manual_review")
            or issue.get("issue_type") == "needs-review"
        )
        if needs_adj and len(issue_candidates) < max_adjudications:
            dom_ctx = extractor.extract_context_for_issue(issue)
            issue_candidates.append((issue, dom_ctx))
        else:
            # Deterministic clear-cut issues retain original status
            if issue.get("issue_type") == "needs-review":
                needs_review_issues.append(issue)
            else:
                verified_failures.append(issue)

    for issue, dom_ctx in issue_candidates:
        # Evaluate deterministic fast path FIRST before heavy RAG retrieval
        fast_result = _pre_adjudicate_fast_path(issue, dom_ctx)
        if fast_result is not None:
            result = fast_result
        else:
            sc = issue.get("wcag_criterion", "")
            try:
                chunks = await retrieve(
                    query=f"{issue.get('rule_id')} WCAG {sc}",
                    filters={"criterion": sc} if sc else None,
                )
            except Exception:
                chunks = []
            result = await verify_finding(issue, dom_ctx, chunks)

        issue["verification_result"] = result.model_dump()
        issue["verification_confidence"] = result.confidence
        if result.wcag_criterion:
            issue["wcag_criterion"] = result.wcag_criterion

        if result.verdict == "pass":
            issue["issue_type"] = "pass"
            issue["confidence"] = result.confidence
            verified_passes.append(issue)
            logger.info(f"Adjudication suppressed false positive: {issue.get('rule_id')} (PASS)")
        elif result.verdict == "needs_review":
            issue["issue_type"] = "needs-review"
            issue["needs_manual_review"] = True
            issue["confidence"] = min(0.65, result.confidence)
            needs_review_issues.append(issue)
        else:
            issue["issue_type"] = "violation"
            issue["confidence"] = max(issue.get("confidence", 0.7), result.confidence)
            verified_failures.append(issue)

    return verified_failures, verified_passes, needs_review_issues
