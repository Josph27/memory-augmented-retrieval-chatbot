from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.chat_service import ChatService
from src.core.contracts import SourcePlan
from src.database import Database, StoredMessage
from src.memory.chat_gist_summarizer import ChatGistSummary
from src.memory.previous_chat_gist import (
    DeterministicPreviousChatGistExtractor,
    FallbackChatGistExtractor,
    PreviousChatGistGenerator,
)
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.routing.route_planner import RoutePlanner


class FakeModel:
    def __init__(self, response: str = "fake response") -> None:
        self.response = response
        self.calls: list[list[dict[str, str]]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del temperature
        self.calls.append(messages)
        return self.response


class RaisingModel:
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        raise RuntimeError("gist endpoint unavailable")


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


class FailingPreviousGistExtractor:
    def summarize(self, messages: list[StoredMessage]) -> ChatGistSummary:
        del messages
        raise RuntimeError("gist endpoint unavailable")


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


def test_global_summary_gist_retrieval_exposes_complete_chronology(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    for index in range(5):
        chat_id = f"history-{index}"
        database.create_chat(chat_id)
        message_id = database.save_message(
            chat_id,
            "user",
            f"Chronological gist source {index}.",
        )
        database.insert_chat_gist(
            chat_id=chat_id,
            source_type="previous_chat_gist",
            gist_text=f"Chronological gist {index}.",
            start_message_id=message_id,
            end_message_id=message_id,
        )

    candidates = PreviousChatGistRetriever(database).retrieve(
        chat_id="new-chat",
        source_plan=SourcePlan(
            source="previous_chat_gist",
            enabled=True,
            query="global summary complete previous content",
            limit=2,
            filters={"context_profile": "global_summary"},
        ),
    )

    assert len(candidates) == 5
    assert [candidate.content for candidate in candidates] == [
        f"Chronological gist {index}." for index in range(5)
    ]


def test_route_planner_enables_previous_chat_gist_by_default_for_previous_intent(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", raising=False)

    route_plan = RoutePlanner().plan("What did we say in previous chat?")
    source = next(source for source in route_plan.sources if source.source == "previous_chat_gist")

    assert source.enabled is True
    assert source.query == "what did we say in previous chat?"


def test_route_planner_emergency_gate_can_disable_previous_chat_gist(monkeypatch) -> None:
    monkeypatch.setenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", "0")

    route_plan = RoutePlanner().plan("What did we say in previous chat?")
    source = next(source for source in route_plan.sources if source.source == "previous_chat_gist")

    assert source.enabled is False


@pytest.mark.parametrize(
    "query",
    [
        "How are you?",
        "What is the capital of France?",
    ],
)
def test_route_planner_does_not_enable_previous_gist_for_unrelated_queries(
    monkeypatch,
    query: str,
) -> None:
    monkeypatch.delenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", raising=False)

    route_plan = RoutePlanner().plan(query)

    assert not next(
        source.enabled
        for source in route_plan.sources
        if source.source == "previous_chat_gist"
    )


def test_previous_chat_exact_quote_reserves_gist_and_raw_span(monkeypatch) -> None:
    monkeypatch.delenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", raising=False)

    route_plan = RoutePlanner().plan(
        "What exact phrase did I use in the previous chat about deployment?"
    )
    enabled = {source.source for source in route_plan.sources if source.enabled}

    assert {"previous_chat_gist", "raw_message_span"} <= enabled
    assert route_plan.metadata["requires_raw_span"] is True


def test_same_chat_recall_keeps_current_chat_span_without_previous_gist(
    monkeypatch,
) -> None:
    monkeypatch.delenv("PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", raising=False)

    route_plan = RoutePlanner().plan(
        "What did I say earlier in this chat about deployment?"
    )
    enabled = {source.source for source in route_plan.sources if source.enabled}

    assert "current_chat_span" in enabled
    assert "previous_chat_gist" not in enabled


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


def test_llm_previous_chat_gist_extractor_is_used_when_configured(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat", title="Old chat")
    database.save_message("old-chat", "user", "We chose SQLite for persistence.")
    database.save_message("old-chat", "assistant", "Recorded.")
    model = FakeModel(
        response=(
            '{"summary":"LLM gist: SQLite persistence decision.",'
            '"topics":["persistence"],'
            '"decisions":["Use SQLite"],'
            '"open_tasks":[],'
            '"important_facts":["SQLite selected"],'
            '"corrections":[]}'
        )
    )
    service = ChatService(
        database=database,
        model=model,  # type: ignore[arg-type]
        raw_message_limit=8,
        memory_update_batch_size=6,
        previous_chat_gist_extractor="llm",
        previous_chat_gist_max_messages_per_gist=30,
    )

    result = service.build_previous_chat_gist_generator().generate_for_existing_chats()

    assert result.created_count == 1
    assert len(model.calls) == 1
    gist = database.chat_gist(result.gist_ids[0])
    assert gist is not None
    assert gist.gist_text == "LLM gist: SQLite persistence decision."
    metadata = json.loads(gist.metadata_json)
    assert metadata["summarizer"] == "FallbackChatGistExtractor"
    assert metadata["effective_summarizer"] == "LLMChatGistExtractor"
    assert metadata["source_message_count"] == 2


def test_llm_previous_chat_gist_falls_back_to_deterministic_on_failure(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("old-chat", title="Old chat")
    database.save_message("old-chat", "user", "Remember the fallback release note.")
    database.save_message("old-chat", "assistant", "Recorded.")
    extractor = FallbackChatGistExtractor(
        primary=FailingPreviousGistExtractor(),
        fallback=DeterministicPreviousChatGistExtractor(),
    )

    result = PreviousChatGistGenerator(
        database=database,
        extractor=extractor,
    ).generate_for_existing_chats()

    assert result.created_count == 1
    gist = database.chat_gist(result.gist_ids[0])
    assert gist is not None
    assert "Earlier user request: Remember the fallback release note." in gist.gist_text
    metadata = json.loads(gist.metadata_json)
    assert metadata["summarizer"] == "FallbackChatGistExtractor"
    assert (
        metadata["effective_summarizer"]
        == "DeterministicPreviousChatGistExtractor"
    )


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
