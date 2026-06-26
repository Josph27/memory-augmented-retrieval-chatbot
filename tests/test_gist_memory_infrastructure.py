from __future__ import annotations

from pathlib import Path
from typing import get_args

from src.core.contracts import MemoryCandidate, MemorySourceType, SourcePlan
from src.database import Database
from src.retrieval.current_chat_gist_retriever import CurrentChatGistRetriever
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.raw_message_span_retriever import (
    RawMessageSpanRetriever,
    source_plan_for_gist_candidate,
)


def test_memory_source_labels_include_gist_sources() -> None:
    labels = set(get_args(MemorySourceType))

    assert {
        "recent_messages",
        "structured_memory",
        "document_memory",
        "current_chat_gist",
        "previous_chat_gist",
        "raw_message_span",
    } <= labels
    assert "current_chat_chunks" in labels
    assert "previous_chat_memory" in labels

    candidate = MemoryCandidate(source="current_chat_gist", content="gist")
    assert candidate.source == "current_chat_gist"


def test_insert_and_read_chat_gists(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat-1")
    gist_id = db.insert_chat_gist(
        chat_id="chat-1",
        source_type="current_chat_gist",
        gist_text="The user chose SQLite for the MVP.",
        topics=["database"],
        decisions=["Use SQLite"],
        open_tasks=["Add upload flow"],
        start_message_id=1,
        end_message_id=4,
        metadata={"status": "active"},
    )

    gist = db.chat_gist(gist_id)
    assert gist is not None
    assert gist.source_type == "current_chat_gist"
    assert gist.gist_text == "The user chose SQLite for the MVP."
    assert gist.start_message_id == 1
    assert gist.end_message_id == 4

    by_chat = db.chat_gists_for_chat("chat-1")
    by_source = db.chat_gists_by_source_type("current_chat_gist")
    assert [item.id for item in by_chat] == [gist_id]
    assert [item.id for item in by_source] == [gist_id]


def test_fetch_raw_messages_by_message_id_span(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat-1")
    first_id = db.save_message("chat-1", "user", "first")
    second_id = db.save_message("chat-1", "assistant", "second")
    third_id = db.save_message("chat-1", "user", "third")

    span = db.messages_for_chat_span(
        chat_id="chat-1",
        start_message_id=first_id,
        end_message_id=second_id,
    )

    assert [message.id for message in span] == [first_id, second_id]
    assert [message.content for message in span] == ["first", "second"]
    assert third_id not in {message.id for message in span}


def test_gist_retrievers_return_empty_when_no_gists_exist(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat-1")

    current = CurrentChatGistRetriever(db).retrieve(
        chat_id="chat-1",
        source_plan=SourcePlan(source="current_chat_gist", enabled=True),
    )
    previous = PreviousChatGistRetriever(db).retrieve(
        chat_id="chat-1",
        source_plan=SourcePlan(source="previous_chat_gist", enabled=True),
    )

    assert current == []
    assert previous == []


def test_current_chat_gist_retriever_returns_candidate_metadata(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat-1")
    first_id = db.save_message("chat-1", "user", "Use SQLite.")
    second_id = db.save_message("chat-1", "assistant", "Acknowledged.")
    gist_id = db.insert_chat_gist(
        chat_id="chat-1",
        source_type="current_chat_gist",
        gist_text="The current chat decided to use SQLite.",
        topics=["database"],
        decisions=["Use SQLite"],
        start_message_id=first_id,
        end_message_id=second_id,
    )

    candidates = CurrentChatGistRetriever(db).retrieve(
        chat_id="chat-1",
        source_plan=SourcePlan(
            source="current_chat_gist",
            enabled=True,
            query="Which database did we decide to use?",
        ),
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source == "current_chat_gist"
    assert candidate.record_id == gist_id
    assert candidate.content == "The current chat decided to use SQLite."
    assert candidate.source_message_ids == [first_id, second_id]
    assert candidate.metadata["topics"] == ["database"]
    assert candidate.metadata["decisions"] == ["Use SQLite"]
    assert candidate.metadata["retrieval_mode"] == "stored_gist_placeholder"


def test_previous_chat_gist_retriever_reads_by_source_type(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("old-chat")
    db.insert_chat_gist(
        chat_id="old-chat",
        source_type="previous_chat_gist",
        gist_text="An older chat discussed document chunking.",
        topics=["documents"],
    )

    candidates = PreviousChatGistRetriever(db).retrieve(
        chat_id="new-chat",
        source_plan=SourcePlan(
            source="previous_chat_gist",
            enabled=True,
            query="What did older chats say about document chunking?",
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].source == "previous_chat_gist"
    assert candidates[0].chat_id == "old-chat"
    assert candidates[0].metadata["topics"] == ["documents"]


def test_raw_message_span_retriever_returns_source_messages_from_gist_span(
    tmp_path: Path,
) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat-1")
    first_id = db.save_message("chat-1", "user", "My project uses Chainlit.")
    second_id = db.save_message("chat-1", "assistant", "Noted.")
    gist_id = db.insert_chat_gist(
        chat_id="chat-1",
        source_type="current_chat_gist",
        gist_text="The project uses Chainlit.",
        start_message_id=first_id,
        end_message_id=second_id,
    )

    candidates = RawMessageSpanRetriever(db).retrieve(
        chat_id="chat-1",
        source_plan=SourcePlan(
            source="raw_message_span",
            enabled=True,
            filters={"gist_id": gist_id},
        ),
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.source == "raw_message_span"
    assert "user: My project uses Chainlit." in candidate.content
    assert "assistant: Noted." in candidate.content
    assert candidate.source_message_ids == [first_id, second_id]
    assert candidate.metadata["source_chat_id"] == "chat-1"
    assert candidate.metadata["gist_id"] == gist_id
    assert candidate.metadata["truncated"] is False


def test_raw_message_span_retriever_accepts_direct_span_filters(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat-1")
    first_id = db.save_message("chat-1", "user", "alpha")
    second_id = db.save_message("chat-1", "assistant", "beta")

    candidates = RawMessageSpanRetriever(db).retrieve(
        chat_id="chat-1",
        source_plan=SourcePlan(
            source="raw_message_span",
            enabled=True,
            filters={
                "start_message_id": first_id,
                "end_message_id": second_id,
            },
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].source_message_ids == [first_id, second_id]
    assert candidates[0].content == "user: alpha\nassistant: beta"


def test_raw_message_span_retriever_accepts_alias_span_filters(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat-1")
    first_id = db.save_message("chat-1", "user", "alpha")
    second_id = db.save_message("chat-1", "assistant", "beta")

    candidates = RawMessageSpanRetriever(db).retrieve(
        chat_id="ignored-current-chat",
        source_plan=SourcePlan(
            source="raw_message_span",
            enabled=True,
            filters={
                "chat_id": "chat-1",
                "message_start_id": first_id,
                "message_end_id": second_id,
            },
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].chat_id == "chat-1"
    assert candidates[0].source_message_ids == [first_id, second_id]


def test_raw_message_span_retriever_truncates_long_spans(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("chat-1")
    first_id = db.save_message("chat-1", "user", "alpha " * 20)
    second_id = db.save_message("chat-1", "assistant", "beta " * 20)

    candidates = RawMessageSpanRetriever(db, max_chars=60).retrieve(
        chat_id="chat-1",
        source_plan=SourcePlan(
            source="raw_message_span",
            enabled=True,
            filters={
                "start_message_id": first_id,
                "end_message_id": second_id,
            },
        ),
    )

    assert len(candidates) == 1
    assert len(candidates[0].content) <= 60
    assert "raw message span truncated" in candidates[0].content
    assert candidates[0].metadata["truncated"] is True


def test_raw_message_span_plan_can_be_derived_from_gist_candidate(tmp_path: Path) -> None:
    db = Database(tmp_path / "chatbot.db")
    db.create_chat("old-chat")
    first_id = db.save_message("old-chat", "user", "Use mature libraries.")
    second_id = db.save_message("old-chat", "assistant", "Noted.")
    gist_id = db.insert_chat_gist(
        chat_id="old-chat",
        source_type="previous_chat_gist",
        gist_text="The user prefers mature libraries.",
        start_message_id=first_id,
        end_message_id=second_id,
    )

    gist_candidates = PreviousChatGistRetriever(db).retrieve(
        chat_id="new-chat",
        source_plan=SourcePlan(
            source="previous_chat_gist",
            enabled=True,
            query="What mature libraries preference appeared before?",
        ),
    )
    span_plan = source_plan_for_gist_candidate(gist_candidates[0])

    assert span_plan is not None
    assert span_plan.source == "raw_message_span"
    assert span_plan.filters == {"gist_id": gist_id}

    raw_candidates = RawMessageSpanRetriever(db).retrieve(
        chat_id="new-chat",
        source_plan=span_plan,
    )
    assert raw_candidates[0].source == "raw_message_span"
    assert raw_candidates[0].metadata["gist_id"] == gist_id
    assert "user: Use mature libraries." in raw_candidates[0].content
