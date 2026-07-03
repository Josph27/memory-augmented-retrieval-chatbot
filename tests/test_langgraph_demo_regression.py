from __future__ import annotations

import json
from pathlib import Path

from src.actions.chat_end import ChatEndAction
from src.agents.context_manager_agent import ContextManagerAgent
from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database
from src.memory.short_term import ChatEndMemoryProcessingResult
from src.orchestration.demo_orchestration import run_read_only_langgraph_orchestration
from src.retrieval.current_chat_span_retriever import CurrentChatSpanRetriever
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.raw_message_span_retriever import RawMessageSpanRetriever
from src.retrieval.recent_messages_retriever import RecentMessagesRetriever
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever


class NoopChatEndMemory:
    def process_all_for_chat_end(self, chat_id: str) -> ChatEndMemoryProcessingResult:
        del chat_id
        return ChatEndMemoryProcessingResult(processed_message_count=0, batch_count=0)


class FixtureDocumentRetriever:
    def retrieve(
        self,
        chat_id: str,
        source_plan: SourcePlan,
    ) -> list[MemoryCandidate]:
        del chat_id, source_plan
        return [
            MemoryCandidate(
                source="document_memory",
                content="The uploaded release guide names Chroma as the document store.",
                record_id="release-guide:0",
                metadata={
                    "document_id": "release-guide",
                    "chunk_index": 0,
                    "file_name": "release-guide.md",
                    "retrieval_backend": "langchain_chroma",
                },
            )
        ]


def run_demo_query(
    database: Database,
    dispatcher: RetrieverDispatcher,
    query: str,
):  # type: ignore[no-untyped-def]
    return run_read_only_langgraph_orchestration(
        chat_id="chat-b",
        query=query,
        dispatcher=dispatcher,
        reranker=MemoryReranker(mode="deterministic"),
        context_manager=ContextManagerAgent(),
        system_prompt="Use typed evidence.",
    )


def test_compact_cross_chat_document_and_casual_demo_regression(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat-a")
    exact_id = database.save_message(
        "chat-a",
        "user",
        "Our exact project phrase is gist orients, span proves.",
    )
    database.save_message(
        "chat-a",
        "assistant",
        "The architecture decision was recorded.",
    )
    ChatEndAction(database, NoopChatEndMemory()).execute("chat-a")
    database.create_chat("chat-b")
    database.save_message("chat-b", "user", "Hello from the new chat.")
    database.upsert_chat_memory_state(
        "chat-b",
        json.dumps(
            {
                "memories": [
                    {
                        "id": "preferences:architecture",
                        "category": "preferences",
                        "key": "architecture",
                        "value": "Keep typed memory source semantics.",
                        "confidence": 0.95,
                        "status": "active",
                        "source_message_ids": [exact_id],
                    }
                ]
            }
        ),
    )
    dispatcher = RetrieverDispatcher(
        database,
        retrievers={
            "recent_messages": RecentMessagesRetriever(database),
            "structured_memory": StructuredMemoryRetriever(database),
            "document_memory": FixtureDocumentRetriever(),
            "current_chat_span": CurrentChatSpanRetriever(database),
            "previous_chat_gist": PreviousChatGistRetriever(database),
            "raw_message_span": RawMessageSpanRetriever(database),
        },
    )

    orientation = run_demo_query(
        database,
        dispatcher,
        "What did we discuss last time about the project phrase?",
    )
    exact = run_demo_query(
        database,
        dispatcher,
        "What exact phrase did I use in the previous chat about the project?",
    )
    document = run_demo_query(
        database,
        dispatcher,
        "According to the uploaded document, what is the document store?",
    )
    preference = run_demo_query(
        database,
        dispatcher,
        "What do I prefer for project architecture?",
    )
    casual = run_demo_query(database, dispatcher, "How are you?")

    orientation_raw = next(
        candidate
        for candidate in orientation.context_packet.candidates
        if candidate.source == "raw_message_span"
    )
    assert "gist orients, span proves" in orientation_raw.content
    orientation_parent_id = orientation_raw.metadata["parent_gist_id"]
    assert orientation_parent_id is not None
    assert any(
        item["record_id"] == orientation_parent_id
        and item["reason"] == "folded_into_raw_child"
        for item in orientation.context_packet.metadata["dropped_candidates"]
    )
    raw = next(
        candidate
        for candidate in exact.context_packet.candidates
        if candidate.source == "raw_message_span"
    )
    assert exact_id in raw.source_message_ids
    assert "gist orients, span proves" in raw.content
    assert raw.metadata["parent_gist_id"] is not None
    assert any(
        candidate.source == "document_memory"
        and "Chroma" in candidate.content
        for candidate in document.context_packet.candidates
    )
    assert any(
        candidate.source == "structured_memory"
        and "typed memory source semantics" in candidate.content
        for candidate in preference.context_packet.candidates
    )
    assert casual.trace.metadata["langgraph"]["route_sources"] == ["recent_messages"]
    assert not {
        "previous_chat_gist",
        "raw_message_span",
        "current_chat_span",
        "document_memory",
    } & {
        candidate.source for candidate in casual.context_packet.candidates
    }
