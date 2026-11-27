import logging
import os
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from .news_fetcher import fetch_news
from .database import SessionLocal
from .ingestion import ingest_articles

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler(timezone="UTC")

def ingest_news():
    articles = fetch_news()
    if not articles:
        logger.warning("Scheduled ingestion received no articles; freshness not confirmed")
        return
    db = SessionLocal()
    try:
        stats = ingest_articles(db, articles)
        logger.info("Scheduled ingestion: %s", stats)
    except Exception:
        db.rollback()
        logger.exception("Scheduled ingestion failed")
    finally:
        db.close()

def start_scheduler():
    if not scheduler.running:
        scheduler.add_job(ingest_news, "interval", minutes=max(180, int(os.getenv("INGEST_INTERVAL_MINUTES", "240"))), id="ingest_news",
                          replace_existing=True, max_instances=1, coalesce=True,
                          next_run_time=datetime.now(timezone.utc))
        scheduler.start()

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
