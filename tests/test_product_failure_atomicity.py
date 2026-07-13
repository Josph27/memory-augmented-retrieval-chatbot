from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from src.actions.chat_end import ChatEndAction
from src.chat_service import ChatService
from src.database import Database


class Model:
    model_name = "fake"

    def __init__(self, *, timeout: bool = False, entered: Event | None = None) -> None:
        self.timeout = timeout
        self.entered = entered

    def chat(self, messages, temperature=None):  # type: ignore[no-untyped-def]
        del messages, temperature
        if self.entered:
            self.entered.set()
        if self.timeout:
            raise TimeoutError("deadline exceeded")
        return "completed answer"


class NoopMemory:
    def process_all_for_chat_end(self, chat_id: str):  # type: ignore[no-untyped-def]
        del chat_id
        return type("Result", (), {"processed_message_count": 0, "batch_count": 0})()


class NoopGist:
    def finalize_chat(self, chat_id: str):  # type: ignore[no-untyped-def]
        del chat_id
        return type(
            "Result",
            (),
            {"created_count": 0, "processed_message_count": 0, "batch_count": 0},
        )()


def make_service(database: Database, model: Model) -> ChatService:
    return ChatService(
        database=database,
        model=model,
        raw_message_limit=8,
        memory_update_batch_size=6,
    )


def test_answer_timeout_preserves_user_without_fake_assistant(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    service = make_service(database, Model(timeout=True))

    result = service.handle_user_turn("chat", "please answer")

    messages = database.messages_for_chat("chat")
    assert [(message.role, message.content) for message in messages] == [
        ("user", "please answer"),
        (
            "assistant",
            "The answer could not be generated. Your message was saved and you can retry this turn.",
        ),
    ]
    assert result.termination_reason == "answer_generation_failed"
    assert result.assistant_message_id is not None
    assert result.metadata["answer_status"] == "failed"
    assert database.is_chat_active("chat") is True
    assert len(database.answer_inspections_for_chat("chat")) == 1


def test_send_and_end_share_one_atomic_chat_guard(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    entered = Event()
    service = make_service(database, Model(entered=entered))
    end_action = ChatEndAction(database, NoopMemory(), NoopGist())

    with ThreadPoolExecutor(max_workers=2) as pool:
        send = pool.submit(service.handle_user_turn, "chat", "question")
        assert entered.wait(timeout=2)
        end = pool.submit(end_action.execute, "chat")
        result = send.result(timeout=2)
        end.result(timeout=2)

    assert result.answer == "completed answer"
    assert database.is_chat_active("chat") is False
    assert [(item.role, item.content) for item in database.messages_for_chat("chat")] == [
        ("user", "question"),
        ("assistant", "completed answer"),
    ]


def test_send_after_end_is_rejected_before_persistence(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    ChatEndAction(database, NoopMemory(), NoopGist()).execute("chat")
    service = make_service(database, Model())

    try:
        service.handle_user_turn("chat", "late question")
    except RuntimeError as error:
        assert "inactive" in str(error)
    else:  # pragma: no cover - assertion clarity
        raise AssertionError("inactive chat accepted a message")

    assert database.messages_for_chat("chat") == []
