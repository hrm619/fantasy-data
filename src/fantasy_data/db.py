"""Database connection and session management."""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

# Canonical shared location, independent of where this repo lives on disk.
# Other projects can reference the same DB regardless of their directory.
HOME_DB_PATH = Path.home() / ".fantasy-data" / "fantasy_data.db"
# Legacy in-repo location, kept as a fallback for un-migrated checkouts.
LEGACY_DB_PATH = Path(__file__).resolve().parent.parent.parent / "fantasy_data.db"


def _default_db_path() -> Path:
    """Resolve the default DB path: prefer the canonical home location,
    fall back to the legacy in-repo file, else create in the home location."""
    if HOME_DB_PATH.exists():
        return HOME_DB_PATH
    if LEGACY_DB_PATH.exists():
        return LEGACY_DB_PATH
    return HOME_DB_PATH


def get_engine(db_path: str | None = None):
    """Create a SQLAlchemy engine for the fantasy data database."""
    path = Path(db_path or os.environ.get("FANTASY_DATA_DB") or _default_db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def get_session(db_path: str | None = None) -> Session:
    """Create a new database session."""
    engine = get_engine(db_path)
    factory = sessionmaker(bind=engine)
    return factory()


def init_db(db_path: str | None = None):
    """Create all tables in the database."""
    from fantasy_data.models import Base

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine
