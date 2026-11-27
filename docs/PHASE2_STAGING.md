# InsightStream — isolated Phase 2 staging runbook

**Scope:** branch `phase-2-database` only. Do not change production `main`, the
Phase 1 branch, existing Render/Vercel projects, Supabase projects, credentials,
or database contents. This runbook prepares a future deployment; it does not
provision anything or authorize a production migration.

## 1. Preflight and approval

- Verify backend/frontend regression and Phase 2 migration workflows are green
  on the exact commit selected for deployment. Preserve both protected branch SHAs.
- Obtain approval before creating any service that may incur cost. Choose a new
  Supabase project/database, new Render service and new Vercel project.
- Use a fresh database rather than copying Phase 1 or production. Confirm the
  project reference, connection host and database name independently in the
  new project's dashboard. Use a project-specific host if possible; a shared
  pooler host and generic database name alone do not establish identity.
- PostgreSQL must support pgvector with HNSW (pgvector >= 0.5) and stored generated
  columns. Prefer a direct connection or a session pooler for migrations; test
  extension permissions and network compatibility. CI uses PostgreSQL 16.
- Use a new randomly generated UUID marker for this database, never the CI
  marker or a copied marker. Use dedicated database credentials and separate API
  keys/quotas where available. Do not paste connection strings into chat,
  commit them to Git, or print them in logs.

## 2. Bootstrap database identity

In the SQL editor of the **newly created Phase 2 database only**, confirm
the project reference and run `SELECT current_database(), current_schema();`
(first schema must be public for the application connection). Generate a UUID
locally with `python -c "import uuid; print(uuid.uuid4())"`. Replace the
placeholder below with that unique UUID. Do not run on an existing production or
Phase 1 database. Do not overwrite an existing marker.

```sql
BEGIN;
CREATE TABLE public.insightstream_environment (
    environment text PRIMARY KEY,
    database_id uuid NOT NULL
);
INSERT INTO public.insightstream_environment (environment, database_id)
VALUES ('insightstream-phase2-staging', '<NEW-UUID>'::uuid);
COMMIT;
```

Record the UUID, exact connection hostname and database name in the private
deployment configuration. The runtime role needs SELECT on the marker and
normal article-table access. If using separate migration/runtime roles, restrict
marker modification to the owner; on a managed database review API exposure
and grants/RLS for the public schema. The marker is an identifier, not a secret
or authentication mechanism. Never create or copy it automatically during
deployment. A mismatched or missing marker blocks migrations and application
startup.

## 3. Apply migrations as a separate authorized step

Check out the approved Phase 2 commit, enter `GenAI`, and install
requirements under Python 3.11 (the currently tested runtime family). Set
`DATABASE_URL`, `PHASE2_DATABASE_HOST`, `PHASE2_DATABASE_NAME`,
`PHASE2_DATABASE_ID` from the new project's verified configuration. See
`.env.phase2.example`. Ensure `current_schema()` is public; use the provider's
supported extension setup if CREATE EXTENSION is restricted.

From the dedicated migration runner, explicitly set
`ALLOW_PHASE2_MIGRATIONS=yes` and execute:

```bash
python -m alembic upgrade head
python -m alembic current
```

Expect `0003_full_text (head)`. Remove the authorization flag afterward.
Do not include migrations in the normal Render start command, auto-deploy
hook or frontend build. The identity guard checks the configured host/name
and live marker on the same transaction before DDL. The baseline downgrade
is intentionally disabled. The tested upgrade/downgrade applies to disposable
CI fixtures; adoption of an arbitrary existing unversioned schema is not
a supported staging shortcut. Use backups before any future non-disposable
migration. Do not use `alembic stamp` to bypass schema creation.

## 4. Render backend (proposed new service)

- Name: `insightstream-backend-phase2` (subject to availability).
- Git branch: `phase-2-database`; root directory: `GenAI`.
- Python: 3.11; build: `pip install -r requirements.txt`.
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1`.
- Health check path: `/ready`. Keep auto-deploy off until first acceptance.
- Environment: use the verified isolated database URL and identity settings.
  Keep `ALLOW_PHASE2_MIGRATIONS=no` (or unset) on the runtime service.
- Initial settings: `INGEST_SCHEDULER_ENABLED=false`,
  `INGEST_RUN_ON_STARTUP=false`, `SEARCH_FETCH_FRESH=false`;
  leave `INGEST_ADMIN_KEY` unset until manual ingestion is authorized.
- `EMBEDDING_PROVIDER=local`, `RETRIEVAL_MODE=semantic`,
  `VECTOR_SEARCH_MODE=exact`, `HNSW_EF_SEARCH=200` (inactive in exact mode).
- Configure a valid Groq model and a dedicated key. Do not assume the
  previously tested model is still available. Keep the single worker because
  cache, rate limiter and scheduler are process-local.
- Set CORS to the exact new frontend origin; use only local development origins
  until the frontend address is known. Never reuse a production frontend
  configuration.

The service refuses startup if identity/schema verification fails. Readiness
returns 503 on missing/wrong identity, unavailable DB, non-head revision,
missing required columns or an unexpected vector dimension. A 200 response
confirms these checks, not freshness, provider availability or complete schema
integrity. Never bypass ASGI lifespan startup in a deployment.

## 5. Vercel frontend (proposed new project)

- Name: `insightstream-phase2` (subject to availability).
- Import repository as a separate project; branch `phase-2-database` only.
- Root directory: `mind-bloom-news-main`; framework: Vite;
  install: `npm ci`; build: `npm run build`; output: `dist`.
- Set `VITE_API_URL` to the new Phase 2 backend HTTPS URL. Do not put secret
  keys in VITE variables (they are public browser configuration).
- Restrict deployment access where supported; otherwise treat the API as
  public and keep quotas/ingestion locked down. Recheck CORS and SSE through
  the actual deployed frontend. No change to existing Vercel projects.

## 6. Staging acceptance tests

1. Confirm service commit/branch and database identity; `GET /ready` must
   return status ok and schema_revision 0003_full_text. Root liveness alone
   is insufficient.
2. Confirm empty-database `/freshness`, `/top-news`, `/analytics` and
   `/ask` behave safely. Seed a small authorized corpus using dedicated
   NewsAPI credentials and a new admin key; never reuse production credentials
   or expose the key in client JavaScript. Unauthorized /ingest must reject.
3. Test answer JSON, cited SSE, invalid-citation fallback, no-result behavior,
   error and disconnect handling, repeat query caching and shared rate limits.
   For SSE use `curl -N` and browser developer tools; measure actual first
   visible chunk and completion. Confirm links correspond to retrieved articles.
4. Check live Groq responses against the cited excerpts with human labels;
   the current heuristic is not an entailment model. Check false positives and
   false negatives, particularly swapped entities and paraphrases. Streamed
   text is provisional until screening completes.
5. Monitor cold/warm latency, CPU, memory, timeouts, database connections and
   ingestion quota. CI performance numbers used simulated LLM delays and are
   not hosted performance claims.
6. Only after validation enable scheduling with
   `INGEST_SCHEDULER_ENABLED=true`. Default interval 240 minutes, floor 180;
   `INGEST_RUN_ON_STARTUP=true` is an explicit opt-in. With startup fetch false,
   the first run is after the interval. Leave query-time fetching off unless
   specifically tested and approved.

## 7. Rollback and release decision

Keep production and Phase 1 untouched at every step. If staging fails, disable
Phase 2 scheduling, suspend or redeploy only the new service, and retain
logs/metrics. Roll back frontend/backend together to a schema-compatible
Phase 2 commit. Do not downgrade or delete a populated database automatically.
For fresh disposable staging, recreate only after explicit approval.
Production promotion requires a separate migration/data backup plan, live
quality and performance validation, security review, and user approval.

## 8. CI

`.github/workflows/phase2-migrations.yml` creates a disposable local
`phase2_test` database, provisions a CI-only marker, verifies that a wrong
marker cannot create tables, tests readiness before and after migrations
and downgrades, then runs all regression benchmarks. CI does not access
the hosted database or API credentials. Change EXPECTED_REVISION and the
runbook when a new Alembic revision is introduced.
