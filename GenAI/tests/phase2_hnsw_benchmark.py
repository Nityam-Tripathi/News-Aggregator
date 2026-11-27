"""Synthetic benchmark; never run against shared or production databases."""
import json
from time import perf_counter
import numpy as np
from psycopg2.extras import execute_values
from app.database import engine
from phase2_migration_check import guard

def main():
    guard()
    rng = np.random.default_rng(42)
    n, k, qcount = 10000, 5, 50
    data = rng.normal(size=(n, 384)).astype(np.float32)
    queries = data[rng.choice(n, qcount, replace=False)] + rng.normal(0, 0.15, (qcount, 384))
    def vector(row):
        return "[" + ",".join(str(float(x)) for x in row) + "]"
    conn = engine.raw_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE bench_articles (id integer PRIMARY KEY, embedding vector(384))")
            execute_values(cur, "INSERT INTO bench_articles VALUES %s", [(i,vector(row)) for i,row in enumerate(data)], template="(%s,%s::vector)", page_size=500)
            started = perf_counter()
            cur.execute("CREATE INDEX bench_hnsw ON bench_articles USING hnsw (embedding vector_cosine_ops)")
            build_seconds = perf_counter() - started
            cur.execute("ANALYZE bench_articles")
            cur.execute("SELECT pg_relation_size('bench_hnsw')")
            index_bytes = cur.fetchone()[0]
            sql = "SELECT id FROM bench_articles ORDER BY embedding <=> %s::vector LIMIT %s"
            reports = {}
            truth = []
            # Force exact scan for ground truth and force HNSW for the comparison.
            # Planner choice in normal operation is measured separately.
            for mode, ef in [("exact",None),("hnsw40",40),("hnsw100",100)]:
                cur.execute("SET enable_seqscan = " + ("on" if ef is None else "off"))
                cur.execute("SET enable_indexscan = " + ("off" if ef is None else "on"))
                cur.execute("SET enable_bitmapscan = off")
                if ef is not None:
                    cur.execute("SET hnsw.ef_search = " + str(ef))
                cur.execute("EXPLAIN (FORMAT JSON) " + sql,(vector(queries[0]),k))
                plan = cur.fetchone()[0][0]["Plan"]
                plan_str = json.dumps(plan)
                assert ("bench_hnsw" in plan_str) == (ef is not None), plan
                for q in queries[:5]:
                    cur.execute(sql,(vector(q),k)); cur.fetchall()
                times, recalls = [], []
                for i,q in enumerate(queries):
                    param = (vector(q),k)
                    start = perf_counter()
                    cur.execute(sql,param)
                    ids = {r[0] for r in cur.fetchall()}
                    times.append((perf_counter()-start)*1000)
                    if ef is None:
                        truth.append(ids)
                    else:
                        recalls.append(len(ids & truth[i])/k)
                reports[mode] = {"p50_ms":round(float(np.median(times)),3),
                                 "p95_ms":round(float(np.percentile(times,95)),3),
                                 "recall_at_5":round(float(np.mean(recalls)),4) if recalls else 1.0,
                                 "plan":plan}
            cur.execute("RESET enable_seqscan")
            cur.execute("RESET enable_indexscan")
            cur.execute("RESET enable_bitmapscan")
            cur.execute("RESET hnsw.ef_search")
            cur.execute("EXPLAIN (FORMAT JSON) "+sql,(vector(queries[0]),k))
            normal_plan = cur.fetchone()[0][0]["Plan"]
            report = {"dataset":"synthetic Gaussian vectors","rows":n,"dimensions":384,"queries":qcount,"k":k,"seed":42,
                      "index_build_seconds":round(build_seconds,3),"index_bytes":index_bytes,
                      "normal_plan":normal_plan,"results":reports}
            with open("hnsw-report.json","w") as f:
                json.dump(report,f,indent=2)
            print(json.dumps(report,indent=2))
    finally:
        conn.rollback()
        conn.close()

if __name__ == "__main__":
    main()
