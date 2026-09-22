"""
GitHub App / PR Automation Adapter and Patch Safety Engine (§51, §52).

Implements the verified automated PR pipeline:
Verified Finding -> Candidate Patch -> Sandbox -> Patch Safety Engine -> Regression Checks -> PR Markdown

Safety Gate:
- Security validation (via PatchPolicy)
- Syntax validation (HTML/JSX parse check)
- Scope boundary check (rejects unexpected files or broad multi-line refactors)
- Differential accessibility regression check (via RemediationSandbox)
- Never auto-merge; least privilege enforcement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.patch_policy import PatchPolicy
from app.services.remediation_sandbox import RemediationSandbox

logger = logging.getLogger(__name__)


@dataclass
class PatchSafetyResult:
    """Detailed evaluation of patch safety before PR generation (§52)."""
    is_safe: bool
    rejection_reasons: list[str] = field(default_factory=list)
    security_passed: bool = True
    syntax_passed: bool = True
    scope_passed: bool = True
    regression_passed: bool = True
    details: dict[str, Any] = field(default_factory=dict)


def validate_patch_safety(
    finding: dict[str, Any],
    candidate_patch: str,
    *,
    target_file: str | None = None,
    allowed_files: list[str] | None = None,
    surrounding_html: str | None = None,
) -> PatchSafetyResult:
    """
    Validates safety, syntax, scope boundary, and differential regressions before opening a PR (§52).
    """
    rejection_reasons: list[str] = []
    orig_html = str(finding.get("html") or finding.get("element") or "").strip()

    # 1. Security Check (Forbidden tags, event handlers, dangerous schemes)
    sec_safe, sec_reasons = PatchPolicy.evaluate(orig_html, candidate_patch)
    security_passed = sec_safe
    if not sec_safe:
        rejection_reasons.extend(sec_reasons)

    # 2. Syntax Check
    syntax_passed = True
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(candidate_patch, "html.parser")
        if not soup.find_all(True) and not candidate_patch.strip():
            syntax_passed = False
            rejection_reasons.append("Empty or unparseable HTML syntax in candidate patch.")
    except Exception as e:
        syntax_passed = False
        rejection_reasons.append(f"Syntax validation failed: {e}")

    # 3. Scope Boundary Check
    scope_passed = True
    if target_file and allowed_files:
        if target_file not in allowed_files:
            scope_passed = False
            rejection_reasons.append(f"Target file '{target_file}' is outside the authorized scope boundary.")

    # Check for unrelated refactor or destructive change
    if len(orig_html) > 0 and len(candidate_patch) > len(orig_html) * 5:
        scope_passed = False
        rejection_reasons.append("Patch length exceeds 5x original snippet length; possible unrelated refactoring detected.")

    # 4. Remediation Sandbox Differential Regression Check
    sandbox = RemediationSandbox()
    finding_id = str(finding.get("id") or finding.get("finding_id") or "f-unknown")
    sandbox_res = sandbox.evaluate_patch(
        finding_id=finding_id,
        original_snippet=orig_html,
        candidate_patch=candidate_patch,
        surrounding_html=surrounding_html,
    )

    regression_passed = sandbox_res.patch_accepted and sandbox_res.new_violations_introduced == 0
    if not regression_passed:
        rejection_reasons.append(
            f"Sandbox regression check failed: {sandbox_res.rejection_reason or f'{sandbox_res.new_violations_introduced} new violation(s) introduced'}"
        )

    is_safe = (security_passed and syntax_passed and scope_passed and regression_passed)

    return PatchSafetyResult(
        is_safe=is_safe,
        rejection_reasons=rejection_reasons,
        security_passed=security_passed,
        syntax_passed=syntax_passed,
        scope_passed=scope_passed,
        regression_passed=regression_passed,
        details={
            "sandbox_violations_before": sandbox_res.violations_before_count,
            "sandbox_violations_after": sandbox_res.violations_after_count,
            "new_violations_introduced": sandbox_res.new_violations_introduced,
            "execution_time_ms": sandbox_res.execution_time_ms,
        },
    )


def format_pr_markdown(
    finding: dict[str, Any],
    candidate_patch: str,
    safety_result: PatchSafetyResult,
    *,
    branch_name: str = "beacon/fix-a11y",
    target_file: str | None = None,
) -> str:
    """
    Constructs the pull request markdown document following enterprise compliance standards (§51).
    Explicitly includes safety checks, sandbox verification, and the strict NO AUTO-MERGE mandate.
    """
    rule_id = finding.get("rule_id", "accessibility-issue")
    sc = finding.get("wcag_criterion", "1.1.1")
    desc = finding.get("description", "Accessibility violation detected by BEACON.")
    orig_html = finding.get("html") or finding.get("element") or ""

    lines = [
        f"## 🌐 BEACON Automated Accessibility Remediation: `{rule_id}`",
        "",
        f"**Target Criterion:** WCAG 2.2 SC **{sc}**",
        f"**Target File:** `{target_file or 'component.html'}`",
        f"**Branch:** `{branch_name}`",
        "",
        "### 📋 Issue Description",
        f"> {desc}",
        "",
        "### 🔍 Verified Evidence",
        f"- **Selector:** `{finding.get('selector', 'unknown')}`",
        f"- **Severity:** `{finding.get('severity', 'moderate').upper()}`",
        f"- **Adjudication Confidence:** `{finding.get('confidence', 0.85)}`",
        "",
        "### 🔄 Proposed Changes (Before vs After)",
        "```html",
        "<!-- BEFORE -->",
        f"{orig_html}",
        "",
        "<!-- AFTER (Proposed Fix) -->",
        f"{candidate_patch}",
        "```",
        "",
        "### 🧪 Sandbox Verification & Safety Checks",
        f"- **Security Check:** {'✅ PASSED' if safety_result.security_passed else '❌ FAILED'}",
        f"- **Syntax Check:** {'✅ PASSED' if safety_result.syntax_passed else '❌ FAILED'}",
        f"- **Scope Boundary Check:** {'✅ PASSED' if safety_result.scope_passed else '❌ FAILED'}",
        f"- **Differential Regression Check:** {'✅ 0 new violations introduced' if safety_result.regression_passed else '❌ Regressions detected'}",
        "",
        "---",
        "### ⚠️ Reviewer Notice & Policy Constraints",
        "> **IMPORTANT:** **DO NOT AUTO-MERGE.**",
        "> Automated patches must be reviewed and tested by a human accessibility specialist or frontend engineer.",
        "> This PR was created using least-privilege repository permissions via the BEACON Platform.",
    ]

    return "\n".join(lines)


def generate_pr_payload(
    finding: dict[str, Any],
    candidate_patch: str,
    *,
    repo: str,
    target_file: str,
    allowed_files: list[str] | None = None,
    surrounding_html: str | None = None,
) -> dict[str, Any]:
    """
    End-to-end PR generation pipeline (§51, §52).
    Evaluates safety; returns complete PR creation payload or rejection status.
    """
    safety = validate_patch_safety(
        finding,
        candidate_patch,
        target_file=target_file,
        allowed_files=allowed_files,
        surrounding_html=surrounding_html,
    )

    finding_id = str(finding.get("id") or finding.get("finding_id") or "issue")
    branch = f"beacon/fix-{finding.get('rule_id', 'a11y')}-{finding_id[:8]}"

    if not safety.is_safe:
        return {
            "status": "REJECTED",
            "message": "Candidate patch failed safety or regression gates.",
            "rejection_reasons": safety.rejection_reasons,
            "safety_result": safety.__dict__,
            "can_open_pr": False,
        }

    pr_body = format_pr_markdown(
        finding,
        candidate_patch,
        safety,
        branch_name=branch,
        target_file=target_file,
    )

    return {
        "status": "READY_FOR_PR",
        "repo": repo,
        "branch": branch,
        "target_file": target_file,
        "commit_message": f"fix(a11y): remediate {finding.get('rule_id', 'accessibility')} ({finding.get('wcag_criterion', 'WCAG')})",
        "pr_title": f"fix(a11y): {finding.get('rule_id', 'accessibility violation')} per WCAG {finding.get('wcag_criterion', '')}",
        "pr_body": pr_body,
        "auto_merge": False,
        "safety_result": safety.__dict__,
        "can_open_pr": True,
    }
