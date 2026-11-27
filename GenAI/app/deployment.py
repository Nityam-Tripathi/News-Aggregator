"""Fail-closed checks for the dedicated Phase 2 database.

The marker is provisioned independently by the database owner, never by the
application or migration runner. It is an isolation identifier, not a password.
"""
import os
from uuid import UUID
from sqlalchemy import text
from .database import engine

EXPECTED_REVISION = "0003_full_text"
ENVIRONMENT = "insightstream-phase2-staging"

class DeploymentCheckError(RuntimeError):
    pass

def expected_identity():
    url = os.getenv("DATABASE_URL", "").strip()
    host = os.getenv("PHASE2_DATABASE_HOST", "").strip()
    name = os.getenv("PHASE2_DATABASE_NAME", "").strip()
    marker = os.getenv("PHASE2_DATABASE_ID", "").strip()
    if not all((url, host, name, marker)):
        raise DeploymentCheckError("Explicit Phase 2 database configuration required")
    try:
        marker = str(UUID(marker))
    except ValueError:
        raise DeploymentCheckError("Invalid Phase 2 database identifier") from None
    if engine.url.host != host or engine.url.database != name:
        raise DeploymentCheckError("Configured database target does not match expected host/name")
    return name, marker

def verify_database_identity(connection, expected):
    name, marker = expected
    identity = connection.execute(text("SELECT current_database(), current_schema()")).one()
    if tuple(identity) != (name, "public"):
        raise DeploymentCheckError("Connected database or schema is not the expected target")
    rows = connection.execute(text(
        "SELECT environment, database_id::text FROM public.insightstream_environment"
    )).all()
    if [tuple(row) for row in rows] != [(ENVIRONMENT, marker)]:
        raise DeploymentCheckError("Phase 2 database marker mismatch")

def check_schema(connection):
    revisions = connection.execute(text("SELECT version_num FROM public.alembic_version")).scalars().all()
    if revisions != [EXPECTED_REVISION]:
        raise DeploymentCheckError("Database migration revision does not match application")
    # Check the required columns, not just the Alembic stamp.
    connection.execute(text("SELECT id, title, content, published_at, embedding, url, image_url, url_key, search_document FROM public.articles LIMIT 0"))
    vector_type = connection.execute(text(
        "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
        "WHERE attrelid = 'public.articles'::regclass AND attname = 'embedding' AND NOT attisdropped"
    )).scalar_one()
    if vector_type.split(".")[-1] != "vector(384)":
        raise DeploymentCheckError("Unexpected embedding column type")

def verify_deployment():
    expected = expected_identity()
    with engine.connect() as connection:
        verify_database_identity(connection, expected)
        check_schema(connection)
