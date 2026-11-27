"""Vector retrieval policy. Exact search stays default until real-data recall is validated."""
import os
from sqlalchemy import text
from .models import NewsArticle

TOP_K = 5
MAX_DISTANCE = 0.65
EF_VALUES = (40, 100, 200, 400)

def settings():
    mode = os.getenv("VECTOR_SEARCH_MODE", "exact").strip().lower()
    if mode not in ("exact", "hnsw"):
        raise ValueError("VECTOR_SEARCH_MODE must be exact or hnsw")
    ef = int(os.getenv("HNSW_EF_SEARCH", "200"))
    if ef not in EF_VALUES:
        raise ValueError("HNSW_EF_SEARCH must be 40, 100, 200 or 400")
    return mode, ef

def retrieve_articles(db, embedding):
    mode, ef = settings()
    distance = NewsArticle.embedding.cosine_distance(embedding)
    query = db.query(NewsArticle).filter(distance <= MAX_DISTANCE).order_by(distance).limit(TOP_K)

    def exact():
        # Transaction-local settings cannot leak into another pooled connection's requests.
        db.execute(text("SET LOCAL enable_seqscan = on"))
        db.execute(text("SET LOCAL enable_indexscan = off"))
        db.execute(text("SET LOCAL enable_indexonlyscan = off"))
        db.execute(text("SET LOCAL enable_bitmapscan = off"))
        return query.all()

    if mode == "exact":
        return exact()
    # Allow the planner to choose a sequential scan for small collections.
    db.execute(text("SELECT set_config('hnsw.ef_search', :ef, true)"), {"ef": str(ef)})
    results = query.all()
    # The ANN filter can eliminate candidates. Exact fallback ensures completeness
    # when fewer than K are returned, but cannot detect incorrect full top-K results.
    return results if len(results) == TOP_K else exact()
