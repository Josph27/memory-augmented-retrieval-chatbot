"""Chainlit entrypoint for browser E2E tests with deterministic local backends."""

from __future__ import annotations

import app as production_app
import json
import os
from pathlib import Path

import src.agents.coordinator_agent as coordinator_module
from src.chat_service import ChatService
from src.core.contracts import MemoryCandidate
from src.memory.structured_state import MemoryUpdateResult


class DeterministicBrowserModel:
    model_name = "product-behavior-browser"

    def chat(self, messages, temperature=None):  # type: ignore[no-untyped-def]
        del temperature
        latest = next(
            (
                message.get("content", "")
                for message in reversed(messages)
                if message.get("role") == "user"
            ),
            "",
        )
        event_path = os.getenv("PRODUCT_BEHAVIOR_MODEL_EVENT_PATH")
        if event_path:
            statuses = []
            with production_app.database.connect() as connection:
                statuses = [
                    str(row["status"])
                    for row in connection.execute(
                        "SELECT status FROM document_records ORDER BY id"
                    ).fetchall()
                ]
            with Path(event_path).open("a", encoding="utf-8") as stream:
                stream.write(
                    json.dumps(
                        {
                            "document_statuses": statuses,
                            "prompt": "\n".join(
                                str(message.get("content", ""))
                                for message in messages
                            ),
                        }
                    )
                    + "\n"
                )
        return f"Deterministic answer: {visible_question_from_prompt(latest)}"


def visible_question_from_prompt(content: str) -> str:
    """Return the user question from the rendered ContextPacket prompt."""
    marker = "[Question]"
    if marker not in content:
        return content
    return content.rsplit(marker, maxsplit=1)[-1].strip()


class DeterministicBrowserIndexer:
    def __init__(self) -> None:
        self.documents: dict[str, str] = {}

    def index_text_document(self, title, text, source="manual", metadata=None):  # type: ignore[no-untyped-def]
        del title, source
        values = dict(metadata or {})
        self.documents[str(values["document_id"])] = str(text)
        return {
            "document_id": values["document_id"],
            "chunk_count": 1 if text else 0,
        }


class DeterministicBrowserDocumentRetriever:
    def __init__(self, indexer: DeterministicBrowserIndexer) -> None:
        self.indexer = indexer

    def retrieve(self, chat_id, source_plan):  # type: ignore[no-untyped-def]
        del chat_id
        return [
            MemoryCandidate(
                source="document_memory",
                content=self.indexer.documents[document_id],
                record_id=f"{document_id}:0",
                metadata={
                    "document_id": document_id,
                    "retrieval_path": "deterministic_browser_fixture",
                },
            )
            for document_id in source_plan.filters.get("allowed_document_ids", [])
            if document_id in self.indexer.documents
        ]


class DeterministicBrowserMemoryUpdater:
    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        del messages
        return MemoryUpdateResult(
            memory_state=existing_memory,
            accepted=True,
        )


class DeterministicBrowserCrossChatRetriever:
    def __init__(self, original) -> None:  # type: ignore[no-untyped-def]
        self.original = original

    def retrieve(self, chat_id, source_plan):  # type: ignore[no-untyped-def]
        query = str(source_plan.query or "").lower()
        if "cross-chat inspector source" not in query:
            return self.original.retrieve(chat_id=chat_id, source_plan=source_plan)
        source_messages = production_app.database.messages_for_chat("ended-a")
        source = next(message for message in source_messages if message.role == "assistant")
        return [
            MemoryCandidate(
                source="raw_message_span",
                content=source.content,
                score=0.95,
                record_id="browser-cross-chat-memory",
                chat_id="ended-a",
                source_message_ids=[source.id],
                metadata={"source_chat_id": "ended-a"},
            )
        ]


_services: dict[str, ChatService] = {}
_real_langgraph_orchestration = coordinator_module.run_read_only_langgraph_orchestration


def deterministic_langgraph_orchestration(**kwargs):  # type: ignore[no-untyped-def]
    """Allow one explicit browser fixture to exercise truthful Native fallback."""
    if kwargs.get("query") == "Force the local graph fallback":
        raise RuntimeError("forced local browser graph failure")
    return _real_langgraph_orchestration(**kwargs)


coordinator_module.run_read_only_langgraph_orchestration = (
    deterministic_langgraph_orchestration
)


def deterministic_chat_service(model_name: str) -> ChatService:
    if model_name not in _services:
        indexer = DeterministicBrowserIndexer()
        service = ChatService(
            database=production_app.database,
            model=DeterministicBrowserModel(),
            raw_message_limit=8,
            memory_update_batch_size=6,
            document_indexer=indexer,
        )
        service.memory.structured_memory = DeterministicBrowserMemoryUpdater()
        service.coordinator.retriever_dispatcher.retrievers["document_memory"] = (
            DeterministicBrowserDocumentRetriever(indexer)
        )
        dispatcher = service.coordinator.retriever_dispatcher
        dispatcher.retrievers["raw_message_span"] = (
            DeterministicBrowserCrossChatRetriever(
                dispatcher.retrievers["raw_message_span"]
            )
        )
        _services[model_name] = service
    return _services[model_name]


production_app.chat_services.clear()
production_app.chat_service_for_model = deterministic_chat_service
