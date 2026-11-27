import unittest
from unittest.mock import MagicMock, patch
from app.retrieval import settings, retrieve_articles

class RetrievalTests(unittest.TestCase):
    @patch.dict("os.environ", {"VECTOR_SEARCH_MODE":"exact","HNSW_EF_SEARCH":"200"})
    def test_exact(self):
        db = MagicMock()
        query = db.query.return_value.filter.return_value.order_by.return_value.limit.return_value
        query.all.return_value = [1,2]
        self.assertEqual(retrieve_articles(db,[1.0]*384), [1,2])
        self.assertEqual(query.all.call_count, 1)
        self.assertEqual(db.execute.call_count,4)

    @patch.dict("os.environ", {"VECTOR_SEARCH_MODE":"hnsw","HNSW_EF_SEARCH":"400"})
    def test_full_hnsw(self):
        db = MagicMock()
        query = db.query.return_value.filter.return_value.order_by.return_value.limit.return_value
        query.all.return_value = list(range(5))
        self.assertEqual(retrieve_articles(db,[1.0]*384),list(range(5)))
        self.assertEqual(query.all.call_count,1)
        self.assertEqual(db.execute.call_args.args[1], {"ef":"400"})

    @patch.dict("os.environ", {"VECTOR_SEARCH_MODE":"hnsw","HNSW_EF_SEARCH":"100"})
    def test_underfilled_fallback(self):
        db = MagicMock()
        query = db.query.return_value.filter.return_value.order_by.return_value.limit.return_value
        query.all.side_effect = [[1],[1,2,3]]
        self.assertEqual(retrieve_articles(db,[1.0]*384),[1,2,3])
        self.assertEqual(query.all.call_count,2)
        self.assertEqual(db.execute.call_count,5)

    @patch.dict("os.environ", {"VECTOR_SEARCH_MODE":"hnsw","HNSW_EF_SEARCH":"999"})
    def test_invalid_setting(self):
        with self.assertRaises(ValueError):
            settings()
