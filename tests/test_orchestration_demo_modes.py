from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import src.agents.coordinator_agent as coordinator_module
from src.agents.context_manager_agent import ContextManagerAgent
from src.chat_service import ChatService
from src.database import Database
from src.orchestration.demo_orchestration import (
    LANGGRAPH_DEMO,
    LANGGRAPH_SHADOW,
    NATIVE,
    run_read_only_langgraph_orchestration,
)
from src.retrieval.reranker import MemoryReranker


class RecordingModel:
    def __init__(self) -> None:
        self.calls: list[list[dict[str, str]]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del temperature
        self.calls.append([dict(message) for message in messages])
        return "recorded answer"


def build_service(tmp_path: Path) -> tuple[Database, RecordingModel, ChatService]:
    database = Database(tmp_path / "chatbot.db")
    model = RecordingModel()
    service = ChatService(
        database=database,
        model=model,  # type: ignore[arg-type]
        raw_message_limit=4,
        memory_update_batch_size=50,
    )
    return database, model, service


def database_snapshot(path: Path) -> dict[str, list[tuple]]:
    with sqlite3.connect(path) as connection:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name != 'sqlite_sequence' "
                "ORDER BY name"
            ).fetchall()
        ]
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
            for table in tables
        }


def test_native_remains_default_and_does_not_run_graph(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database, _model, service = build_service(tmp_path)
    chat_id = service.start_chat("native-chat")

    def fail_graph(**kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        raise AssertionError("default native mode must not run LangGraph")

    monkeypatch.setattr(coordinator_module, "run_read_only_langgraph_orchestration", fail_graph)

    result = service.handle_user_turn(chat_id, "How are you?")

    assert result.answer == "recorded answer"
    assert result.trace.metadata["orchestration"]["requested_mode"] == NATIVE
    assert database.message_count(chat_id) == 2


def test_langgraph_demo_context_packet_is_used_for_model_answer(tmp_path: Path) -> None:
    database, model, service = build_service(tmp_path)
    chat_id = service.start_chat("graph-chat")
    target_id = database.save_message(
        chat_id,
        "user",
        "My exact router phrase is span proves exact content.",
    )
    database.save_message(chat_id, "assistant", "Recorded.")

    result = service.handle_user_turn(
        chat_id,
        "What exact phrase did I use earlier in this chat about router?",
        orchestration_mode=LANGGRAPH_DEMO,
    )

    orchestration = result.trace.metadata["orchestration"]
    assert orchestration["requested_mode"] == LANGGRAPH_DEMO
    assert orchestration["authoritative_context"] == "langgraph"
    assert orchestration["fallback_used"] is False
    assert model.calls[-1] == result.trace.context_packet.model_messages
    span = next(
        candidate
        for candidate in result.trace.context_packet.candidates
        if candidate.source == "current_chat_span"
    )
    assert target_id in span.source_message_ids


def test_langgraph_shadow_keeps_native_context_authoritative(tmp_path: Path) -> None:
    _database, model, service = build_service(tmp_path)
    chat_id = service.start_chat("shadow-chat")

    result = service.handle_user_turn(
        chat_id,
        "How are you?",
        orchestration_mode=LANGGRAPH_SHADOW,
    )

    orchestration = result.trace.metadata["orchestration"]
    assert orchestration["requested_mode"] == LANGGRAPH_SHADOW
    assert orchestration["authoritative_context"] == "native"
    assert orchestration["comparison"] is not None
    assert orchestration["langgraph_trace"] is not None
    assert model.calls[-1] == result.trace.context_packet.model_messages


def test_langgraph_demo_failure_visibly_falls_back_to_native(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _database, model, service = build_service(tmp_path)
    chat_id = service.start_chat("fallback-chat")

    def broken_graph(**kwargs):  # type: ignore[no-untyped-def]
        del kwargs
        raise RuntimeError("graph unavailable")

    monkeypatch.setattr(
        coordinator_module,
        "run_read_only_langgraph_orchestration",
        broken_graph,
    )

    result = service.handle_user_turn(
        chat_id,
        "How are you?",
        orchestration_mode=LANGGRAPH_DEMO,
    )

    orchestration = result.trace.metadata["orchestration"]
    assert orchestration["effective_mode"] == NATIVE
    assert orchestration["fallback_used"] is True
    assert orchestration["error"] == "RuntimeError: graph unavailable"
    assert model.calls[-1] == result.trace.context_packet.model_messages


def test_direct_langgraph_execution_is_read_only_for_all_sqlite_tables(
    tmp_path: Path,
) -> None:
    database, _model, service = build_service(tmp_path)
    chat_id = service.start_chat("read-only-chat")
    database.save_message(chat_id, "user", "The exact phrase is preserve provenance.")
    database.save_message(chat_id, "assistant", "Recorded.")
    before = database_snapshot(database.path)

    result = run_read_only_langgraph_orchestration(
        chat_id=chat_id,
        query="What exact phrase did I use earlier in this chat?",
        dispatcher=service.coordinator.retriever_dispatcher,
        reranker=MemoryReranker(mode="deterministic"),
        context_manager=ContextManagerAgent(),
        system_prompt=service.coordinator.system_prompt,
    )

    assert result.context_packet.candidates
    assert database_snapshot(database.path) == before
    assert result.trace.metadata["langgraph"]["provenance_valid"] is True
