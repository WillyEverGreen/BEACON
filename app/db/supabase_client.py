import logging
import os
import time
from typing import Optional

from app.config import settings
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

logger = logging.getLogger(__name__)

_client: Optional[Client] = None
_circuit_open_until: float = 0.0
_CIRCUIT_COOLDOWN_SECONDS: float = 60.0


def record_supabase_failure() -> None:
    """Record a failure and open the circuit breaker to prevent blocking."""
    global _circuit_open_until
    _circuit_open_until = time.time() + _CIRCUIT_COOLDOWN_SECONDS
    logger.warning(
        "Supabase circuit breaker OPENED for %ss due to connection failure. Falling back to local storage.",
        _CIRCUIT_COOLDOWN_SECONDS,
    )


def record_supabase_success() -> None:
    """Record a success and close the circuit breaker."""
    global _circuit_open_until
    _circuit_open_until = 0.0


def is_supabase_available() -> bool:
    """Check whether the circuit breaker allows trying Supabase."""
    return time.time() >= _circuit_open_until


def get_supabase() -> Client:
    """Get or initialize the Supabase client with safe 2s timeout options."""
    global _client
    if _client is None:
        url = settings.supabase_url
        key = settings.supabase_key
        if not url or not key:
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

        options = SyncClientOptions(
            postgrest_client_timeout=2.0,
            function_client_timeout=2.0,
            storage_client_timeout=2.0,
        )
        _client = create_client(url, key, options=options)
    return _client


def get_supabase_or_none() -> Optional[Client]:
    """Return Supabase client if circuit breaker is closed, else None."""
    if not is_supabase_available():
        return None
    try:
        return get_supabase()
    except Exception as exc:
        record_supabase_failure()
        return None

