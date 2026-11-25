import unittest
from unittest.mock import patch, Mock
from app import news_fetcher as nf

class NewsFetcherTests(unittest.TestCase):
    def setUp(self):
        nf._attempts.clear()
        nf._blocked_until = 0
        self.addCleanup(nf._attempts.clear)
        self.addCleanup(setattr, nf, "_blocked_until", 0)

    @patch.dict("os.environ", {"NEWS_API_KEY": "test-key"})
    @patch("app.news_fetcher.requests.get")
    def test_quota_backoff(self, get):
        get.return_value = Mock(ok=False, status_code=429)
        get.return_value.json.return_value = {"code": "rateLimited"}
        self.assertEqual(nf.fetch_news(), [])
        self.assertEqual(get.call_count, 1)

    @patch.dict("os.environ", {"NEWS_API_KEY": "test-key"})
    @patch("app.news_fetcher.requests.get")
    def test_success(self, get):
        get.return_value = Mock(ok=True)
        get.return_value.json.return_value = {"status": "ok", "articles": [{"title": "Example"}]}
        self.assertEqual(nf.fetch_news_query("AI"), [{"title": "Example"}])

    @patch.dict("os.environ", {"NEWS_API_KEY": "test-key"})
    @patch("app.news_fetcher.requests.get")
    def test_budget(self, get):
        nf._attempts[:] = [nf.monotonic()] * 80
        self.assertEqual(nf.fetch_news_query("AI"), [])
        get.assert_not_called()
