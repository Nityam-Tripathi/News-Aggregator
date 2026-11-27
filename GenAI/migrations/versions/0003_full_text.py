from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0003_full_text"
down_revision = "0002_indexes"

def upgrade():
    op.add_column("articles", sa.Column("search_document", TSVECTOR(),
        sa.Computed("setweight(to_tsvector('english'::regconfig, coalesce(title, '')), 'A') || "
                    "setweight(to_tsvector('english'::regconfig, coalesce(content, '')), 'B')", persisted=True)))
    op.create_index("ix_articles_search_document", "articles", ["search_document"], postgresql_using="gin")

def downgrade():
    op.drop_index("ix_articles_search_document", table_name="articles")
    op.drop_column("articles", "search_document")
