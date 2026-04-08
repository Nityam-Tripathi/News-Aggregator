from app.database import engine
from app.models import Base, NewsArticle  # IMPORTANT

Base.metadata.create_all(bind=engine)

print("Tables created")