from __future__ import annotations

from dataclasses import dataclass

from src.routing.routing_agent import RoutingAgent


@dataclass(frozen=True)
class RoutingCase:
    name: str
    query: str
    use_document_memory: bool
    expected_intent: str


class FakeRoutingModel:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[list[dict[str, str]]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del temperature
        self.calls.append(messages)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


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


def test_routing_agent_enables_only_intended_previous_gist_source() -> None:
    decision = RoutingAgent().route("What did we discuss in previous chat?")
    trace = decision.to_trace_dict()

    assert decision.use_recent_messages is True
    assert decision.use_structured_memory is True
    assert decision.fallback_mode is False
    assert "current_chat_gist" in trace["disabled_sources"]
    assert "previous_chat_gist" in trace["active_sources"]
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
        "routing_mode",
        "routing_fallback_reason",
        "active_sources",
        "disabled_sources",
        "intent",
        "context_profile",
    }


def test_routing_agent_rule_mode_is_default_and_does_not_call_model() -> None:
    model = FakeRoutingModel(
        '{"use_recent_messages": false, "use_structured_memory": false, '
        '"use_document_memory": true, "reason": "model", "confidence": 0.9}'
    )

    decision = RoutingAgent(model=model).route("Can you inspect the README document?")

    assert model.calls == []
    assert decision.routing_mode == "rule"
    assert decision.use_recent_messages is True
    assert decision.use_structured_memory is True
    assert decision.use_document_memory is True


def test_routing_agent_llm_mode_uses_valid_structured_output() -> None:
    model = FakeRoutingModel(
        '{"use_recent_messages": true, "use_structured_memory": true, '
        '"use_document_memory": true, "reason": "Needs the uploaded document.", '
        '"confidence": 0.87}'
    )

    decision = RoutingAgent(mode="llm", model=model).route("What does the report say?")
    trace = decision.to_trace_dict()

    assert len(model.calls) == 1
    assert decision.routing_mode == "llm"
    assert decision.fallback_mode is False
    assert decision.routing_fallback_reason is None
    assert decision.use_recent_messages is True
    assert decision.use_structured_memory is True
    assert decision.use_document_memory is True
    assert decision.reason == "Needs the uploaded document."
    assert decision.confidence == 0.87
    assert trace["routing_mode"] == "llm"
    assert trace["routing_fallback_reason"] is None
    assert "document_memory" in trace["active_sources"]
    assert "current_chat_gist" in trace["disabled_sources"]
    assert "raw_message_span" in trace["disabled_sources"]


def test_routing_agent_hybrid_mode_preserves_core_memory_sources() -> None:
    model = FakeRoutingModel(
        '{"use_recent_messages": false, "use_structured_memory": false, '
        '"use_document_memory": true, "reason": "Hybrid document route.", '
        '"confidence": 0.9}'
    )

    decision = RoutingAgent(mode="hybrid", model=model).route("Read this document.")

    assert decision.routing_mode == "hybrid"
    assert decision.fallback_mode is False
    assert decision.use_recent_messages is True
    assert decision.use_structured_memory is True
    assert decision.use_document_memory is True


def test_routing_agent_llm_mode_falls_back_when_model_missing() -> None:
    decision = RoutingAgent(mode="llm", model=None).route("Hello")
    trace = decision.to_trace_dict()

    assert decision.routing_mode == "llm"
    assert decision.fallback_mode is True
    assert decision.routing_fallback_reason == "missing_model"
    assert decision.use_recent_messages is True
    assert decision.use_structured_memory is True
    assert decision.use_document_memory is False
    assert trace["routing_fallback_reason"] == "missing_model"


def test_routing_agent_llm_mode_falls_back_on_invalid_json() -> None:
    decision = RoutingAgent(mode="llm", model=FakeRoutingModel("not json")).route(
        "Can you inspect the README document?"
    )

    assert decision.routing_mode == "llm"
    assert decision.fallback_mode is True
    assert "JSONDecodeError" in str(decision.routing_fallback_reason)
    assert decision.use_document_memory is True


def test_routing_agent_llm_mode_falls_back_on_low_confidence() -> None:
    model = FakeRoutingModel(
        '{"use_recent_messages": true, "use_structured_memory": true, '
        '"use_document_memory": true, "reason": "uncertain", "confidence": 0.2}'
    )

    decision = RoutingAgent(mode="llm", model=model).route("What about that?")

    assert decision.routing_mode == "llm"
    assert decision.fallback_mode is True
    assert decision.routing_fallback_reason == "low_confidence"
    assert decision.use_document_memory is False


def test_routing_agent_llm_mode_falls_back_on_model_error() -> None:
    model = FakeRoutingModel(RuntimeError("timeout"))

    decision = RoutingAgent(mode="llm", model=model).route("What does the document say?")

    assert decision.routing_mode == "llm"
    assert decision.fallback_mode is True
    assert "RuntimeError: timeout" == decision.routing_fallback_reason
    assert decision.use_document_memory is True
