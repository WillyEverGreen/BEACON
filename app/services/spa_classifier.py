"""SPA classification layer based on multiple runtime signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping


ConfidenceLabel = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class SPASignalSnapshot:
    """Normalized SPA signal payload used by the classifier."""

    strict_framework: str | None = None
    legacy_framework: str | None = None
    hydration_waited: bool = False

    history_state_ops: int = 0
    route_marker_count: int = 0

    dom_mutation_count: int = 0
    dom_nodes_added: int = 0
    dom_nodes_delta: int = 0
    dom_text_delta: int = 0

    script_count: int = 0
    shell_root_detected: bool = False
    body_text_length: int = 0
    body_child_count: int = 0

    @classmethod
    def from_mapping(cls, payload: Mapping[str, Any]) -> "SPASignalSnapshot":
        return cls(
            strict_framework=_as_str_or_none(payload.get("strict_framework")),
            legacy_framework=_as_str_or_none(payload.get("legacy_framework")),
            hydration_waited=_as_bool(payload.get("hydration_waited")),
            history_state_ops=_as_int(payload.get("history_state_ops")),
            route_marker_count=_as_int(payload.get("route_marker_count")),
            dom_mutation_count=_as_int(payload.get("dom_mutation_count")),
            dom_nodes_added=_as_int(payload.get("dom_nodes_added")),
            dom_nodes_delta=_as_int(payload.get("dom_nodes_delta")),
            dom_text_delta=_as_int(payload.get("dom_text_delta")),
            script_count=_as_int(payload.get("script_count")),
            shell_root_detected=_as_bool(payload.get("shell_root_detected")),
            body_text_length=_as_int(payload.get("body_text_length")),
            body_child_count=_as_int(payload.get("body_child_count")),
        )


def classify_spa(snapshot: SPASignalSnapshot | Mapping[str, Any]) -> dict[str, Any]:
    """
    Classify a page as SPA/non-SPA using positive + negative runtime signals.

    Output schema is intentionally stable for downstream reporting:
      - is_spa: bool
      - confidence: high | medium | low
      - signals: list[str]
    """
    snap = snapshot if isinstance(snapshot, SPASignalSnapshot) else SPASignalSnapshot.from_mapping(snapshot)

    positive_signals: list[str] = []
    negative_signals: list[str] = []
    score = 0

    strong_framework = (snap.strict_framework or "").strip().lower() or None
    if strong_framework:
        positive_signals.append(f"framework_detected:{strong_framework}")
        score += 4
    elif snap.legacy_framework and snap.hydration_waited:
        positive_signals.append(f"framework_hint:{snap.legacy_framework.lower()}")
        score += 1

    client_navigation = snap.history_state_ops >= 1 or snap.route_marker_count >= 2
    if client_navigation:
        positive_signals.append("client_navigation")
        score += 2
    else:
        negative_signals.append("no_client_side_routing")
        score -= 1

    dynamic_dom_change = (
        snap.dom_mutation_count >= 30
        or snap.dom_nodes_added >= 20
        or abs(snap.dom_nodes_delta) >= 30
        or abs(snap.dom_text_delta) >= 180
    )
    if dynamic_dom_change:
        positive_signals.append("dynamic_dom_change")
        score += 2
    else:
        negative_signals.append("no_dom_mutation")
        score -= 1

    client_shell = (
        snap.shell_root_detected
        and snap.script_count >= 12
        and snap.body_text_length < 1200
        and snap.body_child_count <= 20
    )
    if client_shell:
        positive_signals.append("client_shell")
        score += 1

    if snap.route_marker_count >= 3:
        positive_signals.append("route_markers")
        score += 1

    script_heavy_shell = (
        snap.script_count >= 24
        and snap.body_child_count <= 20
        and snap.body_text_length <= 2200
    )
    if script_heavy_shell:
        positive_signals.append("script_heavy_shell")
        score += 1

    if snap.hydration_waited:
        positive_signals.append("hydration_detected")
        score += 1

    dynamic_client_boot = (
        dynamic_dom_change
        and snap.script_count >= 10
        and snap.body_child_count <= 24
        and snap.body_text_length <= 8000
    )

    static_html_only = (
        snap.script_count <= 7
        and snap.body_text_length >= 260
        and snap.body_child_count >= 12
        and not client_shell
        and not dynamic_dom_change
        and snap.history_state_ops == 0
        and snap.route_marker_count == 0
    )
    if static_html_only:
        negative_signals.append("static_html_only")
        score -= 3

    is_spa = False
    if strong_framework and (client_navigation or dynamic_dom_change or snap.hydration_waited or client_shell):
        is_spa = True
    elif client_navigation and (dynamic_dom_change or client_shell):
        is_spa = True
    elif strong_framework and score >= 2 and not static_html_only:
        is_spa = True
    elif strong_framework and not static_html_only and score >= 4:
        is_spa = True
    elif dynamic_client_boot:
        is_spa = True
    elif script_heavy_shell and (dynamic_dom_change or snap.body_text_length <= 1500):
        is_spa = True
    elif client_shell and snap.script_count >= 18 and (client_navigation or snap.route_marker_count >= 2):
        is_spa = True

    confidence: ConfidenceLabel
    if is_spa:
        if strong_framework and (client_navigation or dynamic_dom_change):
            confidence = "high"
        elif client_navigation and dynamic_dom_change:
            confidence = "high"
        elif dynamic_client_boot or script_heavy_shell:
            confidence = "medium"
        elif strong_framework or client_shell:
            confidence = "medium"
        else:
            confidence = "low"
    else:
        if static_html_only and not client_navigation and not dynamic_dom_change:
            confidence = "high"
        elif not strong_framework and (not client_navigation or not dynamic_dom_change):
            confidence = "medium"
        else:
            confidence = "low"

    framework_out = strong_framework if strong_framework else None
    if framework_out is None and is_spa and snap.legacy_framework:
        framework_out = snap.legacy_framework.lower()

    return {
        "is_spa": bool(is_spa),
        "confidence": confidence,
        "signals": positive_signals + negative_signals,
        "framework": framework_out,
        "evidence": {
            "history_state_ops": snap.history_state_ops,
            "route_marker_count": snap.route_marker_count,
            "dom_mutation_count": snap.dom_mutation_count,
            "dom_nodes_added": snap.dom_nodes_added,
            "dom_nodes_delta": snap.dom_nodes_delta,
            "dom_text_delta": snap.dom_text_delta,
            "script_count": snap.script_count,
            "shell_root_detected": snap.shell_root_detected,
            "body_text_length": snap.body_text_length,
            "body_child_count": snap.body_child_count,
            "hydration_waited": snap.hydration_waited,
            "strict_framework": strong_framework,
            "legacy_framework": snap.legacy_framework,
            "score": score,
        },
    }


def compute_confusion_matrix(rows: list[tuple[bool, bool]]) -> dict[str, int]:
    """Compute TP/FP/FN/TN from (truth, predicted) pairs."""
    tp = fp = fn = tn = 0
    for truth, predicted in rows:
        if truth and predicted:
            tp += 1
        elif not truth and predicted:
            fp += 1
        elif truth and not predicted:
            fn += 1
        else:
            tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision_recall(confusion: Mapping[str, int]) -> tuple[float, float]:
    """Return precision and recall from confusion matrix."""
    tp = int(confusion.get("tp", 0))
    fp = int(confusion.get("fp", 0))
    fn = int(confusion.get("fn", 0))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return precision, recall


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _as_bool(value: Any) -> bool:
    return bool(value)


def _as_str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
