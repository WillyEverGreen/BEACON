"""
Legacy SQLAlchemy base wrapper. 
DEPRECATED: Shifting to Supabase SDK completely.
"""
from contextlib import contextmanager

def init_db() -> None:
    """No-op for Supabase migration."""
    pass

def ensure_db_ready() -> None:
    """No-op for Supabase migration."""
    pass

@contextmanager
def get_session():
    """
    Deprecated: Do not use this. Use get_supabase() instead.
    Provided only to prevent immediate import errors during migration.
    """
    yield None
