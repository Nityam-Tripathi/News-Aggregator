from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine
from .models import Base

from sqlalchemy import text

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