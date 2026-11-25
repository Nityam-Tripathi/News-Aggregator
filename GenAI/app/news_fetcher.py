import logging
import os
import requests
from threading import Lock
from time import monotonic

_lock = Lock()
_blocked_until = 0.0
_attempts = []

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def _fetch(endpoint, params):
    global _blocked_until
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        logger.warning("NEWS_API_KEY is not configured")
        return []
    with _lock:
        now = monotonic()
        _attempts[:] = [t for t in _attempts if t > now - 86400]
        if now < _blocked_until or len(_attempts) >= 80:
            return []
        _attempts.append(now)
    try:
        response = requests.get(
            f"https://newsapi.org/v2/{endpoint}",
            params=params, headers={"X-Api-Key": api_key}, timeout=(3, 10)
        )
        if not response.ok:
            try:
                code = response.json().get("code", "unknown")
            except (ValueError, AttributeError):
                code = "unknown"
            safe_codes = {"apiKeyDisabled", "apiKeyExhausted", "apiKeyInvalid", "apiKeyMissing", "rateLimited", "parameterInvalid", "parametersMissing", "sourcesTooMany", "sourceDoesNotExist", "unexpectedError"}
            logger.warning("NewsAPI failure endpoint=%s status=%s code=%s", endpoint, response.status_code, code if isinstance(code, str) and code in safe_codes else "unknown")
            if response.status_code in (401, 403, 426, 429) or code in ("apiKeyExhausted", "rateLimited"):
                with _lock:
                    _blocked_until = max(_blocked_until, monotonic() + (3600 if response.status_code == 429 or code in ("apiKeyExhausted", "rateLimited") else 900))
            return []
        data = response.json()
        if data.get("status") != "ok":
            logger.warning("NewsAPI returned an unsuccessful response")
            return []
        articles = data.get("articles", [])
        return [a for a in articles if isinstance(a, dict)] if isinstance(articles, list) else []
    except (requests.RequestException, ValueError, AttributeError) as exc:
        logger.warning("NewsAPI request failed endpoint=%s type=%s", endpoint, type(exc).__name__)
        return []

def fetch_news():
    articles = []
    for category in ("technology", "business", "science", "health"):
        articles.extend(_fetch("top-headlines", {"country": "us", "category": category, "pageSize": 20}))
    for keyword in ("artificial intelligence", "machine learning", "startup", "economy", "crypto", "global politics"):
        articles.extend(_fetch("everything", {"q": keyword, "pageSize": 20, "sortBy": "publishedAt"}))
    return articles

def fetch_news_query(query):
    return _fetch("everything", {"q": query, "pageSize": 10, "sortBy": "publishedAt"})
