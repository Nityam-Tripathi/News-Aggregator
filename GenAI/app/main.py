from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from .models import Base
from .news_fetcher import fetch_news
from sqlalchemy import text
from .embeddings import generate_embedding

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Only DB + vector setup
with engine.connect() as conn:
    try:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    except Exception as e:
        print("Vector extension issue:", e)

Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "Backend stable ✅"}

@app.get("/test")
def test():
    return {"status": "ok"}

@app.get("/news-test")
def news_test():
    articles = fetch_news()
    return {"count": len(articles)}

@app.get("/embed-test")
def embed_test():
    vec = generate_embedding("test text")
    return {"length": len(vec)}