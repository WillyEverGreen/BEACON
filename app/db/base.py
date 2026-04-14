"""SQLAlchemy engine/session setup."""

from __future__ import annotations

from contextlib import contextmanager
import threading

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from app.config import settings


Base = declarative_base()
_db_init_lock = threading.Lock()
_db_initialized = False


def _engine_kwargs() -> dict:
    kwargs = {
        "echo": bool(getattr(settings, "db_echo", False)),
        "future": True,
        "pool_pre_ping": True,
    }

    db_url = str(getattr(settings, "db_url", "sqlite:///./beacon.db"))
    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = int(getattr(settings, "db_pool_size", 5) or 5)
        kwargs["max_overflow"] = int(getattr(settings, "db_max_overflow", 5) or 5)
        kwargs["pool_timeout"] = int(getattr(settings, "db_pool_timeout_seconds", 30) or 30)
        kwargs["pool_recycle"] = int(getattr(settings, "db_pool_recycle_seconds", 1800) or 1800)

    return kwargs


engine = create_engine(settings.db_url, **_engine_kwargs())
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
)


def init_db() -> None:
    """Initialize DB metadata only when explicit auto-create is enabled."""
    global _db_initialized
    from app.db import models  # noqa: F401

    if bool(getattr(settings, "db_auto_create", False)):
        Base.metadata.create_all(bind=engine)

    _db_initialized = True


def ensure_db_ready() -> None:
    """Optionally ensure SQLite schema exists for CLI/test contexts."""
    global _db_initialized
    if _db_initialized:
        return

    if not bool(getattr(settings, "db_auto_create", False)):
        return

    db_url = str(getattr(settings, "db_url", "sqlite:///./beacon.db"))
    if not db_url.startswith("sqlite"):
        return

    with _db_init_lock:
        if _db_initialized:
            return
        init_db()


@contextmanager
def get_session():
    """Yield a session with automatic commit/rollback."""
    ensure_db_ready()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
