from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "0001_baseline"
down_revision = None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    if not sa.inspect(op.get_bind()).has_table("articles"):
        op.create_table("articles", sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("title", sa.String()), sa.Column("content", sa.Text()),
            sa.Column("published_at", sa.DateTime()), sa.Column("embedding", Vector(384)),
            sa.Column("url", sa.String()), sa.Column("image_url", sa.String()))
    else:
        required = {"id", "title", "content", "published_at", "embedding", "url", "image_url"}
        if not required.issubset({c["name"] for c in sa.inspect(op.get_bind()).get_columns("articles")}):
            raise RuntimeError("Existing schema does not match baseline")

def downgrade():
    raise RuntimeError("Baseline downgrade intentionally disabled to preserve articles")
