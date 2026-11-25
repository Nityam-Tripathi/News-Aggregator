import logging
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from .news_fetcher import fetch_news
from .database import SessionLocal
from .models import NewsArticle
from .embeddings import generate_embedding

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="UTC")

def ingest_news():
    db = SessionLocal()
    inserted = 0
    try:
        for article in fetch_news():
            title = article.get("title")
            content = article.get("description") or ""
            if not title or not content:
                continue
            if db.query(NewsArticle).filter(NewsArticle.title == title).first():
                continue
            try:
                embedding = generate_embedding(f"{title}. {content}")
            except Exception:
                logger.warning("Scheduled article embedding failed")
                continue
            published = article.get("publishedAt")
            try:
                timestamp = datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None
                if timestamp and timestamp.tzinfo:
                    timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
            except (ValueError, TypeError, AttributeError):
                timestamp = None
            db.add(NewsArticle(title=title, content=content, url=article.get("url"),
                image_url=article.get("urlToImage"), embedding=embedding, published_at=timestamp))
            inserted += 1
        db.commit()
        logger.info("Scheduled ingestion committed %s articles", inserted)
    except Exception:
        db.rollback()
        logger.exception("Scheduled ingestion failed")
    finally:
        db.close()

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(ingest_news, "interval", minutes=30, id="ingest_news",
                          replace_existing=True, max_instances=1, coalesce=True,
                          next_run_time=datetime.now(timezone.utc))
        scheduler.start()

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
