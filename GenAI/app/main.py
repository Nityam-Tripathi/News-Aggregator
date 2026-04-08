from fastapi import FastAPI
from .database import engine, SessionLocal
from .models import Base, NewsArticle
from .news_fetcher import fetch_news
from .embeddings import generate_embedding
from .rag_pipeline import generate_answer
from .scheduler import start_scheduler
from .news_fetcher import fetch_news
from datetime import datetime,timedelta
from collections import Counter
import re
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


@app.post("/ingest")
def ingest():
    db = SessionLocal()
    articles = fetch_news()

    for article in articles:
        title = article.get("title")
        content = article.get("description") or ""
        published = article.get("publishedAt")

        try:
            if published:
                published_time = datetime.fromisoformat(
                    published.replace("Z", "+00:00")
                )
            else:
                published_time = None
        except Exception as e:
            print("Error parsing date:", e)
            published_time = None

        if title and content:
            combined_text = f"{title}. {content}"
            embedding = generate_embedding(combined_text)
            
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
    db.close()

    return {"message": "News inserted with embeddings"}


@app.get("/search")
def search(query: str):
    db = SessionLocal()

    # Convert query → embedding
    expanded_query = f"{query} artificial intelligence AI technology news latest updates"
    query_embedding = generate_embedding(expanded_query)

    # Vector similarity search
    results = db.query(NewsArticle).order_by(
        NewsArticle.embedding.cosine_distance(query_embedding)
    ).limit(10).all()

    db.close()

    return [
        {
            "title": article.title,
            "content": article.content
        }
        for article in results
    ]
    
@app.get("/ask")
def ask(query: str):
    db = SessionLocal()

    # 🔥 STEP 1: Fetch fresh news for this query
    from .news_fetcher import fetch_news_query

    fresh_articles = fetch_news_query(query)

    for article in fresh_articles:
        title = article.get("title")
        content = article.get("description") or ""

        if not title or not content:
            continue

        # Avoid duplicates
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
        published_at=published_time,   # ✅ ADD THIS
        embedding=embedding
        )

        db.add(news)

    db.commit()

    # 🔥 STEP 2: Now perform semantic search
    expanded_query = f"{query} news latest updates"
    query_embedding = generate_embedding(expanded_query)

    raw_results = db.query(NewsArticle).order_by(
        NewsArticle.embedding.cosine_distance(query_embedding),
        NewsArticle.published_at.desc()
    ).limit(15).all()

    # Remove duplicates
    seen = set()
    results = []

    for article in raw_results:
        if article.title not in seen:
            seen.add(article.title)
            results.append(article)

        if len(results) == 5:
            break

    # 🔥 STEP 3: Build context
    context = "\n\n".join([
        f"""
Article {i+1}:
Title: {article.title}
Content: {article.content}
"""
        for i, article in enumerate(results)
    ])

    db.close()

    # 🔥 STEP 4: Generate answer
    answer = generate_answer(query, context)

    return {
        "query": query,
        "answer": answer,
        "sources": [
            {
                "title": article.title,
                "url": article.url,
                "image": article.image_url,
                "published_at": str(article.published_at)
            }
            for article in results
        ]
    }
    
@app.get("/top-news")
def top_news():
    db = SessionLocal()

    articles = db.query(NewsArticle).order_by(
        NewsArticle.id.desc()
    ).limit(10).all()

    db.close()

    return [
        {
            "title": article.title,
            "url": article.url,
            "image": article.image_url, 
            "content": article.content,
            "published_at": str(article.published_at)
        }
        for article in articles
    ]
    
@app.get("/analytics")
def analytics():
    db = SessionLocal()

    articles = db.query(NewsArticle).all()

    data = [
        {
            "title": a.title,
            "content": a.content
        }
        for a in articles
    ]

    db.close()

    return data

@app.get("/trending")
def trending():
    db = SessionLocal()

    # 🔥 Last 24 hours
    time_limit = datetime.utcnow() - timedelta(hours=24)

    articles = db.query(NewsArticle).filter(
        NewsArticle.published_at != None,
        NewsArticle.published_at >= time_limit
    ).all()

    db.close()

    # 🔥 Extract words
    words = []

    for article in articles:
        title = article.title.lower()

        # Remove symbols
        clean = re.sub(r'[^a-zA-Z0-9 ]', '', title)

        words.extend(clean.split())

    # 🔥 Remove useless words
    stopwords = {
        "the", "is", "in", "on", "at", "a", "an", "and",
        "to", "of", "for", "with", "by", "from", "as"
    }

    filtered = [w for w in words if w not in stopwords and len(w) > 3]

    # 🔥 Count frequency
    counts = Counter(filtered).most_common(10)

    return [
        {"topic": word, "count": count}
        for word, count in counts
    ]