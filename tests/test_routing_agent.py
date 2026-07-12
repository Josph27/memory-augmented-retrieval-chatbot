from __future__ import annotations

from dataclasses import dataclass

from src.core.contracts import RoutePlan
from src.routing.routing_agent import RoutingAgent, SemanticFullExpansion


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


class BrokenSemanticRouter:
    def route(self, query: str, task_context: str | None = None) -> object:
        del query, task_context
        return object()

    def to_route_plan(self, semantic_plan: object) -> RoutePlan:
        del semantic_plan
        return RoutePlan(
            query="broken",
            intent="broken",
            sources=[],
        )


class BrokenSemanticFullBackend:
    def classify(self, query: str) -> object:
        del query
        return object()


class UnavailableSemanticFullBackend:
    def classify(self, query: str) -> SemanticFullExpansion:
        del query
        raise RuntimeError("classifier unavailable")


class LowConfidenceSemanticFullBackend:
    def classify(self, query: str) -> SemanticFullExpansion:
        del query
        return SemanticFullExpansion(
            enabled_sources=frozenset({"document_memory"}),
            confidence=0.2,
            reason="low confidence test route",
        )


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


def test_routing_agent_enables_gist_and_direct_raw_previous_sources() -> None:
    decision = RoutingAgent().route("What did we discuss in previous chat?")
    trace = decision.to_trace_dict()

    assert decision.use_recent_messages is True
    assert decision.use_structured_memory is True
    assert decision.fallback_mode is False
    assert "current_chat_gist" in trace["disabled_sources"]
    assert "previous_chat_gist" in trace["active_sources"]
    assert "raw_message_span" in trace["active_sources"]
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


def test_routing_agent_rule_mode_behavior_unchanged_for_semantic_full_queries() -> None:
    """Paraphrased document cues remain rule-mode behavior until opt-in."""
    decision = RoutingAgent(mode="rule").route(
        "Can you answer using the material I provided?"
    )
    trace = decision.to_trace_dict()

    assert decision.routing_mode == "rule"
    assert decision.fallback_mode is False
    assert decision.use_recent_messages is True
    assert decision.use_structured_memory is True
    assert decision.use_document_memory is False
    assert "document_memory" in trace["disabled_sources"]


def test_routing_agent_semantic_mode_routes_document_reference() -> None:
    decision = RoutingAgent(mode="semantic").route(
        "According to the uploaded document, what does it say about risk?"
    )
    trace = decision.to_trace_dict()

    assert decision.routing_mode == "semantic"
    assert decision.fallback_mode is False
    assert trace["semantic_routing_used"] is True
    assert decision.use_document_memory is True
    assert "document_memory" in trace["active_sources"]
    assert trace["intent"] == "DOCUMENT_QA"


def test_routing_agent_semantic_mode_routes_previous_chat_recall_to_raw_sources() -> None:
    decision = RoutingAgent(mode="semantic").route("What did we discuss last time?")
    trace = decision.to_trace_dict()

    assert decision.routing_mode == "semantic"
    assert decision.fallback_mode is False
    assert "previous_chat_gist" in trace["active_sources"]
    assert "raw_message_span" in trace["active_sources"]


def test_routing_agent_semantic_mode_does_not_over_retrieve_for_general_query() -> None:
    decision = RoutingAgent(mode="semantic").route("Hello, how are you?")
    trace = decision.to_trace_dict()

    assert decision.routing_mode == "semantic"
    assert decision.fallback_mode is False
    assert trace["active_sources"] == ["recent_messages"]
    assert decision.use_structured_memory is False
    assert decision.use_document_memory is False


def test_routing_agent_hybrid_semantic_mode_falls_back_on_invalid_schema() -> None:
    decision = RoutingAgent(
        mode="hybrid_semantic",
        semantic_router=BrokenSemanticRouter(),
    ).route("According to the uploaded document, what does it say?")

    assert decision.routing_mode == "hybrid_semantic"
    assert decision.fallback_mode is True
    assert "semantic route plan did not include any sources" in str(
        decision.routing_fallback_reason
    )
    assert decision.use_document_memory is True


def test_routing_agent_semantic_full_routes_paraphrased_document_queries() -> None:
    queries = [
        "Can you summarize what I just uploaded?",
        "What is the main point of the report?",
        "Based on the attachment, what are the limitations?",
        "Can you answer using the material I provided?",
    ]

    for query in queries:
        decision = RoutingAgent(mode="semantic_full").route(query)
        trace = decision.to_trace_dict()

        assert decision.routing_mode == "semantic_full", query
        assert decision.fallback_mode is False, query
        assert decision.use_document_memory is True, query
        assert "document_memory" in trace["active_sources"], query
        assert trace["semantic_full_used"] is True, query
        assert trace["semantic_full_confidence"] >= 0.62, query


def test_routing_agent_semantic_full_routes_previous_chat_recall() -> None:
    queries = [
        "What did we discuss last time about the project?",
        "What did I tell you before about my housing contract?",
    ]

    for query in queries:
        trace = RoutingAgent(mode="semantic_full").route(query).to_trace_dict()

        assert "previous_chat_gist" in trace["active_sources"], query
        assert "raw_message_span" in trace["active_sources"], query
        assert trace["semantic_full_used"] is True, query


def test_routing_agent_semantic_full_routes_durable_user_memory_questions() -> None:
    queries = [
        "What do you remember about my preferences?",
        "What constraints did I ask you to keep in mind?",
    ]

    for query in queries:
        decision = RoutingAgent(mode="semantic_full").route(query)
        trace = decision.to_trace_dict()

        assert decision.use_structured_memory is True, query
        assert "structured_memory" in trace["active_sources"], query
        assert trace["semantic_full_used"] is True, query


def test_routing_agent_semantic_full_does_not_over_retrieve_documents() -> None:
    queries = [
        "What is the capital of France?",
        "Write a short email to my supervisor.",
    ]

    for query in queries:
        trace = RoutingAgent(mode="semantic_full").route(query).to_trace_dict()

        assert "document_memory" in trace["disabled_sources"], query
        assert "document_memory" not in trace["active_sources"], query
        assert trace["semantic_full_added_sources"] == [], query


def test_routing_agent_semantic_full_falls_back_on_invalid_output() -> None:
    decision = RoutingAgent(
        mode="semantic_full",
        semantic_full_backend=BrokenSemanticFullBackend(),  # type: ignore[arg-type]
    ).route("Can you summarize what I just uploaded?")

    assert decision.routing_mode == "semantic_full"
    assert decision.fallback_mode is True
    assert "TypeError" in str(decision.routing_fallback_reason)
    assert decision.use_document_memory is True


def test_routing_agent_semantic_full_falls_back_when_unavailable() -> None:
    decision = RoutingAgent(
        mode="semantic_full",
        semantic_full_backend=UnavailableSemanticFullBackend(),
    ).route("Can you summarize what I just uploaded?")

    assert decision.routing_mode == "semantic_full"
    assert decision.fallback_mode is True
    assert "RuntimeError: classifier unavailable" == decision.routing_fallback_reason
    assert decision.use_document_memory is True


def test_routing_agent_semantic_full_falls_back_on_low_confidence() -> None:
    decision = RoutingAgent(
        mode="semantic_full",
        semantic_full_backend=LowConfidenceSemanticFullBackend(),
    ).route("Can you answer using the material I provided?")

    assert decision.routing_mode == "semantic_full"
    assert decision.fallback_mode is True
    assert decision.routing_fallback_reason == "semantic_full_low_confidence"
    assert decision.use_document_memory is False


def test_routing_agent_semantic_full_comparison_fixture() -> None:
    cases = [
        (
            "Can you answer using the material I provided?",
            {"document_memory"},
            "improved",
        ),
        (
            "What did we discuss last time about the project?",
            {"previous_chat_gist", "raw_message_span"},
            "matched",
        ),
        (
            "What is the capital of France?",
            set(),
            "matched",
        ),
    ]

    for query, expected_sources, expected_result in cases:
        rule_sources = set(
            RoutingAgent(mode="rule").route(query).to_trace_dict()["active_sources"]
        )
        semantic_sources = set(
            RoutingAgent(mode="semantic_full")
            .route(query)
            .to_trace_dict()["active_sources"]
        )

        assert expected_sources <= semantic_sources, query
        if expected_result == "improved":
            assert expected_sources - rule_sources, query
        else:
            assert not expected_sources - rule_sources, query
        assert rule_sources <= semantic_sources, query


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
