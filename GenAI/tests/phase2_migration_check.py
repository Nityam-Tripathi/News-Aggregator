"""Integration checks. Run from GenAI against the dedicated CI database only."""
import os
import sys
from sqlalchemy import text
from app.database import engine
from app.url_identity import url_key

def guard():
    if (os.getenv("ALLOW_PHASE2_MIGRATIONS") != "yes"
        or engine.url.host not in ("localhost", "127.0.0.1")
        or engine.url.database != "phase2_test"):
        raise RuntimeError("Disposable local phase2_test database required")

fixtures = [
    (101, "Shared headline", "https://example.com/story?utm_source=mail"),
    (102, "Different headline", "https://EXAMPLE.com:443/story#part"),
    (103, "Shared headline", "https://example.com/other?id=1"),
    (104, "No URL", None),
    (105, "Invalid URL", "javascript:alert(1)"),
]
VECTOR = "[" + ",".join(["1"] + ["0"] * 383) + "]"

def seed():
    with engine.begin() as conn:
        for id_, title, url in fixtures:
            conn.execute(text("""INSERT INTO articles
                (id,title,url,content,published_at,embedding)
                VALUES (:id,:title,:url,'original body','2026-01-01',CAST(:v AS vector))"""),
                dict(id=id_, title=title, url=url, v=VECTOR))
    print("Seeded five legacy rows, including duplicate canonical URLs")

def verify(head=True):
    with engine.begin() as conn:
        extra = ", url_key" if head else ""
        rows = conn.execute(text("SELECT id,title,url,content,published_at,embedding::text AS vector" + extra + " FROM articles ORDER BY id")).mappings().all()
        assert len(rows) == len(fixtures), rows
        for row, fixture in zip(rows, fixtures):
            assert (row["id"],row["title"],row["url"]) == fixture
            assert row["content"] == "original body" and row["vector"] == VECTOR
            assert row["published_at"].isoformat() == "2026-01-01T00:00:00"
        if head:
            assert [r["url_key"] for r in rows] == [url_key(fixtures[0][2]),None,url_key(fixtures[2][2]),None,None]
            indexes = dict(conn.execute(text("SELECT indexname,indexdef FROM pg_indexes WHERE tablename='articles'")).all())
            assert "USING hnsw" in indexes["ix_articles_embedding_hnsw"]
            assert "vector_cosine_ops" in indexes["ix_articles_embedding_hnsw"]
            assert "ix_articles_published_at" in indexes
            result = conn.execute(text("""INSERT INTO articles (id,title,url,url_key)
                VALUES (106,'duplicate','https://example.com/story',:key)
                ON CONFLICT (url_key) DO NOTHING"""), {"key": url_key(fixtures[0][2])})
            assert result.rowcount == 0
            result = conn.execute(text("""INSERT INTO articles (id,title,url,url_key)
                VALUES (107,'Shared headline','https://example.com/new',:key)
                ON CONFLICT (url_key) DO NOTHING"""), {"key": url_key("https://example.com/new")})
            assert result.rowcount == 1
            conn.execute(text("DELETE FROM articles WHERE id=107"))
    print("PASS: preserved five legacy rows and original content" + ("; URL constraint and HNSW index verified" if head else "; downgrade preserved data"))

if __name__ == "__main__":
    guard()
    {"seed": seed, "verify": verify, "verify-baseline": lambda: verify(False)}[sys.argv[1]]()
