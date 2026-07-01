from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from src.actions.chat_end import ChatEndAction
from src.database import Database
from src.memory.short_term import ChatEndMemoryProcessingResult
from src.orchestration.langgraph_memory_pipeline import (
    build_langgraph_memory_pipeline,
    run_langgraph_memory_pipeline,
)
from src.retrieval.current_chat_span_retriever import CurrentChatSpanRetriever
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.recent_messages_retriever import RecentMessagesRetriever
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.semantic_router import CASUAL_CHAT, EXACT_QUOTE, SemanticRouter


@dataclass
class NoopChatEndMemoryProcessor:
    """Avoid semantic writes while exercising the real chat-end gist lifecycle."""

    def process_all_for_chat_end(
        self,
        chat_id: str,
    ) -> ChatEndMemoryProcessingResult:
        del chat_id
        return ChatEndMemoryProcessingResult(
            processed_message_count=0,
            batch_count=0,
        )


def run_semantic_graph(
    *,
    database: Database,
    chat_id: str,
    query: str,
    retrievers: dict[str, object],
):  # type: ignore[no-untyped-def]
    dispatcher = RetrieverDispatcher(
        database,
        retrievers=retrievers,  # type: ignore[arg-type]
    )
    graph = build_langgraph_memory_pipeline(
        routing_agent=None,
        dispatcher=dispatcher,
        semantic_router=SemanticRouter(),
        use_semantic_router=True,
    )
    return run_langgraph_memory_pipeline(
        graph,
        run_id="semantic-router-v2-validation",
        chat_id=chat_id,
        user_query=query,
    )


@pytest.mark.parametrize(
    ("query", "exact_sentence"),
    [
        (
            "What exact phrase did I use about router principle?",
            "My router principle is: gist tells where to look, "
            "span proves exact content.",
        ),
        (
            "How did I phrase the memory rule?",
            "My memory rule is: preserve typed sources before combining evidence.",
        ),
        (
            "What were my exact words about gist and span?",
            "My exact words are: gist is orientation and span is evidence.",
        ),
        (
            "Can you quote my earlier message about context budget?",
            "My context budget rule is: drop older noise before newer evidence.",
        ),
    ],
)
def test_same_chat_quote_paraphrases_reach_exact_raw_span(
    tmp_path: Path,
    query: str,
    exact_sentence: str,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("active-chat")
    exact_id = database.save_message("active-chat", "user", exact_sentence)
    database.save_message("active-chat", "assistant", "Recorded.")
    for index in range(10):
        database.save_message(
            "active-chat",
            "user" if index % 2 == 0 else "assistant",
            f"Later neutral filler turn {index}.",
        )

    before_messages = database.messages_for_chat("active-chat")
    state = run_semantic_graph(
        database=database,
        chat_id="active-chat",
        query=query,
        retrievers={
            "recent_messages": RecentMessagesRetriever(database, default_limit=8),
            "current_chat_span": CurrentChatSpanRetriever(database),
        },
    )

    semantic_plan = state["semantic_route_plan"]
    assert semantic_plan.intents[0].intent == EXACT_QUOTE
    assert semantic_plan.evidence_contract.requires_raw_span is True
    assert "current_chat_span" in semantic_plan.enabled_sources
    recent_contents = [
        candidate.content
        for candidate in state["candidates"]
        if candidate.source == "recent_messages"
    ]
    assert all(exact_sentence not in content for content in recent_contents)

    raw_span = next(
        candidate
        for candidate in state["context_packet"].candidates
        if candidate.source == "current_chat_span"
        and exact_sentence in candidate.content
    )
    assert raw_span.chat_id == "active-chat"
    assert exact_id in raw_span.source_message_ids
    assert state["insufficient_evidence"] is False
    assert state["mock_answer"].startswith("MOCK ANSWER:")

    generated_queries = {
        item.text
        for item in semantic_plan.retrieval_queries
        if item.is_generated
    }
    assert generated_queries
    assert all(
        candidate.content not in generated_queries
        for candidate in state["context_packet"].candidates
    )
    assert database.messages_for_chat("active-chat") == before_messages


def test_previous_chat_quote_expands_finalized_gist_to_raw_span(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("ended-chat")
    exact_sentence = (
        "My previous router principle is: preserve provenance before compression."
    )
    first_id = database.save_message("ended-chat", "user", exact_sentence)
    second_id = database.save_message("ended-chat", "assistant", "Recorded.")

    end_result = ChatEndAction(
        database,
        NoopChatEndMemoryProcessor(),
    ).execute("ended-chat")
    gists = database.chat_gists_for_chat("ended-chat", "previous_chat_gist")
    assert end_result.gist_count == 1
    assert len(gists) == 1

    database.create_chat("current-chat")
    query = "What exact phrase did I use about my previous router principle?"
    state = run_semantic_graph(
        database=database,
        chat_id="current-chat",
        query=query,
        retrievers={
            "previous_chat_gist": PreviousChatGistRetriever(database),
        },
    )

    assert state["semantic_route_plan"].intents[0].intent == EXACT_QUOTE
    assert any(
        candidate.source == "previous_chat_gist"
        for candidate in state["candidates"]
    )
    raw_span = next(
        candidate
        for candidate in state["context_packet"].candidates
        if candidate.source == "raw_message_span"
    )
    assert exact_sentence in raw_span.content
    assert raw_span.source_message_ids == [first_id, second_id]
    assert raw_span.metadata["parent_gist_id"] == gists[0].id
    assert raw_span.metadata["parent_source"] == "previous_chat_gist"
    assert state["insufficient_evidence"] is False


def test_gist_only_quote_fails_closed_through_semantic_graph(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("ended-chat")
    database.insert_chat_gist(
        chat_id="ended-chat",
        source_type="previous_chat_gist",
        gist_text="Context budget wording was discussed.",
    )

    state = run_semantic_graph(
        database=database,
        chat_id="current-chat",
        query="Can you quote my earlier message about context budget?",
        retrievers={
            "previous_chat_gist": PreviousChatGistRetriever(database),
        },
    )

    assert state["evidence_contract"].requires_raw_span is True
    assert state["trace"]["context_sources"] == ["previous_chat_gist"]
    assert state["insufficient_evidence"] is True
    assert state["mock_answer"].startswith("MOCK INSUFFICIENT EVIDENCE:")
    assert "raw span evidence required" in state["mock_answer"]
    assert "mock_answer" not in state["visited_nodes"]


def test_casual_chat_uses_only_recent_messages_in_semantic_graph(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("active-chat")
    database.save_message("active-chat", "assistant", "Hello.")

    state = run_semantic_graph(
        database=database,
        chat_id="active-chat",
        query="How are you?",
        retrievers={
            "recent_messages": RecentMessagesRetriever(database),
            "current_chat_span": CurrentChatSpanRetriever(database),
        },
    )

    semantic_plan = state["semantic_route_plan"]
    assert semantic_plan.intents[0].intent == CASUAL_CHAT
    assert semantic_plan.enabled_sources == ("recent_messages",)
    assert state["trace"]["route_sources"] == ["recent_messages"]
    assert "current_chat_span" not in state["trace"]["route_sources"]
    assert "raw_message_span" not in state["trace"]["route_sources"]
    assert "document_memory" not in state["trace"]["route_sources"]
    assert state["insufficient_evidence"] is False
    assert state["mock_answer"].startswith("MOCK ANSWER:")

