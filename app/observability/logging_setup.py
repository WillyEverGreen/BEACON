"""
Application logging setup with structured daily-rotated logs.

This module provides backward compatibility with the new centralized logging system.
"""

from __future__ import annotations

import logging
import os

from app.config import settings
from app.core.logging_config import setup_logging


def configure_logging() -> None:
    """
    Configure console + rotating file log handlers once.
    
    This function now delegates to the centralized logging configuration
    while maintaining backward compatibility.
    """
    root = logging.getLogger()
    if getattr(root, "_beacon_logging_configured", False):
        return
    
    # Get configuration from settings
    level_name = str(getattr(settings, "backend_log_level", "INFO")).upper()
    logs_dir = str(getattr(settings, "logs_dir", "./logs"))
    
    # Determine log format based on environment
    environment = os.getenv("ENVIRONMENT", "development").lower()
    log_format = "json" if environment in ("production", "staging") else "text"
    
    # Setup centralized logging
    setup_logging(
        log_level=level_name,
        log_format=log_format,
        logs_dir=logs_dir,
        app_name="beacon"
    )
    
    # Mark as configured
    root._beacon_logging_configured = True  # type: ignore
