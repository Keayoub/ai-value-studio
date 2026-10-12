from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache

from app.config import get_settings
from app.db.base import load_metadata
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine


@lru_cache(maxsize=4)
def _build_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(
        database_url,
        echo=False,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def get_engine() -> Engine:
    load_metadata()
    return _build_engine(get_settings().database_url)


def clear_engine_cache() -> None:
    _build_engine.cache_clear()


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session


def database_ready() -> bool:
    with Session(get_engine()) as session:
        session.exec(text("SELECT 1"))
    return True


def _set_postgres_setting(session: Session, setting_name: str, value: str) -> None:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    session.connection().execute(
        text("SELECT set_config(:setting_name, :setting_value, true)"),
        {"setting_name": setting_name, "setting_value": value},
    )


def set_postgres_workspace(session: Session, workspace_id: str) -> None:
    _set_postgres_setting(session, "app.workspace_id", workspace_id)


def set_postgres_actor(session: Session, identity_subject_id: str) -> None:
    _set_postgres_setting(session, "app.identity_subject_id", identity_subject_id)


def set_postgres_workspace_verified(session: Session) -> None:
    _set_postgres_setting(session, "app.workspace_access_verified", "true")


def set_postgres_workspace_create_allowed(session: Session) -> None:
    _set_postgres_setting(session, "app.workspace_create_allowed", "true")
