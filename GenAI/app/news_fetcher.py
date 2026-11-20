import os
import logging

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
NEWS_API_URL = "https://newsapi.org/v2"
REQUEST_TIMEOUT_SECONDS = 10


class NewsAPIError(RuntimeError):
    """Raised when NewsAPI cannot provide a valid article response."""


def _get_api_key() -> str:
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        raise NewsAPIError("NEWS_API_KEY is not configured")
    return api_key


def _request_articles(endpoint: str, params: dict) -> list[dict]:
    request_params = {**params, "apiKey": _get_api_key()}

    try:
        response = requests.get(
            f"{NEWS_API_URL}/{endpoint}",
            params=request_params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise NewsAPIError(f"NewsAPI request failed: {exc}") from exc
    except ValueError as exc:
        raise NewsAPIError("NewsAPI returned invalid JSON") from exc

    if payload.get("status") != "ok":
        message = payload.get("message", "Unknown NewsAPI error")
        raise NewsAPIError(f"NewsAPI rejected the request: {message}")

    articles = payload.get("articles")
    if not isinstance(articles, list):
        raise NewsAPIError("NewsAPI response did not contain an article list")

    return articles


def fetch_news() -> list[dict]:
    categories = ["technology", "business", "science", "health"]
    keywords = [
        "artificial intelligence",
        "machine learning",
        "startup",
        "economy",
        "crypto",
        "global politics",
    ]

    articles = []
    failures = []

    for category in categories:
        try:
            articles.extend(
                _request_articles(
                    "top-headlines",
                    {"country": "us", "category": category, "pageSize": 20},
                )
            )
        except NewsAPIError as exc:
            failures.append(str(exc))
            logger.warning("Could not fetch %s headlines: %s", category, exc)

    for keyword in keywords:
        try:
            articles.extend(
                _request_articles(
                    "everything",
                    {"q": keyword, "pageSize": 20, "sortBy": "publishedAt"},
                )
            )
        except NewsAPIError as exc:
            failures.append(str(exc))
            logger.warning("Could not fetch news for %r: %s", keyword, exc)

    if not articles and failures:
        raise NewsAPIError("All NewsAPI requests failed: " + "; ".join(failures))

    return articles


def fetch_news_query(query: str) -> list[dict]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query must not be empty")

    return _request_articles(
        "everything",
        {
            "q": query.strip(),
            "pageSize": 10,
            "sortBy": "publishedAt",
        },
    )
