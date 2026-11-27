import unittest
from unittest.mock import MagicMock, patch
from sqlalchemy.engine import make_url
from app import deployment, main, scheduler

CONFIG = {"DATABASE_URL":"postgresql://user:pass@db.example.org/phase2",
          "PHASE2_DATABASE_HOST":"db.example.org","PHASE2_DATABASE_NAME":"phase2",
          "PHASE2_DATABASE_ID":"b735e5a8-56fb-4e6b-a8ea-276510cb0821"}
IDENTITY = ("phase2",CONFIG["PHASE2_DATABASE_ID"])

class DeploymentTests(unittest.TestCase):
    @patch.dict("os.environ", CONFIG, clear=True)
    def test_explicit_identity(self):
        with patch.object(deployment,"engine") as engine:
            engine.url=make_url(CONFIG["DATABASE_URL"])
            self.assertEqual(deployment.expected_identity(), IDENTITY)

    @patch.dict("os.environ", {}, clear=True)
    def test_no_fallback(self):
        with self.assertRaises(deployment.DeploymentCheckError):
            deployment.expected_identity()

    @patch.dict("os.environ", CONFIG, clear=True)
    def test_wrong_host(self):
        with patch.object(deployment,"engine") as engine:
            engine.url=make_url("postgresql://user:pass@other.example.org/phase2")
            with self.assertRaises(deployment.DeploymentCheckError):
                deployment.expected_identity()

    def test_marker(self):
        conn=MagicMock()
        conn.execute.return_value.one.return_value=("phase2","public")
        conn.execute.return_value.all.return_value=[(deployment.ENVIRONMENT,IDENTITY[1])]
        deployment.verify_database_identity(conn,IDENTITY)
        conn.execute.return_value.all.return_value=[(deployment.ENVIRONMENT,"other")]
        with self.assertRaises(deployment.DeploymentCheckError):
            deployment.verify_database_identity(conn,IDENTITY)

    def test_wrong_schema(self):
        conn=MagicMock()
        conn.execute.return_value.one.return_value=("phase2","other")
        with self.assertRaises(deployment.DeploymentCheckError):
            deployment.verify_database_identity(conn,IDENTITY)

    def test_schema_revision(self):
        conn=MagicMock()
        conn.execute.return_value.scalars.return_value.all.return_value=[deployment.EXPECTED_REVISION]
        conn.execute.return_value.scalar_one.return_value="vector(384)"
        deployment.check_schema(conn)
        conn.execute.return_value.scalars.return_value.all.return_value=["0002_indexes"]
        with self.assertRaises(deployment.DeploymentCheckError):
            deployment.check_schema(conn)

    def test_wrong_dimensions(self):
        conn=MagicMock()
        conn.execute.return_value.scalars.return_value.all.return_value=[deployment.EXPECTED_REVISION]
        conn.execute.return_value.scalar_one.return_value="vector(768)"
        with self.assertRaises(deployment.DeploymentCheckError):
            deployment.check_schema(conn)

    @patch.object(main,"start_scheduler")
    @patch.object(main,"verify_deployment",side_effect=RuntimeError("database mismatch"))
    def test_startup_blocks_scheduler(self,verify,start):
        with self.assertRaises(RuntimeError):
            main.start()
        start.assert_not_called()

    @patch.object(main,"start_scheduler")
    @patch.object(main,"verify_deployment")
    def test_startup_allows_verified_database(self,verify,start):
        main.start()
        verify.assert_called_once()
        start.assert_called_once()

class SchedulerTests(unittest.TestCase):
    @patch.dict("os.environ", {}, clear=True)
    @patch.object(scheduler,"scheduler")
    def test_disabled_by_default(self, instance):
        scheduler.start_scheduler()
        instance.start.assert_not_called()
        instance.add_job.assert_not_called()

    @patch.dict("os.environ", {"INGEST_SCHEDULER_ENABLED":"true","INGEST_INTERVAL_MINUTES":"30"}, clear=True)
    @patch.object(scheduler,"scheduler")
    def test_enabled_delayed_and_minimum_interval(self,instance):
        instance.running=False
        scheduler.start_scheduler()
        self.assertEqual(instance.add_job.call_args.kwargs["minutes"],180)
        self.assertNotIn("next_run_time",instance.add_job.call_args.kwargs)
        instance.start.assert_called_once()

    @patch.dict("os.environ", {"INGEST_SCHEDULER_ENABLED":"true","INGEST_RUN_ON_STARTUP":"true"}, clear=True)
    @patch.object(scheduler,"scheduler")
    def test_immediate_opt_in(self,instance):
        instance.running=False
        scheduler.start_scheduler()
        self.assertIn("next_run_time",instance.add_job.call_args.kwargs)

    @patch.dict("os.environ", {"INGEST_SCHEDULER_ENABLED":"yes"}, clear=True)
    def test_invalid_boolean(self):
        with self.assertRaises(ValueError):
            scheduler.start_scheduler()
