from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from .models import Base
from .news_fetcher import fetch_news
from .database import SessionLocal
from .models import NewsArticle
from sqlalchemy import desc
from sqlalchemy import text
from .embeddings import generate_embedding

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Only DB + vector setup
with engine.connect() as conn:
    try:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    except Exception as e:
        print("Vector extension issue:", e)

Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "Backend stable ✅"}

@app.get("/test")
def test():
    return {"status": "ok"}

@app.get("/news-test")
def news_test():
    articles = fetch_news()
    return {"count": len(articles)}

@app.get("/embed-test")
def embed_test():
    vec = generate_embedding("test text")
    return {"length": len(vec)}

@app.get("/ask")
def ask(query: str):
    db = SessionLocal()

    # 🔹 Fetch fresh news
    from .news_fetcher import fetch_news_query
    articles = fetch_news_query(query)

    for article in articles:
        title = article.get("title")
        content = article.get("description") or ""

        if not title or not content:
            continue

        exists = db.query(NewsArticle).filter(
            NewsArticle.title == title
        ).first()

        if exists:
            continue

        embedding = generate_embedding(title + content)

        news = NewsArticle(
            title=title,
            content=content,
            url=article.get("url"),
            image_url=article.get("urlToImage"),
            embedding=embedding
        )

        db.add(news)

    db.commit()

    # 🔹 Query DB
    query_embedding = generate_embedding(query)

    results = db.query(NewsArticle).order_by(
        desc(NewsArticle.id)
    ).limit(5).all()

    db.close()

    # 🔹 Simple answer (safe version)
    answer = "\n\n".join([a.title for a in results])

    return {
        "answer": answer,
        "sources": [
            {
                "title": a.title,
                "url": a.url,
                "image": a.image_url
            }
            for a in results
        ]
    }
    
@app.get("/top-news")
def top_news():
    db = SessionLocal()

    articles = db.query(NewsArticle).order_by(
        desc(NewsArticle.id)
    ).limit(10).all()

    db.close()

    return [
        {
            "title": a.title,
            "url": a.url,
            "image": a.image_url,
            "content": a.content
        }
        for a in articles
    ]
    
from collections import Counter
import re

@app.get("/trending")
def trending():
    db = SessionLocal()

    articles = db.query(NewsArticle).all()
    db.close()

    words = []

    for a in articles:
        clean = re.sub(r'[^a-zA-Z0-9 ]', '', a.title.lower())
        words.extend(clean.split())

    stopwords = {"the","is","in","on","at","and","to","of","for"}
    words = [w for w in words if w not in stopwords and len(w) > 3]

    counts = Counter(words).most_common(10)

    return [{"topic": w, "count": c} for w, c in counts]