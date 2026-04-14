from fastapi import FastAPI
from .database import engine
from .models import Base

app = FastAPI()

# Create tables
Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"message": "Backend + DB working ✅"}

@app.get("/test")
def test():
    return {"status": "ok"}