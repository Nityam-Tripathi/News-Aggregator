from fastapi import FastAPI
from .database import engine
from .models import Base

app = FastAPI()

# Create tables
from sqlalchemy import text

with engine.connect() as conn:
    try:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    except Exception as e:
        print("Vector extension issue:", e)

Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "Backend + DB working ✅"}

@app.get("/test")
def test():
    return {"status": "ok"}