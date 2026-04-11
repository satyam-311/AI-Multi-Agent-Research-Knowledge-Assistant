import logging
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

if settings.database_url.startswith("sqlite:///"):
    sqlite_target = settings.database_url.replace("sqlite:///", "", 1)
    sqlite_path = Path(sqlite_target)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def initialize_database() -> None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "password_hash" not in columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT ''")
            )
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    if "content_text" not in document_columns:
        with engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE documents ADD COLUMN content_text TEXT NOT NULL DEFAULT ''")
            )
    if engine.dialect.name == "postgresql" and inspector.has_table("document_chunks"):
        try:
            with engine.begin() as connection:
                connection.execute(
                    text("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(768)")
                )
        except Exception as exc:
            logger.warning("Could not update document_chunks.embedding to vector(768): %s", exc)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
