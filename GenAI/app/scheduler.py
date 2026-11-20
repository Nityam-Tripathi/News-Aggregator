import logging
import os
from datetime import datetime

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from .database import SessionLocal
from .embeddings import generate_embedding
from .models import NewsArticle
from .news_fetcher import NewsAPIError, fetch_news

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()


def _parse_published_at(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except (TypeError, ValueError):
        return None


def ingest_news():
    """Fetch and persist new articles without storing invalid embeddings."""
    logger.info("Starting scheduled news ingestion")
    db = SessionLocal()

    try:
        articles = fetch_news()
        inserted = 0
        skipped = 0
        embedding_failures = 0

        for article in articles:
            title = article.get("title")
            content = article.get("description") or ""
            url = article.get("url")

            if not title or not content:
                skipped += 1
                continue

            duplicate_query = db.query(NewsArticle)
            if url:
                exists = duplicate_query.filter(
                    NewsArticle.url == url
                ).first()
            else:
                exists = duplicate_query.filter(
                    NewsArticle.title == title
                ).first()

            if exists:
                skipped += 1
                continue

            try:
                embedding = generate_embedding(f"{title}. {content}")
            except (RuntimeError, ValueError):
                embedding_failures += 1
                logger.exception("Skipping article because embedding failed: %s", title)
                continue

            db.add(
                NewsArticle(
                    title=title,
                    content=content,
                    url=url,
                    image_url=article.get("urlToImage"),
                    published_at=_parse_published_at(article.get("publishedAt")),
                    embedding=embedding,
                )
            )
            inserted += 1

        db.commit()
        logger.info(
            "Scheduled ingestion complete: fetched=%s inserted=%s skipped=%s "
            "embedding_failures=%s",
            len(articles),
            inserted,
            skipped,
            embedding_failures,
        )
        return {
            "fetched": len(articles),
            "inserted": inserted,
            "skipped": skipped,
            "embedding_failures": embedding_failures,
        }
    except NewsAPIError:
        db.rollback()
        logger.exception("Scheduled ingestion could not fetch news")
        return {"error": "NewsAPI request failed"}
    except Exception:
        db.rollback()
        logger.exception("Unexpected scheduled ingestion failure")
        return {"error": "Scheduled ingestion failed"}
    finally:
        db.close()


def ping_server():
    server_url = os.getenv("SERVER_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        response = requests.get(f"{server_url}/test", timeout=5)
        response.raise_for_status()
        logger.info("Pinged %s/test", server_url)
    except requests.RequestException:
        logger.warning("Could not ping %s/test", server_url, exc_info=True)


def start_scheduler():
    """Start one scheduler instance and avoid duplicate job registration."""
    if _scheduler.running:
        logger.info("Scheduler is already running")
        return

    # Keep the existing immediate ingestion behaviour, but isolate failures.
    ingest_news()

    _scheduler.add_job(
        ingest_news,
        "interval",
        minutes=10,
        id="news_ingestion",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.add_job(
        ping_server,
        "interval",
        minutes=10,
        id="server_ping",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    logger.info("News scheduler started")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("News scheduler stopped")
