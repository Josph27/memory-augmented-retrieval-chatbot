"""Cross-encoder pairwise reranker with timeout fallback."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from src.core.contracts import MemoryCandidate

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """Cross-encoder pairwise scoring. Scores candidates [0-1] per query-chunk match.

    Model is lazy-loaded on first rank() call.
    ThreadPoolExecutor is created once and reused across calls [Oracle F3].
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model = None
        self._executor = ThreadPoolExecutor(max_workers=1)

    def rank(
        self,
        *,
        query: str,
        candidates: list[MemoryCandidate],
        mem_k: int,
        doc_k: int,
        timeout_ms: int,
    ) -> list[MemoryCandidate]:
        """Score candidates, separate cutoff by source (mem_k > doc_k)."""
        if not candidates:
            return []

        model = self._get_model()
        if model is None:
            return candidates

        from dataclasses import replace

        pairs = [(query, c.content) for c in candidates]
        try:
            future = self._executor.submit(model.predict, pairs)
            scores = future.result(timeout=timeout_ms / 1000.0)
        except (FutureTimeoutError, Exception) as exc:
            logger.warning("cross_encoder scoring failed: %s", exc)
            return candidates

        # Attach scores and apply source-specific cutoffs
        mem_scored: list[MemoryCandidate] = []
        doc_scored: list[MemoryCandidate] = []
        for candidate, score in zip(candidates, scores):
            try:
                numeric = clamp(float(score))
            except (ValueError, TypeError):
                numeric = 0.5
            scored = replace(candidate, score=clamp(numeric))
            if candidate.source == "document_memory":
                doc_scored.append(scored)
            else:
                mem_scored.append(scored)

        mem_scored.sort(key=lambda c: -(c.score or 0))
        doc_scored.sort(key=lambda c: -(c.score or 0))

        result = mem_scored[:mem_k] + doc_scored[:doc_k]
        # Append remaining in original score order as overflow
        remaining = [c for c in mem_scored[mem_k:] + doc_scored[doc_k:]]
        remaining.sort(key=lambda c: -(c.score or 0))
        result.extend(remaining)
        return result

    def _get_model(self):
        """Lazy-load the cross-encoder model."""
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]

            self._model = CrossEncoder(self._model_name)
            return self._model
        except Exception as exc:
            logger.warning("failed to load cross-encoder model: %s", exc)
            return None

    def close(self) -> None:
        """Shut down the thread pool."""
        self._executor.shutdown(wait=True)


def clamp(value: float) -> float:
    """Clamp a value to [0, 1]."""
    return max(0.0, min(1.0, value))
