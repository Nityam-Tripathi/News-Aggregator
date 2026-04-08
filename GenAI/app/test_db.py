# test_db.py
from sqlalchemy import create_engine

engine = create_engine("postgresql://postgres:postgres@127.0.0.1:5433/newsdb_v2")

conn = engine.connect()
print("Connected successfully")
conn.close()