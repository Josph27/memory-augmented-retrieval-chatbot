from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.core.contracts import (
    AgentTurnResult,
    ContextBudget,
    ContextPacket,
    MemoryCandidate,
    RoutePlan,
    SourcePlan,
    WorkflowTrace,
)
from src.database import Database
from src.inspection.answer_inspector import (
    build_answer_inspection,
    inspection_rows_for_ui,
    persist_answer_inspection,
)


def make_result(
    database: Database,
    *,
    chat_id: str = "chat",
    requested_mode: str = "langgraph_demo",
    effective_mode: str = "langgraph_demo",
    authoritative_context: str = "langgraph",
    fallback_used: bool = False,
    candidates: list[MemoryCandidate] | None = None,
) -> AgentTurnResult:
    selected = list(candidates or [])
    assistant_message_id = database.save_message(chat_id, "assistant", "Answer text")
    route = RoutePlan(
        query="question",
        intent="memory_recall",
        context_profile="memory_recall",
        sources=[SourcePlan(source=item.source) for item in selected],
    )
    packet = ContextPacket(
        chat_id=chat_id,
        candidates=selected,
        budget=ContextBudget(memory_tokens=8192),
        metadata={
            "estimated_prompt_tokens": 321,
            "evidence_contract_satisfied": True,
            "dropped_candidates": [
                {
                    "candidate_id": "raw:2",
                    "source": "raw_message_span",
                    "reason": "overlapping_selected_span",
                    "overlap_ratio": 0.8,
                }
            ],
        },
    )
    trace = WorkflowTrace(
        trace_id="trace-1",
        chat_id=chat_id,
        route_plan=route,
        retrieved_candidates=selected,
        ranked_candidates=selected,
        context_budget=packet.budget,
        context_packet=packet,
        metadata={
            "estimated_prompt_tokens": 321,
            "context_manager": {"selected_memory_tokens": 123},
            "orchestration": {
                "requested_mode": requested_mode,
                "effective_mode": effective_mode,
                "authoritative_context": authoritative_context,
                "fallback_used": fallback_used,
                "langgraph_trace": (
                    {"insufficient_evidence": False}
                    if authoritative_context == "langgraph"
                    else None
                ),
            },
        },
    )
    return AgentTurnResult(
        answer="Answer text",
        chat_id=chat_id,
        trace_id="trace-1",
        termination_reason="completed",
        trace=trace,
        assistant_message_id=assistant_message_id,
    )


def test_completed_graph_answer_persists_reloadable_read_only_inspection(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chat.db")
    database.create_chat("chat", title="Current")
    prior_user = database.save_message("chat", "user", "My project uses SQLite.")
    candidate = MemoryCandidate(
        source="current_chat_span",
        content="user: My project uses SQLite.",
        score=0.9,
        record_id="span-1",
        chat_id="chat",
        source_message_ids=[prior_user],
        metadata={"final_rank": 1, "retrieval_path": "direct_raw"},
    )
    result = make_result(database, candidates=[candidate])

    assert persist_answer_inspection(result, database) is True
    rows = inspection_rows_for_ui(database, "chat")

    assert len(rows) == 1
    assert rows[0]["answer_text"] == "Answer text"
    assert rows[0]["overview"] == {
        "requested_mode": "langgraph_demo",
        "effective_mode": "langgraph_demo",
        "authoritative_context": "langgraph",
        "graph_executed": True,
        "native_fallback_used": False,
        "route": ["current_chat_span"],
        "route_intent": "memory_recall",
        "context_profile": "memory_recall",
    }
    source = rows[0]["selected_sources"][0]
    assert source["source_label"] == "Current/recent chat message"
    assert source["source_chat_title"] == "Current"
    assert source["current_chat"] is True
    assert rows[0]["evidence_summary"]["selected_context_tokens"] == 123
    assert "system_prompt" not in json.dumps(rows[0])


def test_forced_graph_failure_reports_native_fallback_truthfully(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chat.db")
    database.create_chat("chat")
    result = make_result(
        database,
        effective_mode="native",
        authoritative_context="native",
        fallback_used=True,
    )

    payload = build_answer_inspection(result, database)

    assert payload["overview"]["graph_executed"] is True
    assert payload["overview"]["native_fallback_used"] is True
    assert payload["overview"]["authoritative_context"] == "native"


def test_document_inspection_enforces_chat_scope_and_reports_lifecycle(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chat.db")
    database.create_chat("chat")
    database.create_document_record("allowed", "report.pdf", status="Ready")
    database.update_document_status("allowed", "Ready", chunk_count=4)
    database.associate_document_with_chat("chat", "allowed")
    database.create_document_record("other", "private.pdf", status="Ready")
    allowed = MemoryCandidate(
        source="document_memory",
        content="The report states the scoped answer.",
        record_id="allowed:2",
        metadata={
            "document_id": "allowed",
            "chunk_id": "allowed:2",
            "chunk_index": 2,
        },
    )
    outside_scope = MemoryCandidate(
        source="document_memory",
        content="Unrelated private evidence.",
        record_id="other:1",
        metadata={"document_id": "other", "chunk_id": "other:1"},
    )
    result = make_result(database, candidates=[allowed, outside_scope])

    payload = build_answer_inspection(result, database)

    assert [item["document_id"] for item in payload["selected_sources"]] == ["allowed"]
    assert payload["documents"] == [
        {
            "document_id": "allowed",
            "filename": "report.pdf",
            "status": "Ready",
            "chunk_count": 4,
            "selected": True,
        }
    ]
    assert "private.pdf" not in json.dumps(payload)


def test_current_chat_evidence_cannot_expose_another_chat(tmp_path: Path) -> None:
    database = Database(tmp_path / "chat.db")
    database.create_chat("chat")
    database.create_chat("other")
    other_message_id = database.save_message("other", "user", "private")
    candidate = MemoryCandidate(
        source="current_chat_span",
        content="private",
        chat_id="other",
        source_message_ids=[other_message_id],
    )
    result = make_result(database, candidates=[candidate])

    payload = build_answer_inspection(result, database)

    assert payload["selected_sources"] == []
    assert "private" not in json.dumps(payload)


def test_cross_chat_raw_span_reports_prior_chat_and_message_provenance(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chat.db")
    database.create_chat("chat", title="Current")
    database.create_chat("prior", title="Prior research")
    prior_message_id = database.save_message("prior", "user", "Use SQLite.")
    candidate = MemoryCandidate(
        source="raw_message_span",
        content="user: Use SQLite.",
        chat_id="prior",
        source_message_ids=[prior_message_id],
    )
    result = make_result(database, candidates=[candidate])

    payload = build_answer_inspection(result, database)

    source = payload["selected_sources"][0]
    assert source["source_label"] == "Raw-message span"
    assert source["source_chat_title"] == "Prior research"
    assert source["message_ids"] == [prior_message_id]
    assert source["current_chat"] is False


def test_missing_diagnostics_and_serialization_failure_do_not_break_answer(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database = Database(tmp_path / "chat.db")
    database.create_chat("chat")
    result = make_result(database)
    payload = build_answer_inspection(result, database)
    assert payload["selected_sources"] == []

    def fail(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("disk unavailable")

    monkeypatch.setattr(database, "save_answer_inspection", fail)
    assert persist_answer_inspection(result, database) is False
    assert result.answer == "Answer text"


def test_fork_copies_inspection_to_remapped_assistant_message(tmp_path: Path) -> None:
    database = Database(tmp_path / "chat.db")
    database.create_chat("source")
    source_user_id = database.save_message("source", "user", "Question")
    candidate = MemoryCandidate(
        source="current_chat_span",
        content="Question",
        chat_id="source",
        source_message_ids=[source_user_id],
    )
    result = make_result(database, chat_id="source", candidates=[candidate])
    assert persist_answer_inspection(result, database)

    database.fork_chat("source", "fork")

    rows = inspection_rows_for_ui(database, "fork")
    assert len(rows) == 1
    assert rows[0]["chat_id"] == "fork"
    assert rows[0]["selected_sources"][0]["source_chat_id"] == "fork"
    assert rows[0]["assistant_message_id"] != result.assistant_message_id


def test_answer_inspection_schema_is_added_idempotently_to_old_database(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """
            CREATE TABLE chats (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

    first = Database(path)
    second = Database(path)

    assert first.answer_inspections_for_chat("missing") == []
    assert second.answer_inspections_for_chat("missing") == []
