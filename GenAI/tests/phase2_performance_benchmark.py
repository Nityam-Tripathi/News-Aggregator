"""Run only on disposable local phase2_test. No external LLM or news calls.
Real MiniLM inference and database retrieval; simulated Groq latency via loopback SSE.
"""
import asyncio
import json
import os
import resource
import socket
from contextlib import contextmanager
from pathlib import Path
from threading import Event, Thread
from time import perf_counter, sleep
from unittest.mock import patch

import httpx
import numpy as np
import uvicorn
from sqlalchemy import text
from app import main
from app.answer_cache import AnswerCache, cache_key
from app.database import SessionLocal
from app.embeddings import generate_embedding, generate_embeddings
from app.models import NewsArticle
from app.url_identity import url_key
from datetime import datetime
from phase2_migration_check import guard

FIXTURES = Path(__file__).parent / "fixtures/news_retrieval.json"
FIRST_DELAY = .08
CHUNK_DELAY = .02
CHUNKS = ["A ", "complete ", "grounded ", "answer."]
ANSWER = "".join(CHUNKS)

def describe(values):
    return {"p50_ms": round(float(np.median(values)), 4),
            "p95_ms": round(float(np.percentile(values,95)), 4),
            "samples":len(values)}

def embedding_bench(texts):
    sample = (texts*4)[:64]
    generate_embedding(sample[0]) # warm model, excludes download
    baseline = [generate_embedding(t) for t in sample]
    results = {}
    for size in (1,2,4,8):
        times = []
        min_cosine = 1.0
        for _ in range(5):
            start = perf_counter()
            vectors = []
            for i in range(0,len(sample),size):
                if size==1:
                    vectors.append(generate_embedding(sample[i]))
                else:
                    vectors.extend(generate_embeddings(sample[i:i+size]))
            times.append((perf_counter()-start)*1000)
            a,b = np.asarray(baseline),np.asarray(vectors)
            min_cosine = min(min_cosine,float(np.min((a*b).sum(1)/(np.linalg.norm(a,axis=1)*np.linalg.norm(b,axis=1)))))
        assert min_cosine >= .999, (size,min_cosine)
        results[str(size)] = {**describe(times),"articles_per_second":round(len(sample)*1000/float(np.median(times)),2),
                              "minimum_cosine_vs_single":round(min_cosine,6)}
    return {"texts_per_trial":len(sample),"results":results,
            "process_peak_rss_mib":round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2)}

def cache_bench():
    c = AnswerCache()
    args=("query","article content "*100,[{"url":"https://example.org"}],"model","v1")
    key=cache_key(*args)
    c.put(key,ANSWER)
    raw, combined = [], []
    for _ in range(2000):
        start=perf_counter()
        value=c.get(key)
        raw.append((perf_counter()-start)*1000)
        assert value==ANSWER
        start=perf_counter()
        value=c.get(cache_key(*args))
        combined.append((perf_counter()-start)*1000)
        assert value==ANSWER
    return {"lookup_only":describe(raw),"key_and_lookup":describe(combined)}

@contextmanager
def loopback():
    sock=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    sock.bind(("127.0.0.1",0))
    port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(main.app,host="127.0.0.1",port=port,lifespan="off",log_level="error"))
    thread=Thread(target=server.run,kwargs={"sockets":[sock]},daemon=True)
    thread.start()
    try:
        deadline=perf_counter()+10
        while not server.started:
            if not thread.is_alive() or perf_counter()>deadline:
                raise RuntimeError("Loopback server did not start")
            sleep(.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit=True
        thread.join(10)
        sock.close()
        if thread.is_alive():
            raise RuntimeError("Loopback server did not stop")

def stream_request(client, query):
    start=perf_counter()
    first=None
    events=[]
    tokens=[]
    event=None
    with client.stream("GET","/ask/stream",params={"query":query}) as response:
        response.raise_for_status()
        assert "text/event-stream" in response.headers["content-type"]
        for line in response.iter_lines():
            if line.startswith("event:"):
                event=line[6:].strip()
            elif line.startswith("data:"):
                payload=json.loads(line[5:])
                events.append(event)
                if event=="delta":
                    if first is None:
                        first=(perf_counter()-start)*1000
                    tokens.append(payload["text"])
    return {"first_delta_ms":first,"total_ms":(perf_counter()-start)*1000,
            "events":events,"answer":"".join(tokens)}

def endpoint_bench(articles):
    # This database is local, disposable and checked by guard(). Avoid modifying legacy test rows.
    with SessionLocal() as db:
        for i,a in enumerate(articles,1001):
            db.add(NewsArticle(id=i,title=a["title"],content=a["content"],
                url=a["url"],url_key=url_key(a["url"]),published_at=datetime.fromisoformat(a["date"]),
                embedding=generate_embedding(a["title"]+". "+a["content"])))
        db.commit()
    calls={"stream":0,"json":0}
    closed=Event()
    mode=["normal"]
    async def simulated_stream(*args):
        calls["stream"]+=1
        try:
            await asyncio.sleep(FIRST_DELAY)
            yield CHUNKS[0]
            if mode[0]=="error":
                raise RuntimeError("simulated provider error")
            if mode[0]=="abort":
                await asyncio.sleep(5)
            for token in CHUNKS[1:]:
                await asyncio.sleep(CHUNK_DELAY)
                yield token
        finally:
            closed.set()
    def simulated_answer(*args):
        calls["json"]+=1
        sleep(FIRST_DELAY+CHUNK_DELAY*(len(CHUNKS)-1))
        return ANSWER
    query="Artemis II lunar flyby photographs"
    cold, warm, json_hit, json_miss = [], [], [], []
    cache=AnswerCache()
    try:
        with patch.object(main,"answer_cache",cache), patch.object(main,"stream_answer",side_effect=simulated_stream), patch.object(main,"generate_answer",side_effect=simulated_answer), patch.dict(main.app.dependency_overrides,{main.limit_search:lambda:None}), loopback() as base:
            with httpx.Client(base_url=base,timeout=15,trust_env=False) as client:
                # Confirm real evidence is retrieved and warm the query embedding/database path.
                prepared=main.prepare_answer(query)
                assert prepared[2], "No evidence for benchmark query"
                key=cache_key(*prepared,main.model_name(),main.PROMPT_VERSION)
                for _ in range(15):
                    cache.entries.clear() # no active request when resetting
                    item=stream_request(client,query)
                    assert item["events"]==["sources"]+["delta"]*len(CHUNKS)+["done"],item
                    assert item["answer"]==ANSWER
                    cold.append(item)
                    before=dict(calls)
                    item=stream_request(client,query)
                    assert item["events"]==["sources","delta","done"] and item["answer"]==ANSWER
                    assert calls==before
                    warm.append(item)
                    start=perf_counter()
                    response=client.get("/ask",params={"query":query})
                    json_hit.append((perf_counter()-start)*1000)
                    assert response.status_code==200 and response.json()["answer"]==ANSWER and calls==before
                    cache.entries.clear()
                    start=perf_counter()
                    response=client.get("/ask",params={"query":query})
                    json_miss.append((perf_counter()-start)*1000)
                    assert response.status_code==200 and response.json()["answer"]==ANSWER
                cache.entries.clear()
                mode[0]="error"
                for _ in range(5):
                    item=stream_request(client,query)
                    assert item["events"][-1]=="error" and "done" not in item["events"]
                    assert cache.get(key) is None
                mode[0]="abort"
                closed.clear()
                with client.stream("GET","/ask/stream",params={"query":query}) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if line=="event: delta":
                            break
                abort_closed=closed.wait(3)
                assert abort_closed,"Provider generator was not closed promptly on client disconnect"
                assert cache.get(key) is None
        return {"simulated_provider_first_delay_ms":FIRST_DELAY*1000,
                "simulated_provider_chunk_delay_ms":CHUNK_DELAY*1000,
                "uncached_sse_first_delta":describe([x["first_delta_ms"] for x in cold]),
                "uncached_sse_total":describe([x["total_ms"] for x in cold]),
                "cached_sse_first_delta":describe([x["first_delta_ms"] for x in warm]),
                "cached_sse_total":describe([x["total_ms"] for x in warm]),
                "json_cache_hit":describe(json_hit),"json_cache_miss":describe(json_miss),
                "reliability":{"successful_uncached":len(cold),"successful_cached":len(warm),
                "provider_errors_handled":5,"disconnect_closed":abort_closed,"incomplete_answers_cached":0},
                "provider_calls":calls,
                "note":"Loopback HTTP, actual local embeddings and database retrieval, mocked provider delays; rate limiter bypassed only in benchmark."}
    finally:
        with SessionLocal() as db:
            db.execute(text("DELETE FROM articles WHERE id >= 1001 AND id < :end"),{"end":1001+len(articles)})
            db.commit()

def run():
    guard()
    data=json.loads(FIXTURES.read_text())
    articles=data["articles"]
    with patch.dict(os.environ,{"EMBEDDING_PROVIDER":"local","VECTOR_SEARCH_MODE":"exact",
        "RETRIEVAL_MODE":"semantic","SEARCH_FETCH_FRESH":"false"}):
        report={"embedding":embedding_bench([a["title"]+". "+a["content"] for a in articles]),
                "cache":cache_bench(),"endpoints":endpoint_bench(articles)}
    Path("performance-report.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=="__main__":
    run()
