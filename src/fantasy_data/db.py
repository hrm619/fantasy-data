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
    """Create all tables, then add any columns the models gained since the DB was built."""
    from fantasy_data.models import Base

    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    sync_schema(engine)
    return engine


def sync_schema(engine=None, db_path: str | None = None) -> dict[str, list[str]]:
    """Add columns that exist on the ORM models but not yet in the live tables.

    `create_all()` only creates missing *tables* — it will not touch a table that already
    exists, so a new `Mapped[...]` attribute is invisible to an existing database and every
    query against it fails with "no such column". The alternative is rebuilding, which for
    this DB means re-running a twelve-season ingest.

    Deliberately narrow: it only ever runs `ALTER TABLE ... ADD COLUMN`. It never drops,
    renames, retypes, or reorders anything, so it cannot destroy data — a column that exists
    is left exactly as it is, even if its type no longer matches the model. Anything beyond
    an additive column change still needs a hand-written migration.

    **It emits the column TYPE only.** `nullable=False`, `unique=True` and ForeignKey on an
    added column are silently dropped, so a database patched by this function can differ in
    constraints from one built fresh by `create_all`. That is data-safe but not equivalent —
    if a new column needs a constraint, write the migration by hand. None of the RP columns
    added so far declare one.

    Returns {table_name: [added columns]} for the ones it actually added.
    """
    from sqlalchemy import inspect, text

    from fantasy_data.models import Base

    if engine is None:
        engine = get_engine(db_path)

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    added: dict[str, list[str]] = {}

    with engine.begin() as conn:
        for table in Base.metadata.tables.values():
            if table.name not in existing_tables:
                continue  # create_all() just made it; it is already current
            live_columns = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in live_columns:
                    continue
                col_type = column.type.compile(engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {col_type}'))
                added.setdefault(table.name, []).append(column.name)

    return added
