import os
import logging
import threading
import time

import numpy as np
from huggingface_hub import InferenceClient

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384
# A 402 response means the provider account cannot currently run inference.
# Avoid hammering it for every article/query; retry after this cooldown.
HF_402_COOLDOWN_SECONDS = int(os.getenv("HF_402_COOLDOWN_SECONDS", "900"))

logger = logging.getLogger(__name__)
HF_TOKEN = os.getenv("HF_TOKEN")
client = InferenceClient(token=HF_TOKEN)
_provider_lock = threading.Lock()
_provider_blocked_until = 0.0


def generate_embedding(text: str) -> list[float]:
    """Generate a validated embedding, failing fast during provider outages."""
    global _provider_blocked_until

    if not isinstance(text, str) or not text.strip():
        raise ValueError("Embedding input must be a non-empty string")

    with _provider_lock:
        if time.monotonic() < _provider_blocked_until:
            raise RuntimeError(
                "Hugging Face inference is temporarily paused after HTTP 402; "
                "check account credits/billing before retrying"
            )

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

        with _provider_lock:
            _provider_blocked_until = 0.0
        return embedding.tolist()
    except Exception as exc:
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code == 402:
            with _provider_lock:
                _provider_blocked_until = time.monotonic() + HF_402_COOLDOWN_SECONDS
            logger.error(
                "Hugging Face returned HTTP 402; pausing embedding requests for %s seconds",
                HF_402_COOLDOWN_SECONDS,
            )
        else:
            logger.exception("Error generating embedding via Hugging Face")
        raise RuntimeError("Could not generate a valid news embedding") from exc
