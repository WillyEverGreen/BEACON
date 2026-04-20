"""
Feedback tracking and confidence recalibration.
Stores developer feedback (accepted/edited/rejected/ignored) and adjusts
confidence baselines over time.
"""
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)

# Local feedback storage
FEEDBACK_DIR = Path(__file__).resolve().parent.parent.parent / "feedback_data"
FEEDBACK_FILE = FEEDBACK_DIR / "feedback_log.json"
CALIBRATION_FILE = FEEDBACK_DIR / "confidence_calibration.json"


def _ensure_dir():
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def _load_feedback_log() -> list[dict]:
    """Load feedback history from disk."""
    _ensure_dir()
    if FEEDBACK_FILE.exists():
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load feedback log: {e}")
    return []


def _save_feedback_log(entries: list[dict]):
    """Save feedback history to disk."""
    _ensure_dir()
    try:
        with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save feedback log: {e}")


def _load_calibration() -> dict:
    """Load confidence calibration data."""
    _ensure_dir()
    if CALIBRATION_FILE.exists():
        try:
            with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load calibration: {e}")
    return {"version": 1, "rules": {}}


def _save_calibration(calibration: dict):
    """Save calibration data to disk."""
    _ensure_dir()
    try:
        with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
            json.dump(calibration, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save calibration: {e}")


def record_feedback(
    issue_id: str,
    rule_id: str = "",
    state: str = "ignored",
    edited_fix: Optional[str] = None,
    comment: Optional[str] = None,
) -> dict:
    """
    Record developer feedback for a suggested fix.
    
    States: accepted, edited, rejected, ignored
    """
    entries = _load_feedback_log()

    entry = {
        "issue_id": issue_id,
        "rule_id": rule_id,
        "state": state,
        "edited_fix": edited_fix,
        "comment": comment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    entries.append(entry)
    _save_feedback_log(entries)

    logger.info(f"Feedback recorded: issue={issue_id}, state={state}")

    return {
        "status": "recorded",
        "issue_id": issue_id,
        "message": f"Feedback '{state}' recorded for issue {issue_id}",
    }


def get_feedback_stats() -> dict:
    """Get aggregate feedback statistics."""
    entries = _load_feedback_log()

    stats = {
        "total": len(entries),
        "accepted": sum(1 for e in entries if e["state"] == "accepted"),
        "edited": sum(1 for e in entries if e["state"] == "edited"),
        "rejected": sum(1 for e in entries if e["state"] == "rejected"),
        "ignored": sum(1 for e in entries if e["state"] == "ignored"),
    }

    if stats["total"] > 0:
        stats["acceptance_rate"] = (stats["accepted"] + stats["edited"]) / stats["total"]
    else:
        stats["acceptance_rate"] = 0.0

    # Per-rule stats
    rule_stats = {}
    for entry in entries:
        rule_id = entry.get("rule_id", "unknown")
        if rule_id not in rule_stats:
            rule_stats[rule_id] = {"total": 0, "accepted": 0, "rejected": 0}
        rule_stats[rule_id]["total"] += 1
        if entry["state"] in ("accepted", "edited"):
            rule_stats[rule_id]["accepted"] += 1
        elif entry["state"] == "rejected":
            rule_stats[rule_id]["rejected"] += 1

    stats["per_rule"] = rule_stats
    return stats


def run_recalibration() -> dict:
    """
    Recalibrate confidence baselines based on feedback history.
    
    If acceptance rate for a rule < 0.3 → lower default confidence
    If acceptance rate for a rule > 0.8 → raise default confidence
    """
    entries = _load_feedback_log()
    calibration = _load_calibration()

    # Group by rule_id
    rule_feedback = {}
    for entry in entries:
        rule_id = entry.get("rule_id", "unknown")
        if rule_id not in rule_feedback:
            rule_feedback[rule_id] = {"accepted": 0, "total": 0}
        rule_feedback[rule_id]["total"] += 1
        if entry["state"] in ("accepted", "edited"):
            rule_feedback[rule_id]["accepted"] += 1

    # Recalibrate
    adjustments = {}
    for rule_id, counts in rule_feedback.items():
        if counts["total"] < 5:
            continue  # Need minimum sample size

        rate = counts["accepted"] / counts["total"]

        if rate < 0.3:
            adjustment = -0.1
        elif rate > 0.8:
            adjustment = 0.1
        else:
            adjustment = 0.0

        if adjustment != 0:
            current = calibration["rules"].get(rule_id, {}).get("adjustment", 0.0)
            new_adjustment = round(current + adjustment, 2)
            new_adjustment = max(-0.3, min(0.3, new_adjustment))  # Clamp

            calibration["rules"][rule_id] = {
                "adjustment": new_adjustment,
                "acceptance_rate": round(rate, 2),
                "sample_size": counts["total"],
                "last_calibrated": datetime.now(timezone.utc).isoformat(),
            }
            adjustments[rule_id] = new_adjustment

    if adjustments:
        calibration["version"] = calibration.get("version", 1) + 1
        _save_calibration(calibration)
        logger.info(f"Recalibration v{calibration['version']}: adjusted {len(adjustments)} rules")
    else:
        logger.info("Recalibration: no adjustments needed")

    return {
        "version": calibration["version"],
        "adjustments": adjustments,
        "total_feedback": len(entries),
    }


def get_confidence_adjustment(rule_id: str) -> float:
    """Get the confidence adjustment for a specific rule (from calibration)."""
    calibration = _load_calibration()
    rule_data = calibration.get("rules", {}).get(rule_id, {})
    return rule_data.get("adjustment", 0.0)
