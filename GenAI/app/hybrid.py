"""Keyword + semantic rank fusion. Recency cannot introduce non-matching documents."""
import os
from datetime import datetime, timezone
from sqlalchemy import func, literal_column
from .models import NewsArticle
from .retrieval import retrieve_articles, TOP_K
from .url_identity import url_key

CANDIDATES = 20
RRF_K = 60
RECENCY_WEIGHT = 0.15
HALF_LIFE_DAYS = 30

def lexical_search(db, query, limit=CANDIDATES):
    tsquery = func.websearch_to_tsquery(literal_column("'english'::regconfig"), query)
    rank = func.ts_rank_cd(NewsArticle.search_document, tsquery)
    return (db.query(NewsArticle)
        .filter(NewsArticle.search_document.op("@@")(tsquery))
        .order_by(rank.desc(), NewsArticle.id.asc()).limit(limit).all())

def identity(article):
    return url_key(article.url) or f"id:{article.id}"

def recency_multiplier(article, now, weight):
    published = article.published_at
    if not published:
        return 1.0
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    if published > now:
        return 1.0
    age = (now - published).total_seconds() / 86400
    return 1 + weight * 2 ** (-age / HALF_LIFE_DAYS)

def fuse(rankings, limit=TOP_K, recency_weight=RECENCY_WEIGHT, now=None):
    if not 0 <= recency_weight <= 0.25:
        raise ValueError("Recency weight must be between 0 and 0.25")
    now = now or datetime.now(timezone.utc)
    scores, articles = {}, {}
    for ranking in rankings:
        seen = set()
        for article in ranking:
            key = identity(article)
            if key in seen:
                continue
            seen.add(key)
            articles.setdefault(key, article)
            scores[key] = scores.get(key, 0) + 1 / (RRF_K + len(seen))
    ranked = sorted(scores, key=lambda key: (-scores[key]*recency_multiplier(articles[key], now, recency_weight), articles[key].id))
    return [articles[key] for key in ranked[:limit]]

def hybrid_search(db, query, embedding, recency_weight=RECENCY_WEIGHT, now=None):
    # Keyword first: exact vector retrieval changes planner settings locally.
    lexical = lexical_search(db, query)
    semantic = retrieve_articles(db, embedding, limit=CANDIDATES)
    return fuse([lexical, semantic], recency_weight=recency_weight, now=now)

def search_articles(db, query, embedding):
    mode = os.getenv("RETRIEVAL_MODE", "semantic").strip().lower()
    if mode == "semantic":
        return retrieve_articles(db, embedding)
    if mode == "hybrid":
        return hybrid_search(db, query, embedding)
    raise ValueError("RETRIEVAL_MODE must be semantic or hybrid")
