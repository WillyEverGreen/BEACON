"""API key authentication and role-based authorization middleware."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock

import bcrypt
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.config import settings

logger = logging.getLogger(__name__)

ROLE_ORDER = {
    "viewer": 1,
    "auditor": 2,
    "admin": 3,
}

_PUBLIC_PATH_PREFIXES = (
    "/",
    "/health",
    "/v1/config",
    "/docs",
    "/redoc",
    "/openapi.json",
)

_ADMIN_PATH_PREFIXES = (
    "/metrics",
    "/audit/cache/stats",
    "/ingest",
    "/test/trigger_alert",
    "/cache",
)


@dataclass(frozen=True)
class AuthResult:
    role: str
    label: str


class APIKeyStore:
    """JSON-backed API key registry with bcrypt verification."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self._lock = RLock()
        self._records: list[dict] = []
        self._mtime: float = 0.0

    def initialize(self) -> None:
        """Ensure key storage exists with bootstrap keys."""
        with self._lock:
            if os.path.exists(self.file_path):
                self._reload_locked(force=True)
                return

            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            now = datetime.now(timezone.utc).isoformat()
            payload = {
                "version": 1,
                "created_at": now,
                "keys": [
                    self._make_record("bootstrap-viewer", settings.bootstrap_viewer_api_key, "viewer", now),
                    self._make_record("bootstrap-auditor", settings.bootstrap_auditor_api_key, "auditor", now),
                    self._make_record("bootstrap-admin", settings.bootstrap_admin_api_key, "admin", now),
                ],
            }
            self._write_locked(payload)
            self._records = payload["keys"]
            self._mtime = os.path.getmtime(self.file_path)
            logger.warning(
                "Initialized API key store with bootstrap keys at %s. Rotate these keys before production use.",
                self.file_path,
            )

    def authenticate(self, raw_key: str) -> AuthResult | None:
        if not raw_key:
            return None

        with self._lock:
            self._reload_locked(force=False)
            for record in self._records:
                if bool(record.get("revoked", False)):
                    continue

                key_hash = str(record.get("key_hash", "")).encode("utf-8")
                if not key_hash:
                    continue

                try:
                    valid = bcrypt.checkpw(raw_key.encode("utf-8"), key_hash)
                except ValueError:
                    valid = False

                if valid:
                    role = str(record.get("role", ""))
                    label = str(record.get("label", "unknown"))
                    if role not in ROLE_ORDER:
                        continue
                    return AuthResult(role=role, label=label)

        return None

    def _reload_locked(self, *, force: bool) -> None:
        if not os.path.exists(self.file_path):
            return

        mtime = os.path.getmtime(self.file_path)
        if not force and mtime == self._mtime:
            return

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as exc:
            logger.error("Failed to load API key store: %s", exc)
            return

        keys = payload.get("keys", []) if isinstance(payload, dict) else []
        self._records = [k for k in keys if isinstance(k, dict)]
        self._mtime = mtime

    @staticmethod
    def _make_record(label: str, raw_key: str, role: str, created_at: str) -> dict:
        key_hash = bcrypt.hashpw(raw_key.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        return {
            "label": label,
            "role": role,
            "key_hash": key_hash,
            "created_at": created_at,
            "revoked": False,
        }

    def _write_locked(self, payload: dict) -> None:
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)


def has_required_role(actual_role: str, required_role: str) -> bool:
    return ROLE_ORDER.get(actual_role, 0) >= ROLE_ORDER.get(required_role, 99)


def required_role_for_request(method: str, path: str) -> str | None:
    path = path or "/"
    method = (method or "GET").upper()

    if method == "OPTIONS":
        return None

    # Keep health/docs publicly reachable.
    if any(path == p or path.startswith(f"{p}/") for p in _PUBLIC_PATH_PREFIXES if p != "/"):
        return None
    if path == "/":
        return None

    # Allow dashboard projects and scans access for users
    if any(
        path == p or path.startswith(f"{p}/")
        for p in (
            "/v1/projects",
            "/projects",
            "/v1/scans",
            "/scans",
            "/v1/api/projects",
            "/api/projects",
            "/v1/api/scans",
            "/api/scans",
        )
    ):
        return None

    if any(path == p or path.startswith(f"{p}/") for p in _ADMIN_PATH_PREFIXES):
        return "admin"

    if method in {"POST", "PUT", "PATCH", "DELETE"}:
        return "auditor"

    return "viewer"


def _extract_api_key(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return request.headers.get("X-API-Key", "").strip()


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Auth middleware enforcing role checks by HTTP method and route."""

    def __init__(self, app):
        super().__init__(app)
        self._store = APIKeyStore(settings.auth_key_store_path)
        self._store.initialize()

    async def dispatch(self, request: Request, call_next):
        if not bool(getattr(settings, "auth_enabled", True)):
            return await call_next(request)

        required_role = required_role_for_request(request.method, request.url.path)
        if required_role is None:
            return await call_next(request)

        key = _extract_api_key(request)
        if not key:
            # Check for Supabase JWT
            from app.security.jwt_utils import extract_user_id_from_jwt
            token = request.headers.get("X-Supabase-Token") or request.headers.get("Authorization")
            user_id = extract_user_id_from_jwt(token)
            if user_id:
                request.state.role = "auditor" if request.method in {"POST", "PUT", "PATCH", "DELETE"} else "viewer"
                request.state.user_id = user_id
                return await call_next(request)
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        result = self._store.authenticate(key)
        if result is None:
            # Check if key is actually a Supabase JWT
            from app.security.jwt_utils import extract_user_id_from_jwt
            user_id = extract_user_id_from_jwt(key)
            if user_id:
                request.state.role = "auditor" if request.method in {"POST", "PUT", "PATCH", "DELETE"} else "viewer"
                request.state.user_id = user_id
                return await call_next(request)
            return JSONResponse({"error": "unauthorized"}, status_code=401)

        if not has_required_role(result.role, required_role):
            return JSONResponse({"error": "forbidden"}, status_code=403)

        request.state.role = result.role
        request.state.api_key_label = result.label
        return await call_next(request)


def bootstrap_auth_store() -> None:
    """Initialize auth store during startup if auth is enabled."""
    if not bool(getattr(settings, "auth_enabled", True)):
        return
    APIKeyStore(settings.auth_key_store_path).initialize()
