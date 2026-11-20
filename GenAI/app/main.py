import logging
import os
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import SessionLocal, engine
from .embeddings import generate_embedding
from .models import Base, NewsArticle
from .news_fetcher import NewsAPIError, fetch_news, fetch_news_query
from .rag_pipeline import generate_answer
from .scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)

app = FastAPI(title="AI News Aggregator")

# Configure comma-separated frontend origins in CORS_ORIGINS.
# Wildcard origins are supported only without credentialed requests.
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]
allow_credentials = "*" not in cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
except Exception:
    logger.exception("Could not create the PostgreSQL vector extension")

Base.metadata.create_all(bind=engine)


def _parse_published_at(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except (TypeError, ValueError):
        return None


def _store_articles(db, articles):
    """Persist new articles; never save an article with a failed embedding."""
    inserted = 0
    skipped = 0
    embedding_failures = 0

    for article in articles:
        title = article.get("title")
        content = article.get("description") or ""
        url = article.get("url")

        if not title or not content:
            skipped += 1
            continue

        duplicate_query = db.query(NewsArticle)
        if url:
            exists = duplicate_query.filter(NewsArticle.url == url).first()
        else:
            exists = duplicate_query.filter(NewsArticle.title == title).first()

        if exists:
            skipped += 1
            continue

        try:
            embedding = generate_embedding(f"{title}. {content}")
        except (RuntimeError, ValueError):
            embedding_failures += 1
            logger.exception("Skipping article because embedding failed: %s", title)
            continue

        db.add(
            NewsArticle(
                title=title,
                content=content,
                url=url,
                image_url=article.get("urlToImage"),
                published_at=_parse_published_at(article.get("publishedAt")),
                embedding=embedding,
            )
        )
        inserted += 1

    return {
        "inserted": inserted,
        "skipped": skipped,
        "embedding_failures": embedding_failures,
    }


@app.on_event("startup")
def on_startup():
    start_scheduler()


@app.on_event("shutdown")
def on_shutdown():
    stop_scheduler()


@app.get("/")
def root():
    return {"message": "AI News Aggregator running"}


@app.get("/test")
def test():
    return {"status": "ok"}


@app.post("/ingest")
def ingest():
    db = SessionLocal()
    try:
        try:
            articles = fetch_news()
        except NewsAPIError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        result = _store_articles(db, articles)
        db.commit()
        return {
            "message": "News ingestion complete",
            "fetched": len(articles),
            **result,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Manual ingestion failed")
        raise HTTPException(
            status_code=500, detail="News ingestion failed"
        ) from exc
    finally:
        db.close()


@app.get("/ask")
def ask(query: str = Query(..., min_length=1, max_length=500)):
    db = SessionLocal()
    try:
        try:
            fresh_articles = fetch_news_query(query)
        except NewsAPIError:
            # Continue with already indexed articles if NewsAPI is unavailable.
            logger.warning("Live news search failed; using indexed articles", exc_info=True)
            fresh_articles = []

        _store_articles(db, fresh_articles)
        db.commit()

        try:
            query_embedding = generate_embedding(query)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(
                status_code=503,
                detail="The embedding service is temporarily unavailable",
            ) from exc

        results = (
            db.query(NewsArticle)
            .filter(NewsArticle.embedding.isnot(None))
            .order_by(NewsArticle.embedding.cosine_distance(query_embedding))
            .limit(5)
            .all()
        )

        if not results:
            raise HTTPException(
                status_code=404,
                detail="No indexed news articles are available yet",
            )

        context = "\n\n".join(
            f"{article.title}. {article.content}" for article in results
        )

        try:
            answer = generate_answer(query, context)
        except Exception as exc:
            logger.exception("Answer generation failed")
            raise HTTPException(
                status_code=503,
                detail="The AI answer service is temporarily unavailable",
            ) from exc

        return {
            "query": query,
            "answer": answer,
            "sources": [
                {
                    "title": article.title,
                    "url": article.url,
                    "image": article.image_url,
                    "published_at": str(article.published_at)
                    if article.published_at
                    else None,
                }
                for article in results
            ],
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("News question request failed")
        raise HTTPException(
            status_code=500, detail="Could not process the news question"
        ) from exc
    finally:
        db.close()


@app.get("/top-news")
def top_news():
    db = SessionLocal()
    try:
        # Refresh the database before reading it. If the provider is down,
        # continue serving the most recently stored articles.
        try:
            fresh_articles = fetch_news()
            _store_articles(db, fresh_articles)
            db.commit()
        except NewsAPIError:
            db.rollback()
            logger.warning("News refresh failed; returning cached articles", exc_info=True)

        articles = (
            db.query(NewsArticle)
            .order_by(NewsArticle.published_at.desc().nullslast(), NewsArticle.id.desc())
            .limit(10)
            .all()
        )

        return [
            {
                "title": article.title,
                "url": article.url,
                "image": article.image_url,
                "content": article.content,
                "published_at": str(article.published_at)
                if article.published_at
                else None,
            }
            for article in articles
        ]
    finally:
        db.close()


@app.get("/analytics")
def analytics():
    db = SessionLocal()
    try:
        articles = db.query(NewsArticle).all()
        return [
            {"title": article.title, "content": article.content}
            for article in articles
        ]
    finally:
        db.close()


@app.get("/trending")
def trending():
    db = SessionLocal()
    try:
        time_limit = datetime.utcnow() - timedelta(hours=24)
        articles = (
            db.query(NewsArticle)
            .filter(
                NewsArticle.published_at.isnot(None),
                NewsArticle.published_at >= time_limit,
            )
            .all()
        )

        words = []
        for article in articles:
            clean = re.sub(r"[^a-zA-Z0-9 ]", "", article.title.lower())
            words.extend(clean.split())

        stopwords = {
            "the", "is", "in", "on", "at", "a", "an", "and",
            "to", "of", "for", "with", "by", "from", "as",
        }
        filtered = [
            word for word in words if word not in stopwords and len(word) > 3
        ]
        return [
            {"topic": word, "count": count}
            for word, count in Counter(filtered).most_common(10)
        ]
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000)),
    )
