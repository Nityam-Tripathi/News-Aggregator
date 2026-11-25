import os
import math
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from functools import lru_cache
from threading import Lock

load_dotenv()
client = InferenceClient(token=os.getenv("HF_TOKEN"))

def validate_embedding(result):
    vector = result.tolist() if hasattr(result, "tolist") else result
    if not isinstance(vector, list) or len(vector) != 384:
        raise ValueError("Expected a 384-dimensional embedding")
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in vector):
        raise ValueError("Embedding contains invalid values")
    if not any(vector):
        raise ValueError("Embedding must not be a zero vector")
    return vector

_model_lock = Lock()

@lru_cache(maxsize=1)
def local_model():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2", threads=1)

def generate_embedding(text: str):
    if not text.strip():
        raise ValueError("Embedding input must not be empty")
    if os.getenv("EMBEDDING_PROVIDER", "hf") == "local":
        with _model_lock:
            result = next(iter(local_model().embed([text], batch_size=1)))
        return validate_embedding(result)
    result = client.feature_extraction(
        text, model="sentence-transformers/all-MiniLM-L6-v2"
    )
    return validate_embedding(result)
