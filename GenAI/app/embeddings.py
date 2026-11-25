import os
import math
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

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

def generate_embedding(text: str):
    if not text.strip():
        raise ValueError("Embedding input must not be empty")
    result = client.feature_extraction(
        text, model="sentence-transformers/all-MiniLM-L6-v2"
    )
    return validate_embedding(result)
