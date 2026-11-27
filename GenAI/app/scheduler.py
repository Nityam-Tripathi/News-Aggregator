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

def env_bool(name, default="false"):
    value = os.getenv(name, default).strip().lower()
    if value not in ("true", "false"):
        raise ValueError(f"{name} must be true or false")
    return value == "true"

def start_scheduler():
    if not env_bool("INGEST_SCHEDULER_ENABLED"):
        logger.info("Scheduled ingestion disabled")
        return
    if not scheduler.running:
        interval = max(180, int(os.getenv("INGEST_INTERVAL_MINUTES", "240")))
        options = {}
        if env_bool("INGEST_RUN_ON_STARTUP"):
            options["next_run_time"] = datetime.now(timezone.utc)
        scheduler.add_job(ingest_news, "interval", minutes=interval, id="ingest_news",
                          replace_existing=True, max_instances=1, coalesce=True, **options)
        scheduler.start()

def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
