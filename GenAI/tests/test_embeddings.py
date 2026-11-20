import numpy as np
import pytest

from app import embeddings


class FakeInferenceClient:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def feature_extraction(self, text, model):
        self.calls.append((text, model))
        if self.error:
            raise self.error
        return self.result


def test_generate_embedding_returns_valid_384_dimension_vector(monkeypatch):
    client = FakeInferenceClient(result=np.ones(384, dtype=float))
    monkeypatch.setattr(embeddings, "client", client)

    result = embeddings.generate_embedding("AI news")

    assert len(result) == 384
    assert all(value == 1.0 for value in result)
    assert client.calls[0][0] == "AI news"


@pytest.mark.parametrize("value", ["", "   ", None])
def test_generate_embedding_rejects_empty_input(value):
    with pytest.raises(ValueError, match="non-empty"):
        embeddings.generate_embedding(value)


def test_generate_embedding_rejects_wrong_dimensions(monkeypatch):
    monkeypatch.setattr(
        embeddings, "client", FakeInferenceClient(result=np.ones(12))
    )

    with pytest.raises(RuntimeError, match="valid news embedding"):
        embeddings.generate_embedding("AI news")


def test_generate_embedding_rejects_non_finite_values(monkeypatch):
    vector = np.ones(384)
    vector[3] = np.nan
    monkeypatch.setattr(
        embeddings, "client", FakeInferenceClient(result=vector)
    )

    with pytest.raises(RuntimeError, match="valid news embedding"):
        embeddings.generate_embedding("AI news")


def test_generate_embedding_propagates_provider_failure(monkeypatch):
    monkeypatch.setattr(
        embeddings,
        "client",
        FakeInferenceClient(error=RuntimeError("provider offline")),
    )

    with pytest.raises(RuntimeError, match="valid news embedding"):
        embeddings.generate_embedding("AI news")
