"""Shared bounded ingestion for scheduled, manual and optional query fetches."""
import logging
from datetime import datetime, timezone
from sqlalchemy import or_
from sqlalchemy.dialects.postgresql import insert
from .models import NewsArticle
from .embeddings import generate_embeddings
from .url_identity import url_key

logger = logging.getLogger(__name__)
BATCH_SIZE = 8

def parse_timestamp(value):
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc).replace(tzinfo=None) if stamp.tzinfo else stamp
    except (ValueError, TypeError, AttributeError):
        return None

def ingest_articles(db, articles):
    stats = dict(fetched=len(articles), inserted=0, skipped=0, embedding_failures=0)
    seen = set()
    consecutive_failures = 0
    for offset in range(0, len(articles), BATCH_SIZE):
        pending = []
        for article in articles[offset:offset+BATCH_SIZE]:
            title, content = article.get("title"), article.get("description")
            if not isinstance(title,str) or not title.strip() or not isinstance(content,str) or not content.strip():
                stats["skipped"] += 1
                continue
            key = url_key(article.get("url"))
            identity = ("url", key) if key else ("title", title)
            if identity in seen:
                stats["skipped"] += 1
                continue
            seen.add(identity)
            pending.append(dict(title=title, content=content, url_key=key, url=article.get("url"),
                image_url=article.get("urlToImage"), published_at=parse_timestamp(article.get("publishedAt"))))
        if not pending:
            continue
        keys = [r["url_key"] for r in pending if r["url_key"]]
        titles = [r["title"] for r in pending if not r["url_key"]]
        existing = db.query(NewsArticle.url_key, NewsArticle.title).filter(
            or_(NewsArticle.url_key.in_(keys), NewsArticle.title.in_(titles))).all()
        existing_keys = {r[0] for r in existing if r[0]}
        existing_titles = {r[1] for r in existing}
        fresh = [r for r in pending if not (r["url_key"] in existing_keys if r["url_key"] else r["title"] in existing_titles)]
        stats["skipped"] += len(pending)-len(fresh)
        if not fresh:
            continue
        try:
            vectors = generate_embeddings([r["title"]+". "+r["content"] for r in fresh])
        except Exception as exc:
            logger.warning("Embedding batch failed: %s", type(exc).__name__)
            stats["embedding_failures"] += len(fresh)
            consecutive_failures += 1
            if consecutive_failures >= 3:
                stats["embedding_failures"] += max(0, len(articles)-offset-BATCH_SIZE)
                break
            continue
        consecutive_failures = 0
        for row, vector in zip(fresh,vectors):
            row["embedding"] = vector
        result = db.execute(insert(NewsArticle).values(fresh).on_conflict_do_nothing(index_elements=["url_key"]))
        stats["inserted"] += result.rowcount
        stats["skipped"] += len(fresh)-result.rowcount
    db.commit()
    return stats
