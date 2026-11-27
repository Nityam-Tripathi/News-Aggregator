import json
import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app import main
from app.answer_cache import AnswerCache, cache_key
from app.embeddings import generate_embeddings
from app.ingestion import ingest_articles

class CacheTests(unittest.TestCase):
    def test_ttl_and_lru(self):
        now = [0]
        c = AnswerCache(max_entries=2, ttl=5, clock=lambda: now[0])
        c.put("a","A"); c.put("b","B")
        self.assertEqual(c.get("a"),"A")
        c.put("c","C")
        self.assertIsNone(c.get("b"))
        now[0] = 5
        self.assertIsNone(c.get("a"))

    def test_evidence_and_model_change_key(self):
        args = ("Query","Evidence",[],"model","v1")
        key = cache_key(*args)
        for i, value in enumerate(("query","New evidence",[{"url":"https://example.org"}],"other","v2")):
            changed = list(args); changed[i] = value
            self.assertNotEqual(key,cache_key(*changed))

    def test_blank_not_cached(self):
        c = AnswerCache()
        c.put("x"," ")
        self.assertIsNone(c.get("x"))

class BatchTests(unittest.TestCase):
    @patch.dict("os.environ",{"EMBEDDING_PROVIDER":"local"})
    @patch("app.embeddings.local_model")
    def test_batch_order(self,model):
        model.return_value.embed.return_value = iter([[1.0]*384,[2.0]*384])
        self.assertEqual(generate_embeddings(["one","two"]),[[1.0]*384,[2.0]*384])
        model.return_value.embed.assert_called_once_with(["one","two"],batch_size=2)

    @patch.dict("os.environ",{"EMBEDDING_PROVIDER":"local"})
    @patch("app.embeddings.local_model")
    def test_bad_batch(self,model):
        model.return_value.embed.return_value = iter([[1.0]*384])
        with self.assertRaises(ValueError):
            generate_embeddings(["one","two"])

    @patch("app.ingestion.generate_embeddings")
    def test_dedup_and_batch(self,embed):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        db.execute.return_value.rowcount = 2
        embed.return_value = [[1.0]*384]*2
        a = {"title":"A","description":"text","url":"https://example.org/a"}
        duplicate = dict(a,url="https://example.org/a?utm_source=x")
        b = dict(a,title="B",url="https://example.org/b")
        stats = ingest_articles(db,[a,duplicate,b])
        self.assertEqual(stats,{"fetched":3,"inserted":2,"skipped":1,"embedding_failures":0})
        embed.assert_called_once_with(["A. text","B. text"])
        db.commit.assert_called_once()

    @patch("app.ingestion.generate_embeddings",side_effect=RuntimeError("offline"))
    def test_no_invalid_insert(self,embed):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        stats = ingest_articles(db,[{"title":"A","description":"B","url":"https://example.org"}])
        self.assertEqual(stats["embedding_failures"],1)
        db.execute.assert_not_called()

class StreamTests(unittest.TestCase):
    def setUp(self):
        main._rate_buckets.clear()
        main._global_requests.clear()
        self.cache_patch = patch.object(main,"answer_cache",AnswerCache())
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)
        self.addCleanup(main._rate_buckets.clear)
        self.addCleanup(main._global_requests.clear)
        self.client = TestClient(main.app)
        self.sources = [{"source_id":1,"title":"Article","url":"https://example.org","image":None,"published_at":None}]
        self.context = json.dumps([{"source_id":1,"title":"Article","content":"Hello world."}])

    @patch("app.main.prepare_answer")
    def test_stream_and_cache(self,prepare):
        prepare.return_value = ("query",self.context,self.sources)
        async def chunks(*args):
            yield "Hello "
            yield "world [1]"
        with patch("app.main.stream_answer",side_effect=chunks) as stream:
            response = self.client.get("/ask/stream",params={"query":"query"})
            self.assertEqual(response.status_code,200)
            self.assertIn("text/event-stream",response.headers["content-type"])
            self.assertIn('event: sources',response.text)
            self.assertIn('event: delta',response.text)
            self.assertIn('event: done',response.text)
            self.assertIn("Hello ",response.text)
            again = self.client.get("/ask",params={"query":"query"})
            self.assertEqual(again.json()["answer"],"Hello world [1]")
            stream.assert_called_once()

    @patch("app.main.prepare_answer")
    def test_failed_stream_not_cached(self,prepare):
        prepare.return_value = ("query",self.context,self.sources)
        async def broken(*args):
            yield "partial"
            raise RuntimeError("offline")
        with patch("app.main.stream_answer",side_effect=broken) as stream:
            for _ in range(2):
                response = self.client.get("/ask/stream",params={"query":"query"})
                self.assertIn("event: error",response.text)
                self.assertNotIn("event: done",response.text)
            self.assertEqual(stream.call_count,2)

    @patch("app.main.prepare_answer",return_value=("query","",[]))
    @patch("app.main.stream_answer")
    def test_empty_retrieval(self,stream,prepare):
        response = self.client.get("/ask/stream",params={"query":"query"})
        self.assertIn(main.NO_RESULTS,response.text)
        self.assertIn("event: done",response.text)
        stream.assert_not_called()
