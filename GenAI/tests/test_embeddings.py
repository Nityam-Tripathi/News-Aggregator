import unittest
from unittest.mock import patch
from app.embeddings import validate_embedding, generate_embedding

class EmbeddingTests(unittest.TestCase):
    def test_valid_vector(self):
        vector = [0.1] * 384
        self.assertEqual(validate_embedding(vector), vector)

    def test_invalid_vectors(self):
        for vector in ([0.0] * 384, [1.0], [float("nan")] * 384, [float("inf")] * 384):
            with self.subTest(vector=vector[:1]):
                with self.assertRaises(ValueError):
                    validate_embedding(vector)

    def test_blank_input(self):
        with self.assertRaises(ValueError):
            generate_embedding(" ")

    @patch("app.embeddings.client.feature_extraction", side_effect=RuntimeError("offline"))
    def test_provider_failure_propagates(self, mock):
        with self.assertRaises(RuntimeError):
            generate_embedding("news")
