import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
from app.hybrid import fuse, recency_multiplier, search_articles

NOW = datetime(2026,10,8,tzinfo=timezone.utc)

def article(id, days=0, url=None):
    return SimpleNamespace(id=id, url=url or f"https://example.com/{id}",
        published_at=NOW-timedelta(days=days))

class HybridTests(unittest.TestCase):
    def test_rank_fusion_rewards_agreement(self):
        a,b,c = article(1),article(2),article(3)
        self.assertEqual(fuse([[a,b],[c,b]],recency_weight=0,now=NOW)[0].id,2)

    def test_url_duplicates(self):
        a = article(1,url="https://example.com/story?utm_source=test")
        b = article(2,url="https://example.com/story")
        self.assertEqual(len(fuse([[a,b],[b]],now=NOW)),1)

    def test_recency_only_breaks_relevance_ranking(self):
        old,new = article(1,180),article(2,1)
        self.assertEqual(fuse([[old],[new]],recency_weight=0,now=NOW)[0].id,1)
        self.assertEqual(fuse([[old],[new]],now=NOW)[0].id,2)
        self.assertEqual(fuse([[],[]],now=NOW),[])
        self.assertEqual(recency_multiplier(article(3,-1),NOW,.15),1)

    def test_recency_bound(self):
        self.assertAlmostEqual(recency_multiplier(article(1),NOW,.15),1.15)
        self.assertAlmostEqual(recency_multiplier(article(1,30),NOW,.15),1.075)

    @patch.dict("os.environ",{"RETRIEVAL_MODE":"semantic"})
    @patch("app.hybrid.retrieve_articles",return_value=[])
    def test_default_semantic_route(self, retrieve):
        self.assertEqual(search_articles(None,"test",[1]*384),[])
        retrieve.assert_called_once()

    @patch.dict("os.environ",{"RETRIEVAL_MODE":"hybrid"})
    @patch("app.hybrid.hybrid_search",return_value=[])
    def test_hybrid_route(self, retrieve):
        self.assertEqual(search_articles(None,"test",[1]*384),[])
        retrieve.assert_called_once()

    def test_invalid_weight(self):
        with self.assertRaises(ValueError):
            fuse([],recency_weight=1,now=NOW)
