from fastapi import FastAPI, HTTPException, Query, Header, Request, Depends
from secrets import compare_digest
import logging
from .database import engine, SessionLocal
from .url_identity import url_key
from sqlalchemy.dialects.postgresql import insert
from .models import Base, NewsArticle
from .news_fetcher import fetch_news, fetch_news_query
from .embeddings import generate_embedding
from .rag_pipeline import generate_answer
from .scheduler import start_scheduler, stop_scheduler 

from datetime import datetime, timedelta, timezone
from collections import Counter, deque
from threading import Lock
from time import monotonic
import re
import os

from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import text, func

app = FastAPI()
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "https://insightstream-three.vercel.app,http://localhost:5173,http://localhost:8080").split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schema changes are managed explicitly by Alembic.

@app.on_event("startup")
def start():
    start_scheduler()

@app.on_event("shutdown")
def shutdown():
    stop_scheduler()

@app.get("/")
def root():
    return {"message": "AI News Aggregator running"}


@app.get("/ready")
def ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Database unavailable")
    return {"status": "ok", "database": "reachable"}


@app.get("/test")
def test():
    return {"status": "ok"}


# 🔥 SAFE DB HANDLER
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/ingest")
def ingest(x_admin_key: str = Header(default="")):
    admin_key = os.getenv('INGEST_ADMIN_KEY')
    if not admin_key:
        raise HTTPException(status_code=503, detail='Manual ingestion is disabled')
    if not compare_digest(x_admin_key.encode('utf-8'), admin_key.encode('utf-8')):
        raise HTTPException(status_code=403, detail='Forbidden')
    db = SessionLocal()
    try:
        articles = fetch_news()
        fetched_count = len(articles)
        inserted_count = 0
        skipped_count = 0
        failed_count = 0

        for article in articles:
            title = article.get("title")
            content = article.get("description") or ""
            published = article.get("publishedAt")

            try:
                published_time = datetime.fromisoformat(
                    published.replace("Z", "+00:00")
                ) if published else None
            except:
                published_time = None

            if title and content:
                key = url_key(article.get("url"))
            exists = db.query(NewsArticle).filter(NewsArticle.url_key == key).first() if key else db.query(NewsArticle).filter(NewsArticle.title == title).first()

                if exists:
                    skipped_count += 1
                    continue

                combined_text = f"{title}. {content}"

                # 🔥 SAFE EMBEDDING
                try:
                    embedding = generate_embedding(combined_text)
                except Exception:
                    logger.exception('Article embedding failed')
                    failed_count += 1
                    continue

                news = insert(NewsArticle).values(url_key=key,
                    title=title,
                    content=content,
                    url=article.get("url"),
                    image_url=article.get("urlToImage"),
                    published_at=published_time,
                    embedding=embedding
                )

                result = db.execute(news.on_conflict_do_nothing(index_elements=["url_key"]))
                inserted_count += result.rowcount
                skipped_count += 1 - result.rowcount
            else:
                skipped_count += 1

        db.commit()
        print(
            "Manual ingestion complete: "
            f"fetched={fetched_count}, inserted={inserted_count}, "
            f"skipped={skipped_count}, embedding_failures={failed_count}"
        )
        return {
            "message": "News ingestion complete",
            "fetched": fetched_count,
            "inserted": inserted_count,
            "skipped": skipped_count,
            "embedding_failures": failed_count
        }

    finally:
        db.close()


# Per-process limits; use a shared store for multi-worker deployments.
_rate_lock = Lock()
_rate_buckets = {}
_global_requests = deque()

def limit_search(request: Request):
    now = monotonic()
    key = request.client.host if request.client else "unknown"
    with _rate_lock:
        for ip, bucket in list(_rate_buckets.items()):
            if not bucket or bucket[-1] <= now - 60:
                del _rate_buckets[ip]
        while _global_requests and _global_requests[0] <= now - 60:
            _global_requests.popleft()
        bucket = _rate_buckets.get(key, deque())
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= 5 or len(_global_requests) >= 30:
            raise HTTPException(status_code=429, detail="Too many search requests. Try again shortly.",
                                headers={"Retry-After": "60"})
        bucket.append(now)
        _rate_buckets[key] = bucket
        _global_requests.append(now)

@app.get("/ask", dependencies=[Depends(limit_search)])
def ask(query: str = Query(..., min_length=1, max_length=500)):
    query = query.strip()
    if not query:
        raise HTTPException(status_code=422, detail='Query must not be blank')
    db = SessionLocal()

    try:
        fresh_articles = fetch_news_query(query) if os.getenv("SEARCH_FETCH_FRESH", "false").lower() == "true" else []

        for article in fresh_articles:
            title = article.get("title")
            content = article.get("description") or ""

            if not title or not content:
                continue

            key = url_key(article.get("url"))
            exists = db.query(NewsArticle).filter(NewsArticle.url_key == key).first() if key else db.query(NewsArticle).filter(NewsArticle.title == title).first()

            if exists:
                continue

            combined = f"{title}. {content}"

            try:
                embedding = generate_embedding(combined)
            except Exception:
                logger.exception('Article embedding failed')
                continue

            published = article.get("publishedAt")

            try:
                published_time = datetime.fromisoformat(
                    published.replace("Z", "+00:00")
                ) if published else None
            except:
                published_time = None

            news = insert(NewsArticle).values(url_key=key,
                title=title,
                content=content,
                url=article.get("url"),
                image_url=article.get("urlToImage"),
                published_at=published_time,
                embedding=embedding
            )

            db.execute(news.on_conflict_do_nothing(index_elements=["url_key"]))

        db.commit()

        # 🔍 Semantic Search using pgvector cosine distance
        try:
            query_embedding = generate_embedding(query)
        except Exception:
            logger.exception('Query embedding failed')
            raise HTTPException(status_code=503, detail='Search temporarily unavailable')

        distance = NewsArticle.embedding.cosine_distance(query_embedding)
        results = db.query(NewsArticle).filter(distance <= 0.65).order_by(distance).limit(5).all()
        if not results:
            return {'query': query, 'answer': 'No sufficiently relevant news articles found.', 'sources': []}

        context = "\n\n".join([
            f"{a.title}. {a.content}" for a in results
        ])

        try:
            answer = generate_answer(query, context)
        except Exception:
            logger.exception('Answer generation failed')
            raise HTTPException(status_code=503, detail='Answer generation temporarily unavailable')

        return {
            "query": query,
            "answer": answer,
            "sources": [
                {
                    "title": a.title,
                    "url": a.url,
                    "image": a.image_url,
                    "published_at": a.published_at.isoformat() if a.published_at else None
                }
                for a in results
            ]
        }

    finally:
        db.close()


@app.get("/freshness")
def freshness():
    db = SessionLocal()
    try:
        latest = db.query(func.max(NewsArticle.published_at)).scalar()
        if latest is None:
            return {"latest_published_at": None, "age_hours": None, "stale": True}
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        age = max(0, (datetime.now(timezone.utc) - latest).total_seconds() / 3600)
        return {"latest_published_at": latest.isoformat(), "age_hours": round(age, 2), "stale": age >= 24}
    finally:
        db.close()


@app.get("/top-news")
def top_news():
    db = SessionLocal()
    try:
        articles = db.query(NewsArticle).order_by(
            NewsArticle.published_at.desc().nullslast(), NewsArticle.id.desc()
        ).limit(10).all()

        return [
            {
                "title": a.title,
                "url": a.url,
                "image": a.image_url,
                "content": a.content,
                "published_at": a.published_at.isoformat() if a.published_at else None
            }
            for a in articles
        ]
    finally:
        db.close()


@app.get("/analytics")
def analytics():
    db = SessionLocal()
    try:
        articles = db.query(NewsArticle).all()

        return [
            {"title": a.title, "content": a.content}
            for a in articles
        ]
    finally:
        db.close()


@app.get("/trending")
def trending():
    db = SessionLocal()

    try:
        time_limit = datetime.utcnow() - timedelta(hours=24)

        articles = db.query(NewsArticle).filter(
            NewsArticle.published_at != None,
            NewsArticle.published_at >= time_limit
        ).all()

        words = []

        for a in articles:
            clean = re.sub(r'[^a-zA-Z0-9 ]', '', a.title.lower())
            words.extend(clean.split())

        stopwords = {
            "the", "is", "in", "on", "at", "a", "an", "and",
            "to", "of", "for", "with", "by", "from", "as"
        }

        filtered = [w for w in words if w not in stopwords and len(w) > 3]

        counts = Counter(filtered).most_common(10)

        return [{"topic": w, "count": c} for w, c in counts]

    finally:
        db.close()


# 🚀 Render start
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 10000))
    )
