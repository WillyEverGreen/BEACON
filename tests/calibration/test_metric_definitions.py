"""
Test canonical metric definitions.
Validates:
- p95 excludes degraded audits when configured
- p95 excludes timeout audits when configured
- p95 is consistent across suite configurations
"""
import math
import pytest
from app.config import METRIC_DEFINITIONS


def _percentile(values: list[float], p: float) -> float:
    """Compute percentile matching the prioritizer implementation."""
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    ordered = sorted(values)
    rank = (len(ordered) - 1) * p
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[int(rank)])
    weight = rank - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * weight)


def _apply_metric_filter(
    audit_results: list[dict],
    metric_name: str,
) -> list[float]:
    """Filter audit results according to METRIC_DEFINITIONS config."""
    config = METRIC_DEFINITIONS.get(metric_name, {})
    exclude_degraded = config.get("exclude_degraded", False)
    exclude_timeouts = config.get("exclude_timeouts", False)
    timeout_threshold = config.get("timeout_threshold_seconds", 30)

    filtered = []
    for result in audit_results:
        if exclude_degraded and result.get("degraded_mode", False):
            continue
        scan_time = result.get("scan_time_seconds", 0.0)
        if exclude_timeouts and scan_time >= timeout_threshold:
            continue
        if scan_time > 0:
            filtered.append(scan_time)
    return filtered


class TestMetricDefinitions:
    """Validate METRIC_DEFINITIONS configuration and behavior."""

    def test_fast_mode_p95_config_exists(self):
        assert "fast_mode_p95_time" in METRIC_DEFINITIONS
        config = METRIC_DEFINITIONS["fast_mode_p95_time"]
        assert config["scope"] == "successful_audits_only"
        assert config["exclude_degraded"] is True
        assert config["exclude_timeouts"] is True
        assert config["timeout_threshold_seconds"] == 30

    def test_p95_excludes_degraded_audits(self):
        results = [
            {"scan_time_seconds": 2.0, "degraded_mode": False},
            {"scan_time_seconds": 3.0, "degraded_mode": False},
            {"scan_time_seconds": 4.0, "degraded_mode": False},
            {"scan_time_seconds": 5.0, "degraded_mode": False},
            {"scan_time_seconds": 25.0, "degraded_mode": True},  # degraded → excluded
        ]
        filtered = _apply_metric_filter(results, "fast_mode_p95_time")
        assert len(filtered) == 4
        assert 25.0 not in filtered

        p95 = _percentile(filtered, 0.95)
        assert p95 <= 5.0

    def test_p95_excludes_timeout_audits(self):
        results = [
            {"scan_time_seconds": 2.0, "degraded_mode": False},
            {"scan_time_seconds": 3.0, "degraded_mode": False},
            {"scan_time_seconds": 4.0, "degraded_mode": False},
            {"scan_time_seconds": 35.0, "degraded_mode": False},  # timeout → excluded
            {"scan_time_seconds": 40.0, "degraded_mode": False},  # timeout → excluded
        ]
        filtered = _apply_metric_filter(results, "fast_mode_p95_time")
        assert len(filtered) == 3
        assert all(t < 30 for t in filtered)

    def test_p95_consistent_across_runs(self):
        """Deterministic — same input always gives same output."""
        results = [
            {"scan_time_seconds": 1.5, "degraded_mode": False},
            {"scan_time_seconds": 2.3, "degraded_mode": False},
            {"scan_time_seconds": 3.1, "degraded_mode": False},
            {"scan_time_seconds": 4.7, "degraded_mode": False},
            {"scan_time_seconds": 5.9, "degraded_mode": False},
        ]
        filtered_1 = _apply_metric_filter(results, "fast_mode_p95_time")
        filtered_2 = _apply_metric_filter(results, "fast_mode_p95_time")

        p95_1 = _percentile(filtered_1, 0.95)
        p95_2 = _percentile(filtered_2, 0.95)
        assert p95_1 == p95_2

    def test_empty_results_handled(self):
        filtered = _apply_metric_filter([], "fast_mode_p95_time")
        assert filtered == []
        p95 = _percentile(filtered, 0.95)
        assert p95 == 0.0

    def test_all_filtered_out(self):
        results = [
            {"scan_time_seconds": 35.0, "degraded_mode": True},
            {"scan_time_seconds": 40.0, "degraded_mode": True},
        ]
        filtered = _apply_metric_filter(results, "fast_mode_p95_time")
        assert filtered == []
