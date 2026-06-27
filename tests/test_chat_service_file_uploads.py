from __future__ import annotations

from pathlib import Path

from src.chat_service import ChatService
from src.database import Database


class FakeModel:
    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        return "fake response"


class FakeIndexer:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def index_text_document(
        self,
        title: str,
        text: str,
        source: str = "manual",
        metadata: dict | None = None,
    ):
        self.calls.append(
            {
                "title": title,
                "text": text,
                "source": source,
                "metadata": metadata or {},
            }
        )
        return {"document_id": "fake-doc", "chunk_count": 2}


def test_chat_service_indexes_uploaded_file_through_configured_indexer(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    indexer = FakeIndexer()
    service = ChatService(
        database=database,
        model=FakeModel(),
        raw_message_limit=8,
        memory_update_batch_size=6,
        document_indexer=indexer,
    )
    path = tmp_path / "upload.md"
    path.write_text("# Upload\n\nUnique upload fact.", encoding="utf-8")

    result = service.index_document_file(path)

    assert result.file_name == "upload.md"
    assert result.document_id == "fake-doc"
    assert result.chunk_count == 2
    assert indexer.calls[0]["title"] == "upload"
    assert "Unique upload fact." in indexer.calls[0]["text"]
    assert indexer.calls[0]["source"] == "file"
    assert indexer.calls[0]["metadata"]["file_name"] == "upload.md"


def test_chat_service_uses_display_name_for_chainlit_temp_upload(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    indexer = FakeIndexer()
    service = ChatService(
        database=database,
        model=FakeModel(),
        raw_message_limit=8,
        memory_update_batch_size=6,
        document_indexer=indexer,
    )
    path = tmp_path / "chainlit-upload.bin"
    path.write_text("# README\n\nUnique upload fact.", encoding="utf-8")

    result = service.index_document_file(path, display_name="README.md")

    assert result.file_name == "README.md"
    assert result.document_id == "fake-doc"
    assert result.chunk_count == 2
    assert indexer.calls[0]["title"] == "README"
    assert indexer.calls[0]["metadata"]["file_name"] == "README.md"
    assert indexer.calls[0]["metadata"]["file_extension"] == ".md"


def test_chat_service_titles_chat_from_first_message(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    service = ChatService(
        database=database,
        model=FakeModel(),
        raw_message_limit=8,
        memory_update_batch_size=6,
        document_indexer=FakeIndexer(),
    )
    chat_id = service.start_chat()

    service.handle_user_message(chat_id, "This is the first topic")

    chat = database.get_chat(chat_id)
    assert chat is not None
    assert chat.title == "This is the first topic"


def test_chat_service_can_start_chat_with_existing_thread_id(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    service = ChatService(
        database=database,
        model=FakeModel(),
        raw_message_limit=8,
        memory_update_batch_size=6,
        document_indexer=FakeIndexer(),
    )

    chat_id = service.start_chat(chat_id="chainlit-thread-id")

    assert chat_id == "chainlit-thread-id"
    assert database.get_chat("chainlit-thread-id") is not None
