import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import database, models

# Suppress schema creation and database access during module import.
with patch.object(database.engine, "connect"), patch.object(models.Base.metadata, "create_all"):
    from app import main

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        main._rate_buckets.clear()
        main._global_requests.clear()
        self.addCleanup(main._rate_buckets.clear)
        self.addCleanup(main._global_requests.clear)

    @patch.dict("os.environ", {"INGEST_ADMIN_KEY": "test-only"})
    @patch.object(main, "SessionLocal")
    def test_ingest_rejects_unauthorized(self, session):
        self.assertEqual(self.client.post("/ingest").status_code, 403)
        self.assertEqual(self.client.post("/ingest", headers={"X-Admin-Key": "wrong"}).status_code, 403)
        session.assert_not_called()

    @patch.dict("os.environ", {"INGEST_ADMIN_KEY": ""})
    def test_ingest_disabled(self):
        self.assertEqual(self.client.post("/ingest").status_code, 503)

    def test_rate_limit(self):
        # Blank queries exercise the limiter without embeddings or database writes.
        for _ in range(5):
            self.assertEqual(self.client.get("/ask", params={"query": " "}).status_code, 422)
        response = self.client.get("/ask", params={"query": " "})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers["Retry-After"], "60")

    @patch.object(main.engine, "connect")
    def test_readiness(self, connect):
        self.assertEqual(self.client.get("/ready").status_code, 200)
        connect.side_effect = RuntimeError("offline")
        self.assertEqual(self.client.get("/ready").status_code, 503)
