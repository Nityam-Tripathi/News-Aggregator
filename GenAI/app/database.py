import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()


def _normalize_database_url(database_url: str) -> str:
    """Use the psycopg2 driver supplied by psycopg2-binary.

    SQLAlchemy 2.1 changed the default driver for postgresql:// URLs to
    psycopg (v3), while this project explicitly installs psycopg2-binary.
    """
    if database_url.startswith("postgres://"):
        return database_url.replace(
            "postgres://", "postgresql+psycopg2://", 1
        )
    if database_url.startswith("postgresql://"):
        return database_url.replace(
            "postgresql://", "postgresql+psycopg2://", 1
        )
    return database_url


DATABASE_URL = _normalize_database_url(
    os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:5433/newsdb_v2",
    )
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()
