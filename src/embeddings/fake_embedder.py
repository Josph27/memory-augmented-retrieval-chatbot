from __future__ import annotations

import math
import re


class FakeEmbedder:
    """Deterministic lightweight embedder for offline tests."""

    def __init__(self, dimension: int = 16, model_name: str = "fake-embedder") -> None:
        self._dimension = dimension
        self._model_name = model_name

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_text(self, text: str) -> list[float]:
        vector = [0.0] * self._dimension
        for token in tokenize(text):
            vector[stable_bucket(token, self._dimension)] += 1.0
        return normalize(vector)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_text(text) for text in texts]


def tokenize(text: str) -> list[str]:
    """Tokenize text for deterministic fake embeddings."""
    return re.findall(r"[a-zA-Z0-9_:.+-]+", text.lower())


def stable_bucket(token: str, dimension: int) -> int:
    """Map a token to a stable vector bucket."""
    return sum(ord(character) for character in token) % dimension


def normalize(vector: list[float]) -> list[float]:
    """L2-normalize a vector."""
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]
