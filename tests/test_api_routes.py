from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src import api_routes
from src.database import Database
from src.memory.previous_chat_gist import PreviousChatGistFinalizationResult
from src.memory.short_term import ChatEndMemoryProcessingResult


class RecordingMemory:
    def __init__(self, failure: Exception | None = None) -> None:
        self.failure = failure
        self.chat_ids: list[str] = []

    def process_all_for_chat_end(self, chat_id: str) -> ChatEndMemoryProcessingResult:
        self.chat_ids.append(chat_id)
        if self.failure is not None:
            raise self.failure
        return ChatEndMemoryProcessingResult(processed_message_count=2, batch_count=1)


class RecordingGistFinalizer:
    def __init__(self) -> None:
        self.chat_ids: list[str] = []

    def finalize_chat(self, chat_id: str) -> PreviousChatGistFinalizationResult:
        self.chat_ids.append(chat_id)
        return PreviousChatGistFinalizationResult(1, 2, 1)


def register_routes(
    monkeypatch,
    database: Database,
    resolver: Callable[[], Any],
    chat_resolver: Callable[[str], Any] | None = None,
) -> TestClient:
    app = FastAPI()
    monkeypatch.setattr(api_routes.cl, "server", SimpleNamespace(app=app), raising=False)
    api_routes.register_api_routes(
        database,
        resolver,
        chat_service_for_chat_getter=chat_resolver,
    )
    return TestClient(app)


def test_rest_end_uses_chat_specific_service_and_canonical_finalizer(
    tmp_path,
    monkeypatch,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("historic", model_name="historic-model")
    memory = RecordingMemory()
    gist = RecordingGistFinalizer()
    resolved_chat_ids: list[str] = []

    def resolver() -> Any:
        raise AssertionError("REST End must not use the default service resolver")

    def chat_resolver(chat_id: str) -> Any:
        resolved_chat_ids.append(chat_id)
        return SimpleNamespace(
            memory=memory,
            build_previous_chat_gist_generator=lambda: gist,
        )

    client = register_routes(monkeypatch, database, resolver, chat_resolver)
    response = client.post("/api/chats/historic/end")

    assert response.status_code == 200
    assert response.json() == {"status": "ended"}
    assert resolved_chat_ids == ["historic"]
    assert memory.chat_ids == ["historic"]
    assert gist.chat_ids == ["historic"]
    assert database.is_chat_active("historic") is False


def test_rest_end_keeps_chat_active_and_returns_500_when_finalization_fails(
    tmp_path,
    monkeypatch,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    memory = RecordingMemory(RuntimeError("memory flush failed"))
    gist = RecordingGistFinalizer()

    client = register_routes(
        monkeypatch,
        database,
        lambda: SimpleNamespace(memory=object()),
        lambda chat_id: SimpleNamespace(
            memory=memory,
            build_previous_chat_gist_generator=lambda: gist,
        ),
    )
    response = client.post("/api/chats/chat/end")

    assert response.status_code == 500
    assert response.json() == {"error": "memory flush failed"}
    assert memory.chat_ids == ["chat"]
    assert gist.chat_ids == []
    assert database.is_chat_active("chat") is True


def test_rest_end_returns_404_without_resolving_a_service(tmp_path, monkeypatch) -> None:
    database = Database(tmp_path / "chatbot.db")

    def unexpected_resolver(*args: object) -> Any:
        raise AssertionError("unknown chat must not resolve a service")

    client = register_routes(monkeypatch, database, unexpected_resolver, unexpected_resolver)
    response = client.post("/api/chats/missing/end")

    assert response.status_code == 404
    assert response.json() == {"error": "not found"}


def test_rest_end_uses_legacy_default_service_and_deterministic_gist_when_unconfigured(
    tmp_path,
    monkeypatch,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    memory = RecordingMemory()
    resolver_calls = 0

    def resolver() -> Any:
        nonlocal resolver_calls
        resolver_calls += 1
        return SimpleNamespace(memory=memory)

    client = register_routes(monkeypatch, database, resolver)
    response = client.post("/api/chats/chat/end")

    assert response.status_code == 200
    assert response.json() == {"status": "ended"}
    assert resolver_calls == 1
    assert memory.chat_ids == ["chat"]
    assert database.is_chat_active("chat") is False
