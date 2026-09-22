"""
Environment variable validation for production deployments.

This module validates that all critical environment variables are set
and do not contain placeholder/example values that would indicate
misconfiguration.
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

# Patterns that indicate placeholder/example values
PLACEHOLDER_PATTERNS = [
    r"^(your|example|replace|change|update|set|add)[-_]",
    r"[-_](here|me|this|now|todo)$",
    r"^(xxx+|test|demo|sample)",
    r"^beacon[-_](viewer|auditor|admin)[-_]dev$",
    r"^(nvapi|sk|pk|Bearer)[-_]xxx+",
]


def is_placeholder_value(value: str) -> bool:
    """
    Check if a value appears to be a placeholder or example.
    
    Args:
        value: The environment variable value to check
        
    Returns:
        True if the value looks like a placeholder
    """
    if not value or value.strip() == "":
        return True
    
    value_lower = value.lower().strip()
    
    for pattern in PLACEHOLDER_PATTERNS:
        if re.search(pattern, value_lower, re.IGNORECASE):
            return True
    
    return False


def validate_production_env() -> tuple[bool, list[str]]:
    """
    Validate critical environment variables for production deployment.
    
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    environment = os.getenv("ENVIRONMENT", "development").lower()
    is_production = environment in ("production", "prod", "staging")
    
    # Critical environment variables that must be set
    critical_vars = {
        # LLM Configuration
        "NVIDIA_API_KEY": "LLM API key for accessibility fix generation",
        "LLM_MODEL": "LLM model identifier",
        "LLM_BASE_URL": "LLM API endpoint URL",
        
        # Database
        "SUPABASE_URL": "Supabase project URL",
        "SUPABASE_KEY": "Supabase anonymous/service key",
        
        # API Authentication
        "BOOTSTRAP_VIEWER_API_KEY": "API key for viewer role",
        "BOOTSTRAP_AUDITOR_API_KEY": "API key for auditor role",
        "BOOTSTRAP_ADMIN_API_KEY": "API key for admin role",
    }
    
    # Check each critical variable
    for var_name, description in critical_vars.items():
        value = os.getenv(var_name, "").strip()
        
        if not value:
            errors.append(
                f"❌ {var_name} is not set. Required: {description}"
            )
        elif is_placeholder_value(value):
            errors.append(
                f"⚠️  {var_name} appears to be a placeholder value: '{value[:20]}...'. "
                f"Required: {description}"
            )
    
    # Production-specific checks
    if is_production:
        # Ensure CORS is configured for production domains
        cors_origins = os.getenv("BACKEND_CORS_ORIGINS", "")
        if "localhost" in cors_origins or not cors_origins:
            errors.append(
                "⚠️  BACKEND_CORS_ORIGINS should not include 'localhost' in production. "
                "Set to your production frontend domain(s)."
            )
        
        # Ensure auth is enabled
        auth_enabled = os.getenv("AUTH_ENABLED", "true").lower()
        if auth_enabled not in ("true", "1", "yes"):
            errors.append(
                "❌ AUTH_ENABLED must be true in production for security."
            )
        
        # Check database URL is not SQLite
        db_url = os.getenv("DATABASE_URL", "")
        if "sqlite" in db_url.lower():
            errors.append(
                "⚠️  DATABASE_URL appears to use SQLite. "
                "Production should use PostgreSQL (Supabase)."
            )
    
    return len(errors) == 0, errors


def validate_or_exit():
    """
    Validate environment variables and exit if validation fails in production.
    
    This should be called during application startup.
    """
    is_valid, errors = validate_production_env()
    environment = os.getenv("ENVIRONMENT", "development").lower()
    is_production = environment in ("production", "prod", "staging")
    
    if not is_valid:
        logger.error("=" * 70)
        logger.error("ENVIRONMENT VALIDATION FAILED")
        logger.error("=" * 70)
        
        for error in errors:
            logger.error(error)
        
        logger.error("=" * 70)
        logger.error("Please set the required environment variables and restart.")
        logger.error("Refer to .env.example for the complete list of variables.")
        logger.error("=" * 70)
        
        if is_production:
            # Exit in production to prevent misconfigured deployment
            import sys
            sys.exit(1)
        else:
            # Just warn in development
            logger.warning(
                "Continuing in development mode despite validation errors. "
                "This would fail in production."
            )
    else:
        logger.info("✅ Environment validation passed")


def get_validation_report() -> dict:
    """
    Get a detailed validation report for debugging.
    
    Returns:
        Dictionary with validation status and details
    """
    is_valid, errors = validate_production_env()
    environment = os.getenv("ENVIRONMENT", "development")
    
    return {
        "is_valid": is_valid,
        "environment": environment,
        "error_count": len(errors),
        "errors": errors,
    }
