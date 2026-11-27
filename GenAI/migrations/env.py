from alembic import context
from app.database import engine, Base
from app import models
from app.deployment import expected_identity, verify_database_identity
import os

if os.getenv("ALLOW_PHASE2_MIGRATIONS") != "yes":
    raise RuntimeError("Explicit migration authorization required on an isolated database")
if context.is_offline_mode():
    raise RuntimeError("Online migrations only")
expected = expected_identity()
# Verify and migrate on the same connection, inside one explicit transaction.
# Alembic must not own/rollback the transaction opened by the identity SELECTs.
with engine.begin() as connection:
    verify_database_identity(connection, expected)
    context.configure(connection=connection, target_metadata=Base.metadata, version_table_schema="public")
    with context.begin_transaction():
        context.run_migrations()
