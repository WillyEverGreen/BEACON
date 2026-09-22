"""
Security middleware for CORS, rate limiting, and request validation.

This module provides production-grade security middleware including:
- CORS configuration with environment-based origins
- Rate limiting with sliding window algorithm
- Security headers
- Request size limits
"""

import logging
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.models.errors import RateLimitError

logger = logging.getLogger(__name__)


# ============================================================================
# CORS Configuration
# ============================================================================

def get_cors_origins() -> list[str]:
    """
    Get allowed CORS origins from environment configuration.
    
    Returns:
        List of allowed origin URLs
    """
    import os
    
    # Get CORS origins from environment (supporting both CORS_ORIGINS and BACKEND_CORS_ORIGINS)
    cors_origins_str = os.getenv("CORS_ORIGINS", "").strip()
    backend_cors_str = os.getenv("BACKEND_CORS_ORIGINS", "").strip()
    
    combined = []
    for raw in [cors_origins_str, backend_cors_str]:
        if raw:
            combined.extend([origin.strip() for origin in raw.split(",") if origin.strip()])
    
    # Deduplicate while preserving order
    origins = list(dict.fromkeys(combined))
    
    if not origins:
        # Default development origins
        logger.warning("CORS_ORIGINS / BACKEND_CORS_ORIGINS not configured, using development defaults")
        return [
            "http://localhost:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3000",
        ]
    
    logger.info(f"CORS configured with {len(origins)} origins: {origins}")
    return origins


def configure_cors(app) -> None:
    """
    Configure CORS middleware with production settings.
    
    Args:
        app: FastAPI application instance
    """
    origins = get_cors_origins()
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Request-ID",
            "Accept",
            "Origin",
            "User-Agent",
        ],
        expose_headers=[
            "X-Request-ID",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
        max_age=3600,  # Cache preflight requests for 1 hour
    )
    
    logger.info("CORS middleware configured")


# ============================================================================
# Rate Limiting
# ============================================================================

class RateLimiter:
    """
    Sliding window rate limiter with per-client tracking.
    
    Tracks request counts per client (identified by API key or IP)
    and enforces configurable rate limits.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        window_size: int = 60
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Max requests per minute per client
            requests_per_hour: Max requests per hour per client
            window_size: Size of sliding window in seconds
        """
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.window_size = window_size
        
        # Store request timestamps per client
        self.client_requests: dict[str, deque] = defaultdict(lambda: deque())
        
        # Last cleanup time
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # Clean up every 5 minutes
        
        logger.info(
            f"Rate limiter initialized: {requests_per_minute}/min, {requests_per_hour}/hr"
        )
    
    def _get_client_id(self, request: Request) -> str:
        """
        Get unique identifier for the client.
        
        Priority: API Key > IP Address
        """
        # Try to get API key from header
        api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization")
        if api_key:
            return f"key:{api_key[:16]}"  # Use first 16 chars
        
        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Use first IP in X-Forwarded-For chain
            client_ip = forwarded_for.split(",")[0].strip()
        
        return f"ip:{client_ip}"
    
    def _cleanup_old_entries(self) -> None:
        """Clean up old request timestamps to prevent memory growth."""
        current_time = time.time()
        
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        cutoff_time = current_time - 3600  # Keep last hour
        
        for client_id in list(self.client_requests.keys()):
            # Remove timestamps older than 1 hour
            while (
                self.client_requests[client_id] and
                self.client_requests[client_id][0] < cutoff_time
            ):
                self.client_requests[client_id].popleft()
            
            # Remove client if no recent requests
            if not self.client_requests[client_id]:
                del self.client_requests[client_id]
        
        self.last_cleanup = current_time
        logger.debug(f"Rate limiter cleanup: {len(self.client_requests)} active clients")
    
    def check_rate_limit(self, request: Request) -> tuple[bool, int | None, int, int]:
        """
        Check if request should be rate limited.
        
        Args:
            request: Incoming request
            
        Returns:
            Tuple of (is_allowed, retry_after, remaining, reset_time)
        """
        current_time = time.time()
        client_id = self._get_client_id(request)
        
        # Clean up old entries periodically
        self._cleanup_old_entries()
        
        # Get client's request history
        requests = self.client_requests[client_id]
        
        # Remove requests outside the minute window
        minute_cutoff = current_time - 60
        while requests and requests[0] < minute_cutoff:
            requests.popleft()
        
        # Count requests in last minute
        minute_count = len(requests)
        
        # Count requests in last hour
        hour_cutoff = current_time - 3600
        hour_count = sum(1 for ts in requests if ts >= hour_cutoff)
        
        # Check limits
        if minute_count >= self.requests_per_minute:
            # Calculate when the oldest request in the window will expire
            retry_after = int(requests[0] + 60 - current_time) + 1
            return False, retry_after, 0, int(requests[0] + 60)
        
        if hour_count >= self.requests_per_hour:
            # Find oldest request in the hour window
            oldest_in_hour = next((ts for ts in requests if ts >= hour_cutoff), current_time)
            retry_after = int(oldest_in_hour + 3600 - current_time) + 1
            return False, retry_after, 0, int(oldest_in_hour + 3600)
        
        # Request allowed, add timestamp
        requests.append(current_time)
        
        # Calculate remaining requests
        remaining = min(
            self.requests_per_minute - minute_count - 1,
            self.requests_per_hour - hour_count - 1
        )
        
        # Calculate when the limit resets
        reset_time = int(current_time + 60)
        
        return True, None, remaining, reset_time


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces rate limits on incoming requests.
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        exempt_paths: set[str] | None = None
    ):
        """
        Initialize rate limit middleware.
        
        Args:
            app: FastAPI application
            requests_per_minute: Max requests per minute per client
            requests_per_hour: Max requests per hour per client
            exempt_paths: Paths exempt from rate limiting (e.g., health checks)
        """
        super().__init__(app)
        self.limiter = RateLimiter(requests_per_minute, requests_per_hour)
        self.exempt_paths = exempt_paths or {"/health", "/", "/docs", "/openapi.json"}
        
        logger.info(f"Rate limit middleware initialized with {len(self.exempt_paths)} exempt paths")
    
    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for exempt paths
        if request.url.path in self.exempt_paths:
            return await call_next(request)
        
        # Check rate limit
        is_allowed, retry_after, remaining, reset_time = self.limiter.check_rate_limit(request)
        
        # Add rate limit headers to response
        response = None
        
        if not is_allowed:
            # Rate limit exceeded
            logger.warning(
                f"Rate limit exceeded for {self.limiter._get_client_id(request)}",
                extra={
                    "path": request.url.path,
                    "retry_after": retry_after,
                }
            )
            
            error = RateLimitError(
                message=f"Rate limit exceeded. Please try again in {retry_after} seconds.",
                retry_after=retry_after
            )
            
            response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": error.code,
                        "message": error.message,
                        "details": error.details
                    }
                }
            )
        else:
            # Process request normally
            response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit-Minute"] = str(self.limiter.requests_per_minute)
        response.headers["X-RateLimit-Limit-Hour"] = str(self.limiter.requests_per_hour)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        if retry_after:
            response.headers["Retry-After"] = str(retry_after)
        
        return response


# ============================================================================
# Security Headers Middleware
# ============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all responses.
    """
    
    async def dispatch(self, request: Request, call_next):
        """Add security headers to response."""
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # HSTS header (only in production with HTTPS)
        import os
        if os.getenv("ENVIRONMENT", "").lower() in ("production", "prod"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        
        return response


# ============================================================================
# Request Size Limit Middleware
# ============================================================================

class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces maximum request body size.
    """
    
    def __init__(self, app, max_size_mb: int = 10):
        """
        Initialize request size limit middleware.
        
        Args:
            app: FastAPI application
            max_size_mb: Maximum request size in megabytes
        """
        super().__init__(app)
        self.max_size = max_size_mb * 1024 * 1024  # Convert to bytes
        logger.info(f"Request size limit: {max_size_mb}MB")
    
    async def dispatch(self, request: Request, call_next):
        """Check request size before processing."""
        # Get content length from headers
        content_length = request.headers.get("content-length")
        
        if content_length and int(content_length) > self.max_size:
            logger.warning(
                f"Request size {int(content_length)} exceeds limit {self.max_size}",
                extra={"path": request.url.path}
            )
            
            return JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "REQUEST_TOO_LARGE",
                        "message": f"Request size exceeds maximum allowed size of {self.max_size // (1024 * 1024)}MB"
                    }
                }
            )
        
        return await call_next(request)
