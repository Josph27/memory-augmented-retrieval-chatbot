from __future__ import annotations

import json
from types import SimpleNamespace

from src.core.contracts import ContextPacket, MemoryCandidate, RoutePlan, SourcePlan, WorkflowTrace

from app import (
    build_trace_payload,
    config,
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
    evidence = "CANDIDATE_EVIDENCE_SENTINEL " * 250
    system = "SYSTEM_PROMPT_SENTINEL " * 250
    candidate = MemoryCandidate(source="current_chat_span", content=evidence, record_id="span-1")
    result = SimpleNamespace(
        trace=WorkflowTrace(
            trace_id="trace-1",
            chat_id="chat-1",
            route_plan=RoutePlan(
                query="recall",
                intent="SAME_CHAT_RECALL",
                sources=[
                    SourcePlan(source="current_chat_span"),
                    SourcePlan(source="document_memory", enabled=False),
                ],
            ),
            retrieved_candidates=[candidate],
            context_packet=ContextPacket(
                chat_id="chat-1", system_prompt=system, candidates=[candidate]
            ),
            metadata={
                "orchestration": {
                    "requested_mode": "langgraph_shadow",
                    "effective_mode": "langgraph_shadow",
                    "authoritative_context": "native",
                    "fallback_used": False,
                },
                "context_manager": {
                    "included_candidate_counts_by_source": {"current_chat_span": 1}
                },
            },
        )
    )

    # The compatibility alias now reports mode only; details belong to the structured payload.
    assert format_orchestration_trace_markdown(result) == "langgraph_shadow"
    payload = build_trace_payload(result, config)
    assert payload["turnOverview"]["routeIntent"] == "SAME_CHAT_RECALL"
    assert payload["turnOverview"]["enabledSources"] == ["current_chat_span"]
    assert payload["retrievalFunnel"]["includedBySource"] == {"current_chat_span": 1}
    assert payload["retrievalFunnel"]["preRerankerCount"] == 1
    assert payload["retrievalFunnel"]["inPromptCount"] == 1
    rendered = json.dumps(payload)
    assert "CANDIDATE_EVIDENCE_SENTINEL" not in rendered
    assert "SYSTEM_PROMPT_SENTINEL" not in rendered
    assert len(rendered) < len(evidence)
