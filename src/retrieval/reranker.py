from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from src.core.contracts import MemoryCandidate


RERANKER_MODES = {"deterministic", "hybrid", "llm"}
DEFAULT_LLM_TOP_K = 10
DEFAULT_LLM_MIN_CONFIDENCE = 0.55


class RerankerModel(Protocol):
    """Minimal model protocol for optional LLM reranking."""

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Return a model response."""
        ...


@dataclass(frozen=True)
class RerankerWeights:
    """Weights for candidate ranking features."""

    lexical_overlap: float = 0.35
    query_source_boost: float = 0.25
    semantic_score: float = 0.2
    similarity_score: float = 0.2
    importance: float = 0.15
    confidence: float = 0.15
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


@dataclass(frozen=True)
class RerankResult:
    """Ranked candidates and explainable reranker trace metadata."""

    candidates: list[MemoryCandidate]
    metadata: dict[str, Any]


class MemoryReranker:
    """Query-aware deterministic reranker with optional LLM reranking."""

    def __init__(
        self,
        policy: RerankerPolicy | None = None,
        mode: str = "deterministic",
        model: RerankerModel | None = None,
        llm_top_k: int = DEFAULT_LLM_TOP_K,
        llm_min_confidence: float = DEFAULT_LLM_MIN_CONFIDENCE,
    ) -> None:
        self.policy = policy or RerankerPolicy()
        self.mode = normalize_reranker_mode(mode)
        self.model = model
        self.llm_top_k = max(1, llm_top_k)
        self.llm_min_confidence = clamp(llm_min_confidence)
        self.last_trace_metadata: dict[str, Any] = {}

    def rank(
        self,
        candidates: list[MemoryCandidate],
        ranking_profile: str | None,
        query: str | None = None,
    ) -> list[MemoryCandidate]:
        """Return candidates sorted by final rank."""
        return self.rank_with_trace(
            candidates=candidates,
            ranking_profile=ranking_profile,
            query=query,
        ).candidates

    def rank_with_trace(
        self,
        candidates: list[MemoryCandidate],
        ranking_profile: str | None,
        query: str | None = None,
    ) -> RerankResult:
        """Rank candidates and return trace metadata for WorkflowTrace."""
        deterministic = self._deterministic_rank(
            candidates=candidates,
            ranking_profile=ranking_profile,
            query=query or "",
        )
        trace = deterministic_trace(self.mode, deterministic)
        if self.mode == "deterministic" or len(deterministic) < 2:
            result = result_with_final_trace(deterministic, trace)
            self.last_trace_metadata = result.metadata
            return result

        if self.model is None:
            result = fallback_result(
                mode=self.mode,
                deterministic=deterministic,
                reason="missing_model",
            )
            self.last_trace_metadata = result.metadata
            return result

        rerank_pool = (
            deterministic[: self.llm_top_k]
            if self.mode == "hybrid"
            else deterministic
        )
        try:
            payload = parse_llm_reranker_response(
                self.model.chat(
                    llm_reranker_messages(query or "", rerank_pool),
                    temperature=0,
                )
            )
            confidence = validate_llm_reranker_payload(
                payload,
                known_ids={
                    candidate.metadata["reranker_candidate_id"]
                    for candidate in rerank_pool
                },
            )
            if confidence < self.llm_min_confidence:
                result = fallback_result(
                    mode=self.mode,
                    deterministic=deterministic,
                    reason="low_confidence",
                    llm_confidence=confidence,
                )
                self.last_trace_metadata = result.metadata
                return result
            ranked = apply_llm_order(
                deterministic=deterministic,
                rerank_pool=rerank_pool,
                ranked_ids=payload["ranked_candidate_ids"],
            )
            trace.update(
                {
                    "fallback_used": False,
                    "fallback_reason": None,
                    "llm_ranked_candidate_ids": list(
                        payload["ranked_candidate_ids"]
                    ),
                    "llm_confidence": confidence,
                    "llm_reason": str(payload.get("reason") or ""),
                }
            )
            result = result_with_final_trace(ranked, trace)
        except Exception as error:
            result = fallback_result(
                mode=self.mode,
                deterministic=deterministic,
                reason=f"{type(error).__name__}: {error}",
            )
        self.last_trace_metadata = result.metadata
        return result

    def _deterministic_rank(
        self,
        candidates: list[MemoryCandidate],
        ranking_profile: str | None,
        query: str,
    ) -> list[MemoryCandidate]:
        """Score candidates deterministically and preserve stable tie ordering."""
        seen_texts: set[str] = set()
        scored = [
            self.score_candidate(
                candidate=candidate,
                ranking_profile=ranking_profile,
                seen_texts=seen_texts,
                query=query,
                original_rank=original_rank,
            )
            for original_rank, candidate in enumerate(candidates)
        ]
        return sorted(
            scored,
            key=lambda candidate: (
                -(candidate.score if candidate.score is not None else 0.0),
                int(candidate.metadata["original_rank"]),
            ),
        )

    def score_candidate(
        self,
        candidate: MemoryCandidate,
        ranking_profile: str | None,
        seen_texts: set[str],
        query: str = "",
        original_rank: int = 0,
    ) -> MemoryCandidate:
        """Compute a score and return a copied candidate with score metadata."""
        features = candidate_features(
            candidate,
            self.policy,
            seen_texts,
            query=query,
        )
        weights = self.policy.weights
        contributions = {
            "lexical_overlap": features["lexical_overlap"] * weights.lexical_overlap,
            "query_source_boost": (
                features["query_source_boost"] * weights.query_source_boost
            ),
            "semantic_score": features["semantic_score"] * weights.semantic_score,
            "similarity_score": (
                features["similarity_score"] * weights.similarity_score
            ),
            "importance": features["importance"] * weights.importance,
            "confidence": features["confidence"] * weights.confidence,
            "recency": features["recency"] * weights.recency,
            "usage_count": features["usage_count"] * weights.usage_count,
            "source_priority": (
                features["source_priority"] * weights.source_priority
            ),
            "status_penalty": (
                -features["status_penalty"] * weights.status_penalty
            ),
            "redundancy_penalty": (
                -features["redundancy_penalty"] * weights.redundancy_penalty
            ),
        }
        final_score = sum(contributions.values())
        metadata = dict(candidate.metadata)
        metadata.update(
            {
                "ranking_profile": ranking_profile or "default",
                "original_rank": original_rank,
                "reranker_candidate_id": f"c{original_rank}",
                "score_breakdown": {
                    "features": features,
                    "weights": weights.__dict__,
                    "contributions": contributions,
                    "final_score": final_score,
                },
            }
        )
        return replace(candidate, score=final_score, metadata=metadata)


def candidate_features(
    candidate: MemoryCandidate,
    policy: RerankerPolicy,
    seen_texts: set[str],
    query: str = "",
) -> dict[str, float]:
    """Extract normalized scoring features from a candidate."""
    normalized_content = normalize_text(candidate.content)
    redundancy_penalty = 0.0
    if normalized_content in seen_texts:
        redundancy_penalty = policy.exact_duplicate_penalty
    else:
        seen_texts.add(normalized_content)

    return {
        "lexical_overlap": lexical_overlap(query, candidate.content),
        "query_source_boost": query_source_boost(query, candidate.source),
        "semantic_score": semantic_score(candidate),
        "similarity_score": numeric_metadata(
            candidate,
            "similarity_score",
            default=0.5,
        ),
        "importance": numeric_metadata(candidate, "importance", default=0.5),
        "confidence": candidate_confidence(candidate),
        "recency": candidate_recency(candidate),
        "usage_count": usage_score(candidate),
        "source_priority": policy.source_priorities.get(candidate.source, 0.3),
        "status_penalty": candidate_status_penalty(candidate, policy),
        "redundancy_penalty": redundancy_penalty,
    }


def lexical_overlap(query: str, content: str) -> float:
    """Return query-token coverage in candidate content."""
    query_terms = meaningful_terms(query)
    if not query_terms:
        return 0.0
    content_terms = meaningful_terms(content)
    return len(query_terms & content_terms) / len(query_terms)


def query_source_boost(query: str, source: str) -> float:
    """Return a source-specific boost based on explicit query intent."""
    normalized = normalize_text(query)
    if source == "document_memory" and contains_any(
        normalized,
        ("document", "file", "readme", "report", "upload"),
    ):
        return 1.0
    if source == "structured_memory" and contains_any(
        normalized,
        ("prefer", "preference", "fact", "decision", "remember", "constraint"),
    ):
        return 1.0
    if source == "previous_chat_gist" and contains_any(
        normalized,
        ("previous", "earlier", "old chat", "before", "discussed", "decided"),
    ):
        return 1.0
    if source == "raw_message_span" and contains_any(
        normalized,
        ("exactly", "exact words", "quote", "evidence", "provenance", "did i say"),
    ):
        return 1.0
    if source == "recent_messages" and contains_any(
        normalized,
        ("just", "recent", "last message", "current chat"),
    ):
        return 1.0
    return 0.0


def semantic_score(candidate: MemoryCandidate) -> float:
    """Read normalized semantic/vector relevance from candidate metadata."""
    for key in ("vector_score", "similarity_score", "semantic_score"):
        value = candidate.metadata.get(key)
        if isinstance(value, int | float):
            return clamp(float(value))
    return 0.5


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


def candidate_status_penalty(
    candidate: MemoryCandidate,
    policy: RerankerPolicy,
) -> float:
    """Return penalty for inactive or archived records."""
    status = str(candidate.metadata.get("status", "")).lower()
    return policy.status_penalties.get(status, 0.0)


def llm_reranker_messages(
    query: str,
    candidates: list[MemoryCandidate],
) -> list[dict[str, str]]:
    """Build strict structured-output messages for optional LLM reranking."""
    rows = [
        {
            "id": candidate.metadata["reranker_candidate_id"],
            "source": candidate.source,
            "content": candidate.content[:500],
            "metadata": compact_metadata(candidate.metadata),
        }
        for candidate in candidates
    ]
    return [
        {
            "role": "system",
            "content": (
                "Rank memory candidates by usefulness for answering the user query. "
                "Prefer grounded provenance when exact evidence is requested and avoid "
                "irrelevant distractors. Return JSON only with ranked_candidate_ids, "
                "confidence from 0 to 1, and reason."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Query: {query}\nCandidates:\n"
                f"{json.dumps(rows, ensure_ascii=True)}"
            ),
        },
    ]


def compact_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Keep only useful JSON-safe metadata in the LLM prompt."""
    keys = (
        "category",
        "key",
        "status",
        "confidence",
        "retrieval_mode",
        "vector_score",
        "similarity_score",
        "source_chat_id",
        "updated_at",
    )
    return {key: metadata[key] for key in keys if key in metadata}


def parse_llm_reranker_response(response: str) -> dict[str, Any]:
    """Parse strict JSON, accepting a single fenced JSON object."""
    text = response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("reranker response must be a JSON object")
    return payload


def validate_llm_reranker_payload(
    payload: dict[str, Any],
    known_ids: set[str],
) -> float:
    """Validate candidate ids, duplicates, and numeric confidence."""
    ranked_ids = payload.get("ranked_candidate_ids")
    confidence = payload.get("confidence")
    if not isinstance(ranked_ids, list) or not ranked_ids:
        raise ValueError("ranked_candidate_ids must be a non-empty list")
    if any(not isinstance(candidate_id, str) for candidate_id in ranked_ids):
        raise ValueError("ranked_candidate_ids must contain strings")
    if len(ranked_ids) != len(set(ranked_ids)):
        raise ValueError("ranked_candidate_ids must not contain duplicates")
    unknown = set(ranked_ids) - known_ids
    if unknown:
        raise ValueError(f"unknown candidate ids: {sorted(unknown)}")
    if not isinstance(confidence, int | float) or isinstance(confidence, bool):
        raise ValueError("confidence must be numeric")
    return clamp(float(confidence))


def apply_llm_order(
    deterministic: list[MemoryCandidate],
    rerank_pool: list[MemoryCandidate],
    ranked_ids: list[str],
) -> list[MemoryCandidate]:
    """Apply validated LLM order and append omitted candidates deterministically."""
    by_id = {
        candidate.metadata["reranker_candidate_id"]: candidate
        for candidate in rerank_pool
    }
    used = set(ranked_ids)
    reranked = [by_id[candidate_id] for candidate_id in ranked_ids]
    reranked.extend(
        candidate
        for candidate in rerank_pool
        if candidate.metadata["reranker_candidate_id"] not in used
    )
    pool_ids = set(by_id)
    reranked.extend(
        candidate
        for candidate in deterministic
        if candidate.metadata["reranker_candidate_id"] not in pool_ids
    )
    return reranked


def apply_final_ranks(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
    """Attach final ranks without mutating existing candidates."""
    return [
        replace(
            candidate,
            metadata={
                **candidate.metadata,
                "final_rank": final_rank,
            },
        )
        for final_rank, candidate in enumerate(candidates)
    ]


def deterministic_trace(
    mode: str,
    candidates: list[MemoryCandidate],
) -> dict[str, Any]:
    """Build base reranker trace metadata."""
    return {
        "reranker_mode": mode,
        "fallback_used": False,
        "fallback_reason": None,
        "deterministic_scores": [
            {
                "candidate_id": candidate.metadata["reranker_candidate_id"],
                "source": candidate.source,
                "original_rank": candidate.metadata["original_rank"],
                "deterministic_rank": rank,
                "score": candidate.score,
                "feature_contributions": candidate.metadata["score_breakdown"][
                    "contributions"
                ],
            }
            for rank, candidate in enumerate(candidates)
        ],
        "llm_ranked_candidate_ids": [],
        "llm_confidence": None,
    }


def fallback_result(
    mode: str,
    deterministic: list[MemoryCandidate],
    reason: str,
    llm_confidence: float | None = None,
) -> RerankResult:
    """Return deterministic ordering with explicit fallback metadata."""
    trace = deterministic_trace(mode, deterministic)
    trace.update(
        {
            "fallback_used": True,
            "fallback_reason": reason,
            "llm_confidence": llm_confidence,
        }
    )
    return result_with_final_trace(deterministic, trace)


def result_with_final_trace(
    candidates: list[MemoryCandidate],
    trace: dict[str, Any],
) -> RerankResult:
    """Attach final candidate ranks to candidates and trace metadata."""
    ranked_candidates = apply_final_ranks(candidates)
    metadata = dict(trace)
    metadata["final_ranks"] = [
        {
            "candidate_id": candidate.metadata["reranker_candidate_id"],
            "source": candidate.source,
            "original_rank": candidate.metadata["original_rank"],
            "final_rank": candidate.metadata["final_rank"],
        }
        for candidate in ranked_candidates
    ]
    return RerankResult(candidates=ranked_candidates, metadata=metadata)


def normalize_reranker_mode(mode: str) -> str:
    """Return supported reranker mode or deterministic default."""
    normalized = (mode or "deterministic").strip().lower()
    return normalized if normalized in RERANKER_MODES else "deterministic"


def meaningful_terms(value: str) -> set[str]:
    """Return normalized terms without common query stopwords."""
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "did",
        "do",
        "does",
        "for",
        "i",
        "in",
        "is",
        "it",
        "me",
        "my",
        "of",
        "on",
        "the",
        "to",
        "what",
        "which",
        "you",
    }
    return {
        term
        for term in normalize_text(value).split()
        if len(term) > 1 and term not in stopwords
    }


def normalize_text(value: str) -> str:
    """Normalize free text for deterministic matching."""
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def contains_any(value: str, phrases: tuple[str, ...]) -> bool:
    """Return whether normalized text contains any phrase."""
    return any(normalize_text(phrase) in value for phrase in phrases)


def clamp(value: float) -> float:
    """Clamp a score feature to [0, 1]."""
    return max(0.0, min(1.0, value))
