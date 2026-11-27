"""Exercise real PostgreSQL identity, migration and readiness guards on CI only."""
import os
import subprocess
import sys
from sqlalchemy import text
from fastapi.testclient import TestClient
from unittest.mock import patch
from app.database import engine
from app.deployment import expected_identity, verify_database_identity, ENVIRONMENT
from app.main import app
from phase2_migration_check import guard

def bootstrap():
    guard()
    _, marker = expected_identity()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE public.insightstream_environment (environment text PRIMARY KEY, database_id uuid NOT NULL)"))
        conn.execute(text("INSERT INTO public.insightstream_environment VALUES (:environment, CAST(:marker AS uuid))"),
                     {"environment":ENVIRONMENT,"marker":marker})
    print("Created independently provisioned CI marker")

def check(expected_status):
    guard()
    with engine.connect() as conn:
        verify_database_identity(conn,expected_identity())
    response=TestClient(app).get("/ready")
    assert response.status_code==expected_status, response.text
    if expected_status == 200:
        with TestClient(app) as client:
            assert client.get("/ready").json()["schema_revision"] == "0003_full_text"
    print("Readiness returned",expected_status)

def reject():
    guard()
    env=dict(os.environ, PHASE2_DATABASE_ID="00000000-0000-4000-8000-000000000001")
    result=subprocess.run([sys.executable,"-m","alembic","upgrade","head"],env=env,capture_output=True,text=True)
    assert result.returncode!=0 and "Phase 2 database marker mismatch" in result.stderr, result.stderr
    with engine.connect() as conn:
        assert conn.execute(text("SELECT to_regclass('public.alembic_version')")).scalar_one() is None
        assert conn.execute(text("SELECT to_regclass('public.articles')")).scalar_one() is None
    with patch.dict(os.environ, {"PHASE2_DATABASE_ID":env["PHASE2_DATABASE_ID"]}):
        assert TestClient(app).get("/ready").status_code == 503
        try:
            with TestClient(app):
                raise AssertionError("Startup unexpectedly succeeded")
        except RuntimeError as exc:
            assert "Phase 2 database identity or schema verification failed" in str(exc)
    print("Wrong marker rejected before schema changes; runtime readiness and startup blocked")

if __name__=="__main__":
    {"bootstrap":bootstrap,"reject":reject,"not-ready":lambda:check(503),"ready":lambda:check(200)}[sys.argv[1]]()
