"""Remediation Sandbox: in-memory DOM isolation and regression testing for AI-generated code patches.

Applies candidate patches against isolated DOM environments, verifies security policy compliance,
and performs differential violation audits (before vs after) to guarantee zero regressions.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from bs4 import BeautifulSoup

from app.models.contracts import PatchResult
from app.services.patch_policy import PatchPolicy
from app.services.static_checks import StaticChecker

logger = logging.getLogger(__name__)


class RemediationSandbox:
    """Safely executes, validates, and differential-audits AI code remediation patches."""

    def __init__(self, sandbox_origin: str = "http://sandbox.local") -> None:
        self.sandbox_origin = sandbox_origin

    def evaluate_patch(
        self,
        finding_id: str,
        original_snippet: str,
        candidate_patch: str,
        surrounding_html: Optional[str] = None,
        target_rule_id: Optional[str] = None,
    ) -> PatchResult:
        """Run policy validation and DOM differential audit on a candidate patch.
        
        Args:
            finding_id: ID of the canonical finding being remediated.
            original_snippet: The original non-compliant HTML code snippet.
            candidate_patch: The AI-proposed replacement HTML code snippet.
            surrounding_html: Optional full page or component DOM context.
            target_rule_id: Optional rule identifier (e.g. 'image-alt', 'button-name').
        """
        start_time = time.perf_counter()

        # Step 1: Security & Stability Policy Check
        is_safe, policy_reasons = PatchPolicy.evaluate(original_snippet, candidate_patch)
        if not is_safe:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return PatchResult(
                finding_id=finding_id,
                original_html=original_snippet,
                patched_html=candidate_patch,
                patch_accepted=False,
                static_validation_passed=False,
                runtime_validation="not_run",
                visual_validation="not_run",
                rejection_reason=f"Policy violation: {'; '.join(policy_reasons)}",
                violations_before_count=0,
                violations_after_count=0,
                new_violations_introduced=0,
                syntax_valid=False,
                execution_time_ms=round(elapsed_ms, 2),
            )

        # Step 2: Construct isolated test environment
        if surrounding_html and original_snippet in surrounding_html:
            dom_before = surrounding_html
            dom_after = surrounding_html.replace(original_snippet, candidate_patch, 1)
        else:
            dom_before = (
                f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>BEACON Sandbox</title></head>"
                f"<body><main>{original_snippet}</main></body></html>"
            )
            dom_after = (
                f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>BEACON Sandbox</title></head>"
                f"<body><main>{candidate_patch}</main></body></html>"
            )

        # Step 3: Run differential static audit
        try:
            checker_before = StaticChecker(dom_before, self.sandbox_origin)
            before_issues = checker_before.run_all()

            checker_after = StaticChecker(dom_after, self.sandbox_origin)
            after_issues = checker_after.run_all()
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return PatchResult(
                finding_id=finding_id,
                original_html=original_snippet,
                patched_html=candidate_patch,
                patch_accepted=False,
                static_validation_passed=False,
                runtime_validation="not_run",
                visual_validation="not_run",
                rejection_reason=f"Sandbox evaluation execution error: {e}",
                violations_before_count=0,
                violations_after_count=0,
                new_violations_introduced=0,
                syntax_valid=False,
                execution_time_ms=round(elapsed_ms, 2),
            )

        # Step 4: Analyze violation signatures for resolution and regressions
        before_rules: Set[str] = {str(i.get("rule_id", "")) for i in before_issues}
        after_rules: Set[str] = {str(i.get("rule_id", "")) for i in after_issues}

        new_rule_regressions = after_rules - before_rules
        new_count = len(new_rule_regressions)

        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        # Regression gate: Reject if any new rule violations introduced
        if new_count > 0:
            reg_names = sorted(list(new_rule_regressions))
            return PatchResult(
                finding_id=finding_id,
                original_html=original_snippet,
                patched_html=candidate_patch,
                patch_accepted=False,
                static_validation_passed=False,
                runtime_validation="not_run",
                visual_validation="not_run",
                rejection_reason=f"Regression detected: patch introduced {new_count} new violation rule(s): {reg_names}",
                violations_before_count=len(before_issues),
                violations_after_count=len(after_issues),
                new_violations_introduced=new_count,
                syntax_valid=True,
                execution_time_ms=round(elapsed_ms, 2),
            )

        # Resolution check: Did the patch actually reduce or fix issues?
        if target_rule_id and target_rule_id in after_rules:
            return PatchResult(
                finding_id=finding_id,
                original_html=original_snippet,
                patched_html=candidate_patch,
                patch_accepted=False,
                static_validation_passed=False,
                runtime_validation="not_run",
                visual_validation="not_run",
                rejection_reason=f"No resolution: target violation '{target_rule_id}' is still present after patch.",
                violations_before_count=len(before_issues),
                violations_after_count=len(after_issues),
                new_violations_introduced=0,
                syntax_valid=True,
                execution_time_ms=round(elapsed_ms, 2),
            )

        if len(after_issues) >= len(before_issues) and before_rules.issubset(after_rules):
            return PatchResult(
                finding_id=finding_id,
                original_html=original_snippet,
                patched_html=candidate_patch,
                patch_accepted=False,
                static_validation_passed=False,
                runtime_validation="not_run",
                visual_validation="not_run",
                rejection_reason="No resolution: patch failed to eliminate target accessibility violation.",
                violations_before_count=len(before_issues),
                violations_after_count=len(after_issues),
                new_violations_introduced=0,
                syntax_valid=True,
                execution_time_ms=round(elapsed_ms, 2),
            )


        # Patch successfully validated with zero static regressions
        return PatchResult(
            finding_id=finding_id,
            original_html=original_snippet,
            patched_html=candidate_patch,
            patch_accepted=True,
            static_validation_passed=True,
            runtime_validation="not_run",
            visual_validation="not_run",
            rejection_reason=None,
            violations_before_count=len(before_issues),
            violations_after_count=len(after_issues),
            new_violations_introduced=0,
            syntax_valid=True,
            execution_time_ms=round(elapsed_ms, 2),
        )
