from alembic import context
from app.database import engine, Base
from app import models
import os

if os.getenv("ALLOW_PHASE2_MIGRATIONS") != "yes":
    raise RuntimeError("Explicit migration authorization required on an isolated database")
if context.is_offline_mode():
    raise RuntimeError("Online migrations only")
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
