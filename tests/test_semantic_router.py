from __future__ import annotations

import pytest

from src.routing.semantic_router import (
    CASUAL_CHAT,
    DOCUMENT_QA,
    EXACT_QUOTE,
    MEMORY_QA,
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


@pytest.mark.parametrize(
    "query",
    [
        "我原话怎么说的？",
        "我当时具体怎么说的？",
        "我用了什么措辞？",
        "能不能逐字引用我之前说的？",
    ],
)
def test_chinese_quote_paraphrases_require_raw_evidence(query: str) -> None:
    plan = SemanticRouter().route(query)

    assert plan.language == "zh"
    assert plan.intents[0].intent == EXACT_QUOTE
    assert plan.evidence_contract.requires_raw_span is True
    assert plan.evidence_contract.must_not_answer_from_gist_only is True
    assert "current_chat_span" in plan.enabled_sources
    assert "raw_message_span" in plan.enabled_sources


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
        source.limit == SEMANTIC_SOURCE_CANDIDATE_LIMIT
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


def test_previous_orientation_does_not_enable_direct_raw_span() -> None:
    plan = SemanticRouter().route("What did we discuss last time?")

    assert plan.enabled_sources == ("recent_messages", "previous_chat_gist")


def test_factual_memory_question_without_temporal_wording_is_not_casual() -> None:
    plan = SemanticRouter().route("Which framework did we choose for this project?")

    assert plan.intents[0].intent == MEMORY_QA
    assert plan.retrieval_need == RETRIEVAL_REQUIRED
    assert plan.memory_scope == "unknown"
    assert plan.enabled_sources == (
        "recent_messages",
        "structured_memory",
        "previous_chat_gist",
    )
    assert not {
        "current_chat_span",
        "raw_message_span",
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
