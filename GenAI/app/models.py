from sqlalchemy import Column, Integer, String, Text, DateTime, Index, UniqueConstraint, Computed
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
from .database import Base

class NewsArticle(Base):
    __tablename__ = "articles"

    __table_args__ = (Index("ix_articles_search_document", "search_document", postgresql_using="gin"), UniqueConstraint("url_key", name="uq_articles_url_key"), Index("ix_articles_published_at", "published_at"), Index("ix_articles_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}))
    search_document = Column(TSVECTOR, Computed("setweight(to_tsvector('english'::regconfig, coalesce(title, '')), 'A') || "
        "setweight(to_tsvector('english'::regconfig, coalesce(content, '')), 'B')", persisted=True))
    url_key = Column(String(64))
    id = Column(Integer, primary_key=True)
    title = Column(String)
    content = Column(Text)
    published_at = Column(DateTime)
    embedding = Column(Vector(384))
    url = Column(String)
    image_url = Column(String)