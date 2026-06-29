# database.py
# SQLAlchemy engine setup, session factory, and schema migration for MARKA.
# Creates the database engine, runs auto-migrations for schema changes that
# cannot be expressed as simple CREATE TABLE statements (added columns), and
# provides the get_db dependency used by all FastAPI route handlers.

from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Application settings provide the DATABASE_URL connection string
from backend.config import get_settings

settings = get_settings()

# Ensure the SQLite parent directory exists before the engine tries to create the file.
# PostgreSQL URLs do not need this; the database must be created externally.
if settings.database_url.startswith("sqlite:///"):
    sqlite_target = settings.database_url.replace("sqlite:///", "", 1)
    sqlite_path = Path(sqlite_target)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

# pool_pre_ping=True tests connections before use, ensuring stale connections from
# a restarted database are detected and replaced rather than causing request failures
engine = create_engine(settings.database_url, pool_pre_ping=True)

# autocommit=False and autoflush=False give explicit control over transaction boundaries;
# each request commits or rolls back exactly what it intended
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Shared declarative base; all ORM models import this to register their table definitions
Base = declarative_base()


def initialize_database() -> None:
    """
    Create all ORM-defined tables and apply any pending schema migrations.

    Called once during FastAPI application startup (via the lifespan context manager
    in main.py). Uses SQLAlchemy's create_all to create missing tables and then
    checks for specific columns that were added in post-initial-schema migrations,
    applying ALTER TABLE statements if they are absent.

    This approach avoids a full Alembic migration setup while still handling
    incremental schema changes safely for both SQLite and PostgreSQL.

    Returns:
        None
    """
    # Create all tables defined by ORM models if they do not already exist
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)

    # Migration: add password_hash column to users table if it was created before
    # email/password authentication was implemented
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "password_hash" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT ''")
            )

    # Migration: add content_text column to documents table if it was created before
    # the PostgreSQL RAG fallback feature was implemented
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    if "content_text" not in document_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE documents ADD COLUMN content_text TEXT NOT NULL DEFAULT ''")
            )


def get_db():
    """
    FastAPI dependency that yields a SQLAlchemy session per request.

    Opens a new database session at the start of each request and closes it
    in the finally block regardless of whether the handler raised an exception.
    Using yield makes this compatible with FastAPI's Depends() injection system.

    Yields:
        Session: An active SQLAlchemy session bound to the configured database engine.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        # Always close the session to return the connection to the pool
        db.close()
