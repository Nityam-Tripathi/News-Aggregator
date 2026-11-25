import logging
import os
import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

def _fetch(endpoint, params):
    api_key = os.getenv("NEWS_API_KEY")
    if not api_key:
        logger.warning("NEWS_API_KEY is not configured")
        return []
    try:
        response = requests.get(
            f"https://newsapi.org/v2/{endpoint}",
            params=params, headers={"X-Api-Key": api_key}, timeout=(3, 10)
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "ok":
            logger.warning("NewsAPI returned an unsuccessful response")
            return []
        articles = data.get("articles", [])
        return [a for a in articles if isinstance(a, dict)] if isinstance(articles, list) else []
    except (requests.RequestException, ValueError):
        logger.warning("NewsAPI request failed for %s", endpoint)
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
