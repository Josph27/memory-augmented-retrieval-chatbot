from __future__ import annotations

from src.core.contracts import MemoryCandidate
from src.retrieval.cross_encoder_reranker import CrossEncoderUnavailable
from src.retrieval.reranker import MemoryReranker


class FakeRerankerModel:
    def __init__(self, response: str = "", error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls = 0

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.response


class FakeCrossEncoderBackend:
    model_name = "fake-cross-encoder"

    def __init__(
        self,
        scores: list[float] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.scores = scores or []
        self.error = error
        self.calls: list[tuple[str, list[str]]] = []

    def score(self, query: str, candidate_texts: list[str]) -> list[float]:
        self.calls.append((query, list(candidate_texts)))
        if self.error is not None:
            raise self.error
        return list(self.scores)


def candidate(
    source: str,
    content: str,
    *,
    metadata: dict | None = None,
) -> MemoryCandidate:
    return MemoryCandidate(
        source=source,  # type: ignore[arg-type]
        content=content,
        metadata=metadata or {},
    )


def test_deterministic_source_prior_prefers_structured_memory() -> None:
    ranked = MemoryReranker().rank(
        [
            candidate("document_memory", "unrelated alpha"),
            candidate("structured_memory", "unrelated beta"),
        ],
        ranking_profile="test",
    )

    assert ranked[0].source == "structured_memory"


def test_deterministic_lexical_overlap_prefers_matching_content() -> None:
    ranked = MemoryReranker().rank(
        [
            candidate("document_memory", "The report discusses UI colors."),
            candidate("document_memory", "The report uses SQLite for chat storage."),
        ],
        ranking_profile="test",
        query="Which report uses SQLite for chat storage?",
    )

    assert "SQLite" in ranked[0].content
    features = ranked[0].metadata["score_breakdown"]["features"]
    assert features["lexical_overlap"] > 0


def test_raw_message_span_gets_provenance_query_boost() -> None:
    ranked = MemoryReranker().rank(
        [
            candidate("structured_memory", "User prefers mature libraries."),
            candidate("raw_message_span", "user: I prefer mature libraries."),
        ],
        ranking_profile="test",
        query="Exactly what did I say? Show the evidence.",
    )

    assert ranked[0].source == "raw_message_span"
    assert (
        ranked[0].metadata["score_breakdown"]["features"]["query_source_boost"]
        == 1.0
    )


def test_previous_chat_gist_gets_earlier_discussion_boost() -> None:
    ranked = MemoryReranker().rank(
        [
            candidate("document_memory", "The demo uses memory."),
            candidate("previous_chat_gist", "An old chat discussed the demo."),
        ],
        ranking_profile="test",
        query="What did we discuss in an earlier chat?",
    )

    assert ranked[0].source == "previous_chat_gist"


def test_document_memory_gets_document_query_boost() -> None:
    ranked = MemoryReranker().rank(
        [
            candidate("structured_memory", "The user likes reports."),
            candidate("document_memory", "README: uploads support Markdown."),
        ],
        ranking_profile="test",
        query="What does the uploaded README document say?",
    )

    assert ranked[0].source == "document_memory"


def test_structured_memory_gets_preference_query_boost() -> None:
    ranked = MemoryReranker().rank(
        [
            candidate("document_memory", "A generic concise-writing guide."),
            candidate("structured_memory", "User preference: concise answers."),
        ],
        ranking_profile="test",
        query="What answer style do I prefer?",
    )

    assert ranked[0].source == "structured_memory"


def test_deterministic_ties_preserve_original_order() -> None:
    candidates = [
        candidate("document_memory", "alpha"),
        candidate("document_memory", "beta"),
        candidate("document_memory", "gamma"),
    ]

    ranked = MemoryReranker().rank(candidates, ranking_profile="test")

    assert [item.content for item in ranked] == ["alpha", "beta", "gamma"]
    assert [item.metadata["original_rank"] for item in ranked] == [0, 1, 2]
    assert [item.metadata["final_rank"] for item in ranked] == [0, 1, 2]


def test_hybrid_mode_applies_valid_llm_order() -> None:
    model = FakeRerankerModel(
        '{"ranked_candidate_ids":["c1","c0"],"confidence":0.9,"reason":"better"}'
    )
    reranker = MemoryReranker(mode="hybrid", model=model, llm_top_k=2)

    result = reranker.rank_with_trace(
        [
            candidate("structured_memory", "Preference memory."),
            candidate("document_memory", "Relevant report evidence."),
            candidate("recent_messages", "A recent message."),
        ],
        ranking_profile="test",
        query="What does the report say?",
    )

    assert result.candidates[0].metadata["reranker_candidate_id"] == "c1"
    assert result.metadata["fallback_used"] is False
    assert result.metadata["llm_ranked_candidate_ids"] == ["c1", "c0"]
    assert result.metadata["llm_confidence"] == 0.9
    assert model.calls == 1


def test_hybrid_falls_back_on_invalid_json() -> None:
    result = MemoryReranker(
        mode="hybrid",
        model=FakeRerankerModel("not-json"),
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="preference",
    )

    assert result.metadata["fallback_used"] is True
    assert "JSONDecodeError" in result.metadata["fallback_reason"]


def test_hybrid_falls_back_on_low_confidence() -> None:
    result = MemoryReranker(
        mode="hybrid",
        model=FakeRerankerModel(
            '{"ranked_candidate_ids":["c1"],"confidence":0.2,"reason":"uncertain"}'
        ),
        llm_min_confidence=0.55,
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="preference",
    )

    assert result.metadata["fallback_used"] is True
    assert result.metadata["fallback_reason"] == "low_confidence"
    assert result.metadata["llm_confidence"] == 0.2


def test_hybrid_falls_back_on_model_exception() -> None:
    result = MemoryReranker(
        mode="hybrid",
        model=FakeRerankerModel(error=RuntimeError("endpoint unavailable")),
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="preference",
    )

    assert result.metadata["fallback_used"] is True
    assert "endpoint unavailable" in result.metadata["fallback_reason"]


def test_hybrid_falls_back_when_model_is_missing() -> None:
    result = MemoryReranker(mode="hybrid", model=None).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="preference",
    )

    assert result.metadata["fallback_used"] is True
    assert result.metadata["fallback_reason"] == "missing_model"


def test_trace_contains_feature_contributions_and_ranks() -> None:
    result = MemoryReranker().rank_with_trace(
        [
            candidate(
                "structured_memory",
                "User prefers concise answers.",
                metadata={"confidence": 0.9, "vector_score": 0.8},
            )
        ],
        ranking_profile="memory_recall",
        query="What answers do I prefer?",
    )

    trace_row = result.metadata["deterministic_scores"][0]
    assert result.metadata["reranker_mode"] == "deterministic"
    assert result.metadata["fallback_used"] is False
    assert trace_row["source"] == "structured_memory"
    assert trace_row["original_rank"] == 0
    assert "lexical_overlap" in trace_row["feature_contributions"]
    assert result.candidates[0].metadata["final_rank"] == 0
    assert result.metadata["final_ranks"][0] == {
        "candidate_id": "c0",
        "source": "structured_memory",
        "original_rank": 0,
        "final_rank": 0,
    }


def test_cross_encoder_mode_combines_mocked_scores_and_reorders() -> None:
    backend = FakeCrossEncoderBackend(scores=[0.1, 0.95])
    result = MemoryReranker(
        mode="cross_encoder",
        cross_encoder_backend=backend,
        cross_encoder_weight=0.9,
    ).rank_with_trace(
        [
            candidate("structured_memory", "User preference about libraries."),
            candidate("document_memory", "The report contains exact evidence."),
        ],
        ranking_profile="test",
        query="What preference do I remember about libraries?",
    )

    assert result.candidates[0].source == "document_memory"
    assert result.metadata["cross_encoder_used"] is True
    assert result.metadata["cross_encoder_model"] == "fake-cross-encoder"
    assert result.metadata["cross_encoder_scores"][1]["score"] == 0.95
    assert result.metadata["combined_scores"]
    assert len(backend.calls) == 1
    assert backend.calls[0][1][0].startswith("[source=")


def test_cross_encoder_mode_limits_scoring_to_top_k() -> None:
    backend = FakeCrossEncoderBackend(scores=[0.8, 0.7])
    result = MemoryReranker(
        mode="cross_encoder",
        cross_encoder_backend=backend,
        cross_encoder_top_k=2,
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference memory."),
            candidate("recent_messages", "Recent detail."),
            candidate("document_memory", "Document detail."),
        ],
        ranking_profile="test",
        query="What is my preference?",
    )

    assert len(backend.calls[0][1]) == 2
    assert len(result.candidates) == 3
    assert result.metadata["cross_encoder_top_k"] == 2
    assert result.candidates[-1].metadata["reranker_candidate_id"] == "c2"


def test_cross_encoder_equal_scores_preserve_source_aware_deterministic_boost() -> None:
    backend = FakeCrossEncoderBackend(scores=[0.5, 0.5])
    result = MemoryReranker(
        mode="cross_encoder",
        cross_encoder_backend=backend,
        cross_encoder_weight=0.65,
    ).rank_with_trace(
        [
            candidate("document_memory", "Generic writing guidance."),
            candidate("structured_memory", "User preference: concise answers."),
        ],
        ranking_profile="test",
        query="What answer style do I prefer?",
    )

    assert result.candidates[0].source == "structured_memory"
    assert (
        result.candidates[0].metadata["normalized_deterministic_score"]
        > result.candidates[1].metadata["normalized_deterministic_score"]
    )


def test_cross_encoder_falls_back_on_backend_exception() -> None:
    backend = FakeCrossEncoderBackend(error=RuntimeError("inference failed"))
    result = MemoryReranker(
        mode="cross_encoder",
        cross_encoder_backend=backend,
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="preference",
    )

    assert result.metadata["fallback_used"] is True
    assert result.metadata["cross_encoder_used"] is False
    assert "inference failed" in result.metadata["fallback_reason"]


def test_cross_encoder_falls_back_when_backend_is_unavailable() -> None:
    backend = FakeCrossEncoderBackend(
        error=CrossEncoderUnavailable("model unavailable")
    )
    result = MemoryReranker(
        mode="cross_encoder",
        cross_encoder_backend=backend,
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="preference",
    )

    assert result.metadata["fallback_used"] is True
    assert "model unavailable" in result.metadata["fallback_reason"]


def test_cross_encoder_falls_back_on_empty_scores() -> None:
    result = MemoryReranker(
        mode="cross_encoder",
        cross_encoder_backend=FakeCrossEncoderBackend(scores=[]),
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="preference",
    )

    assert result.metadata["fallback_used"] is True
    assert "returned no scores" in result.metadata["fallback_reason"]


def test_deterministic_mode_never_calls_cross_encoder_backend() -> None:
    backend = FakeCrossEncoderBackend(
        error=AssertionError("backend should not be called")
    )

    result = MemoryReranker(
        mode="deterministic",
        cross_encoder_backend=backend,
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="preference",
    )

    assert result.metadata["reranker_mode"] == "deterministic"
    assert backend.calls == []
