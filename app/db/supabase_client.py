import os

from app.config import settings
from supabase import Client, create_client

_client: Client = None

def get_supabase() -> Client:
    """Get or initialize the Supabase client."""
    global _client
    if _client is None:
        url = settings.supabase_url
        key = settings.supabase_key
        if not url or not key:
            # Fallback to env directly if settings not reloaded
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_KEY")
            
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
            
        _client = create_client(url, key)
    return _client
