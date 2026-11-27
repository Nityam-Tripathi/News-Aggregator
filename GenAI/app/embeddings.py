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

def generate_embeddings(texts):
    """One bounded local inference batch; preserve input order."""
    if not texts:
        return []
    if len(texts) > 8 or any(not isinstance(t, str) or not t.strip() for t in texts):
        raise ValueError("Expected 1–8 nonblank texts")
    if os.getenv("EMBEDDING_PROVIDER", "hf") != "local":
        # The hosted provider does not guarantee batch feature extraction.
        return [generate_embedding(t) for t in texts]
    with _model_lock:
        vectors = list(local_model().embed(texts, batch_size=len(texts)))
    if len(vectors) != len(texts):
        raise ValueError("Unexpected embedding count")
    return [validate_embedding(v) for v in vectors]
