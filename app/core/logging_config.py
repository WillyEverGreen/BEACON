"""
Centralized logging configuration for the BEACON application.

Provides structured logging with context injection, JSON formatting for production,
and request tracing capabilities.
"""

import json
import logging
import logging.handlers
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

# Context variables for request tracing
request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_ctx: ContextVar[str | None] = ContextVar("user_id", default=None)
audit_id_ctx: ContextVar[str | None] = ContextVar("audit_id", default=None)


class ContextualFormatter(logging.Formatter):
    """
    Formatter that includes contextual information (request_id, user_id, etc.)
    in log records.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # Add context variables to the record
        record.request_id = request_id_ctx.get()
        record.user_id = user_id_ctx.get()
        record.audit_id = audit_id_ctx.get()
        
        return super().format(record)


class JSONFormatter(logging.Formatter):
    """
    Formatter that outputs logs as JSON for structured logging in production.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add context if available
        if hasattr(record, "request_id") and record.request_id:
            log_data["request_id"] = record.request_id
        if hasattr(record, "user_id") and record.user_id:
            log_data["user_id"] = record.user_id
        if hasattr(record, "audit_id") and record.audit_id:
            log_data["audit_id"] = record.audit_id
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields from record
        for key, value in record.__dict__.items():
            if key not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info",
                "request_id", "user_id", "audit_id"
            ]:
                log_data[key] = value
        
        return json.dumps(log_data)


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "text",
    logs_dir: str | None = None,
    app_name: str = "beacon"
) -> None:
    """
    Setup application logging with contextual information.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format style ("text" or "json")
        logs_dir: Directory for log files (None to disable file logging)
        app_name: Application name for log files
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Choose formatter based on format type
    if log_format == "json":
        formatter = JSONFormatter()
    else:
        # Human-readable format for development
        fmt = (
            "%(asctime)s | %(levelname)-8s | "
            "%(name)s:%(funcName)s:%(lineno)d | "
            "%(message)s"
        )
        # Add context fields if available
        if request_id_ctx.get():
            fmt = f"[%(request_id)s] {fmt}"
        
        formatter = ContextualFormatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handlers if logs_dir is specified
    if logs_dir:
        logs_path = Path(logs_dir)
        logs_path.mkdir(parents=True, exist_ok=True)
        
        # Application log file (rotating)
        app_log_file = logs_path / f"{app_name}.log"
        file_handler = logging.handlers.RotatingFileHandler(
            app_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        
        # Error log file (errors and above only)
        error_log_file = logs_path / f"{app_name}.error.log"
        error_handler = logging.handlers.RotatingFileHandler(
            error_log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        root_logger.addHandler(error_handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    
    # Log startup message
    root_logger.info(
        f"Logging initialized: level={log_level}, format={log_format}, "
        f"file_logging={'enabled' if logs_dir else 'disabled'}"
    )


def set_request_context(
    request_id: str | None = None,
    user_id: str | None = None,
    audit_id: str | None = None
) -> None:
    """
    Set contextual information for the current request/operation.
    
    This information will be automatically included in all log messages
    within the same async context.
    
    Args:
        request_id: Unique identifier for the current request
        user_id: User performing the operation
        audit_id: Audit being processed
    """
    if request_id is not None:
        request_id_ctx.set(request_id)
    if user_id is not None:
        user_id_ctx.set(user_id)
    if audit_id is not None:
        audit_id_ctx.set(audit_id)


def clear_request_context() -> None:
    """Clear all contextual information."""
    request_id_ctx.set(None)
    user_id_ctx.set(None)
    audit_id_ctx.set(None)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    
    Args:
        name: Logger name (typically __name__ of the module)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
