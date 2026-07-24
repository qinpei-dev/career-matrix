"""Database engine and session construction."""

from collections.abc import Generator
from functools import lru_cache

from pydantic import ValidationError
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from ...core.config import get_settings


class DatabaseConfigurationError(RuntimeError):
    """The database cannot be used until DATABASE_URL is configured."""


def create_database_engine(database_url: str | None = None) -> Engine:
    """Create an engine for an explicit URL or the configured database."""
    try:
        url = database_url if database_url is not None else get_settings().database_url
    except ValidationError as exc:
        raise DatabaseConfigurationError(
            "DATABASE_URL is not configured; set it before using database features."
        ) from exc
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name == "sqlite":
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a SQLAlchemy 2.x session factory bound to an engine."""
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@lru_cache
def _default_session_factory() -> sessionmaker[Session]:
    return create_session_factory(create_database_engine())


def get_default_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory for startup maintenance tasks."""
    return _default_session_factory()


def get_db_session() -> Generator[Session, None, None]:
    """Yield one transactional session for future application dependencies."""
    session = get_default_session_factory()()
    try:
        yield session
    finally:
        session.close()
