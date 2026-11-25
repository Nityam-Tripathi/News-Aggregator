from alembic import op
import sqlalchemy as sa
from app.url_identity import url_key

revision = "0002_indexes"
down_revision = "0001_baseline"

def upgrade():
    op.add_column("articles", sa.Column("url_key", sa.String(64), nullable=True))
    conn = op.get_bind()
    seen = set()
    # Preserve legacy duplicates; only the first row owns the canonical key.
    for row in conn.execute(sa.text("SELECT id, url FROM articles ORDER BY id")).fetchall():
        key = url_key(row.url)
        if key and key not in seen:
            conn.execute(sa.text("UPDATE articles SET url_key=:key WHERE id=:id"), {"key": key, "id": row.id})
            seen.add(key)
    op.create_unique_constraint("uq_articles_url_key", "articles", ["url_key"])
    op.create_index("ix_articles_published_at", "articles", ["published_at"])
    op.execute("CREATE INDEX ix_articles_embedding_hnsw ON articles USING hnsw (embedding vector_cosine_ops)")

def downgrade():
    op.drop_index("ix_articles_embedding_hnsw", table_name="articles")
    op.drop_index("ix_articles_published_at", table_name="articles")
    op.drop_constraint("uq_articles_url_key", "articles", type_="unique")
    op.drop_column("articles", "url_key")
