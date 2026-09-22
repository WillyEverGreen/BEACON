from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import importlib.util
import sys

# Cleanly mock optional heavy ML modules only if not installed
if not importlib.util.find_spec('sentence_transformers'):
    sys.modules['sentence_transformers'] = MagicMock()

if not importlib.util.find_spec('rag.model_registry'):
    sys.modules['rag.model_registry'] = MagicMock()

from app.config import settings
from app.main import app

client = TestClient(app)


def test_health_check_public():
    """Verify health is public."""
    with patch('app.main.get_chunks_count', return_value=123):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


def test_root_public():
    """Verify root is public."""
    response = client.get("/")
    assert response.status_code == 200
    assert "version" in response.json()


def test_protected_unauthorized():
    """Verify protected endpoint returns 401 when auth is enforced."""
    with patch.object(settings, "auth_enabled", True):
        response = client.get("/history?url=https://test.com")
        assert response.status_code == 401


def test_non_existent_unauthorized():
    """Verify unknown route returns 401 or 404."""
    with patch.object(settings, "auth_enabled", True):
        response = client.get("/this-route-does-not-exist")
        assert response.status_code in (401, 404)


def test_health_ready_schema():
    """Verify health ready schema."""
    with patch('app.db.supabase_client.get_supabase') as mock_sb:
        mock_sb.return_value.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        with patch('app.main.get_chunks_count', return_value=500):
            response = client.get("/health/ready")
            assert response.status_code == 200
            assert response.json()["status"] == "ready"


def test_export_scan_sarif_and_earl():
    """Verify SARIF and EARL export endpoints format output correctly."""
    mock_scan = {
        "id": "testscan1",
        "project_id": "proj1",
        "url": "https://example.com",
        "status": "completed",
        "score": 92,
        "issues": [
            {
                "id": "iss-1",
                "rule_id": "image-alt",
                "engine": "axe",
                "wcag_criterion": "1.1.1",
                "wcag_level": "A",
                "severity": "critical",
                "selector": "img#hero",
                "html_snippet": "<img id='hero'>",
                "description": "Image missing alt attribute",
                "confidence": 0.95,
                "confidence_sources": ["axe", "heuristics"],
                "act_rule_id": "23a2a8",
                "act_adjudicated": True,
            }
        ]
    }
    with patch.object(settings, "auth_enabled", False):
        with patch("app.routers.dashboard_api.get_scan_record", return_value=mock_scan):
            # SARIF
            resp_sarif = client.get("/v1/api/scans/proj1/testscan1/export/sarif")
            assert resp_sarif.status_code == 200
            assert "application/sarif+json" in resp_sarif.headers.get("content-type", "")
            sarif_json = resp_sarif.json()
            assert sarif_json["version"] == "2.1.0"
            assert len(sarif_json["runs"][0]["results"]) == 1

            # EARL
            resp_earl = client.get("/v1/api/scans/proj1/testscan1/export/earl")
            assert resp_earl.status_code == 200
            assert "application/ld+json" in resp_earl.headers.get("content-type", "")
            earl_json = resp_earl.json()
            assert "@graph" in earl_json

            # Markdown
            resp_md = client.get("/v1/api/scans/proj1/testscan1/export/markdown")
            assert resp_md.status_code == 200
            assert "Accessibility Audit Report" in resp_md.text

