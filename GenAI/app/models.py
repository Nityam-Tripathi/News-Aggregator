from sqlalchemy import Column, Integer, String, Text, DateTime
from pgvector.sqlalchemy import Vector
from .database import Base

class NewsArticle(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)
    title = Column(String)
    content = Column(Text)
    published_at = Column(DateTime)
    embedding = Column(Vector(384))
    url = Column(String)
    image_url = Column(String)