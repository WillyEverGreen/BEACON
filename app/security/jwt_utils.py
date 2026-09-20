from typing import Optional
import logging
from fastapi import Header

logger = logging.getLogger(__name__)

def extract_user_id_from_jwt(supabase_token: Optional[str]) -> Optional[str]:
    """
    Extract user_id (sub claim) from a Supabase JWT.
    Does NOT verify signature — Supabase RLS handles authorization.
    Returns None if token is missing or malformed.
    """
    if not supabase_token:
        return None
    
    token = supabase_token.strip()
    if token.startswith("Bearer "):
        token = token[7:]
    
    try:
        import base64, json
        # JWT is three base64 parts: header.payload.signature
        parts = token.split(".")
        if len(parts) < 2:
            logger.warning("Malformed JWT: less than 2 parts")
            return None
            
        payload_part = parts[1]
        # Add padding if needed
        padding = 4 - len(payload_part) % 4
        if padding != 4:
            payload_part += "=" * padding
            
        payload = json.loads(base64.urlsafe_b64decode(payload_part))
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("JWT payload missing 'sub' claim")
        return user_id
    except Exception as e:
        logger.warning(f"Failed to extract user_id from JWT: {e}")
        return None

async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    x_supabase_token: Optional[str] = Header(None, alias="X-Supabase-Token")
) -> Optional[str]:
    """
    FastAPI dependency to extract user_id from various auth headers.
    Prioritizes X-Supabase-Token, falls back to Authorization: Bearer.
    """
    token = x_supabase_token or authorization
    return extract_user_id_from_jwt(token)
