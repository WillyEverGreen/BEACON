"""
Standardized error models and exception handling for the BEACON API.

This module provides consistent error response formats across all endpoints
and custom exception classes for different error scenarios.
"""

from typing import Optional, Any, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """
    Detailed error information for a single error.
    """
    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    field: Optional[str] = Field(None, description="Field name for validation errors")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error context")


class ErrorResponse(BaseModel):
    """
    Standard error response format for all API errors.
    
    This ensures consistent error handling across the application and
    makes it easier for clients to parse and display errors.
    """
    error: ErrorDetail = Field(..., description="Error details")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
        description="ISO 8601 timestamp of when the error occurred"
    )
    path: Optional[str] = Field(None, description="API path that generated the error")


class ValidationErrorDetail(BaseModel):
    """Details for validation errors with multiple fields."""
    errors: List[ErrorDetail] = Field(..., description="List of validation errors")
    request_id: Optional[str] = Field(None, description="Request ID for tracing")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )


# ============================================================================
# Custom Exception Classes
# ============================================================================

class BeaconError(Exception):
    """
    Base exception class for all BEACON-specific errors.
    
    All custom exceptions should inherit from this class to enable
    centralized error handling.
    """
    def __init__(
        self,
        message: str,
        code: str = "BEACON_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class ValidationError(BeaconError):
    """Raised when input validation fails."""
    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=422,
            details={**(details or {}), "field": field} if field else details
        )


class AuthenticationError(BeaconError):
    """Raised when authentication fails."""
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401,
            details=details
        )


class AuthorizationError(BeaconError):
    """Raised when user lacks required permissions."""
    def __init__(self, message: str = "Insufficient permissions", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403,
            details=details
        )


class ResourceNotFoundError(BeaconError):
    """Raised when a requested resource doesn't exist."""
    def __init__(self, resource: str, resource_id: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"{resource} not found: {resource_id}",
            code="RESOURCE_NOT_FOUND",
            status_code=404,
            details={**(details or {}), "resource": resource, "resource_id": resource_id}
        )


class RateLimitError(BeaconError):
    """Raised when rate limit is exceeded."""
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details={**(details or {}), "retry_after": retry_after}
        )


class ExternalServiceError(BeaconError):
    """Raised when an external service (LLM, Database, etc.) fails."""
    def __init__(
        self,
        service: str,
        message: str,
        is_retryable: bool = True,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"{service} error: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details={**(details or {}), "service": service, "retryable": is_retryable}
        )


class DatabaseError(BeaconError):
    """Raised when database operations fail."""
    def __init__(
        self,
        message: str,
        operation: str,
        is_retryable: bool = True,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Database error during {operation}: {message}",
            code="DATABASE_ERROR",
            status_code=503,
            details={**(details or {}), "operation": operation, "retryable": is_retryable}
        )


class AuditError(BeaconError):
    """Raised when audit execution fails."""
    def __init__(
        self,
        message: str,
        url: str,
        scan_mode: str,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Audit failed for {url}: {message}",
            code="AUDIT_ERROR",
            status_code=500,
            details={**(details or {}), "url": url, "scan_mode": scan_mode}
        )


class BrowserError(BeaconError):
    """Raised when browser automation fails."""
    def __init__(
        self,
        message: str,
        browser: str = "unknown",
        is_retryable: bool = False,
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=f"Browser error ({browser}): {message}",
            code="BROWSER_ERROR",
            status_code=500,
            details={**(details or {}), "browser": browser, "retryable": is_retryable}
        )


class ConfigurationError(BeaconError):
    """Raised when application is misconfigured."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"Configuration error: {message}",
            code="CONFIGURATION_ERROR",
            status_code=500,
            details=details
        )


# ============================================================================
# Error Code Mapping
# ============================================================================

ERROR_CODES = {
    # Client Errors (4xx)
    "VALIDATION_ERROR": 422,
    "AUTHENTICATION_ERROR": 401,
    "AUTHORIZATION_ERROR": 403,
    "RESOURCE_NOT_FOUND": 404,
    "RATE_LIMIT_EXCEEDED": 429,
    "INVALID_URL": 400,
    "INVALID_SCAN_MODE": 400,
    
    # Server Errors (5xx)
    "AUDIT_ERROR": 500,
    "BROWSER_ERROR": 500,
    "DATABASE_ERROR": 503,
    "EXTERNAL_SERVICE_ERROR": 502,
    "CONFIGURATION_ERROR": 500,
    "INTERNAL_ERROR": 500,
    "BEACON_ERROR": 500,
}


def get_status_code(error_code: str) -> int:
    """Get HTTP status code for an error code."""
    return ERROR_CODES.get(error_code, 500)
