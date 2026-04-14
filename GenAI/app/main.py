from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, SessionLocal
from .models import Base, NewsArticle
from .news_fetcher import fetch_news, fetch_news_query
from .embeddings import generate_embedding
from .rag_pipeline import generate_answer

from sqlalchemy import desc, text
from datetime import datetime, timedelta
from collections import Counter
import re

app = FastAPI()

# ✅ CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Ensure vector extension
with engine.connect() as conn:
    try:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    except Exception as e:
        print("Vector extension issue:", e)

# ✅ Create tables
Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "AI News Backend 🚀"}


@app.get("/test")
def test():
    return {"status": "ok"}

@app.get("/ask")
def ask(query: str):
    db = SessionLocal()

    # 🔹 Dynamic fetch
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
        embedding = generate_embedding(combined)

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

    # 🔹 Search
    query_embedding = generate_embedding(query)

    results = db.query(NewsArticle).order_by(
        NewsArticle.embedding.cosine_distance(query_embedding),
        desc(NewsArticle.published_at)
    ).limit(5).all()

    context = "\n\n".join([
        f"Title: {a.title}\nContent: {a.content}"
        for a in results
    ])

    db.close()

    answer = generate_answer(query, context)

    return {
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
    
@app.get("/top-news")
def top_news():
    db = SessionLocal()

    articles = db.query(NewsArticle).order_by(
        desc(NewsArticle.published_at)
    ).limit(10).all()

    db.close()

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
    
@app.get("/trending")
def trending():
    db = SessionLocal()

    time_limit = datetime.utcnow() - timedelta(hours=24)

    articles = db.query(NewsArticle).filter(
        NewsArticle.published_at != None,
        NewsArticle.published_at >= time_limit
    ).all()

    db.close()

    words = []

    for a in articles:
        clean = re.sub(r'[^a-zA-Z0-9 ]', '', a.title.lower())
        words.extend(clean.split())

    stopwords = {"the","is","in","on","at","and","to","of","for","with"}
    words = [w for w in words if w not in stopwords and len(w) > 3]

    counts = Counter(words).most_common(10)

    return [{"topic": w, "count": c} for w, c in counts]

