"""
Global error handler middleware for consistent error responses.

This middleware catches all exceptions and converts them to standardized
ErrorResponse format with proper logging and status codes.
"""

import logging
import traceback
from typing import Callable
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError

from app.models.errors import (
    BeaconError,
    ErrorResponse,
    ErrorDetail,
    ValidationErrorDetail,
)

logger = logging.getLogger(__name__)


async def error_handler_middleware(request: Request, call_next: Callable):
    """
    Global error handling middleware that catches all exceptions
    and returns standardized error responses.
    """
    try:
        response = await call_next(request)
        return response
        
    except Exception as exc:
        return handle_exception(request, exc)


def handle_exception(request: Request, exc: Exception) -> JSONResponse:
    """
    Convert any exception to a standardized JSON error response.
    
    Args:
        request: The incoming request
        exc: The exception that was raised
        
    Returns:
        JSONResponse with standardized error format
    """
    # Get request ID if available
    request_id = getattr(request.state, "request_id", None)
    path = request.url.path
    
    # Handle BEACON custom exceptions
    if isinstance(exc, BeaconError):
        return handle_beacon_error(exc, request_id, path)
    
    # Handle FastAPI validation errors
    if isinstance(exc, RequestValidationError):
        return handle_validation_error(exc, request_id, path)
    
    # Handle Pydantic validation errors
    if isinstance(exc, PydanticValidationError):
        return handle_pydantic_validation_error(exc, request_id, path)
    
    # Handle Starlette HTTP exceptions
    if isinstance(exc, StarletteHTTPException):
        return handle_http_exception(exc, request_id, path)
    
    # Handle all other exceptions as internal server errors
    return handle_internal_error(exc, request_id, path)


def handle_beacon_error(exc: BeaconError, request_id: str | None, path: str) -> JSONResponse:
    """Handle custom BEACON exceptions."""
    logger.warning(
        f"BEACON error: {exc.code} - {exc.message}",
        extra={
            "error_code": exc.code,
            "status_code": exc.status_code,
            "details": exc.details,
        }
    )
    
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            details=exc.details if exc.details else None
        ),
        request_id=request_id,
        path=path
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(exclude_none=True)
    )


def handle_validation_error(
    exc: RequestValidationError,
    request_id: str | None,
    path: str
) -> JSONResponse:
    """Handle FastAPI request validation errors."""
    # Extract validation errors
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        errors.append(
            ErrorDetail(
                code="VALIDATION_ERROR",
                message=error["msg"],
                field=field if field else None,
                details={"type": error["type"]}
            )
        )
    
    logger.warning(
        f"Validation error: {len(errors)} field(s) invalid",
        extra={"errors": [e.model_dump() for e in errors]}
    )
    
    response = ValidationErrorDetail(
        errors=errors,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response.model_dump(exclude_none=True)
    )


def handle_pydantic_validation_error(
    exc: PydanticValidationError,
    request_id: str | None,
    path: str
) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        errors.append(
            ErrorDetail(
                code="VALIDATION_ERROR",
                message=error["msg"],
                field=field,
                details={"type": error["type"]}
            )
        )
    
    logger.warning(
        f"Pydantic validation error: {len(errors)} field(s) invalid",
        extra={"errors": [e.model_dump() for e in errors]}
    )
    
    response = ValidationErrorDetail(
        errors=errors,
        request_id=request_id
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=response.model_dump(exclude_none=True)
    )


def handle_http_exception(
    exc: StarletteHTTPException,
    request_id: str | None,
    path: str
) -> JSONResponse:
    """Handle Starlette HTTP exceptions."""
    logger.warning(
        f"HTTP exception: {exc.status_code} - {exc.detail}",
        extra={"status_code": exc.status_code}
    )
    
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=f"HTTP_{exc.status_code}",
            message=str(exc.detail)
        ),
        request_id=request_id,
        path=path
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=error_response.model_dump(exclude_none=True)
    )


def handle_internal_error(
    exc: Exception,
    request_id: str | None,
    path: str
) -> JSONResponse:
    """Handle unexpected internal errors."""
    # Log full exception with stack trace
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        exc_info=True,
        extra={
            "exception_type": type(exc).__name__,
            "exception_message": str(exc),
            "path": path,
        }
    )
    
    # Don't expose internal error details to clients in production
    import os
    is_production = os.getenv("ENVIRONMENT", "development").lower() in ("production", "prod")
    
    if is_production:
        message = "An internal server error occurred. Please try again later."
        details = None
    else:
        message = f"{type(exc).__name__}: {str(exc)}"
        details = {
            "traceback": traceback.format_exc().split("\n")
        }
    
    error_response = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_ERROR",
            message=message,
            details=details
        ),
        request_id=request_id,
        path=path
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_response.model_dump(exclude_none=True)
    )
