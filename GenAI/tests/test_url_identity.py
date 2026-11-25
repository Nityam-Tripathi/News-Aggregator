import unittest
from app.url_identity import url_key, canonical_url

class URLTests(unittest.TestCase):
    def test_tracking(self):
        self.assertEqual(url_key("https://EXAMPLE.com:443/story?utm_source=x#part"), url_key("https://example.com/story"))
    def test_distinct(self):
        self.assertNotEqual(url_key("https://example.com/story?id=1"), url_key("https://example.com/story?id=2"))
    def test_invalid(self):
        for value in (None, "", "javascript:alert(1)", "https://user:pass@example.com"):
            self.assertIsNone(canonical_url(value))
