from __future__ import annotations

from pathlib import Path

import pytest

from src.chat_service import ChatService
from src.core.contracts import SourcePlan
from src.database import Database, StoredMessage
from src.memory.chat_gist_summarizer import ChatGistSummary
from src.memory.previous_chat_gist import (
    DeterministicPreviousChatGistExtractor,
    PreviousChatGistGenerator,
)
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.routing.route_planner import RoutePlanner


class FakeModel:
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        return "fake response"


class FakePreviousGistExtractor:
    def summarize(self, messages: list[StoredMessage]) -> ChatGistSummary:
        return ChatGistSummary(
            summary=f"Previous chat covered {messages[0].content}",
            topics=["previous"],
            decisions=["Keep gists as episodic memory"],
            open_tasks=["Retrieve old summaries"],
        )


class EmptyPreviousGistExtractor:
    def summarize(self, messages: list[StoredMessage]) -> ChatGistSummary:
        del messages
        return ChatGistSummary(summary="")


class FailingGistInsertDatabase(Database):
    def insert_chat_gist(self, *args, **kwargs) -> int:  # type: ignore[no-untyped-def]
        raise RuntimeError("gist insert failed")


class FakePreviousGistGenerator:
    def __init__(self) -> None:
        self.calls: list[str | None] = []

    def generate_for_existing_chats(self, active_chat_id: str | None = None, limit: int = 50):
        del limit
        self.calls.append(active_chat_id)


def test_previous_chat_gist_generator_creates_gist_for_existing_chat(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat", title="Old chat")
    first_id = database.save_message("old-chat", "user", "mature libraries preference")
    second_id = database.save_message("old-chat", "assistant", "noted")
    database.mark_messages_summarized([first_id])

    result = PreviousChatGistGenerator(
        database=database,
        extractor=FakePreviousGistExtractor(),
        min_messages=2,
    ).generate_for_existing_chats()

    assert result.created_count == 1
    assert result.skipped_count == 0
    gist = database.chat_gist(result.gist_ids[0])
    assert gist is not None
    assert gist.chat_id == "old-chat"
    assert gist.source_type == "previous_chat_gist"
    assert gist.gist_text == "Previous chat covered mature libraries preference"
    assert gist.start_message_id == first_id
    assert gist.end_message_id == second_id
    assert database.chat_gists_for_chat("old-chat", "previous_chat_gist")
    messages = database.messages_for_chat("old-chat")
    assert [message.summarized for message in messages] == [True, False]
    assert all(message.gist_processed for message in messages)


def test_previous_chat_gist_generator_skips_active_and_existing_gists(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("active")
    database.save_message("active", "user", "active chat content")
    database.save_message("active", "assistant", "active answer")
    database.create_chat("old")
    database.save_message("old", "user", "old chat content")
    database.save_message("old", "assistant", "old answer")
    database.insert_chat_gist(
        chat_id="old",
        source_type="previous_chat_gist",
        gist_text="already summarized",
    )

    result = PreviousChatGistGenerator(
        database=database,
        extractor=FakePreviousGistExtractor(),
        min_messages=2,
    ).generate_for_existing_chats(active_chat_id="active")

    assert result.created_count == 0
    assert result.skipped_reasons["active"] == "active_chat"
    assert result.skipped_reasons["old"] == "already_has_previous_chat_gist"


def test_previous_chat_gist_retrieval_returns_memory_candidate(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat")
    database.save_message("old-chat", "user", "We discussed mature libraries.")
    database.save_message("old-chat", "assistant", "Acknowledged.")
    PreviousChatGistGenerator(
        database=database,
        extractor=FakePreviousGistExtractor(),
        min_messages=2,
    ).generate_for_existing_chats()

    candidates = PreviousChatGistRetriever(database).retrieve(
        chat_id="new-chat",
        source_plan=SourcePlan(
            source="previous_chat_gist",
            enabled=True,
            query="What did previous chat cover about mature libraries?",
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].source == "previous_chat_gist"
    assert candidates[0].chat_id == "old-chat"
    assert candidates[0].metadata["retrieval_mode"] == "stored_gist_placeholder"
    assert "Previous chat covered" in candidates[0].content


def test_route_planner_keeps_previous_chat_gist_disabled_by_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", raising=False)

    route_plan = RoutePlanner().plan("What did we say in previous chat?")
    source = next(source for source in route_plan.sources if source.source == "previous_chat_gist")

    assert source.enabled is False


def test_route_planner_can_enable_previous_chat_gist_with_config(monkeypatch) -> None:
    monkeypatch.setenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", "1")

    route_plan = RoutePlanner().plan("What did we say in previous chat?")
    source = next(source for source in route_plan.sources if source.source == "previous_chat_gist")

    assert source.enabled is True
    assert source.query == "what did we say in previous chat?"


def test_chat_service_runs_previous_gist_generation_only_when_enabled(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    generator = FakePreviousGistGenerator()
    service = ChatService(
        database=database,
        model=FakeModel(),
        raw_message_limit=8,
        memory_update_batch_size=6,
        previous_chat_gist_generation_enabled=True,
        previous_chat_gist_generator=generator,  # type: ignore[arg-type]
    )

    chat_id = service.start_chat("new-chat")

    assert chat_id == "new-chat"
    assert generator.calls == ["new-chat"]


def test_deterministic_previous_gist_extractor_requires_no_model() -> None:
    summary = DeterministicPreviousChatGistExtractor().summarize(
        [
            StoredMessage(
                id=1,
                chat_id="chat",
                role="user",
                content="I prefer mature open-source libraries.",
                created_at="now",
            ),
            StoredMessage(
                id=2,
                chat_id="chat",
                role="assistant",
                content="Noted.",
                created_at="now",
            ),
        ]
    )

    assert summary is not None
    assert "mature open-source libraries" in summary.summary
    assert summary.topics


def test_invalid_previous_gist_does_not_advance_gist_state(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat")
    database.save_message("old-chat", "user", "temporary")
    database.save_message("old-chat", "assistant", "ack")

    result = PreviousChatGistGenerator(
        database=database,
        extractor=EmptyPreviousGistExtractor(),
        min_messages=2,
    ).generate_for_existing_chats()

    assert result.created_count == 0
    assert database.chat_gists_for_chat("old-chat") == []
    assert all(
        not message.gist_processed
        for message in database.messages_for_chat("old-chat")
    )


def test_failed_previous_gist_insert_does_not_advance_gist_state(
    tmp_path: Path,
) -> None:
    database = FailingGistInsertDatabase(tmp_path / "chatbot.db")
    database.create_chat("old-chat")
    database.save_message("old-chat", "user", "durable discussion")
    database.save_message("old-chat", "assistant", "ack")

    with pytest.raises(RuntimeError, match="gist insert failed"):
        PreviousChatGistGenerator(
            database=database,
            extractor=FakePreviousGistExtractor(),
            min_messages=2,
        ).generate_for_existing_chats()

    assert all(
        not message.gist_processed
        for message in database.messages_for_chat("old-chat")
    )
