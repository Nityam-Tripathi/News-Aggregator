"""Evaluate source-linked news summaries using real MiniLM embeddings and SQL retrieval.
Run only on disposable local phase2_test; no NewsAPI or Groq calls.
"""
import json
import math
import os
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from time import perf_counter
from unittest.mock import patch
from sqlalchemy import text
from app.database import SessionLocal
from app.embeddings import generate_embedding
from app.models import NewsArticle
from app.hybrid import lexical_search, hybrid_search
from app.retrieval import retrieve_articles
from app.url_identity import url_key
from phase2_migration_check import guard

def metrics(found, relevant):
    hits = [int(x in relevant) for x in found[:5]]
    if not relevant:
        return {"empty_correct": not found}
    dcg = sum(h/math.log2(i+2) for i,h in enumerate(hits))
    ideal = sum(1/math.log2(i+2) for i in range(min(5,len(relevant))))
    return {"recall_at_5":sum(hits)/len(relevant), "precision_at_5":sum(hits)/5,
            "mrr_at_5":next((1/(i+1) for i,h in enumerate(hits) if h),0),
            "ndcg_at_5":dcg/ideal}

def main():
    guard()
    data = json.loads((Path(__file__).parent/"fixtures/news_retrieval.json").read_text())
    now = datetime.fromisoformat(data["as_of"])
    ids = {}
    with patch.dict(os.environ,{"EMBEDDING_PROVIDER":"local","VECTOR_SEARCH_MODE":"exact"}), SessionLocal() as db:
        # Shadow public.articles for this transaction; rollback removes the test corpus.
        db.execute(text("CREATE TEMP TABLE articles (LIKE public.articles INCLUDING ALL) ON COMMIT DROP"))
        for i,a in enumerate(data["articles"],1):
            ids[i] = a["id"]
            db.add(NewsArticle(id=i,title=a["title"],content=a["content"],
                url=a["url"],url_key=url_key(a["url"]),
                published_at=datetime.fromisoformat(a["date"]),
                embedding=generate_embedding(a["title"]+". "+a["content"])))
        db.flush()
        assert db.execute(text("SELECT count(*) FROM articles")).scalar() == len(ids)
        assert db.execute(text("SELECT count(*) FROM articles WHERE search_document IS NOT NULL")).scalar() == len(ids)
        reports = {}
        for mode in ("lexical","semantic","hybrid_rrf","hybrid_recency"):
            rows = []
            for q in data["queries"]:
                embedding = generate_embedding(q["query"]) if mode != "lexical" else None
                # Restore planner preferences before each independent retrieval.
                for setting in ("enable_seqscan","enable_indexscan","enable_indexonlyscan","enable_bitmapscan"):
                    db.execute(text("SET LOCAL "+setting+" = DEFAULT"))
                start = perf_counter()
                if mode=="lexical":
                    result = lexical_search(db,q["query"],limit=5)
                elif mode=="semantic":
                    result = retrieve_articles(db,embedding)
                else:
                    result = hybrid_search(db,q["query"],embedding,recency_weight=.15 if mode=="hybrid_recency" else 0,now=now)
                ms = (perf_counter()-start)*1000
                found = [ids[a.id] for a in result]
                rows.append({"id":q["id"],"query":q["query"],"expected":q["relevant"],"retrieved":found,
                    "retrieval_ms":round(ms,3),**metrics(found,set(q["relevant"]))})
            matched = [r for r in rows if r["expected"]]
            summary = {k:round(mean(r[k] for r in matched),4) for k in ("recall_at_5","precision_at_5","mrr_at_5","ndcg_at_5")}
            summary["median_retrieval_ms"] = round(median(r["retrieval_ms"] for r in rows),3)
            summary["no_match_correct"] = sum(r.get("empty_correct",False) for r in rows)
            reports[mode] = {"summary":summary,"queries":rows}
        report = {"corpus":len(ids),"queries":len(data["queries"]),"as_of":data["as_of"],
                  "model":"sentence-transformers/all-MiniLM-L6-v2",
                  "note":"Small curated public-news paraphrase smoke test. Latency excludes embedding generation; not a production or independent quality benchmark.",
                  "results":reports}
        Path("news-retrieval-report.json").write_text(json.dumps(report,indent=2))
        print(json.dumps({k:v["summary"] for k,v in reports.items()},indent=2))
        db.rollback()

if __name__=="__main__":
    main()
