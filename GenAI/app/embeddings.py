import os

import numpy as np
from huggingface_hub import InferenceClient

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384

HF_TOKEN = os.getenv("HF_TOKEN")
client = InferenceClient(token=HF_TOKEN)


def generate_embedding(text: str) -> list[float]:
    """Generate a validated 384-dimensional embedding.

    Fail explicitly when the provider is unavailable. Returning a zero vector
    would silently pollute semantic search results.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Embedding input must be a non-empty string")

    try:
        result = client.feature_extraction(text, model=MODEL_NAME)
        embedding = np.asarray(result, dtype=float).reshape(-1)

        if embedding.size != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Expected {EMBEDDING_DIMENSIONS} embedding values, "
                f"received {embedding.size}"
            )

        if not np.isfinite(embedding).all():
            raise ValueError("Embedding contains non-finite values")

        return embedding.tolist()
    except Exception as exc:
        print(f"Error generating embedding via Hugging Face: {exc}")
        raise RuntimeError("Could not generate a valid news embedding") from exc
