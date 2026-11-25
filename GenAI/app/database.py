import os
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Use DATABASE_URL from env if available, otherwise fall back to local
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5433/newsdb_v2"
)

# Explicitly select the driver installed by requirements.txt.
database_url = make_url(DATABASE_URL)
if database_url.drivername in ("postgres", "postgresql"):
    database_url = database_url.set(drivername="postgresql+psycopg2")
engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()