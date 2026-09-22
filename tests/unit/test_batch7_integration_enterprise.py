"""
Unit tests for Batch 7: Integration & Enterprise (§49–§55).
"""


from app.services.contextual_remediation import (
    generate_contextual_patch,
)
from app.services.evidence_labeling import (
    label_finding_evidence,
)
from app.services.feedback_learning import (
    FeedbackLearningStore,
)
from app.services.github_pr_automation import (
    generate_pr_payload,
    validate_patch_safety,
)
from app.services.knowledge_versioning import (
    KnowledgeStore,
)

# ── §49: Evidence Labeling Tests ──────────────────────────────────────────────

def test_evidence_labeling_provenance():
    """Verify evidence labeling explicitly tags observed, inferred, and untested modalities (§49)."""
    finding_partial = {
        "id": "f-01",
        "rule_id": "image-alt",
        "wcag_criterion": "1.1.1",
        "element_context": {"node_name": "img", "accessible_name": ""},
        "browser_evidence": None,
        "visual_evidence": None,
        "at_evidence": None,
    }

    labeled = label_finding_evidence(finding_partial)
    prov = labeled["evidence_provenance"]

    # DOM is observed
    assert prov["dom"]["status"] == "observed"
    assert prov["dom"]["confidence"] >= 0.9

    # Untested modalities MUST be explicitly marked 'not_tested' (never fabricated as pass)
    assert prov["browser"]["status"] == "not_tested"
    assert prov["visual"]["status"] == "not_tested"
    assert prov["assistive_technology"]["status"] == "not_tested"
    assert prov["assistive_technology"]["confidence"] == 0.0


def test_evidence_labeling_template_inferred():
    """Verify template-inferred findings are tagged as inferred (§49)."""
    finding_inferred = {
        "id": "f-02",
        "rule_id": "heading-order",
        "is_template_inferred": True,
    }
    labeled = label_finding_evidence(finding_inferred)
    assert labeled["evidence_provenance"]["template_inference"]["status"] == "inferred"


# ── §50: Contextual Remediation Tests ─────────────────────────────────────────

def test_contextual_remediation_minimal_patch():
    """Verify contextual remediation generates minimal surgical patches and unified diffs (§50)."""
    finding = {
        "id": "f-10",
        "rule_id": "image-alt",
        "wcag_criterion": "1.1.1",
        "html": '<img src="logo.png">',
        "description": "Image missing alt text.",
        "element_context": {"accessible_name": "Acme Logo"},
    }

    patch_res = generate_contextual_patch(finding, framework="html")
    assert patch_res["is_minimal"] is True
    assert patch_res["is_safe"] is True
    assert 'alt="Acme Logo"' in patch_res["candidate_patch"]
    assert "--- a/component.html" in patch_res["patch_diff"]
    assert "+++ b/component.html" in patch_res["patch_diff"]


def test_contextual_remediation_jsx_framework():
    """Verify JSX framework adaptation converts attributes properly (§50)."""
    finding = {
        "id": "f-11",
        "rule_id": "target-size",
        "wcag_criterion": "2.5.8",
        "html": '<button class="small-btn">X</button>',
    }
    patch_jsx = generate_contextual_patch(finding, framework="react")
    assert "className=" in patch_jsx["candidate_patch"]
    assert "class=" not in patch_jsx["candidate_patch"]


def test_contextual_remediation_auth_paste_unblocking():
    """Verify accessible auth remediation unblocks password paste (§14, §50)."""
    finding = {
        "id": "f-12",
        "rule_id": "accessible-auth",
        "wcag_criterion": "3.3.8",
        "html": '<input type="password" id="pwd" onpaste="return false;">',
    }
    patch_auth = generate_contextual_patch(finding, framework="html")
    assert "onpaste" not in patch_auth["candidate_patch"]
    assert patch_auth["is_safe"] is True


# ── §51 & §52: GitHub App / PR Automation & Patch Safety Tests ────────────────

def test_patch_safety_acceptance():
    """Verify clean patch passes all safety gates (§52)."""
    finding = {
        "id": "f-20",
        "rule_id": "button-name",
        "wcag_criterion": "4.1.2",
        "html": "<button></button>",
    }
    candidate = '<button aria-label="Close dialog">X</button>'

    safety = validate_patch_safety(
        finding,
        candidate,
        target_file="src/Modal.html",
        allowed_files=["src/Modal.html", "src/Header.html"],
    )
    assert safety.is_safe is True
    assert safety.security_passed is True
    assert safety.syntax_passed is True
    assert safety.scope_passed is True
    assert safety.regression_passed is True


def test_patch_safety_rejection_security():
    """Verify patch introducing XSS or forbidden tags is rejected (§52)."""
    finding = {
        "id": "f-21",
        "rule_id": "button-name",
        "html": "<button></button>",
    }
    malicious_patch = '<button onclick="alert(1)">Click</button><script>stealCookies()</script>'

    safety = validate_patch_safety(finding, malicious_patch)
    assert safety.is_safe is False
    assert safety.security_passed is False
    assert any("script" in r.lower() for r in safety.rejection_reasons)


def test_patch_safety_rejection_scope_boundary():
    """Verify patch targeting unauthorized file or massive code blowout is rejected (§52)."""
    finding = {
        "id": "f-22",
        "rule_id": "image-alt",
        "html": '<img src="a.jpg">',
    }
    candidate = '<img src="a.jpg" alt="A">'

    # File outside allowed scope
    safety_file = validate_patch_safety(
        finding,
        candidate,
        target_file="unauthorized/Secret.tsx",
        allowed_files=["src/Public.tsx"],
    )
    assert safety_file.is_safe is False
    assert safety_file.scope_passed is False

    # Massive code blowout (unrelated refactoring)
    huge_patch = '<img src="a.jpg" alt="A">' + ("<div>Refactored line</div>\n" * 50)
    safety_blowout = validate_patch_safety(finding, huge_patch)
    assert safety_blowout.is_safe is False
    assert safety_blowout.scope_passed is False


def test_generate_pr_payload_and_no_auto_merge():
    """Verify PR creation payload enforces NO AUTO-MERGE mandate (§51)."""
    finding = {
        "id": "f-23",
        "rule_id": "target-size",
        "wcag_criterion": "2.5.8",
        "html": '<button style="width: 10px; height: 10px;">+</button>',
        "description": "Touch target under 24x24px.",
    }
    candidate = '<button style="min-width: 24px; min-height: 24px;">+</button>'

    pr_payload = generate_pr_payload(
        finding,
        candidate,
        repo="org/repo",
        target_file="components/Button.html",
        allowed_files=["components/Button.html"],
    )

    assert pr_payload["status"] == "READY_FOR_PR"
    assert pr_payload["can_open_pr"] is True
    assert pr_payload["auto_merge"] is False  # Strict mandate: Never auto-merge!
    assert "DO NOT AUTO-MERGE" in pr_payload["pr_body"]
    assert "target_file" in pr_payload


# ── §53 & §54: Multi-Tenant Knowledge & Standards Versioning Tests ─────────────

def test_knowledge_versioning_and_tenant_isolation():
    """Verify immutable versioned standards and multi-tenant isolation (§53, §54)."""
    store = KnowledgeStore()

    # 1. Retrieve canonical global standards chunk
    chunk_111 = store.get_standard_chunk("1.1.1", version="2023-10-05")
    assert chunk_111 is not None
    assert chunk_111["version"] == "2023-10-05"
    assert "non-text" in chunk_111["content"].lower()
    assert chunk_111["tenant_id"] is None

    # 2. Register custom organization rule for Tenant A
    store.register_tenant_rule(
        tenant_id="tenant-alpha",
        document="Alpha Enterprise A11y Policy",
        criterion="1.1.1",
        content="All images must have alt text approved by the localization team.",
        version="v2.1",
    )

    # Tenant A sees their custom rule
    alpha_rule = store.get_standard_chunk("1.1.1", tenant_id="tenant-alpha")
    assert alpha_rule["tenant_id"] == "tenant-alpha"
    assert "localization team" in alpha_rule["content"]

    # Tenant B or global caller sees canonical standard without bleeding
    beta_rule = store.get_standard_chunk("1.1.1", tenant_id="tenant-beta")
    assert beta_rule["tenant_id"] is None
    assert "localization team" not in beta_rule["content"]

    # List tenant rules strictly isolated
    alpha_list = store.list_tenant_rules("tenant-alpha")
    beta_list = store.list_tenant_rules("tenant-beta")
    assert len(alpha_list) == 1
    assert len(beta_list) == 0


# ── §55: Feedback Learning Tests ──────────────────────────────────────────────

def test_feedback_learning_metrics_and_dataset_export():
    """Verify reviewer decisions, empirical tuning metrics, and evaluation dataset export (§55)."""
    store = FeedbackLearningStore()

    # Record reviewer decisions
    store.record_decision(
        finding_id="f-301",
        rule_id="image-alt",
        decision="confirmed",
        wcag_criterion="1.1.1",
        comment="Genuine missing alt text on hero image.",
    )
    store.record_decision(
        finding_id="f-302",
        rule_id="image-alt",
        decision="fix_accepted",
        wcag_criterion="1.1.1",
    )
    store.record_decision(
        finding_id="f-303",
        rule_id="color-contrast",
        decision="rejected",
        wcag_criterion="1.4.3",
        comment="False positive: text rendered inside canvas with custom shader.",
    )

    # Compute tuning metrics
    metrics = store.compute_rule_tuning_metrics()
    assert metrics["total_decisions_recorded"] == 3
    assert "image-alt" in metrics["rule_metrics"]
    assert "color-contrast" in metrics["rule_metrics"]

    contrast_metrics = metrics["rule_metrics"]["color-contrast"]
    assert contrast_metrics["false_positive_rate"] == 1.0
    assert contrast_metrics["action_recommended"] == "TUNE_DOWN_WEIGHT"

    # Export versioned evaluation dataset
    dataset = store.export_versioned_evaluation_dataset(dataset_version="2026.04-eval")
    assert dataset["dataset_version"] == "2026.04-eval"
    assert dataset["total_cases"] == 3
    assert dataset["cases"][0]["ground_truth"] == "FAIL"
    assert dataset["cases"][2]["ground_truth"] == "PASS"

    # Guardrail check: No automated retraining policy
    assert "No automated retraining" in metrics["policy"]
