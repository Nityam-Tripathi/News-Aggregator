from apscheduler.schedulers.background import BackgroundScheduler
from .news_fetcher import fetch_news
from .database import SessionLocal
from .models import NewsArticle
from datetime import datetime
from .embeddings import generate_embedding

def ingest_news():

    print("🔄 Running scheduled ingestion...")

    db = SessionLocal()
    articles = fetch_news()

    for article in articles:
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

        combined_text = f"{title}. {content}"
        embedding = generate_embedding(combined_text)

        news = NewsArticle(
            title=title,
            content=content,
            url=article.get("url"),
            image_url=article.get("urlToImage"),
            embedding=embedding
        )

        db.add(news)

    db.commit()
    db.close()

    print("✅ News ingestion complete")


def start_scheduler():
    scheduler = BackgroundScheduler()
    
    ingest_news()

    # Run every 30 minutes
    scheduler.add_job(ingest_news, "interval", minutes=30)

    scheduler.start()

    print("🚀 Scheduler started")