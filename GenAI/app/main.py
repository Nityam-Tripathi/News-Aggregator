from fastapi import FastAPI
from .database import engine, SessionLocal
from .models import Base, NewsArticle
from .news_fetcher import fetch_news, fetch_news_query
from .embeddings import generate_embedding
from .rag_pipeline import generate_answer
from .scheduler import start_scheduler 

from datetime import datetime, timedelta
from collections import Counter
import re
import os

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

@app.on_event("startup")
def start():
    start_scheduler()

@app.get("/")
def root():
    return {"message": "AI News Aggregator running"}


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
def ingest():
    db = SessionLocal()
    try:
        articles = fetch_news()

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
                combined_text = f"{title}. {content}"

                # 🔥 SAFE EMBEDDING
                try:
                    embedding = generate_embedding(combined_text)
                except:
                    embedding = [0.0] * 384

                news = NewsArticle(
                    title=title,
                    content=content,
                    url=article.get("url"),
                    image_url=article.get("urlToImage"),
                    published_at=published_time,
                    embedding=embedding
                )

                db.add(news)

        db.commit()
        return {"message": "News inserted with embeddings"}

    finally:
        db.close()


@app.get("/ask")
def ask(query: str):
    db = SessionLocal()

    try:
        fresh_articles = fetch_news_query(query)

        for article in fresh_articles:
            title = article.get("title")
            content = article.get("description") or ""

            if not title or not content:
                continue

            exists = db.query(NewsArticle).filter(
                NewsArticle.title == title
            ).first()

            if exists:
                continue

            combined = f"{title}. {content}"

            try:
                embedding = generate_embedding(combined)
            except:
                embedding = [0.0] * 384

            published = article.get("publishedAt")

            try:
                published_time = datetime.fromisoformat(
                    published.replace("Z", "+00:00")
                ) if published else None
            except:
                published_time = None

            news = NewsArticle(
                title=title,
                content=content,
                url=article.get("url"),
                image_url=article.get("urlToImage"),
                published_at=published_time,
                embedding=embedding
            )

            db.add(news)

        db.commit()

        # 🔍 Search
        query_embedding = generate_embedding(query)

        results = db.query(NewsArticle).order_by(
            NewsArticle.id.desc()
        ).limit(5).all()

        context = "\n\n".join([
            f"{a.title}. {a.content}" for a in results
        ])

        try:
            answer = generate_answer(query, context)
        except:
            answer = context[:500]

        return {
            "query": query,
            "answer": answer,
            "sources": [
                {
                    "title": a.title,
                    "url": a.url,
                    "image": a.image_url,
                    "published_at": str(a.published_at)
                }
                for a in results
            ]
        }

    finally:
        db.close()


@app.get("/top-news")
def top_news():
    fresh = fetch_news()
    db = SessionLocal()
    try:
        articles = db.query(NewsArticle).order_by(
            NewsArticle.id.desc()
        ).limit(10).all()

        return [
            {
                "title": a.title,
                "url": a.url,
                "image": a.image_url,
                "content": a.content,
                "published_at": str(a.published_at)
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