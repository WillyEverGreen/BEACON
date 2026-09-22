"""
Test suite for RemediationSandbox and LLM self-correction integration.
Validates:
- Static differential validation (before vs after)
- Policy enforcement (XSS/script rejection)
- Regression detection (new rule violations introduced)
- Accurate validation scope reporting (Correction 5: static_validation_passed vs runtime/visual not_run)
"""
from app.models.contracts import PatchResult
from app.services.remediation_sandbox import RemediationSandbox


def test_sandbox_evaluates_clean_patch_accepted():
    """Verify that a safe, effective patch is accepted with static_validation_passed=True."""
    sandbox = RemediationSandbox()
    original_html = '<button id="btn1"></button>'
    candidate_patch = '<button id="btn1" aria-label="Close dialog">X</button>'

    result = sandbox.evaluate_patch(
        finding_id="finding-123",
        original_snippet=original_html,
        candidate_patch=candidate_patch,
        target_rule_id="button-name",
    )

    assert isinstance(result, PatchResult)
    assert result.patch_accepted is True
    assert result.static_validation_passed is True
    assert result.runtime_validation == "not_run"
    assert result.visual_validation == "not_run"
    assert result.new_violations_introduced == 0
    assert result.rejection_reason is None

    result_dict = result.to_dict()
    assert result_dict["patch_accepted"] is True
    assert result_dict["static_validation_passed"] is True
    assert result_dict["runtime_validation"] == "not_run"
    assert result_dict["visual_validation"] == "not_run"


def test_sandbox_rejects_security_policy_violation():
    """Verify that a patch with script injection is rejected by policy."""
    sandbox = RemediationSandbox()
    original_html = '<img id="avatar" src="avatar.png">'
    candidate_patch = '<img id="avatar" src="avatar.png" alt="User" onerror="alert(1)"><script>doBadThing()</script>'

    result = sandbox.evaluate_patch(
        finding_id="finding-sec",
        original_snippet=original_html,
        candidate_patch=candidate_patch,
        target_rule_id="image-alt",
    )

    assert result.patch_accepted is False
    assert result.static_validation_passed is False
    assert "Policy violation" in (result.rejection_reason or "")


def test_sandbox_rejects_patch_introducing_regression():
    """Verify that a patch introducing a new violation is rejected."""
    sandbox = RemediationSandbox()
    original_html = '<div id="container"><button id="btn"></button></div>'
    # Patch fixes button-name but introduces an image without alt
    candidate_patch = '<div id="container"><button id="btn">Submit</button><img src="new_unlabeled.png"></div>'

    result = sandbox.evaluate_patch(
        finding_id="finding-reg",
        original_snippet=original_html,
        candidate_patch=candidate_patch,
        target_rule_id="button-name",
    )

    assert result.patch_accepted is False
    assert result.static_validation_passed is False
    assert result.new_violations_introduced > 0
    assert "Regression detected" in (result.rejection_reason or "")
