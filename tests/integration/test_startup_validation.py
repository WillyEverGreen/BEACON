"""
Integration test for application startup with environment validation.
"""

import os
import pytest
from unittest.mock import patch
import sys


def test_startup_fails_with_missing_env_vars_in_production():
    """
    Application should fail to start in production with missing environment variables.
    """
    # Set production environment with missing critical vars
    test_env = {
        "ENVIRONMENT": "production",
        "AUTH_ENABLED": "true",
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        # Import after patching environment
        from app.core.env_validator import validate_or_exit
        
        # Should log errors but not exit in test (we're not actually in production)
        # In real production, this would call sys.exit(1)
        with patch('sys.exit') as mock_exit:
            validate_or_exit()
            # Verify it would have exited
            mock_exit.assert_called_once_with(1)


def test_startup_succeeds_with_valid_env_vars():
    """
    Application should start successfully with all required environment variables.
    """
    test_env = {
        "ENVIRONMENT": "development",
        "NVIDIA_API_KEY": "nvapi-test-key-abc123",
        "LLM_MODEL": "meta/llama-3.1-70b-instruct",
        "LLM_BASE_URL": "https://integrate.api.nvidia.com/v1",
        "SUPABASE_URL": "https://test-project.supabase.co",
        "SUPABASE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test-key",
        "BOOTSTRAP_VIEWER_API_KEY": "viewer-test-key-12345",
        "BOOTSTRAP_AUDITOR_API_KEY": "auditor-test-key-67890",
        "BOOTSTRAP_ADMIN_API_KEY": "admin-test-key-abcdef",
        "BACKEND_CORS_ORIGINS": "http://localhost:3000",
        "AUTH_ENABLED": "true",
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        from app.core.env_validator import validate_or_exit
        
        # Should not raise or exit
        try:
            validate_or_exit()
        except SystemExit:
            pytest.fail("validate_or_exit() raised SystemExit unexpectedly")


def test_config_loads_without_hardcoded_keys():
    """
    Config should not have hardcoded API keys, requiring environment variables.
    """
    test_env = {
        "BOOTSTRAP_VIEWER_API_KEY": "viewer-abc",
        "BOOTSTRAP_AUDITOR_API_KEY": "auditor-def",
        "BOOTSTRAP_ADMIN_API_KEY": "admin-ghi",
    }
    
    with patch.dict(os.environ, test_env, clear=True):
        # Reload config with test environment
        import importlib
        import app.config
        importlib.reload(app.config)
        
        from app.config import settings
        
        # Verify keys come from environment, not hardcoded
        assert settings.bootstrap_viewer_api_key == "viewer-abc"
        assert settings.bootstrap_auditor_api_key == "auditor-def"
        assert settings.bootstrap_admin_api_key == "admin-ghi"


def test_config_has_empty_defaults_not_hardcoded_keys():
    """
    Config defaults should be empty strings, not development keys.
    """
    # Import with minimal environment
    test_env = {"ENVIRONMENT": "development"}
    
    with patch.dict(os.environ, test_env, clear=True):
        import importlib
        import app.config
        importlib.reload(app.config)
        
        from app.config import Settings
        settings = Settings(_env_file=None)
        
        # Verify defaults are empty, not "beacon-*-dev"
        assert settings.bootstrap_viewer_api_key == ""
        assert settings.bootstrap_auditor_api_key == ""
        assert settings.bootstrap_admin_api_key == ""
        
        # These empty values should fail validation
        from app.core.env_validator import is_placeholder_value
        assert is_placeholder_value(settings.bootstrap_viewer_api_key)
        assert is_placeholder_value(settings.bootstrap_auditor_api_key)
        assert is_placeholder_value(settings.bootstrap_admin_api_key)
