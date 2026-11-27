"""Reproducible synthetic retrieval benchmark on a disposable CI database."""
import json
from time import perf_counter
import numpy as np
from psycopg2.extras import execute_values
from app.database import engine
from phase2_migration_check import guard

N, D, K, Q = 10000, 384, 5, 50
THRESHOLD = 0.65
EF_VALUES = (40, 100, 200, 400)

def vector(row):
    return "[" + ",".join(str(float(x)) for x in row) + "]"

def compact_plan(plan):
    return {"node": plan["Node Type"], "index": plan.get("Index Name"),
            "children": [compact_plan(p) for p in plan.get("Plans", [])]}

def evaluate(cur, queries, filtered):
    # Match the application's distance threshold and ordering, not a category proxy.
    sql = "SELECT id FROM bench_articles "
    if filtered:
        sql += "WHERE embedding <=> %s::vector <= %s "
    sql += "ORDER BY embedding <=> %s::vector LIMIT %s"
    params = [(v, THRESHOLD, v, K) if filtered else (v, K)
              for v in map(vector, queries)]
    reports, truth = {}, []
    for ef in (None, *EF_VALUES):
        cur.execute("SET enable_seqscan = " + ("on" if ef is None else "off"))
        cur.execute("SET enable_indexscan = " + ("off" if ef is None else "on"))
        cur.execute("SET enable_indexonlyscan = off")
        cur.execute("SET enable_bitmapscan = off")
        if ef is not None:
            cur.execute("SET hnsw.ef_search = " + str(ef))
        cur.execute("EXPLAIN (FORMAT JSON) " + sql, params[0])
        plan = compact_plan(cur.fetchone()[0][0]["Plan"])
        assert ("bench_hnsw" in json.dumps(plan)) == (ef is not None), plan
        for p in params[:5]:
            cur.execute(sql, p)
            cur.fetchall()
        times, recalls = [], []
        missed_all, underfilled, empty_false_positive = 0, 0, 0
        for i,p in enumerate(params):
            start = perf_counter()
            cur.execute(sql, p)
            ids = {r[0] for r in cur.fetchall()}
            times.append((perf_counter()-start)*1000)
            if ef is None:
                truth.append(ids)
            expected = truth[i]
            if expected:
                recalls.append(len(ids & expected) / len(expected))
                missed_all += not ids
                underfilled += len(ids) < len(expected)
            else:
                empty_false_positive += bool(ids)
        reports["exact" if ef is None else f"hnsw{ef}"] = {
            "p50_ms": round(float(np.median(times)),3),
            "p95_ms": round(float(np.percentile(times,95)),3),
            "recall_at_5": round(float(np.mean(recalls)),4) if recalls else None,
            "nonempty_ground_truth": sum(bool(t) for t in truth),
            "full_top5_ground_truth": sum(len(t)==K for t in truth),
            "empty_ground_truth": sum(not t for t in truth),
            "missed_all": missed_all, "underfilled": underfilled,
            "empty_false_positive": empty_false_positive, "plan": plan}
    for setting in ("enable_seqscan","enable_indexscan","enable_indexonlyscan","enable_bitmapscan","hnsw.ef_search"):
        cur.execute("RESET " + setting)
    cur.execute("EXPLAIN (FORMAT JSON) " + sql, params[0])
    return {"results": reports, "normal_plan": compact_plan(cur.fetchone()[0][0]["Plan"])}

def dataset(cur, name, data, queries):
    cur.execute("CREATE TEMP TABLE bench_articles (id integer PRIMARY KEY, embedding vector(384))")
    execute_values(cur, "INSERT INTO bench_articles VALUES %s",
        [(i,vector(row)) for i,row in enumerate(data)], template="(%s,%s::vector)", page_size=500)
    start = perf_counter()
    cur.execute("CREATE INDEX bench_hnsw ON bench_articles USING hnsw (embedding vector_cosine_ops)")
    build = perf_counter()-start
    cur.execute("ANALYZE bench_articles")
    cur.execute("SELECT pg_relation_size('bench_hnsw')")
    size = cur.fetchone()[0]
    report = {"dataset": name, "index_build_seconds":round(build,3), "index_bytes":size,
              "unfiltered":evaluate(cur,queries,False), "filtered":evaluate(cur,queries,True)}
    cur.execute("DROP TABLE bench_articles")
    return report

def main():
    guard()
    rng = np.random.default_rng(42)
    gaussian = rng.normal(size=(N,D)).astype(np.float32)
    gq = gaussian[rng.choice(N,Q,replace=False)] + rng.normal(0,0.15,(Q,D))
    # Clustered synthetic vectors are a stress test with many eligible neighbors.
    # Include sparse clusters and unrelated queries to exercise fewer-than-five/no-match cases.
    centers = rng.normal(size=(100,D))
    groups = np.concatenate([np.repeat(np.arange(90),111), np.arange(90,100)])
    clustered = (centers[groups]+rng.normal(0,0.35,(N,D))).astype(np.float32)
    cq = np.concatenate([centers[rng.choice(90,35,replace=False)]+rng.normal(0,0.35,(35,D)),
                         centers[90:100]+rng.normal(0,0.35,(10,D)),
                         rng.normal(size=(5,D))])
    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
            version = cur.fetchone()[0]
            reports = [dataset(cur,"gaussian",gaussian,gq), dataset(cur,"clustered",clustered,cq)]
            candidates = []
            for ef in EF_VALUES:
                key = f"hnsw{ef}"
                samples = [r[scope]["results"][key] for r in reports for scope in ("filtered","unfiltered")]
                if all(s["recall_at_5"] is not None and s["recall_at_5"] >= .95 and
                       s["empty_false_positive"] == 0 for s in samples):
                    candidates.append({"ef_search":ef,"mean_p50_ms":float(np.mean([s["p50_ms"] for s in samples]))})
            selected = min(candidates,key=lambda x:x["mean_p50_ms"]) if candidates else None
            report = {"rows":N,"dimensions":D,"queries_per_dataset":Q,"k":K,"seed":42,
                      "pgvector_version":version,"distance_threshold":THRESHOLD,"target_recall":.95,
                      "datasets":reports,"synthetic_candidate":selected,
                      "note":"Synthetic candidate is not a production quality guarantee; validate real embeddings."}
            with open("hnsw-report.json","w") as f:
                json.dump(report,f,indent=2)
            print(json.dumps(report,indent=2))
    finally:
        conn.rollback()
        conn.close()

if __name__ == "__main__":
    main()
