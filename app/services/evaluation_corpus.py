"""
Comprehensive Evaluation Corpus & Empirical Benchmark Engine (§60, §61).

Provides:
- §60: Curated multi-modal evaluation dataset covering:
  deterministic, contextual, visual, browser, ARIA, forms, landmarks,
  keyboard, authentication, multimedia, COGA.
  Split into: development, calibration, held-out.
- §61: Benchmark calculation with mathematically rigorous accounting:
  TP + TN + FP + FN + NEEDS_REVIEW == TOTAL_CASES.
  Explicitly measures precision, recall, false-positive rate, needs-review rate,
  automation coverage, and sandbox regression detection rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EvaluationTestCase:
    """Represents an immutable benchmark evaluation case (§60)."""
    case_id: str
    category: str       # deterministic, contextual, visual, browser, aria, forms, landmarks, keyboard, auth, multimedia, coga
    split: str          # development, calibration, held-out
    wcag_criterion: str
    rule_id: str
    html: str
    ground_truth: str   # FAIL, PASS, NEEDS_REVIEW
    expected_severity: str = "moderate"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "split": self.split,
            "wcag_criterion": self.wcag_criterion,
            "rule_id": self.rule_id,
            "html": self.html,
            "ground_truth": self.ground_truth,
            "expected_severity": self.expected_severity,
            "notes": self.notes,
        }


# Canonical evaluation corpus containing diverse cases (§60)
CANONICAL_EVALUATION_CORPUS: list[EvaluationTestCase] = [
    # 1. Deterministic
    EvaluationTestCase(
        case_id="DET-01",
        category="deterministic",
        split="development",
        wcag_criterion="1.1.1",
        rule_id="image-alt",
        html='<img src="chart.png">',
        ground_truth="FAIL",
        expected_severity="critical",
        notes="Informative chart image missing alt attribute.",
    ),
    EvaluationTestCase(
        case_id="DET-02",
        category="deterministic",
        split="calibration",
        wcag_criterion="1.1.1",
        rule_id="image-alt",
        html='<img src="divider.png" alt="" role="presentation">',
        ground_truth="PASS",
        notes="Decorative image correctly marked with empty alt and presentation role.",
    ),
    # 2. Contextual
    EvaluationTestCase(
        case_id="CTX-01",
        category="contextual",
        split="development",
        wcag_criterion="2.4.4",
        rule_id="link-purpose",
        html='<a href="/report.pdf">Click here</a>',
        ground_truth="FAIL",
        expected_severity="moderate",
        notes="Generic link text lacking surrounding descriptive context.",
    ),
    EvaluationTestCase(
        case_id="CTX-02",
        category="contextual",
        split="held-out",
        wcag_criterion="2.4.4",
        rule_id="link-purpose",
        html='<p>Download our annual report: <a href="/annual.pdf" aria-label="Download 2025 Annual Financial Report (PDF)">Download</a></p>',
        ground_truth="PASS",
        notes="Link text disambiguated via aria-label.",
    ),
    # 3. Visual
    EvaluationTestCase(
        case_id="VIS-01",
        category="visual",
        split="development",
        wcag_criterion="1.4.3",
        rule_id="color-contrast",
        html='<span style="color: #9ca3af; background-color: #ffffff;">Subtle text</span>',
        ground_truth="FAIL",
        expected_severity="serious",
        notes="Contrast ratio 2.85:1 is below the 4.5:1 requirement.",
    ),
    EvaluationTestCase(
        case_id="VIS-02",
        category="visual",
        split="calibration",
        wcag_criterion="1.4.1",
        rule_id="link-color-only",
        html='<p>Read the <a href="/terms" style="color: blue; text-decoration: none;">terms</a>.</p>',
        ground_truth="FAIL",
        expected_severity="serious",
        notes="Link distinguished from surrounding text by color alone without underline.",
    ),
    # 4. Browser / Runtime
    EvaluationTestCase(
        case_id="BRW-01",
        category="browser",
        split="development",
        wcag_criterion="2.5.8",
        rule_id="target-size",
        html='<button style="width: 14px; height: 14px;">X</button>',
        ground_truth="FAIL",
        expected_severity="moderate",
        notes="Rendered target size 14x14px is smaller than 24x24px minimum.",
    ),
    EvaluationTestCase(
        case_id="BRW-02",
        category="browser",
        split="held-out",
        wcag_criterion="2.4.11",
        rule_id="focus-obscured",
        html='<div style="position: fixed; top: 0; height: 100px; z-index: 1000;"><input style="margin-top: 20px;"></div>',
        ground_truth="NEEDS_REVIEW",
        notes="Focus may be obscured by fixed header overlay depending on scroll position.",
    ),
    # 5. ARIA
    EvaluationTestCase(
        case_id="ARIA-01",
        category="aria",
        split="calibration",
        wcag_criterion="4.1.2",
        rule_id="button-name",
        html='<button><svg></svg></button>',
        ground_truth="FAIL",
        expected_severity="critical",
        notes="Icon-only button missing aria-label or accessible name.",
    ),
    # 6. Forms
    EvaluationTestCase(
        case_id="FRM-01",
        category="forms",
        split="development",
        wcag_criterion="3.3.2",
        rule_id="input-label",
        html='<input type="text" placeholder="Your name">',
        ground_truth="FAIL",
        expected_severity="moderate",
        notes="Input relies on placeholder alone without associated <label>.",
    ),
    EvaluationTestCase(
        case_id="FRM-02",
        category="forms",
        split="held-out",
        wcag_criterion="3.3.7",
        rule_id="redundant-entry",
        html='<form><input id="shipping_zip"><input id="billing_zip"></form>',
        ground_truth="NEEDS_REVIEW",
        notes="Repeated zip code entry requires verification of auto-populate or copy option.",
    ),
    # 7. Landmarks
    EvaluationTestCase(
        case_id="LND-01",
        category="landmarks",
        split="calibration",
        wcag_criterion="1.3.1",
        rule_id="landmark-one-main",
        html='<body><main id="m1"></main><main id="m2"></main></body>',
        ground_truth="FAIL",
        expected_severity="moderate",
        notes="Document contains more than one top-level <main> landmark.",
    ),
    # 8. Keyboard
    EvaluationTestCase(
        case_id="KEY-01",
        category="keyboard",
        split="development",
        wcag_criterion="2.1.2",
        rule_id="keyboard-trap",
        html='<div onkeydown="event.preventDefault()">Trapped</div>',
        ground_truth="FAIL",
        expected_severity="critical",
        notes="Modal traps keyboard focus without escape mechanism.",
    ),
    # 9. Authentication
    EvaluationTestCase(
        case_id="AUTH-01",
        category="authentication",
        split="held-out",
        wcag_criterion="3.3.8",
        rule_id="accessible-auth",
        html='<input type="password" onpaste="return false;">',
        ground_truth="FAIL",
        expected_severity="serious",
        notes="Password field blocks copy/paste from password managers.",
    ),
    # 10. Multimedia
    EvaluationTestCase(
        case_id="MED-01",
        category="multimedia",
        split="calibration",
        wcag_criterion="1.2.2",
        rule_id="video-captions",
        html='<video src="clip.mp4"></video>',
        ground_truth="FAIL",
        expected_severity="critical",
        notes="Prerecorded video missing captions track.",
    ),
    # 11. COGA
    EvaluationTestCase(
        case_id="COG-01",
        category="coga",
        split="held-out",
        wcag_criterion="3.2.6",
        rule_id="consistent-help",
        html='<footer><a href="/help">Help Desk</a></footer>',
        ground_truth="PASS",
        notes="Help mechanism present in standard footer position across templates.",
    ),
]


def get_evaluation_corpus(split: str | None = None) -> list[dict[str, Any]]:
    """Returns the evaluation corpus, optionally filtered by dataset split (§60)."""
    if split:
        norm_split = split.strip().lower()
        return [c.to_dict() for c in CANONICAL_EVALUATION_CORPUS if c.split == norm_split]
    return [c.to_dict() for c in CANONICAL_EVALUATION_CORPUS]


def calculate_benchmark_metrics(evaluation_results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Computes rigorous empirical benchmark metrics (§61).
    Mathematical Guarantee:
      TP + TN + FP + FN + NEEDS_REVIEW == TOTAL_CASES.
    """
    tp = 0
    tn = 0
    fp = 0
    fn = 0
    needs_review = 0

    wcag_mapped_correctly = 0
    sandbox_regressions_detected = 0
    total_sandbox_checks = 0

    total_cases = len(evaluation_results)

    for item in evaluation_results:
        ground_truth = str(item.get("ground_truth", "")).upper()
        predicted = str(item.get("predicted", "")).upper()

        if item.get("wcag_correct", True):
            wcag_mapped_correctly += 1

        if "sandbox_regression" in item:
            total_sandbox_checks += 1
            if item["sandbox_regression"] is True:
                sandbox_regressions_detected += 1

        if predicted == "NEEDS_REVIEW":
            needs_review += 1
        elif ground_truth == "FAIL":
            if predicted == "FAIL":
                tp += 1
            else:
                fn += 1
        elif ground_truth == "PASS":
            if predicted == "PASS":
                tn += 1
            else:
                fp += 1
        else:
            # Ground truth itself is NEEDS_REVIEW
            needs_review += 1

    # Exact mathematical verification
    accounted_cases = tp + tn + fp + fn + needs_review
    assert accounted_cases == total_cases, f"Accounting error: {accounted_cases} != {total_cases}"

    binary_decided = tp + tn + fp + fn

    # Detection / Adjudication metrics
    precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    fp_rate = (fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fn_rate = (fn / (fn + tp)) if (fn + tp) > 0 else 0.0
    needs_review_rate = (needs_review / total_cases) if total_cases > 0 else 0.0

    mapping_accuracy = (wcag_mapped_correctly / total_cases) if total_cases > 0 else 1.0

    return {
        "accounting": {
            "total_cases": total_cases,
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
            "needs_review": needs_review,
            "binary_decided_cases": binary_decided,
        },
        "adjudication_metrics": {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1, 4),
            "false_positive_rate": round(fp_rate, 4),
            "false_negative_rate": round(fn_rate, 4),
            "needs_review_rate": round(needs_review_rate, 4),
        },
        "coverage_and_accuracy": {
            "automation_coverage_rate": round(binary_decided / total_cases, 4) if total_cases > 0 else 0.0,
            "wcag_mapping_accuracy": round(mapping_accuracy, 4),
            "sandbox_regression_detection_rate": round(
                (sandbox_regressions_detected / total_sandbox_checks), 4
            ) if total_sandbox_checks > 0 else 1.0,
        },
    }
