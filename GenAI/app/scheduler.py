from apscheduler.schedulers.background import BackgroundScheduler
from .news_fetcher import fetch_news
from .database import SessionLocal
from .models import NewsArticle
from .embeddings import generate_embedding

def job():
    db = SessionLocal()

    articles = fetch_news()

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

        embedding = [0.0] * 384  # safe

        news = NewsArticle(
            title=title,
            content=content,
            url=article.get("url"),
            image_url=article.get("urlToImage")
        )

        db.add(news)

    db.commit()
    db.close()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, "interval", minutes=30)  # every 30 min
    scheduler.start()