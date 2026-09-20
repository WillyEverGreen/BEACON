import argparse
import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from scripts.run_detailed_audit_cli import _run_cli

@pytest.mark.asyncio
async def test_run_cli_fail_on_threshold(tmp_path):
    """Test that _run_cli returns 4 when the score is below the specified threshold."""
    args = argparse.Namespace(
        url="https://example.com",
        scan_mode="fast",
        max_pages=1,
        precision_profile="balanced",
        enable_enrichment=False,
        max_enrich_issues=20,
        disable_cognitive=True,
        await_enrichment=False,
        use_cache=False,
        run_id=None,
        output_dir=str(tmp_path),
        slug=None,
        show_top=25,
        fail_on_degraded=False,
        min_confidence=None,
        fail_on_threshold=80.0,
    )
    
    mock_result = {
        "url": "https://example.com",
        "scan_mode": "fast",
        "score": 75.0,  # Below threshold 80.0
        "score_raw": 75.0,
        "issues": [],
        "groups": [],
        "priority_ranking": [],
        "degraded_mode": False,
        "confidence_score": 0.9,
    }
    
    with patch("scripts.run_detailed_audit_cli.run_audit", new_callable=AsyncMock) as mock_audit:
        mock_audit.return_value = mock_result
        exit_code = await _run_cli(args)
        assert exit_code == 4


@pytest.mark.asyncio
async def test_run_cli_passes_above_threshold(tmp_path):
    """Test that _run_cli returns 0 when the score is at or above the threshold."""
    args = argparse.Namespace(
        url="https://example.com",
        scan_mode="fast",
        max_pages=1,
        precision_profile="balanced",
        enable_enrichment=False,
        max_enrich_issues=20,
        disable_cognitive=True,
        await_enrichment=False,
        use_cache=False,
        run_id=None,
        output_dir=str(tmp_path),
        slug=None,
        show_top=25,
        fail_on_degraded=False,
        min_confidence=None,
        fail_on_threshold=70.0,  # Below score 75.0
    )
    
    mock_result = {
        "url": "https://example.com",
        "scan_mode": "fast",
        "score": 75.0,
        "score_raw": 75.0,
        "issues": [],
        "groups": [],
        "priority_ranking": [],
        "degraded_mode": False,
        "confidence_score": 0.9,
    }
    
    with patch("scripts.run_detailed_audit_cli.run_audit", new_callable=AsyncMock) as mock_audit:
        mock_audit.return_value = mock_result
        exit_code = await _run_cli(args)
        assert exit_code == 0

