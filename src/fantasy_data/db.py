"""Database connection and session management."""

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "fantasy_data.db"


def get_engine(db_path: str | None = None):
    """Create a SQLAlchemy engine for the fantasy data database."""
    path = db_path or os.environ.get("FANTASY_DATA_DB", str(DEFAULT_DB_PATH))
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
