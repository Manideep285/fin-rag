from __future__ import annotations
from contextlib import contextmanager
from typing import Iterator, Optional
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db(project_id: Optional[UUID] = None) -> Iterator[Session]:
    """FastAPI dependency. Sets RLS project context if provided."""
    db = SessionLocal()
    try:
        if project_id is not None:
            db.execute(
                text("SELECT set_config('app.current_project_id', :pid, true)"),
                {"pid": str(project_id)},
            )
        yield db
    finally:
        db.close()


@contextmanager
def session_scope(project_id: Optional[UUID] = None) -> Iterator[Session]:
    db = SessionLocal()
    try:
        if project_id is not None:
            db.execute(
                text("SELECT set_config('app.current_project_id', :pid, true)"),
                {"pid": str(project_id)},
            )
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
