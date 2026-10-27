from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

from support.deterministic_services import local_document_retriever

from src.actions.chat_end import ChatEndAction
from src.chat_service import ChatService
from src.database import Database


class Model:
    model_name = "fake"

    def __init__(
        self, *, timeout: bool = False, entered: Event | None = None, release: Event | None = None
    ) -> None:
        self.timeout = timeout
        self.entered = entered
        self.release = release

    def chat(self, messages, temperature=None):  # type: ignore[no-untyped-def]
        del messages, temperature
        if self.entered:
            self.entered.set()
        if self.release is not None:
            assert self.release.wait(timeout=10), "test did not release the blocked answer"
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
        document_indexer=local_document_retriever(database),
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
    entered, release, end_attempted, finalizer_entered = Event(), Event(), Event(), Event()
    service = make_service(database, Model(entered=entered, release=release))

    class ObservedMemory(NoopMemory):
        def process_all_for_chat_end(self, chat_id: str):
            finalizer_entered.set()
            assert [(m.role, m.content) for m in database.messages_for_chat(chat_id)] == [
                ("user", "question"),
                ("assistant", "completed answer"),
            ]
            return super().process_all_for_chat_end(chat_id)

    end_action = ChatEndAction(database, ObservedMemory(), NoopGist())

    def end_chat():
        end_attempted.set()
        return end_action.execute("chat")

    with ThreadPoolExecutor(max_workers=2) as pool:
        send = pool.submit(service.handle_user_turn, "chat", "question")
        try:
            assert entered.wait(timeout=5)
            end = pool.submit(end_chat)
            assert end_attempted.wait(timeout=2)
            # Send is genuinely suspended inside the model while End is attempting entry.
            assert not finalizer_entered.wait(timeout=0.2)
            assert not send.done()
            assert not end.done()
            assert database.is_chat_active("chat") is True
            assert [(m.role, m.content) for m in database.messages_for_chat("chat")] == [
                ("user", "question")
            ]
        finally:
            release.set()
        result = send.result(timeout=5)
        end.result(timeout=5)
        assert finalizer_entered.is_set()

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
