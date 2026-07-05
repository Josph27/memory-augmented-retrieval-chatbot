from __future__ import annotations

import pytest

from src.routing.semantic_router import (
    CASUAL_CHAT,
    DOCUMENT_QA,
    EXACT_QUOTE,
    MEMORY_QA,
    PREVIOUS_CHAT_RECALL,
    RETRIEVAL_NONE,
    RETRIEVAL_REQUIRED,
    SCOPE_CURRENT_CHAT,
    SCOPE_DOCUMENT,
    SCOPE_PREVIOUS_CHAT,
    SEMANTIC_SOURCE_CANDIDATE_LIMIT,
    STRUCTURED_PREFERENCE_RECALL,
    SemanticRouter,
)


@pytest.mark.parametrize(
    "query",
    [
        "Quote exactly what I said about router.",
        "What exact phrase did I use about router?",
        "What were my exact words about router?",
        "How did I phrase router?",
        "What wording did I use about router?",
    ],
)
def test_english_quote_paraphrases_require_raw_evidence(query: str) -> None:
    plan = SemanticRouter().route(query)

    assert plan.intents[0].intent == EXACT_QUOTE
    assert plan.evidence_contract.requires_raw_span is True
    assert plan.evidence_contract.must_not_answer_from_gist_only is True
    assert {
        "current_chat_span",
        "previous_chat_gist",
        "raw_message_span",
    } <= set(plan.enabled_sources)


def test_document_question_requires_document_citation() -> None:
    plan = SemanticRouter().route(
        "According to the uploaded document, what does it say about X?"
    )

    assert plan.intents[0].intent == DOCUMENT_QA
    assert plan.enabled_sources == ("recent_messages", "document_memory")
    assert plan.evidence_contract.requires_document_citation is True
    assert plan.evidence_contract.requires_raw_span is False
    assert plan.primary_scope == SCOPE_DOCUMENT
    assert plan.required_scopes == frozenset({SCOPE_DOCUMENT})


def test_current_chat_question_remains_current_chat_scoped() -> None:
    plan = SemanticRouter().route(
        "What did I say earlier in this chat about the deployment constraint?"
    )

    assert plan.required_scopes == frozenset({SCOPE_CURRENT_CHAT})
    assert plan.enabled_sources == ("recent_messages", "current_chat_span")


def test_document_and_current_chat_query_unions_required_sources() -> None:
    plan = SemanticRouter().route(
        "According to the uploaded report, compare it with the constraint "
        "I mentioned earlier in this chat."
    )

    assert plan.intents[0].intent == DOCUMENT_QA
    assert plan.primary_scope == SCOPE_DOCUMENT
    assert plan.required_scopes == frozenset(
        {SCOPE_DOCUMENT, SCOPE_CURRENT_CHAT}
    )
    assert plan.enabled_sources == (
        "recent_messages",
        "document_memory",
        "current_chat_span",
    )


def test_document_and_previous_chat_query_unions_required_sources() -> None:
    plan = SemanticRouter().route(
        "Using the uploaded report, compare it with what we discussed "
        "in the previous chat."
    )

    assert plan.intents[0].intent == DOCUMENT_QA
    assert plan.required_scopes == frozenset(
        {SCOPE_DOCUMENT, SCOPE_PREVIOUS_CHAT}
    )
    assert plan.enabled_sources == (
        "recent_messages",
        "document_memory",
        "previous_chat_gist",
        "raw_message_span",
    )


def test_document_and_previous_exact_wording_keeps_raw_span_contract() -> None:
    plan = SemanticRouter().route(
        "Using the uploaded report, compare it with the exact phrase "
        "I used in the previous chat."
    )

    assert plan.intents[0].intent == EXACT_QUOTE
    assert plan.required_scopes == frozenset(
        {SCOPE_DOCUMENT, SCOPE_PREVIOUS_CHAT}
    )
    assert plan.enabled_sources == (
        "recent_messages",
        "document_memory",
        "previous_chat_gist",
        "raw_message_span",
    )
    assert plan.evidence_contract.requires_raw_span is True
    assert plan.evidence_contract.must_not_answer_from_gist_only is True


def test_structured_preference_recall_requires_structured_memory() -> None:
    plan = SemanticRouter().route("What do I prefer for project architecture?")

    assert plan.intents[0].intent == STRUCTURED_PREFERENCE_RECALL
    assert "structured_memory" in plan.enabled_sources
    assert plan.evidence_contract.requires_structured_memory is True


def test_casual_chat_only_uses_recent_messages() -> None:
    plan = SemanticRouter().route("How are you?")

    assert plan.intents[0].intent == CASUAL_CHAT
    assert plan.enabled_sources == ("recent_messages",)
    assert plan.evidence_contract.requires_raw_span is False
    assert plan.evidence_contract.requires_document_citation is False


def test_original_query_and_generated_variants_remain_typed_hints() -> None:
    query = "What exact phrase did I use about Router V2?"
    router = SemanticRouter()
    semantic_plan = router.route(query)
    route_plan = router.to_route_plan(semantic_plan)

    assert semantic_plan.original_query == query
    assert semantic_plan.retrieval_queries[0].text == query
    assert semantic_plan.retrieval_queries[0].is_generated is False
    assert any(item.is_generated for item in semantic_plan.retrieval_queries)
    assert all(
        source.query == query
        for source in route_plan.sources
        if source.enabled
    )
    assert all(
        source.limit
        == (
            12
            if source.source == "raw_message_span"
            else SEMANTIC_SOURCE_CANDIDATE_LIMIT
        )
        for source in route_plan.sources
        if source.enabled
    )


def test_exact_quote_sources_follow_temporal_scope() -> None:
    router = SemanticRouter()

    current = router.route(
        "What exact phrase did I use earlier in this chat about context?"
    )
    previous = router.route(
        "What exact phrase did I use in the previous chat about context?"
    )

    assert current.enabled_sources == ("recent_messages", "current_chat_span")
    assert previous.enabled_sources == (
        "recent_messages",
        "previous_chat_gist",
        "raw_message_span",
    )


def test_previous_orientation_enables_gist_and_direct_raw_paths() -> None:
    plan = SemanticRouter().route("What did we discuss last time?")

    assert plan.enabled_sources == (
        "recent_messages",
        "previous_chat_gist",
        "raw_message_span",
    )


def test_factual_memory_question_without_temporal_wording_is_not_casual() -> None:
    plan = SemanticRouter().route("Which framework did we choose for this project?")

    assert plan.intents[0].intent == MEMORY_QA
    assert plan.retrieval_need == RETRIEVAL_REQUIRED
    assert plan.memory_scope == "unknown"
    assert plan.enabled_sources == (
        "recent_messages",
        "structured_memory",
        "previous_chat_gist",
        "raw_message_span",
    )
    assert not {
        "current_chat_span",
        "document_memory",
    } & set(plan.enabled_sources)


def test_memory_qa_task_context_is_generic_and_bounded() -> None:
    plan = SemanticRouter().route(
        "Who was the Norse leader?",
        task_context="memory_qa",
    )

    assert plan.intents[0].intent == MEMORY_QA
    assert plan.retrieval_need == RETRIEVAL_REQUIRED
    assert plan.memory_scope == "unknown"
    assert plan.task_context == "memory_qa"
    assert plan.enabled_sources == (
        "recent_messages",
        "structured_memory",
        "previous_chat_gist",
        "raw_message_span",
    )


@pytest.mark.parametrize(
    "query",
    [
        "Hello!",
        "Thanks.",
        "How are you?",
        "Rewrite this paragraph to be clearer.",
        "Brainstorm a product name.",
    ],
)
def test_non_retrieval_requests_remain_recent_only(query: str) -> None:
    plan = SemanticRouter().route(query)

    assert plan.intents[0].intent == CASUAL_CHAT
    assert plan.retrieval_need == RETRIEVAL_NONE
    assert plan.enabled_sources == ("recent_messages",)


def test_book_summary_request_is_not_routed_as_casual_chat() -> None:
    router = SemanticRouter()
    plan = router.route("Summarize the book.")

    assert plan.intents[0].intent == MEMORY_QA
    assert plan.retrieval_need == RETRIEVAL_REQUIRED
    assert "previous_chat_gist" in plan.enabled_sources
    route_plan = router.to_route_plan(plan)
    assert route_plan.context_profile == "global_summary"
    assert route_plan.metadata["retrieval_query"] == (
        "global summary complete book chronological content"
    )


def test_summary_of_earlier_user_content_is_memory_grounded() -> None:
    plan = SemanticRouter().route("Summarize what I told you earlier.")

    assert plan.intents[0].intent == MEMORY_QA
    assert plan.retrieval_need == RETRIEVAL_REQUIRED
    assert "previous_chat_gist" in plan.enabled_sources


def test_previous_conversation_summary_prefers_previous_chat_memory() -> None:
    plan = SemanticRouter().route("Give me a summary of the previous conversation.")

    assert plan.intents[0].intent == PREVIOUS_CHAT_RECALL
    assert plan.retrieval_need == RETRIEVAL_REQUIRED
    assert plan.enabled_sources == (
        "recent_messages",
        "previous_chat_gist",
        "raw_message_span",
    )
    assert SemanticRouter().to_route_plan(plan).context_profile == "global_summary"


def test_inline_summary_does_not_require_historical_memory() -> None:
    router = SemanticRouter()
    plan = router.route("Summarize this text: The cat sat on the mat.")

    assert plan.intents[0].intent == CASUAL_CHAT
    assert plan.retrieval_need == RETRIEVAL_NONE
    assert plan.enabled_sources == ("recent_messages",)
    assert router.to_route_plan(plan).context_profile == "general_chat"


def test_direct_memory_question_uses_memory_recall_profile() -> None:
    router = SemanticRouter()
    plan = router.route("Which framework did we choose for this project?")

    assert router.to_route_plan(plan).context_profile == "memory_recall"


def test_simplified_query_is_used_only_for_candidate_retrieval() -> None:
    query = (
        "Based on all the information above, who is older, "
        "Annie Morton or Terry Richardson?"
    )
    router = SemanticRouter()
    semantic = router.route(query, task_context="memory_qa")
    route_plan = router.to_route_plan(semantic)

    assert route_plan.query == query
    assert route_plan.metadata["original_query"] == query
    assert route_plan.metadata["retrieval_query"] == (
        "Annie Morton age born Terry Richardson age born older"
    )
    assert all(
        source.query
        == (
            query
            if source.source == "recent_messages"
            else "Annie Morton age born Terry Richardson age born older"
        )
        for source in route_plan.sources
        if source.enabled
    )


@pytest.mark.parametrize("query", ("Hello, how are you?", "Tell me a joke."))
def test_summary_routing_does_not_change_casual_messages(query: str) -> None:
    plan = SemanticRouter().route(query)

    assert plan.intents[0].intent == CASUAL_CHAT
    assert plan.retrieval_need == RETRIEVAL_NONE
    assert plan.enabled_sources == ("recent_messages",)
