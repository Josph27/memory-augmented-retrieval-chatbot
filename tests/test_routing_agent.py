from __future__ import annotations

from dataclasses import dataclass

from src.routing.routing_agent import RoutingAgent


@dataclass(frozen=True)
class RoutingCase:
    name: str
    query: str
    use_document_memory: bool
    expected_intent: str


def test_routing_agent_representative_query_table() -> None:
    cases = [
        RoutingCase(
            name="normal conversational query",
            query="Can you explain this idea in simple terms?",
            use_document_memory=False,
            expected_intent="general_question",
        ),
        RoutingCase(
            name="user project preference query",
            query="What preferences do I have for this project?",
            use_document_memory=False,
            expected_intent="general_question",
        ),
        RoutingCase(
            name="document readme question",
            query="According to the README document, how do I run the app?",
            use_document_memory=True,
            expected_intent="document_question",
        ),
        RoutingCase(
            name="uploaded file question",
            query="Can you inspect the uploaded report file?",
            use_document_memory=True,
            expected_intent="document_question",
        ),
        RoutingCase(
            name="ambiguous short query",
            query="What about that?",
            use_document_memory=False,
            expected_intent="general_question",
        ),
    ]

    router = RoutingAgent()

    for case in cases:
        decision = router.route(case.query)
        trace = decision.to_trace_dict()

        assert decision.use_recent_messages is True, case.name
        assert decision.use_structured_memory is True, case.name
        assert decision.use_document_memory is case.use_document_memory, case.name
        assert decision.fallback_mode is False, case.name
        assert decision.confidence is not None, case.name
        assert decision.reason, case.name
        assert trace["intent"] == case.expected_intent, case.name
        assert "recent_messages" in trace["active_sources"], case.name
        assert "structured_memory" in trace["active_sources"], case.name

        if case.use_document_memory:
            assert "document_memory" in trace["active_sources"], case.name
        else:
            assert "document_memory" in trace["disabled_sources"], case.name


def test_routing_agent_keeps_gist_and_raw_span_sources_disabled_by_default() -> None:
    decision = RoutingAgent().route("What did we discuss in previous chats?")
    trace = decision.to_trace_dict()

    assert decision.use_recent_messages is True
    assert decision.use_structured_memory is True
    assert decision.fallback_mode is False
    assert "current_chat_gist" in trace["disabled_sources"]
    assert "previous_chat_gist" in trace["disabled_sources"]
    assert "raw_message_span" in trace["disabled_sources"]
    assert "current_chat_chunks" in trace["disabled_sources"]
    assert "previous_chat_memory" in trace["disabled_sources"]


def test_routing_agent_trace_fields_are_stable() -> None:
    trace = RoutingAgent().route("Read this source file.").to_trace_dict()

    assert set(trace) >= {
        "use_recent_messages",
        "use_structured_memory",
        "use_document_memory",
        "reason",
        "confidence",
        "fallback_mode",
        "active_sources",
        "disabled_sources",
        "intent",
        "context_profile",
    }
