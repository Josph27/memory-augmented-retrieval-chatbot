from __future__ import annotations

from dataclasses import dataclass, field, replace

from src.core.contracts import MemoryCandidate


@dataclass(frozen=True)
class RerankerWeights:
    """Weights for candidate ranking features."""

    similarity_score: float = 0.35
    importance: float = 0.2
    confidence: float = 0.2
    recency: float = 0.1
    usage_count: float = 0.05
    source_priority: float = 0.1
    status_penalty: float = 1.0
    redundancy_penalty: float = 1.0


@dataclass(frozen=True)
class RerankerPolicy:
    """Centralized scoring policy for memory candidates."""

    weights: RerankerWeights = field(default_factory=RerankerWeights)
    source_priorities: dict[str, float] = field(
        default_factory=lambda: {
            "structured_memory": 0.95,
            "recent_messages": 0.9,
            "current_chat_gist": 0.72,
            "previous_chat_gist": 0.65,
            "document_memory": 0.6,
            "raw_message_span": 0.58,
            "previous_chat_memory": 0.6,
            "current_chat_chunks": 0.55,
            "unknown": 0.3,
        }
    )
    status_penalties: dict[str, float] = field(
        default_factory=lambda: {
            "active": 0.0,
            "": 0.0,
            "archived": 0.15,
            "superseded": 0.7,
            "deleted": 1.0,
        }
    )
    exact_duplicate_penalty: float = 0.08


class MemoryReranker:
    """Score and sort retrieved memory candidates for trace visibility.

    The reranker is trace-only for now. It returns copied candidates with score
    metadata and does not affect prompt construction.
    """

    def __init__(self, policy: RerankerPolicy | None = None) -> None:
        self.policy = policy or RerankerPolicy()

    def rank(
        self,
        candidates: list[MemoryCandidate],
        ranking_profile: str | None,
    ) -> list[MemoryCandidate]:
        """Return candidates sorted by final score descending."""
        seen_texts: set[str] = set()
        ranked = [
            self.score_candidate(
                candidate=candidate,
                ranking_profile=ranking_profile,
                seen_texts=seen_texts,
            )
            for candidate in candidates
        ]
        return sorted(
            ranked,
            key=lambda candidate: (
                candidate.score if candidate.score is not None else 0.0,
                candidate.metadata.get("order_sort", 0),
            ),
            reverse=True,
        )

    def score_candidate(
        self,
        candidate: MemoryCandidate,
        ranking_profile: str | None,
        seen_texts: set[str],
    ) -> MemoryCandidate:
        """Compute a score and return a copied candidate with score metadata."""
        features = candidate_features(candidate, self.policy, seen_texts)
        weights = self.policy.weights
        contributions = {
            "similarity_score": features["similarity_score"] * weights.similarity_score,
            "importance": features["importance"] * weights.importance,
            "confidence": features["confidence"] * weights.confidence,
            "recency": features["recency"] * weights.recency,
            "usage_count": features["usage_count"] * weights.usage_count,
            "source_priority": features["source_priority"] * weights.source_priority,
            "status_penalty": -features["status_penalty"] * weights.status_penalty,
            "redundancy_penalty": -features["redundancy_penalty"] * weights.redundancy_penalty,
        }
        final_score = sum(contributions.values())
        metadata = dict(candidate.metadata)
        metadata["ranking_profile"] = ranking_profile or "default"
        metadata["score_breakdown"] = {
            "features": features,
            "weights": weights.__dict__,
            "contributions": contributions,
            "final_score": final_score,
        }
        return replace(candidate, score=final_score, metadata=metadata)


def candidate_features(
    candidate: MemoryCandidate,
    policy: RerankerPolicy,
    seen_texts: set[str],
) -> dict[str, float]:
    """Extract normalized scoring features from a candidate."""
    normalized_content = " ".join(candidate.content.lower().split())
    redundancy_penalty = 0.0
    if normalized_content in seen_texts:
        redundancy_penalty = policy.exact_duplicate_penalty
    else:
        seen_texts.add(normalized_content)

    return {
        "similarity_score": numeric_metadata(candidate, "similarity_score", default=0.5),
        "importance": numeric_metadata(candidate, "importance", default=0.5),
        "confidence": candidate_confidence(candidate),
        "recency": candidate_recency(candidate),
        "usage_count": usage_score(candidate),
        "source_priority": policy.source_priorities.get(candidate.source, 0.3),
        "status_penalty": candidate_status_penalty(candidate, policy),
        "redundancy_penalty": redundancy_penalty,
    }


def numeric_metadata(candidate: MemoryCandidate, key: str, default: float) -> float:
    """Read a numeric metadata feature with a safe default."""
    value = candidate.metadata.get(key)
    if isinstance(value, int | float):
        return clamp(float(value))
    return default


def candidate_confidence(candidate: MemoryCandidate) -> float:
    """Return candidate confidence from metadata, score, or default."""
    value = candidate.metadata.get("confidence")
    if isinstance(value, int | float):
        return clamp(float(value))
    if candidate.score is not None:
        return clamp(candidate.score)
    return 0.5


def candidate_recency(candidate: MemoryCandidate) -> float:
    """Estimate recency from current metadata when available."""
    order = candidate.metadata.get("order")
    if isinstance(order, int):
        return clamp(1.0 / (order + 1))
    return numeric_metadata(candidate, "recency", default=0.5)


def usage_score(candidate: MemoryCandidate) -> float:
    """Normalize usage count into [0, 1]."""
    usage_count = candidate.metadata.get("usage_count")
    if isinstance(usage_count, int | float):
        return clamp(float(usage_count) / 10.0)
    return 0.0


def candidate_status_penalty(candidate: MemoryCandidate, policy: RerankerPolicy) -> float:
    """Return penalty for inactive or archived records."""
    status = str(candidate.metadata.get("status", "")).lower()
    return policy.status_penalties.get(status, 0.0)


def clamp(value: float) -> float:
    """Clamp a score feature to [0, 1]."""
    return max(0.0, min(1.0, value))
