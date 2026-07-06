"""Chainlit entrypoint for browser E2E tests with deterministic local backends."""

from __future__ import annotations

import app as production_app
import json
import os
from pathlib import Path

from src.chat_service import ChatService
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
                stream.write(json.dumps({"document_statuses": statuses}) + "\n")
        return f"Deterministic answer: {latest}"


class DeterministicBrowserIndexer:
    def index_text_document(self, title, text, source="manual", metadata=None):  # type: ignore[no-untyped-def]
        del title, source
        values = dict(metadata or {})
        return {
            "document_id": values["document_id"],
            "chunk_count": 1 if text else 0,
        }


class DeterministicBrowserMemoryUpdater:
    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        del messages
        return MemoryUpdateResult(
            memory_state=existing_memory,
            accepted=True,
        )


_services: dict[str, ChatService] = {}


def deterministic_chat_service(model_name: str) -> ChatService:
    if model_name not in _services:
        service = ChatService(
            database=production_app.database,
            model=DeterministicBrowserModel(),
            raw_message_limit=8,
            memory_update_batch_size=6,
            document_indexer=DeterministicBrowserIndexer(),
        )
        service.memory.structured_memory = DeterministicBrowserMemoryUpdater()
        _services[model_name] = service
    return _services[model_name]


production_app.chat_services.clear()
production_app.chat_service_for_model = deterministic_chat_service
