import pytest
import requests

from app import news_fetcher


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self.payload


def test_fetch_news_query_uses_params_and_returns_articles(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured.update(url=url, params=params, timeout=timeout)
        return FakeResponse({"status": "ok", "articles": [{"title": "A"}]})

    monkeypatch.setenv("NEWS_API_KEY", "test-key")
    monkeypatch.setattr(news_fetcher.requests, "get", fake_get)

    articles = news_fetcher.fetch_news_query('AI & "chips"')

    assert articles == [{"title": "A"}]
    assert captured["url"].endswith("/everything")
    assert captured["params"]["q"] == 'AI & "chips"'
    assert captured["params"]["apiKey"] == "test-key"
    assert captured["timeout"] > 0


def test_fetch_news_query_rejects_empty_query():
    with pytest.raises(ValueError, match="must not be empty"):
        news_fetcher.fetch_news_query("  ")


def test_fetch_news_query_requires_api_key(monkeypatch):
    monkeypatch.delenv("NEWS_API_KEY", raising=False)

    with pytest.raises(news_fetcher.NewsAPIError, match="not configured"):
        news_fetcher.fetch_news_query("AI")


def test_fetch_news_query_raises_for_http_failure(monkeypatch):
    def fake_get(*args, **kwargs):
        return FakeResponse({}, status_code=503)

    monkeypatch.setenv("NEWS_API_KEY", "test-key")
    monkeypatch.setattr(news_fetcher.requests, "get", fake_get)

    with pytest.raises(news_fetcher.NewsAPIError, match="request failed"):
        news_fetcher.fetch_news_query("AI")


def test_fetch_news_query_raises_for_provider_error(monkeypatch):
    def fake_get(*args, **kwargs):
        return FakeResponse(
            {"status": "error", "message": "rateLimited", "articles": []}
        )

    monkeypatch.setenv("NEWS_API_KEY", "test-key")
    monkeypatch.setattr(news_fetcher.requests, "get", fake_get)

    with pytest.raises(news_fetcher.NewsAPIError, match="rateLimited"):
        news_fetcher.fetch_news_query("AI")


def test_fetch_news_query_rejects_malformed_payload(monkeypatch):
    def fake_get(*args, **kwargs):
        return FakeResponse({"status": "ok", "articles": None})

    monkeypatch.setenv("NEWS_API_KEY", "test-key")
    monkeypatch.setattr(news_fetcher.requests, "get", fake_get)

    with pytest.raises(news_fetcher.NewsAPIError, match="article list"):
        news_fetcher.fetch_news_query("AI")


def test_fetch_news_returns_partial_results_if_one_category_fails(monkeypatch):
    calls = []

    def fake_request(endpoint, params):
        calls.append((endpoint, params))
        if params.get("category") == "technology":
            raise news_fetcher.NewsAPIError("temporary failure")
        return [{"title": params.get("category") or params.get("q")}]

    monkeypatch.setattr(news_fetcher, "_request_articles", fake_request)

    articles = news_fetcher.fetch_news()

    assert len(calls) == 10
    assert articles
