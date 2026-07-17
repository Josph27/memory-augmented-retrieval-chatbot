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
        self.preload_called = False

    def score(self, query: str, candidate_texts: list[str]) -> list[float]:
        self.calls.append((query, list(candidate_texts)))
        if self.error is not None:
            raise self.error
        return list(self.scores)

    def preload(self) -> None:
        self.preload_called = True


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
    assert ranked[0].metadata["score_breakdown"]["features"]["query_source_boost"] == 1.0


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
    reranker = MemoryReranker(
        mode="hybrid",
        model=model,
        llm_top_k=2,
        hybrid_backend="llm",
        llm_ambiguity_margin=10.0,
    )

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
        hybrid_backend="llm",
        llm_ambiguity_margin=10.0,
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
        hybrid_backend="llm",
        llm_ambiguity_margin=10.0,
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
        hybrid_backend="llm",
        llm_ambiguity_margin=10.0,
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
    result = MemoryReranker(
        mode="hybrid",
        model=None,
        hybrid_backend="llm",
        llm_ambiguity_margin=10.0,
    ).rank_with_trace(
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
    backend = FakeCrossEncoderBackend(error=CrossEncoderUnavailable("model unavailable"))
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
    backend = FakeCrossEncoderBackend(error=AssertionError("backend should not be called"))

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


def test_hybrid_auto_uses_cross_encoder_and_skips_llm_for_large_margin() -> None:
    backend = FakeCrossEncoderBackend(scores=[1.0, 0.0])
    model = FakeRerankerModel(
        '{"ranked_candidate_ids":["c1","c0"],"confidence":0.9,"reason":"unused"}'
    )
    result = MemoryReranker(
        mode="hybrid",
        hybrid_backend="auto",
        cross_encoder_backend=backend,
        cross_encoder_weight=1.0,
        model=model,
        llm_ambiguity_margin=0.15,
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference memory."),
            candidate("document_memory", "Document evidence."),
        ],
        ranking_profile="test",
        query="Which memory is relevant?",
    )

    assert result.metadata["hybrid_backend"] == "auto"
    assert result.metadata["cross_encoder_used"] is True
    assert result.metadata["llm_rerank_considered"] is True
    assert result.metadata["llm_rerank_used"] is False
    assert result.metadata["llm_rerank_skip_reason"] == "top_margin_above_threshold"
    assert result.metadata["post_cross_encoder_top_margin"] == 1.0
    assert len(backend.calls) == 1
    assert model.calls == 0


def test_hybrid_auto_skips_llm_when_top_candidates_share_source() -> None:
    backend = FakeCrossEncoderBackend(scores=[0.51, 0.5, 0.49])
    model = FakeRerankerModel(
        '{"ranked_candidate_ids":["c1","c0"],"confidence":0.9,"reason":"unused"}'
    )
    result = MemoryReranker(
        mode="hybrid",
        hybrid_backend="auto",
        cross_encoder_backend=backend,
        cross_encoder_weight=1.0,
        model=model,
    ).rank_with_trace(
        [
            candidate("document_memory", "Document alpha."),
            candidate("document_memory", "Document beta."),
            candidate("document_memory", "Document gamma."),
        ],
        ranking_profile="test",
        query="Which document is relevant?",
    )

    assert result.metadata["llm_rerank_used"] is False
    assert result.metadata["llm_rerank_skip_reason"] == "top_candidates_same_source"
    assert result.metadata["top_candidate_sources"] == ["document_memory"]
    assert model.calls == 0


def test_hybrid_auto_uses_llm_for_small_cross_source_margin() -> None:
    backend = FakeCrossEncoderBackend(scores=[0.51, 0.5])
    model = FakeRerankerModel(
        '{"ranked_candidate_ids":["c1","c0"],"confidence":0.9,"reason":"ambiguous"}'
    )
    result = MemoryReranker(
        mode="hybrid",
        hybrid_backend="auto",
        cross_encoder_backend=backend,
        cross_encoder_weight=1.0,
        model=model,
        llm_ambiguity_margin=0.15,
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference memory."),
            candidate("document_memory", "Document evidence."),
        ],
        ranking_profile="test",
        query="Which source is relevant?",
    )

    assert result.metadata["cross_encoder_used"] is True
    assert result.metadata["llm_rerank_considered"] is True
    assert result.metadata["llm_rerank_used"] is True
    assert result.metadata["llm_rerank_skip_reason"] is None
    assert result.metadata["llm_confidence"] == 0.9
    assert model.calls == 1


def test_provenance_gist_raw_conflict_triggers_llm_despite_large_margin() -> None:
    backend = FakeCrossEncoderBackend(scores=[1.0, 0.0])
    model = FakeRerankerModel(
        '{"ranked_candidate_ids":["c1","c0"],"confidence":0.9,"reason":"provenance"}'
    )
    result = MemoryReranker(
        mode="hybrid",
        hybrid_backend="auto",
        cross_encoder_backend=backend,
        cross_encoder_weight=1.0,
        model=model,
        llm_ambiguity_margin=0.01,
        llm_provenance_queries=True,
    ).rank_with_trace(
        [
            candidate("previous_chat_gist", "The user selected SQLite."),
            candidate("raw_message_span", "user: Use SQLite exactly."),
        ],
        ranking_profile="test",
        query="Show the exact evidence and quote what I said.",
    )

    assert result.metadata["llm_rerank_used"] is True
    assert model.calls == 1


def test_hybrid_cross_encoder_backend_never_calls_llm() -> None:
    backend = FakeCrossEncoderBackend(scores=[0.5, 0.5])
    model = FakeRerankerModel(error=AssertionError("LLM must not be called"))
    result = MemoryReranker(
        mode="hybrid",
        hybrid_backend="cross_encoder",
        cross_encoder_backend=backend,
        model=model,
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="Which is relevant?",
    )

    assert result.metadata["cross_encoder_used"] is True
    assert result.metadata["llm_rerank_used"] is False
    assert result.metadata["llm_rerank_skip_reason"] == "hybrid_backend_cross_encoder_only"
    assert model.calls == 0


def test_hybrid_llm_backend_never_calls_cross_encoder() -> None:
    backend = FakeCrossEncoderBackend(error=AssertionError("cross encoder must not be called"))
    model = FakeRerankerModel(
        '{"ranked_candidate_ids":["c1","c0"],"confidence":0.9,"reason":"ambiguous"}'
    )
    result = MemoryReranker(
        mode="hybrid",
        hybrid_backend="llm",
        cross_encoder_backend=backend,
        model=model,
        llm_ambiguity_margin=10.0,
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="Which is relevant?",
    )

    assert backend.calls == []
    assert result.metadata["cross_encoder_used"] is False
    assert result.metadata["llm_rerank_used"] is True
    assert model.calls == 1


def test_hybrid_cross_encoder_failure_preserves_deterministic_order() -> None:
    result = MemoryReranker(
        mode="hybrid",
        hybrid_backend="cross_encoder",
        cross_encoder_backend=FakeCrossEncoderBackend(
            error=CrossEncoderUnavailable("not available")
        ),
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="preference",
    )

    assert result.candidates[0].source == "structured_memory"
    assert result.metadata["fallback_used"] is True
    assert "not available" in result.metadata["fallback_reason"]
    assert result.metadata["llm_rerank_used"] is False


def test_hybrid_llm_failure_preserves_cross_encoder_order() -> None:
    backend = FakeCrossEncoderBackend(scores=[0.0, 1.0])
    model = FakeRerankerModel(error=RuntimeError("LLM unavailable"))
    result = MemoryReranker(
        mode="hybrid",
        hybrid_backend="auto",
        cross_encoder_backend=backend,
        cross_encoder_weight=1.0,
        model=model,
        llm_ambiguity_margin=2.0,
    ).rank_with_trace(
        [
            candidate("structured_memory", "Preference."),
            candidate("document_memory", "Document."),
        ],
        ranking_profile="test",
        query="Which is relevant?",
    )

    assert result.candidates[0].source == "document_memory"
    assert result.metadata["cross_encoder_used"] is True
    assert result.metadata["llm_rerank_used"] is False
    assert result.metadata["fallback_used"] is True
    assert "LLM unavailable" in result.metadata["fallback_reason"]


def test_skip_rerank_preserves_score_and_rank() -> None:
    """Candidates with skip_rerank=True keep their score and rank above others."""
    result = MemoryReranker().rank_with_trace(
        [
            candidate("document_memory", "Regular chunk one.", metadata={"similarity_score": 0.5}),
            MemoryCandidate(
                source="document_memory",
                content="Pre-computed summary.",
                score=0.95,
                record_id="doc:summary",
                metadata={
                    "skip_rerank": True,
                    "document_id": "doc",
                    "retrieval_mode": "pre_computed_summary",
                },
            ),
            candidate("document_memory", "Regular chunk two.", metadata={"similarity_score": 0.4}),
        ],
        ranking_profile="test",
        query="summarize the document",
    )
    assert result.candidates[0].record_id == "doc:summary"
    assert result.candidates[0].score == 0.95
    assert result.candidates[0].metadata["original_rank"] == 1
    assert result.candidates[0].metadata["reranker_candidate_id"] == "c1"
    assert "skip_rerank" in result.candidates[0].metadata
    assert "score_breakdown" in result.candidates[0].metadata
    assert "final_rank" in result.candidates[0].metadata


def test_skip_rerank_trace_has_no_key_errors() -> None:
    """deterministic_trace must not crash on skip_rerank candidates."""
    result = MemoryReranker().rank_with_trace(
        [
            MemoryCandidate(
                source="document_memory",
                content="Pre-computed summary.",
                score=0.95,
                record_id="doc:summary",
                metadata={"skip_rerank": True},
            ),
        ],
        ranking_profile="test",
        query="summarize",
    )
    # If we got here without crashing, the trace was built successfully.
    assert result.metadata["fallback_used"] is False
    assert len(result.metadata["deterministic_scores"]) == 1
    trace_entry = result.metadata["deterministic_scores"][0]
    assert trace_entry["candidate_id"] == "c0"
    assert trace_entry["score"] == 0.95
    # feature_contributions must be present (even if empty for skip_rerank).
    assert "feature_contributions" in trace_entry


def test_skip_rerank_mixed_with_regular_candidates() -> None:
    """skip_rerank candidate ranks above regular candidates regardless of content."""
    result = MemoryReranker().rank_with_trace(
        [
            candidate(
                "document_memory",
                "Highly relevant text that matches query exactly.",
                metadata={"similarity_score": 0.9},
            ),
            MemoryCandidate(
                source="document_memory",
                content="Summary with no query overlap.",
                score=0.95,
                record_id="doc:summary",
                metadata={"skip_rerank": True},
            ),
        ],
        ranking_profile="test",
        query="Highly relevant text that matches query exactly",
    )
    # The exact-match regular candidate may outrank the summary (correct!).
    # But both must be present and the summary's score must be preserved.
    summary = [c for c in result.candidates if c.record_id == "doc:summary"]
    assert len(summary) == 1
    assert summary[0].score == 0.95
    assert "skip_rerank" in summary[0].metadata


# ── Cross-encoder preload tests ──


def test_cross_encoder_backend_preload_loads_model() -> None:
    """SentenceTransformersCrossEncoderBackend.preload() eagerly loads _model."""
    from src.retrieval.cross_encoder_reranker import (
        SentenceTransformersCrossEncoderBackend,
    )

    backend = SentenceTransformersCrossEncoderBackend()
    assert backend._model is None  # not loaded yet
    backend.preload()
    assert backend._model is not None  # loaded eagerly


def test_reranker_preload_calls_backend_preload() -> None:
    """MemoryReranker.preload() delegates to the cross-encoder backend."""
    fake = FakeCrossEncoderBackend()
    assert not fake.preload_called

    reranker = MemoryReranker(
        mode="cross_encoder",
        cross_encoder_backend=fake,
    )
    reranker.preload()
    assert fake.preload_called


def test_reranker_preload_skips_for_deterministic_mode() -> None:
    """MemoryReranker.preload() is a no-op when mode is deterministic."""
    fake = FakeCrossEncoderBackend()
    reranker = MemoryReranker(
        mode="deterministic",
        cross_encoder_backend=fake,
    )
    reranker.preload()
    assert not fake.preload_called


def test_build_reranker_preloads_for_cross_encoder_mode() -> None:
    """ChatService._build_reranker() calls preload when mode is cross_encoder."""
    from unittest.mock import patch

    with patch("src.retrieval.reranker.MemoryReranker.preload") as mock_preload:
        from src.chat_service import ChatService

        ChatService._build_reranker(
            reranker_mode="cross_encoder",
            model=None,  # type: ignore[arg-type]
            reranker_llm_top_k=10,
            reranker_llm_min_confidence=0.55,
            reranker_cross_encoder_model="BAAI/bge-reranker-v2-m3",
            reranker_cross_encoder_top_k=10,
            reranker_cross_encoder_weight=0.65,
            reranker_hybrid_backend="auto",
            reranker_llm_ambiguity_margin=0.15,
            reranker_llm_require_cross_source_conflict=True,
            reranker_llm_provenance_queries=True,
        )
        mock_preload.assert_called_once()


def test_build_reranker_skips_preload_for_deterministic_mode() -> None:
    """ChatService._build_reranker() does not preload for deterministic mode."""
    from unittest.mock import patch

    with patch("src.retrieval.reranker.MemoryReranker.preload") as mock_preload:
        from src.chat_service import ChatService

        ChatService._build_reranker(
            reranker_mode="deterministic",
            model=None,  # type: ignore[arg-type]
            reranker_llm_top_k=10,
            reranker_llm_min_confidence=0.55,
            reranker_cross_encoder_model="BAAI/bge-reranker-v2-m3",
            reranker_cross_encoder_top_k=10,
            reranker_cross_encoder_weight=0.65,
            reranker_hybrid_backend="auto",
            reranker_llm_ambiguity_margin=0.15,
            reranker_llm_require_cross_source_conflict=True,
            reranker_llm_provenance_queries=True,
        )
        mock_preload.assert_not_called()
