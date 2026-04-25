
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


import os
import requests

def ping_server():
    server_url = os.getenv("SERVER_URL", "http://127.0.0.1:8000")
    try:
        requests.get(f"{server_url}/test", timeout=5)
        print(f"🏓 Pinged {server_url}/test to keep awake")
    except Exception as e:
        print(f"⚠️ Ping failed: {e}")

def start_scheduler():
    scheduler = BackgroundScheduler()
    
    ingest_news()

    # Run every 10 minutes
    scheduler.add_job(ingest_news, "interval", minutes=10)
    scheduler.add_job(ping_server, "interval", minutes=10)

    scheduler.start()

    print("🚀 Scheduler started")