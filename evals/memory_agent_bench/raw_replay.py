from __future__ import annotations

import re
from math import sqrt
from dataclasses import replace
from typing import Any, Protocol

from src.agents.context_manager_agent import (
    ContextManagerAgent,
    ContextManagerResult,
    context_manager_metadata,
)
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan


EVAL_RAW_REPLAY_SOURCE = "eval_raw_replay_chunk"
MAX_DIAGNOSTIC_IDS = 10
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "do",
    "does",
    "for",
    "how",
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
    "you",
}
RAW_REPLAY_MODES = ("lexical", "embedding", "hybrid")


class ReplayEmbeddingBackend(Protocol):
    """Minimal embedding contract used only by the benchmark diagnostic."""

    model_name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed replay chunks."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed one benchmark question."""
        ...


class HuggingFaceReplayEmbeddingBackend:
    """Lazy sentence-transformer backend for explicit embedding eval runs."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._backend: Any | None = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._load().embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._load().embed_query(text)

    def _load(self) -> Any:
        if self._backend is not None:
            return self._backend
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
        except ImportError as error:
            msg = (
                "Embedding raw replay retrieval requires the optional "
                "langchain-huggingface dependency."
            )
            raise RuntimeError(msg) from error
        try:
            self._backend = HuggingFaceEmbeddings(model_name=self.model_name)
        except Exception as error:
            msg = f"Could not load raw replay embedding model {self.model_name!r}: {error}"
            raise RuntimeError(msg) from error
        return self._backend


class EvalRawReplayChunkRetriever:
    """Eval-only deterministic retrieval over incrementally replayed chunks."""

    def __init__(
        self,
        replayed_chunks: list[dict[str, Any]],
        *,
        top_k: int = 8,
        max_chars: int = 4000,
        retrieval_mode: str = "lexical",
        embedding_backend: ReplayEmbeddingBackend | None = None,
        candidate_pool_size: int = 50,
    ) -> None:
        if retrieval_mode not in RAW_REPLAY_MODES:
            msg = f"raw replay retrieval mode must be one of {RAW_REPLAY_MODES}"
            raise ValueError(msg)
        if retrieval_mode != "lexical" and embedding_backend is None:
            msg = f"{retrieval_mode} raw replay retrieval requires an embedding backend"
            raise ValueError(msg)
        self.replayed_chunks = replayed_chunks
        self.top_k = max(1, top_k)
        self.max_chars = max(1, max_chars)
        self.retrieval_mode = retrieval_mode
        self.embedding_backend = embedding_backend
        self.candidate_pool_size = max(self.top_k, candidate_pool_size)
        self.last_rankings: dict[int, dict[str, int]] = {}
        self.last_candidate_pool_ids: set[int] = set()

    def retrieve(
        self,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> list[MemoryCandidate]:
        """Return query-ranked raw replay chunks without using benchmark gold."""
        del chat_id
        query = source_plan.query or ""
        query_terms = lexical_terms(query)
        if self.retrieval_mode == "lexical" and not query_terms:
            return []

        replayed_with_text = [
            (replayed, str(replayed.get("content", "")))
            for replayed in self.replayed_chunks
        ]
        lexical_scores = [
            lexical_score(query_terms, content)
            for _, content in replayed_with_text
        ]
        embedding_scores = self._embedding_scores(
            query,
            [content for _, content in replayed_with_text],
        )
        stable_ids = [
            replay_message_id(replayed) or -1
            for replayed, _ in replayed_with_text
        ]
        lexical_ranks = score_ranks(lexical_scores, stable_ids=stable_ids)
        embedding_ranks = score_ranks(embedding_scores, stable_ids=stable_ids)
        hybrid_scores = reciprocal_rank_fusion(lexical_ranks, embedding_ranks)
        hybrid_ranks = score_ranks(hybrid_scores, stable_ids=stable_ids)

        active_scores = {
            "lexical": lexical_scores,
            "embedding": embedding_scores,
            "hybrid": hybrid_scores,
        }[self.retrieval_mode]
        active_ranks = {
            "lexical": lexical_ranks,
            "embedding": embedding_ranks,
            "hybrid": hybrid_ranks,
        }[self.retrieval_mode]
        pool_indexes = self._candidate_pool_indexes(
            lexical_ranks=lexical_ranks,
            embedding_ranks=embedding_ranks,
            active_ranks=active_ranks,
        )
        self.last_candidate_pool_ids = {
            message_id
            for index in pool_indexes
            if (message_id := replay_message_id(replayed_with_text[index][0])) is not None
        }
        self.last_rankings = {}
        for index, (replayed, _) in enumerate(replayed_with_text):
            message_id = replay_message_id(replayed)
            if message_id is not None:
                self.last_rankings[message_id] = {
                    "lexical": lexical_ranks[index],
                    "embedding": embedding_ranks[index],
                    "hybrid": hybrid_ranks[index],
                }

        scored: list[tuple[float, int, int, dict[str, Any]]] = []
        for index in pool_indexes:
            replayed, _ = replayed_with_text[index]
            score = active_scores[index]
            if self.retrieval_mode == "lexical" and score <= 0:
                continue
            message_id = replay_message_id(replayed)
            stable_id = message_id if message_id is not None else -1
            scored.append((score, active_ranks[index], stable_id, replayed))

        limit = min(source_plan.limit or self.top_k, self.top_k)
        selected = sorted(
            scored,
            key=lambda item: (item[1], -item[2]),
        )[: max(1, limit)]
        return [
            replay_candidate(
                replayed,
                score=score,
                query=query,
                max_chars=self.max_chars,
                retrieval_mode=self.retrieval_mode,
                retrieval_rank=rank,
                candidate_pool_size=self.candidate_pool_size,
                embedding_model=(
                    self.embedding_backend.model_name
                    if self.embedding_backend is not None
                    else None
                ),
            )
            for score, rank, _, replayed in selected
        ]

    def gold_rank_diagnostics(self, gold_message_ids: set[int]) -> dict[str, Any]:
        """Look up post-hoc ranks without allowing gold to affect retrieval."""
        ranks = [
            self.last_rankings[message_id]
            for message_id in gold_message_ids
            if message_id in self.last_rankings
        ]
        return {
            "raw_replay_mode": self.retrieval_mode,
            "raw_replay_candidate_pool_size": self.candidate_pool_size,
            "gold_rank_lexical": min(
                (rank["lexical"] for rank in ranks),
                default=None,
            ),
            "gold_rank_embedding": min(
                (rank["embedding"] for rank in ranks),
                default=None,
            ),
            "gold_rank_hybrid": min(
                (rank["hybrid"] for rank in ranks),
                default=None,
            ),
            "gold_in_candidate_pool": bool(
                gold_message_ids & self.last_candidate_pool_ids
            ),
        }

    def _embedding_scores(self, query: str, contents: list[str]) -> list[float]:
        if self.embedding_backend is None:
            return [0.0] * len(contents)
        query_embedding = self.embedding_backend.embed_query(query)
        chunk_embeddings = self.embedding_backend.embed_documents(contents)
        if len(chunk_embeddings) != len(contents):
            raise ValueError("embedding backend returned an unexpected vector count")
        return [
            cosine_similarity(query_embedding, embedding)
            for embedding in chunk_embeddings
        ]

    def _candidate_pool_indexes(
        self,
        *,
        lexical_ranks: list[int],
        embedding_ranks: list[int],
        active_ranks: list[int],
    ) -> list[int]:
        if self.retrieval_mode == "hybrid":
            indexes = {
                index
                for index, rank in enumerate(lexical_ranks)
                if rank <= self.candidate_pool_size
            }
            indexes.update(
                index
                for index, rank in enumerate(embedding_ranks)
                if rank <= self.candidate_pool_size
            )
            return sorted(indexes, key=lambda index: active_ranks[index])
        return [
            index
            for index, rank in enumerate(active_ranks)
            if rank <= self.candidate_pool_size
        ]


class EvalRawReplayContextManager(ContextManagerAgent):
    """Route eval-only chunks through existing raw-span budgeting and layout."""

    def build_context_packet(  # type: ignore[override]
        self,
        *,
        system_prompt: str,
        latest_user_message: dict[str, str],
        ranked_candidates: list[MemoryCandidate],
        route_plan: RoutePlan,
    ) -> ContextManagerResult:
        mapped = [
            map_eval_candidate_to_raw(candidate)
            for candidate in ranked_candidates
        ]
        result = super().build_context_packet(
            system_prompt=system_prompt,
            latest_user_message=latest_user_message,
            ranked_candidates=mapped,
            route_plan=route_plan,
        )
        restored_candidates = [
            restore_eval_candidate(candidate)
            for candidate in result.context_packet.candidates
        ]
        packet = replace(
            result.context_packet,
            candidates=restored_candidates,
        )
        return ContextManagerResult(
            context_budget=result.context_budget,
            context_packet=packet,
            metadata=context_manager_metadata(result.context_budget, packet),
        )


def replay_candidate(
    replayed: dict[str, Any],
    *,
    score: float,
    query: str,
    max_chars: int,
    retrieval_mode: str = "lexical",
    retrieval_rank: int | None = None,
    candidate_pool_size: int | None = None,
    embedding_model: str | None = None,
) -> MemoryCandidate:
    """Normalize one replay chunk into a bounded eval-only candidate."""
    content = str(replayed.get("content", ""))
    bounded = query_centered_text(content, query=query, max_chars=max_chars)
    message_id = replayed.get("user_message_id")
    source_ids = [message_id] if isinstance(message_id, int) else []
    session_id = str(replayed.get("session_id", "unknown"))
    chunk_index = replayed.get("chunk_index")
    return MemoryCandidate(
        source=EVAL_RAW_REPLAY_SOURCE,  # type: ignore[arg-type]
        content=bounded,
        score=score,
        record_id=f"eval-replay:{session_id}:{chunk_index}",
        chat_id=(
            str(replayed["chat_id"])
            if isinstance(replayed.get("chat_id"), str)
            else None
        ),
        source_message_ids=source_ids,
        metadata={
            "eval_only": True,
            "source_type": EVAL_RAW_REPLAY_SOURCE,
            "session_id": session_id,
            "chunk_index": chunk_index,
            "user_message_id": message_id,
            "role": "user",
            "retrieval_mode": f"eval_raw_replay_{retrieval_mode}",
            "retrieval_rank": retrieval_rank,
            "candidate_pool_size": candidate_pool_size,
            "embedding_model": embedding_model,
            "original_char_count": len(content),
            "window_char_count": len(bounded),
            "truncated": bounded != content,
            "status": "active",
        },
    )


def lexical_terms(value: str) -> set[str]:
    """Return deterministic non-stopword terms for eval-only retrieval."""
    return {
        token
        for token in TOKEN_PATTERN.findall(value.lower())
        if token not in STOPWORDS and len(token) > 1
    }


def lexical_score(query_terms: set[str], content: str) -> float:
    """Score one replay chunk by normalized query-term coverage."""
    overlap = len(query_terms & lexical_terms(content))
    return overlap / len(query_terms) if query_terms else 0.0


def replay_message_id(replayed: dict[str, Any]) -> int | None:
    message_id = replayed.get("user_message_id")
    return message_id if isinstance(message_id, int) else None


def score_ranks(
    scores: list[float],
    *,
    stable_ids: list[int] | None = None,
) -> list[int]:
    """Return stable one-based ranks for one score vector."""
    tie_breakers = stable_ids or list(reversed(range(len(scores))))
    ordered = sorted(
        range(len(scores)),
        key=lambda index: (-scores[index], -tie_breakers[index]),
    )
    ranks = [0] * len(scores)
    for rank, index in enumerate(ordered, start=1):
        ranks[index] = rank
    return ranks


def reciprocal_rank_fusion(
    lexical_ranks: list[int],
    embedding_ranks: list[int],
    *,
    rank_constant: int = 60,
) -> list[float]:
    """Fuse lexical and semantic rankings without score calibration."""
    maximum = 2.0 / (rank_constant + 1)
    return [
        (
            (1.0 / (rank_constant + lexical_rank))
            + (1.0 / (rank_constant + embedding_rank))
        )
        / maximum
        for lexical_rank, embedding_rank in zip(
            lexical_ranks,
            embedding_ranks,
            strict=True,
        )
    ]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding vectors must have matching dimensions")
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )


def query_centered_text(content: str, *, query: str, max_chars: int) -> str:
    """Keep a bounded query-relevant character window from one replay chunk."""
    if len(content) <= max_chars:
        return content
    terms = sorted(lexical_terms(query), key=len, reverse=True)
    lowered = content.lower()
    positions = [
        (lowered.find(term), len(term))
        for term in terms
        if lowered.find(term) >= 0
    ]
    center = (
        max(positions, key=lambda item: item[1])[0]
        if positions
        else len(content) // 2
    )
    prefix = "[... earlier replay text omitted ...]\n"
    suffix = "\n[... later replay text omitted ...]"
    available = max(1, max_chars - len(prefix) - len(suffix))
    start = max(0, center - available // 2)
    start = min(start, len(content) - available)
    return f"{prefix}{content[start : start + available]}{suffix}"[:max_chars]


def map_eval_candidate_to_raw(candidate: MemoryCandidate) -> MemoryCandidate:
    """Use the established raw-span context path without changing production."""
    if candidate.source != EVAL_RAW_REPLAY_SOURCE:
        return candidate
    return replace(
        candidate,
        source="raw_message_span",
        metadata={
            **candidate.metadata,
            "_eval_original_source": EVAL_RAW_REPLAY_SOURCE,
        },
    )


def restore_eval_candidate(candidate: MemoryCandidate) -> MemoryCandidate:
    """Restore the explicit eval-only source label in ContextPacket traces."""
    if candidate.metadata.get("_eval_original_source") != EVAL_RAW_REPLAY_SOURCE:
        return candidate
    metadata = dict(candidate.metadata)
    metadata.pop("_eval_original_source", None)
    return replace(
        candidate,
        source=EVAL_RAW_REPLAY_SOURCE,  # type: ignore[arg-type]
        metadata=metadata,
    )


def raw_replay_diagnostics(
    *,
    enabled: bool,
    gold_answers: tuple[str, ...],
    retrieved_candidates: list[MemoryCandidate],
    context_candidates: list[MemoryCandidate],
    gold_message_ids: set[int],
    rank_diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return bounded post-hoc diagnostics; gold never affects retrieval."""
    retrieved = [
        candidate
        for candidate in retrieved_candidates
        if candidate.source == EVAL_RAW_REPLAY_SOURCE
    ]
    context = [
        candidate
        for candidate in context_candidates
        if candidate.source == EVAL_RAW_REPLAY_SOURCE
    ]
    normalized_gold = [
        " ".join(answer.lower().split())
        for answer in gold_answers
        if answer.strip()
    ]
    def contains_gold(candidate: MemoryCandidate) -> bool:
        normalized_content = " ".join(candidate.content.lower().split())
        return any(
            gold and gold in normalized_content
            for gold in normalized_gold
        )

    def covers_gold_message(candidate: MemoryCandidate) -> bool:
        return bool(
            gold_message_ids.intersection(candidate.source_message_ids)
        )

    return {
        "raw_replay_enabled": enabled,
        **(rank_diagnostics or {}),
        "raw_replay_candidate_count": len(retrieved),
        "raw_replay_top_ids": [
            candidate.record_id for candidate in retrieved[:MAX_DIAGNOSTIC_IDS]
        ],
        "raw_replay_gold_literal_found": any(map(contains_gold, retrieved)),
        "raw_replay_gold_message_found": any(
            map(covers_gold_message, retrieved)
        ),
        "raw_replay_reached_context": bool(context),
        "raw_replay_gold_literal_reached_context": any(
            map(contains_gold, context)
        ),
        "raw_replay_gold_message_reached_context": any(
            map(covers_gold_message, context)
        ),
        "raw_replay_context_ids": [
            candidate.record_id for candidate in context[:MAX_DIAGNOSTIC_IDS]
        ],
    }
