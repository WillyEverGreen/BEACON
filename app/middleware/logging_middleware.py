"""
Middleware for request logging and context injection.

Automatically generates request IDs, tracks request/response timing,
and injects context into all log messages for the request.
"""

import logging
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logging_config import clear_request_context, set_request_context

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    - Generates unique request IDs
    - Injects request context into logs
    - Logs request/response information with timing
    - Excludes health check endpoints from verbose logging
    """
    
    def __init__(
        self,
        app: ASGIApp,
        exclude_paths: list[str] | None = None
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/health/live", "/health/ready", "/metrics"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Get user_id from request if available (from auth middleware)
        user_id = getattr(request.state, "user_id", None)
        
        # Set context for logging
        set_request_context(request_id=request_id, user_id=user_id)
        
        # Add request_id to request state for access in route handlers
        request.state.request_id = request_id
        
        # Check if this is an excluded path
        is_excluded = any(request.url.path.startswith(path) for path in self.exclude_paths)
        
        # Log request start (except for excluded paths)
        if not is_excluded:
            logger.info(
                f"Request started: {request.method} {request.url.path}",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "query_params": str(request.query_params),
                    "client_host": request.client.host if request.client else None,
                }
            )
        
        # Track timing
        start_time = time.perf_counter()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Add request_id to response headers
            response.headers["X-Request-ID"] = request_id
            
            # Log response (except for excluded paths)
            if not is_excluded:
                log_level = logging.INFO if response.status_code < 400 else logging.WARNING
                logger.log(
                    log_level,
                    f"Request completed: {request.method} {request.url.path} -> {response.status_code}",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "duration_ms": round(duration_ms, 2),
                    }
                )
            
            return response
            
        except Exception as exc:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log error
            logger.error(
                f"Request failed: {request.method} {request.url.path}",
                exc_info=True,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": round(duration_ms, 2),
                    "error": str(exc),
                }
            )
            
            # Re-raise to let error handlers deal with it
            raise
            
        finally:
            # Clear context
            clear_request_context()
