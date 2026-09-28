from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings
from app.db.models import Base

_engine = None
_SessionLocal = None


def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        db_path = Path(settings.memory_db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(_engine)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


@contextmanager
def get_session() -> Session:
    get_engine()  # ensure initialized
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
