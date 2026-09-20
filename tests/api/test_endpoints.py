import os
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Cleanly mock optional heavy ML modules only if not installed
try:
    import sentence_transformers
except ImportError:
    import sys
    sys.modules['sentence_transformers'] = MagicMock()

try:
    import rag.model_registry
except ImportError:
    import sys
    sys.modules['rag.model_registry'] = MagicMock()

from app.main import app
from app.config import settings

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
