from __future__ import annotations

import pytest

from src.routing.semantic_router import (
    CASUAL_CHAT,
    DOCUMENT_QA,
    EXACT_QUOTE,
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
