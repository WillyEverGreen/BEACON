"""
Input validation utilities for API requests.

This module provides validation functions for common inputs like URLs,
scan modes, and other user-provided data to prevent injection attacks
and ensure data integrity.
"""

import logging
import re
from urllib.parse import urlparse

from pydantic import BaseModel, Field, validator

from app.models.errors import ValidationError

logger = logging.getLogger(__name__)

# ============================================================================
# URL Validation
# ============================================================================

# Allowed URL schemes
ALLOWED_SCHEMES = {"http", "https"}

# Blocked domains (example - add malicious/test domains)
BLOCKED_DOMAINS: set[str] = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "[::]",
    # Add more blocked domains as needed
}

# Blocked IP ranges (private/internal)
PRIVATE_IP_PATTERNS = [
    r"^10\.",  # 10.0.0.0/8
    r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",  # 172.16.0.0/12
    r"^192\.168\.",  # 192.168.0.0/16
    r"^169\.254\.",  # 169.254.0.0/16 (link-local)
    r"^fd[0-9a-f]{2}:",  # IPv6 ULA
    r"^fe80:",  # IPv6 link-local
]


def validate_url(url: str, allow_local: bool = False) -> str:
    """
    Validate and sanitize a URL.
    
    Args:
        url: URL to validate
        allow_local: If True, allow localhost/private IPs (for development)
        
    Returns:
        Validated URL
        
    Raises:
        ValidationError: If URL is invalid or blocked
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL is required", field="url")
    
    # Strip whitespace
    url = url.strip()
    
    # Check length
    if len(url) > 2048:
        raise ValidationError(
            "URL is too long (max 2048 characters)",
            field="url",
            details={"length": len(url)}
        )
    
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise ValidationError(
            f"Invalid URL format: {exc!s}",
            field="url"
        )
    
    # Validate scheme
    if not parsed.scheme:
        raise ValidationError("URL must include a scheme (http:// or https://)", field="url")
    
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise ValidationError(
            f"URL scheme '{parsed.scheme}' not allowed. Use http or https.",
            field="url",
            details={"allowed_schemes": list(ALLOWED_SCHEMES)}
        )
    
    # Validate hostname
    if not parsed.netloc:
        raise ValidationError("URL must include a hostname", field="url")
    
    hostname = parsed.netloc.split(":")[0].lower()  # Remove port
    
    # Check for blocked domains (unless allow_local is True)
    if not allow_local:
        if hostname in BLOCKED_DOMAINS:
            raise ValidationError(
                f"URL domain '{hostname}' is not allowed",
                field="url",
                details={"reason": "blocked_domain"}
            )
        
        # Check for private IP ranges
        for pattern in PRIVATE_IP_PATTERNS:
            if re.match(pattern, hostname):
                raise ValidationError(
                    f"Private IP addresses are not allowed: {hostname}",
                    field="url",
                    details={"reason": "private_ip"}
                )
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r"[<>\"']",  # HTML/script injection
        r"javascript:",  # JavaScript protocol
        r"data:",  # Data URLs
        r"file:",  # File protocol
        r"\.\.\/",  # Path traversal
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            raise ValidationError(
                "URL contains suspicious characters or patterns",
                field="url",
                details={"pattern": pattern}
            )
    
    return url


def validate_url_list(
    urls: list[str],
    max_count: int = 100,
    allow_local: bool = False
) -> list[str]:
    """
    Validate a list of URLs.
    
    Args:
        urls: List of URLs to validate
        max_count: Maximum number of URLs allowed
        allow_local: If True, allow localhost/private IPs
        
    Returns:
        List of validated URLs
        
    Raises:
        ValidationError: If any URL is invalid or list is too long
    """
    if not urls:
        raise ValidationError("At least one URL is required", field="urls")
    
    if not isinstance(urls, list):
        raise ValidationError("URLs must be provided as a list", field="urls")
    
    if len(urls) > max_count:
        raise ValidationError(
            f"Too many URLs (max {max_count})",
            field="urls",
            details={"count": len(urls), "max": max_count}
        )
    
    validated_urls = []
    errors = []
    
    for i, url in enumerate(urls):
        try:
            validated_url = validate_url(url, allow_local=allow_local)
            validated_urls.append(validated_url)
        except ValidationError as exc:
            errors.append(f"URL {i + 1}: {exc.message}")
    
    if errors:
        raise ValidationError(
            f"Invalid URLs: {'; '.join(errors)}",
            field="urls",
            details={"errors": errors}
        )
    
    return validated_urls


# ============================================================================
# Scan Mode Validation
# ============================================================================

VALID_SCAN_MODES = {
    "quick",
    "comprehensive",
    "deep",
    "custom"
}


def validate_scan_mode(scan_mode: str) -> str:
    """
    Validate scan mode.
    
    Args:
        scan_mode: Scan mode to validate
        
    Returns:
        Validated scan mode
        
    Raises:
        ValidationError: If scan mode is invalid
    """
    if not scan_mode:
        raise ValidationError("Scan mode is required", field="scan_mode")
    
    scan_mode = scan_mode.lower().strip()
    
    if scan_mode not in VALID_SCAN_MODES:
        raise ValidationError(
            f"Invalid scan mode: {scan_mode}",
            field="scan_mode",
            details={"valid_modes": list(VALID_SCAN_MODES)}
        )
    
    return scan_mode


# ============================================================================
# String Validation
# ============================================================================

def validate_string(
    value: str,
    field_name: str,
    min_length: int = 1,
    max_length: int = 1000,
    pattern: str | None = None,
    allow_empty: bool = False
) -> str:
    """
    Validate a string input.
    
    Args:
        value: String to validate
        field_name: Name of the field (for error messages)
        min_length: Minimum length
        max_length: Maximum length
        pattern: Optional regex pattern to match
        allow_empty: If True, allow empty strings
        
    Returns:
        Validated string
        
    Raises:
        ValidationError: If string is invalid
    """
    if value is None:
        if allow_empty:
            return ""
        raise ValidationError(f"{field_name} is required", field=field_name)
    
    if not isinstance(value, str):
        raise ValidationError(
            f"{field_name} must be a string",
            field=field_name,
            details={"type": type(value).__name__}
        )
    
    # Strip whitespace
    value = value.strip()
    
    # Check length
    if not allow_empty and len(value) < min_length:
        raise ValidationError(
            f"{field_name} is too short (min {min_length} characters)",
            field=field_name,
            details={"length": len(value), "min": min_length}
        )
    
    if len(value) > max_length:
        raise ValidationError(
            f"{field_name} is too long (max {max_length} characters)",
            field=field_name,
            details={"length": len(value), "max": max_length}
        )
    
    # Check pattern
    if pattern and value:
        if not re.match(pattern, value):
            raise ValidationError(
                f"{field_name} does not match required pattern",
                field=field_name,
                details={"pattern": pattern}
            )
    
    return value


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and injection.
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        Sanitized filename
        
    Raises:
        ValidationError: If filename is invalid
    """
    if not filename:
        raise ValidationError("Filename is required", field="filename")
    
    # Remove path separators and dangerous characters
    dangerous_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(dangerous_chars, "_", filename)
    
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip(". ")
    
    # Check for reserved names (Windows)
    reserved_names = {
        "CON", "PRN", "AUX", "NUL",
        "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
        "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    }
    
    base_name = sanitized.split(".")[0].upper()
    if base_name in reserved_names:
        sanitized = f"_{sanitized}"
    
    # Check length
    if len(sanitized) > 255:
        raise ValidationError(
            "Filename is too long (max 255 characters)",
            field="filename",
            details={"length": len(sanitized)}
        )
    
    if not sanitized:
        raise ValidationError("Filename is empty after sanitization", field="filename")
    
    return sanitized


# ============================================================================
# Pydantic Models for Request Validation
# ============================================================================

class AuditRequestValidator(BaseModel):
    """Validator for audit request payloads."""
    
    url: str = Field(..., description="URL to audit")
    scan_mode: str = Field("comprehensive", description="Scan mode")
    max_pages: int | None = Field(None, ge=1, le=1000, description="Max pages to scan")
    include_screenshots: bool = Field(False, description="Include screenshots")
    
    @validator("url")
    def validate_url_field(cls, v):
        """Validate URL field."""
        return validate_url(v, allow_local=False)
    
    @validator("scan_mode")
    def validate_scan_mode_field(cls, v):
        """Validate scan mode field."""
        return validate_scan_mode(v)
    
    class Config:
        """Pydantic config."""
        str_strip_whitespace = True
        str_min_length = 1


class BulkAuditRequestValidator(BaseModel):
    """Validator for bulk audit request payloads."""
    
    urls: list[str] = Field(..., min_items=1, max_items=100, description="URLs to audit")
    scan_mode: str = Field("comprehensive", description="Scan mode")
    max_pages: int | None = Field(None, ge=1, le=100, description="Max pages per site")
    
    @validator("urls")
    def validate_urls_field(cls, v):
        """Validate URLs field."""
        return validate_url_list(v, max_count=100, allow_local=False)
    
    @validator("scan_mode")
    def validate_scan_mode_field(cls, v):
        """Validate scan mode field."""
        return validate_scan_mode(v)
    
    class Config:
        """Pydantic config."""
        str_strip_whitespace = True
