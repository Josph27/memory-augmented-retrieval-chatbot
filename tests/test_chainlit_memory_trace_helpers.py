from __future__ import annotations

from types import SimpleNamespace

from app import (
    format_orchestration_trace_markdown,
    retrieved_memory_rows,
    saved_memory_rows,
)


def test_saved_memory_rows_reads_result_metadata() -> None:
    result = SimpleNamespace(metadata={"saved_memory_rows": [{"memory_id": "m1"}]})

    assert saved_memory_rows(result) == [{"memory_id": "m1"}]


def test_retrieved_memory_rows_falls_back_to_trace_metadata() -> None:
    result = SimpleNamespace(
        metadata={},
        trace=SimpleNamespace(metadata={"retrieved_memory_rows": [{"memory_id": "m2"}]}),
    )

    assert retrieved_memory_rows(result) == [{"memory_id": "m2"}]


def test_orchestration_trace_is_bounded_and_contains_no_evidence_text() -> None:
    result = SimpleNamespace(
        trace=SimpleNamespace(
            metadata={
                "orchestration": {
                    "requested_mode": "langgraph_shadow",
                    "effective_mode": "langgraph_shadow",
                    "authoritative_context": "native",
                    "fallback_used": False,
                    "error": None,
                    "comparison": {
                        "native_only_sources": ["structured_memory"],
                        "langgraph_only_sources": ["current_chat_span"],
                        "selected_candidate_overlap": 1,
                        "token_difference": 12,
                    },
                    "langgraph_trace": {
                        "route_sources": ["recent_messages", "current_chat_span"],
                        "routing": {
                            "routing_mode": "semantic_v2",
                            "intents": [{"intent": "SAME_CHAT_RECALL"}],
                        },
                        "evidence_contract": {"requires_raw_span": False},
                        "candidate_counts_by_source": {"current_chat_span": 1},
                        "selected_counts_by_source": {"current_chat_span": 1},
                        "dropped_counts_by_source": {},
                        "source_budgets": {"current_chat_span": 400},
                        "actual_context_tokens": 120,
                        "provenance_valid": True,
                        "node_timings_ms": {"route": 0.2},
                    },
                }
            }
        )
    )

    rendered = format_orchestration_trace_markdown(result)

    assert "LangGraph" not in rendered or "langgraph_shadow" in rendered
    assert "SAME_CHAT_RECALL" in rendered
    assert "current_chat_span" in rendered
    assert "system prompt" not in rendered.lower()
    assert "candidate content" not in rendered.lower()
