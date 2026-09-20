"""
Unit tests for environment variable validation.
"""

import os
import pytest
from unittest.mock import patch

from app.core.env_validator import (
    is_placeholder_value,
    validate_production_env,
    get_validation_report,
)


class TestPlaceholderDetection:
    """Test placeholder value detection."""
    
    def test_detects_example_prefixes(self):
        """Should detect common placeholder prefixes."""
        assert is_placeholder_value("your-api-key-here")
        assert is_placeholder_value("example-project-id")
        assert is_placeholder_value("replace_me_viewer")
        assert is_placeholder_value("change-this-value")
        assert is_placeholder_value("set_your_key_here")
    
    def test_detects_example_suffixes(self):
        """Should detect common placeholder suffixes."""
        assert is_placeholder_value("api_key_here")
        assert is_placeholder_value("set-this-now")
        assert is_placeholder_value("update_me")
    
    def test_detects_test_demo_values(self):
        """Should detect test/demo placeholder values."""
        assert is_placeholder_value("xxx-api-key")
        assert is_placeholder_value("test-key-123")
        assert is_placeholder_value("demo-project")
        assert is_placeholder_value("sample-value")
    
    def test_detects_development_keys(self):
        """Should detect hardcoded development keys."""
        assert is_placeholder_value("beacon-viewer-dev")
        assert is_placeholder_value("beacon-auditor-dev")
        assert is_placeholder_value("beacon_admin_dev")
    
    def test_detects_empty_values(self):
        """Should detect empty or whitespace-only values."""
        assert is_placeholder_value("")
        assert is_placeholder_value("   ")
        assert is_placeholder_value("\t\n")
    
    def test_allows_valid_keys(self):
        """Should allow real API keys."""
        assert not is_placeholder_value("sk-proj-abc123def456")
        assert not is_placeholder_value("nvapi-DQaXr8F_hLmN2kP9sT4vW7yZ")
        assert not is_placeholder_value("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9")
        assert not is_placeholder_value("https://myproject.supabase.co")


class TestProductionValidation:
    """Test production environment validation."""
    
    @pytest.fixture
    def valid_env(self):
        """Valid production environment variables."""
        return {
            "ENVIRONMENT": "production",
            "NVIDIA_API_KEY": "nvapi-abc123xyz789",
            "LLM_MODEL": "meta/llama-3.1-70b-instruct",
            "LLM_BASE_URL": "https://integrate.api.nvidia.com/v1",
            "SUPABASE_URL": "https://myproject.supabase.co",
            "SUPABASE_KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid-key",
            "BOOTSTRAP_VIEWER_API_KEY": "viewer-secure-key-abc123",
            "BOOTSTRAP_AUDITOR_API_KEY": "auditor-secure-key-def456",
            "BOOTSTRAP_ADMIN_API_KEY": "admin-secure-key-ghi789",
            "BACKEND_CORS_ORIGINS": "https://beacon.example.com",
            "AUTH_ENABLED": "true",
            "DATABASE_URL": "postgresql://user:pass@host/db",
        }
    
    def test_valid_production_env_passes(self, valid_env):
        """Should pass with all valid production environment variables."""
        with patch.dict(os.environ, valid_env, clear=True):
            is_valid, errors = validate_production_env()
            assert is_valid
            assert len(errors) == 0
    
    def test_development_env_allows_missing_vars(self):
        """Development mode should be more permissive."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}, clear=True):
            is_valid, errors = validate_production_env()
            # Should fail but not crash
            assert not is_valid
            assert len(errors) > 0
    
    def test_detects_missing_llm_api_key(self, valid_env):
        """Should detect missing LLM API key."""
        env = valid_env.copy()
        del env["NVIDIA_API_KEY"]
        
        with patch.dict(os.environ, env, clear=True):
            is_valid, errors = validate_production_env()
            assert not is_valid
            assert any("NVIDIA_API_KEY" in error for error in errors)
    
    def test_detects_placeholder_api_keys(self, valid_env):
        """Should detect placeholder API keys."""
        env = valid_env.copy()
        env["BOOTSTRAP_ADMIN_API_KEY"] = "replace_me_admin"
        
        with patch.dict(os.environ, env, clear=True):
            is_valid, errors = validate_production_env()
            assert not is_valid
            assert any("BOOTSTRAP_ADMIN_API_KEY" in error and "placeholder" in error 
                      for error in errors)
    
    def test_detects_localhost_cors_in_production(self, valid_env):
        """Should warn about localhost in production CORS."""
        env = valid_env.copy()
        env["BACKEND_CORS_ORIGINS"] = "http://localhost:3000"
        
        with patch.dict(os.environ, env, clear=True):
            is_valid, errors = validate_production_env()
            assert not is_valid
            assert any("CORS" in error and "localhost" in error for error in errors)
    
    def test_detects_disabled_auth_in_production(self, valid_env):
        """Should require auth in production."""
        env = valid_env.copy()
        env["AUTH_ENABLED"] = "false"
        
        with patch.dict(os.environ, env, clear=True):
            is_valid, errors = validate_production_env()
            assert not is_valid
            assert any("AUTH_ENABLED" in error for error in errors)
    
    def test_detects_sqlite_in_production(self, valid_env):
        """Should warn about SQLite in production."""
        env = valid_env.copy()
        env["DATABASE_URL"] = "sqlite:///./beacon.db"
        
        with patch.dict(os.environ, env, clear=True):
            is_valid, errors = validate_production_env()
            assert not is_valid
            assert any("SQLite" in error for error in errors)
    
    def test_validates_all_bootstrap_keys(self, valid_env):
        """Should validate all three bootstrap API keys."""
        env = valid_env.copy()
        env["BOOTSTRAP_VIEWER_API_KEY"] = ""
        env["BOOTSTRAP_AUDITOR_API_KEY"] = "your-key-here"
        env["BOOTSTRAP_ADMIN_API_KEY"] = "xxx-admin-key"
        
        with patch.dict(os.environ, env, clear=True):
            is_valid, errors = validate_production_env()
            assert not is_valid
            # Should have errors for all three keys
            assert any("BOOTSTRAP_VIEWER_API_KEY" in error for error in errors)
            assert any("BOOTSTRAP_AUDITOR_API_KEY" in error for error in errors)
            assert any("BOOTSTRAP_ADMIN_API_KEY" in error for error in errors)


class TestValidationReport:
    """Test validation report generation."""
    
    def test_report_includes_environment(self):
        """Report should include environment name."""
        with patch.dict(os.environ, {"ENVIRONMENT": "staging"}, clear=True):
            report = get_validation_report()
            assert report["environment"] == "staging"
    
    def test_report_includes_validation_status(self):
        """Report should include validation status."""
        report = get_validation_report()
        assert "is_valid" in report
        assert isinstance(report["is_valid"], bool)
    
    def test_report_includes_error_count(self):
        """Report should include error count."""
        report = get_validation_report()
        assert "error_count" in report
        assert isinstance(report["error_count"], int)
    
    def test_report_includes_error_list(self):
        """Report should include list of errors."""
        report = get_validation_report()
        assert "errors" in report
        assert isinstance(report["errors"], list)
