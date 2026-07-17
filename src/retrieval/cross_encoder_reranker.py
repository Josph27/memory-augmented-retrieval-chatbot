from __future__ import annotations

import math
from typing import Protocol


DEFAULT_CROSS_ENCODER_MODEL = "BAAI/bge-reranker-v2-m3"


class CrossEncoderUnavailable(RuntimeError):
    """Raised when the optional cross-encoder backend cannot be used."""


class CrossEncoderBackend(Protocol):
    """Minimal semantic scoring interface used by MemoryReranker."""

    @property
    def model_name(self) -> str:
        """Return the configured cross-encoder model name."""
        ...

    def score(self, query: str, candidate_texts: list[str]) -> list[float]:
        """Return one normalized relevance score per candidate."""
        ...


class SentenceTransformersCrossEncoderBackend:
    """Lazy sentence-transformers CrossEncoder adapter."""

    def __init__(self, model_name: str = DEFAULT_CROSS_ENCODER_MODEL) -> None:
        self._model_name = model_name
        self._model = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def preload(self) -> None:
        """Load the cross-encoder model eagerly so the first message is not delayed."""
        self._load_model()

    def score(self, query: str, candidate_texts: list[str]) -> list[float]:
        """Score query/candidate pairs and normalize logits to [0, 1]."""
        if not candidate_texts:
            return []
        model = self._load_model()
        try:
            raw_scores = model.predict(
                [(query, candidate_text) for candidate_text in candidate_texts]
            )
        except Exception as error:
            raise CrossEncoderUnavailable(
                f"Cross-encoder inference failed for {self.model_name!r}: {error}"
            ) from error
        if hasattr(raw_scores, "tolist"):
            raw_scores = raw_scores.tolist()
        if not isinstance(raw_scores, list):
            raw_scores = list(raw_scores)
        return normalize_cross_encoder_scores(raw_scores)

    def _load_model(self):
        """Import and load the cross encoder only on first use."""
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as error:
            raise CrossEncoderUnavailable(
                "sentence-transformers is unavailable. Install it only when "
                "RERANKER_MODE=cross_encoder is needed."
            ) from error
        try:
            self._model = CrossEncoder(self.model_name)
        except Exception as error:
            raise CrossEncoderUnavailable(
                f"Could not load cross-encoder model {self.model_name!r}: {error}"
            ) from error
        return self._model


def normalize_cross_encoder_scores(scores: list[object]) -> list[float]:
    """Validate scores and normalize logits to [0, 1]."""
    normalized_values = []
    for score in scores:
        if isinstance(score, bool) or not isinstance(score, int | float):
            raise CrossEncoderUnavailable("Cross-encoder returned a non-numeric score.")
        value = float(score)
        if not math.isfinite(value):
            raise CrossEncoderUnavailable("Cross-encoder returned a non-finite score.")
        normalized_values.append(value)
    if all(0.0 <= value <= 1.0 for value in normalized_values):
        return normalized_values
    return [sigmoid(value) for value in normalized_values]


def sigmoid(value: float) -> float:
    """Return a numerically stable logistic score."""
    if value >= 0:
        exponent = math.exp(-value)
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(value)
    return exponent / (1.0 + exponent)
