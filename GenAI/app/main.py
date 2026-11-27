from fastapi import FastAPI, HTTPException, Query, Header, Request, Depends
from secrets import compare_digest
import logging
from .database import engine, SessionLocal
from .ingestion import ingest_articles
from .answer_cache import answer_cache, cache_key
from .answer_quality import assess_answer, evidence_context, FALLBACK
from fastapi.responses import StreamingResponse
import json
from contextlib import aclosing
from .models import Base, NewsArticle
from .news_fetcher import fetch_news, fetch_news_query
from .embeddings import generate_embedding
from .rag_pipeline import generate_answer, stream_answer, model_name, PROMPT_VERSION
from .hybrid import search_articles
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
        return {"message": "News ingestion complete", **ingest_articles(db, fetch_news())}
    except Exception:
        db.rollback()
        raise
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

NO_RESULTS = "No sufficiently relevant news articles found."

def prepare_answer(query):
    query = query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="Query must not be blank")
    db = SessionLocal()
    try:
        if os.getenv("SEARCH_FETCH_FRESH", "false").lower() == "true":
            ingest_articles(db, fetch_news_query(query))
        try:
            embedding = generate_embedding(query)
        except Exception:
            logger.warning("Query embedding failed")
            raise HTTPException(status_code=503, detail="Search temporarily unavailable")
        results = search_articles(db, query, embedding)
        context = evidence_context(results)
        sources = [{"source_id":i,"title":a.title,"url":a.url,"image":a.image_url,
            "published_at":a.published_at.isoformat() if a.published_at else None} for i,a in enumerate(results,1)]
        return query, context, sources
    finally:
        db.close()

@app.get("/ask", dependencies=[Depends(limit_search)])
def ask(query: str = Query(..., min_length=1, max_length=500)):
    query, context, sources = prepare_answer(query)
    if not sources:
        return {"query":query,"answer":NO_RESULTS,"sources":[]}
    key = cache_key(query, context, sources, model_name(), PROMPT_VERSION)
    answer = answer_cache.get(key)
    if answer is None:
        try:
            answer = generate_answer(query, context)
        except Exception:
            logger.warning("Answer generation failed")
            raise HTTPException(status_code=503, detail="Answer generation temporarily unavailable")
        quality = assess_answer(answer, context, len(sources))
        if not quality.accepted:
            logger.info("Answer evidence screening flagged: %s", quality.issues)
            return {"query":query,"answer":FALLBACK,"sources":sources,"quality":"flagged"}
        if quality.status == "screened":
            answer_cache.put(key, answer)
    return {"query":query,"answer":answer,"sources":sources,
            "quality":assess_answer(answer, context, len(sources)).status}

def sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

async def answer_events(query, context, sources):
    yield sse("sources", sources)
    if not sources:
        yield sse("delta", {"text":NO_RESULTS})
        yield sse("done", {})
        return
    key = cache_key(query, context, sources, model_name(), PROMPT_VERSION)
    cached = answer_cache.get(key)
    if cached is not None:
        yield sse("delta", {"text":cached})
        yield sse("done", {})
        return
    parts = []
    try:
        async with aclosing(stream_answer(query, context)) as stream:
            async for delta in stream:
                parts.append(delta)
                yield sse("delta", {"text":delta})
        answer = "".join(parts)
        if not answer.strip():
            raise ValueError("Empty answer stream")
        quality = assess_answer(answer, context, len(sources))
        if not quality.accepted:
            logger.info("Stream evidence screening flagged: %s", quality.issues)
            yield sse("replace", {"text":FALLBACK})
        elif quality.status == "screened":
            answer_cache.put(key, answer)
        yield sse("done", {"quality":quality.status})
    except Exception:
        logger.warning("Answer streaming failed")
        yield sse("error", {"message":"Answer generation interrupted. Please retry."})

@app.get("/ask/stream", dependencies=[Depends(limit_search)])
def ask_stream(query: str = Query(..., min_length=1, max_length=500)):
    query, context, sources = prepare_answer(query)
    return StreamingResponse(answer_events(query, context, sources), media_type="text/event-stream",
        headers={"Cache-Control":"no-cache, no-transform","X-Accel-Buffering":"no"})

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
