import sys
from unittest.mock import MagicMock, patch
import os

# 1. SETUP MOCKS BEFORE ANY IMPORTS
test_auth_path = os.path.abspath("auth_store_test_temp.json")

# Mock settings
mock_settings = MagicMock()
mock_settings.auth_enabled = True
mock_settings.bootstrap_viewer_api_key = "test-viewer-key"
mock_settings.bootstrap_auditor_api_key = "test-auditor-key"
mock_settings.bootstrap_admin_api_key = "test-admin-key"
mock_settings.auth_key_store_path = test_auth_path
mock_settings.vector_store = "mock"
mock_settings.llm_model = "mock"
mock_settings.embedding_model = "mock"
mock_settings.supabase_url = "https://mock.supabase.co"
mock_settings.supabase_key = "mock-key"
mock_settings.cors_origins = ["*"]
mock_settings.backend_log_level = "INFO"
mock_settings.schema_version = "3.1"

# Inject into sys.modules to prevent real imports
mock_config = MagicMock()
mock_config.settings = mock_settings
sys.modules['app.config'] = mock_config

# Mock heavy modules
mock_heavy = [
    'sentence_transformers',
    'app.services.vector_store',
    'app.services.ingestion',
    'app.services.audit_runner',
    'app.services.lighthouse_runner',
    'app.services.ibm_checker',
    'rag.model_registry',
    'app.observability.logging_setup',
    'app.observability.telemetry'
]
for mod in mock_heavy:
    sys.modules[mod] = MagicMock()

# 2. NOW IMPORT APP
import pytest
from fastapi.testclient import TestClient
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
    """Verify protected endpoint returns 401."""
    response = client.get("/history?url=https://test.com")
    assert response.status_code == 401

def test_non_existent_unauthorized():
    """Verify unknown route returns 401."""
    response = client.get("/this-route-does-not-exist")
    assert response.status_code == 401

def test_health_ready_schema():
    """Verify health ready schema."""
    with patch('app.db.supabase_client.get_supabase') as mock_sb:
        mock_sb.return_value.table.return_value.select.return_value.limit.return_value.execute.return_value = MagicMock()
        with patch('app.main.get_chunks_count', return_value=500):
            response = client.get("/health/ready")
            assert response.status_code == 200
            assert response.json()["status"] == "ready"

@pytest.fixture(scope="session", autouse=True)
def cleanup(request):
    """Cleanup temp file."""
    def remove_temp():
        if os.path.exists(test_auth_path):
            try:
                os.remove(test_auth_path)
            except:
                pass
    request.addfinalizer(remove_temp)

if __name__ == "__main__":
    pytest.main([__file__])
