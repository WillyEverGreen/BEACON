"""SQLAlchemy engine/session setup."""

from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker

from app.config import settings


Base = declarative_base()


def _engine_kwargs() -> dict:
    kwargs = {
        "echo": bool(getattr(settings, "db_echo", False)),
        "future": True,
    }

    db_url = str(getattr(settings, "db_url", "sqlite:///./beacon.db"))
    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}

    return kwargs


engine = create_engine(settings.db_url, **_engine_kwargs())
SessionLocal = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
)


def init_db() -> None:
    """Initialize all declared SQLAlchemy tables."""
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


@contextmanager
def get_session():
    """Yield a session with automatic commit/rollback."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
