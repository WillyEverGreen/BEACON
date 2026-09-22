"""
Feedback Learning & Evaluation Dataset Engine (§55).

Stores and analyzes reviewer decisions:
- confirmed
- rejected
- needs_more_evidence
- fix_accepted
- fix_rejected

Used for:
- Rule tuning metrics & empirical false-positive analysis
- Confidence calibration adjustment
- Benchmark dataset creation

Strict Guardrail (§55):
- Never silently retrains production models from live feedback
- Exports immutable, versioned evaluation datasets for offline benchmarking
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

FEEDBACK_DECISIONS = {
    "confirmed",
    "rejected",
    "needs_more_evidence",
    "fix_accepted",
    "fix_rejected",
}

DEFAULT_STORAGE_PATH = Path(__file__).resolve().parent.parent.parent / "feedback_data" / "reviewer_decisions.json"


@dataclass
class ReviewerDecision:
    """Represents a human reviewer decision on a finding or fix (§55)."""
    finding_id: str
    rule_id: str
    decision: str  # One of FEEDBACK_DECISIONS
    wcag_criterion: str = ""
    reviewer_id: str = "qa_reviewer"
    comment: str | None = None
    selector: str | None = None
    html_snippet: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "decision": self.decision,
            "wcag_criterion": self.wcag_criterion,
            "reviewer_id": self.reviewer_id,
            "comment": self.comment,
            "selector": self.selector,
            "html_snippet": self.html_snippet,
            "timestamp": self.timestamp,
        }


class FeedbackLearningStore:
    """Manages reviewer decisions, rule-tuning metrics, and evaluation dataset export (§55)."""

    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or DEFAULT_STORAGE_PATH
        self._in_memory_decisions: list[ReviewerDecision] = []

    def record_decision(
        self,
        finding_id: str,
        rule_id: str,
        decision: str,
        *,
        wcag_criterion: str = "",
        reviewer_id: str = "qa_reviewer",
        comment: str | None = None,
        selector: str | None = None,
        html_snippet: str | None = None,
    ) -> dict[str, Any]:
        """Records a human QA/specialist review decision."""
        norm_decision = str(decision).strip().lower()
        if norm_decision not in FEEDBACK_DECISIONS:
            raise ValueError(f"Invalid feedback decision '{decision}'. Valid decisions: {sorted(list(FEEDBACK_DECISIONS))}")

        entry = ReviewerDecision(
            finding_id=finding_id,
            rule_id=rule_id,
            decision=norm_decision,
            wcag_criterion=wcag_criterion,
            reviewer_id=reviewer_id,
            comment=comment,
            selector=selector,
            html_snippet=html_snippet,
        )
        self._in_memory_decisions.append(entry)
        return entry.to_dict()

    def list_decisions(self, rule_id: str | None = None) -> list[dict[str, Any]]:
        """Returns recorded reviewer decisions, optionally filtered by rule_id."""
        if rule_id:
            return [d.to_dict() for d in self._in_memory_decisions if d.rule_id == rule_id]
        return [d.to_dict() for d in self._in_memory_decisions]

    def compute_rule_tuning_metrics(self) -> dict[str, Any]:
        """
        Computes empirical calibration and false-positive metrics per rule (§55).
        Identifies rules with high rejection rates for algorithmic tuning.
        """
        rule_stats: dict[str, dict[str, int]] = {}

        for d in self._in_memory_decisions:
            r = d.rule_id or "unknown"
            stats = rule_stats.setdefault(r, {
                "total_reviews": 0,
                "confirmed": 0,
                "rejected": 0,
                "needs_more_evidence": 0,
                "fix_accepted": 0,
                "fix_rejected": 0,
            })
            stats["total_reviews"] += 1
            if d.decision in stats:
                stats[d.decision] += 1

        tuning_report: dict[str, Any] = {}
        for rule, s in rule_stats.items():
            total = s["total_reviews"]
            fp_rate = (s["rejected"] / total) if total > 0 else 0.0
            fix_accept_rate = (s["fix_accepted"] / (s["fix_accepted"] + s["fix_rejected"])) if (s["fix_accepted"] + s["fix_rejected"]) > 0 else 1.0

            tuning_report[rule] = {
                "total_reviews": total,
                "confirmation_rate": round(s["confirmed"] / total, 3) if total > 0 else 0.0,
                "false_positive_rate": round(fp_rate, 3),
                "fix_acceptance_rate": round(fix_accept_rate, 3),
                "action_recommended": "TUNE_DOWN_WEIGHT" if fp_rate > 0.20 else "MAINTAIN",
            }

        return {
            "total_decisions_recorded": len(self._in_memory_decisions),
            "rules_evaluated_count": len(tuning_report),
            "rule_metrics": tuning_report,
            "policy": "No automated retraining of production models. Metrics exported for offline evaluation only.",
        }

    def export_versioned_evaluation_dataset(self, dataset_version: str = "v1.0") -> dict[str, Any]:
        """
        Exports an immutable versioned evaluation dataset from human decisions (§55).
        Allows regression and benchmark validation without mutating models.
        """
        test_cases = []
        for d in self._in_memory_decisions:
            ground_truth = "FAIL" if d.decision in {"confirmed", "fix_accepted"} else "PASS" if d.decision == "rejected" else "NEEDS_REVIEW"
            test_cases.append({
                "case_id": d.finding_id,
                "rule_id": d.rule_id,
                "wcag_criterion": d.wcag_criterion,
                "selector": d.selector,
                "html": d.html_snippet,
                "ground_truth": ground_truth,
                "reviewer_notes": d.comment,
            })

        return {
            "dataset_version": dataset_version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_cases": len(test_cases),
            "cases": test_cases,
        }


# Global singleton instance
feedback_learning_store = FeedbackLearningStore()
