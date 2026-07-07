from __future__ import annotations

from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest

from src.chat_service import ChatService
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.documents.registry import DocumentAmbiguityError, DocumentRegistry
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever


class FakeModel:
    model_name = "fake"

    def chat(self, messages, temperature=None):  # type: ignore[no-untyped-def]
        del messages, temperature
        return "answer"


class CapturingIndexer:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.metadata: dict[str, object] = {}

    def index_text_document(self, title, text, source="manual", metadata=None):  # type: ignore[no-untyped-def]
        del title, text, source
        self.metadata = dict(metadata or {})
        if self.fail:
            raise RuntimeError("index unavailable")
        return {
            "document_id": self.metadata["document_id"],
            "chunk_count": 2,
        }


class ScopedRetriever:
    def __init__(self) -> None:
        self.calls: list[SourcePlan] = []

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        del chat_id
        self.calls.append(source_plan)
        return [
            MemoryCandidate(
                source="document_memory",
                content=f"content:{document_id}",
                record_id=f"{document_id}:0",
                metadata={"document_id": document_id},
            )
            for document_id in source_plan.filters.get("allowed_document_ids", [])
        ]


def service(database: Database, indexer: object) -> ChatService:
    return ChatService(
        database=database,
        model=FakeModel(),
        raw_message_limit=8,
        memory_update_batch_size=6,
        document_indexer=indexer,
    )


def upload(
    tmp_path: Path,
    database: Database,
    chat_id: str,
    name: str,
    *,
    indexer: CapturingIndexer | None = None,
) -> str:
    path = tmp_path / name
    path.write_text(f"content for {name}", encoding="utf-8")
    result = service(database, indexer or CapturingIndexer()).index_document_file(
        path,
        chat_id=chat_id,
    )
    return result.document_id


def test_document_lifecycle_and_chat_association_survive_reload(tmp_path: Path) -> None:
    path = tmp_path / "chatbot.db"
    database = Database(path)
    database.create_chat("chat-a")
    document_id = upload(tmp_path, database, "chat-a", "alpha.txt")

    rebuilt = Database(path)
    documents = rebuilt.documents_for_chat("chat-a")

    assert [(item.id, item.file_name, item.status, item.chunk_count) for item in documents] == [
        (document_id, "alpha.txt", "Ready", 2)
    ]


def test_document_association_is_persisted_after_indexing_reaches_ready(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    observed: list[tuple[str, int]] = []

    class InspectingIndexer(CapturingIndexer):
        def index_text_document(self, title, text, source="manual", metadata=None):  # type: ignore[no-untyped-def]
            document_id = str((metadata or {})["document_id"])
            document = database.get_document(document_id)
            observed.append(
                (
                    document.status if document is not None else "missing",
                    len(database.documents_for_chat("chat")),
                )
            )
            return super().index_text_document(
                title,
                text,
                source=source,
                metadata=metadata,
            )

    document_id = upload(
        tmp_path,
        database,
        "chat",
        "ordered.txt",
        indexer=InspectingIndexer(),
    )

    assert observed == [("Indexing", 0)]
    associated = database.documents_for_chat("chat")
    assert [(item.id, item.status) for item in associated] == [
        (document_id, "Ready")
    ]


def test_same_turn_attachment_forces_scoped_retrieval_without_duplicate_user_message(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    chat_service = service(database, CapturingIndexer())
    chat_id = chat_service.start_chat("chat")
    user_message_id = chat_service.persist_user_message_for_turn(
        chat_id,
        "what are the key findings",
    )
    document_id = upload(
        tmp_path,
        database,
        chat_id,
        "findings.md",
        indexer=CapturingIndexer(),
    )
    retriever = ScopedRetriever()
    chat_service.coordinator.retriever_dispatcher.retrievers["document_memory"] = (
        retriever
    )

    result = chat_service.handle_user_turn(
        chat_id,
        "what are the key findings",
        task_context="document_qa",
        persisted_user_message_id=user_message_id,
    )

    assert result.trace.route_plan is not None
    document_source = next(
        source
        for source in result.trace.route_plan.sources
        if source.source == "document_memory"
    )
    assert document_source.enabled is True
    assert document_source.filters["same_turn_attachment"] is True
    assert retriever.calls[0].filters["allowed_document_ids"] == [document_id]
    assert any(
        candidate.metadata.get("document_id") == document_id
        for candidate in result.trace.retrieved_candidates
    )
    assert any(
        candidate.metadata.get("document_id") == document_id
        for candidate in result.trace.context_packet.candidates
    )
    messages = database.messages_for_chat(chat_id)
    assert [message.role for message in messages] == ["user", "assistant"]
    assert [message.content for message in messages].count(
        "what are the key findings"
    ) == 1


def test_index_failure_persists_failed_state_and_never_ready(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat-a")
    path = tmp_path / "broken.txt"
    path.write_text("content", encoding="utf-8")

    with pytest.raises(RuntimeError, match="index unavailable"):
        service(database, CapturingIndexer(fail=True)).index_document_file(
            path,
            chat_id="chat-a",
        )

    documents = database.documents_for_chat("chat-a")
    assert len(documents) == 1
    assert documents[0].status == "Failed"
    assert "index unavailable" in (documents[0].error or "")


def test_document_retrieval_is_scoped_to_current_chat(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat-a")
    database.create_chat("chat-b")
    document_a = upload(tmp_path, database, "chat-a", "alpha.txt")
    upload(tmp_path, database, "chat-b", "beta.txt")
    retriever = ScopedRetriever()
    dispatcher = RetrieverDispatcher(
        database,
        retrievers={"document_memory": retriever},
    )

    candidates = dispatcher.retrieve(
        "chat-a",
        RoutePlan(
            query="according to the document",
            sources=[
                SourcePlan(
                    source="document_memory",
                    query="according to the document",
                )
            ],
        ),
    )

    assert [candidate.metadata["document_id"] for candidate in candidates] == [document_a]
    assert retriever.calls[0].filters["allowed_document_ids"] == [document_a]


def test_explicit_filename_and_ambiguity_resolution(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    alpha = upload(tmp_path, database, "chat", "alpha.txt")
    upload(tmp_path, database, "chat", "beta.txt")
    registry = DocumentRegistry(database)

    resolved = registry.resolve("chat", "Summarize alpha.txt")

    assert resolved.document_ids == (alpha,)
    with pytest.raises(DocumentAmbiguityError):
        registry.resolve("chat", "Summarize the document")


def test_empty_explicit_document_scope_never_searches_all_documents(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    retriever = ScopedRetriever()
    dispatcher = RetrieverDispatcher(
        database,
        retrievers={"document_memory": retriever},
    )

    candidates = dispatcher.retrieve(
        "missing-chat",
        RoutePlan(
            query="document",
            sources=[
                SourcePlan(
                    source="document_memory",
                    query="document",
                    filters={"allowed_document_ids": []},
                )
            ],
        ),
    )

    assert candidates == []
    assert retriever.calls[0].filters["allowed_document_ids"] == []


def test_retriever_exception_is_captured_without_false_evidence(tmp_path: Path) -> None:
    class Failing:
        def retrieve(self, chat_id, source_plan):  # type: ignore[no-untyped-def]
            del chat_id, source_plan
            raise RuntimeError("backend failed")

    dispatcher = RetrieverDispatcher(
        Database(tmp_path / "chatbot.db"),
        retrievers={"document_memory": Failing()},
    )

    candidates = dispatcher.retrieve(
        "missing-chat",
        RoutePlan(
            query="document",
            sources=[SourcePlan(source="document_memory", query="document")],
        ),
    )

    assert candidates == []
    assert dispatcher.last_errors == [
        {
            "source": "document_memory",
            "type": "RuntimeError",
            "message": "backend failed",
        }
    ]


def test_repeated_database_initialization_is_idempotent_upgrade(tmp_path: Path) -> None:
    path = tmp_path / "existing.db"
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
            INSERT INTO chats VALUES ('preserved', 'Existing', 't0', 't0');
            INSERT INTO messages (chat_id, role, content, created_at)
            VALUES ('preserved', 'user', 'keep me', 't0');
            """
        )

    Database(path)
    rebuilt = Database(path)

    assert rebuilt.get_chat("preserved") is not None
    assert [message.content for message in rebuilt.messages_for_chat("preserved")] == [
        "keep me"
    ]
    with rebuilt.connect() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert {"document_records", "chat_documents", "operation_results"} <= tables


def test_document_association_foreign_keys_are_enforced(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")

    with pytest.raises(sqlite3.IntegrityError):
        database.associate_document_with_chat("chat", "missing-document")

    database.create_document_record("document", "report.txt")
    with pytest.raises(sqlite3.IntegrityError):
        database.associate_document_with_chat("missing-chat", "document")


def test_duplicate_upload_operation_reuses_exact_ready_document(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    indexer = CapturingIndexer()
    path = tmp_path / "report.txt"
    path.write_text("content", encoding="utf-8")
    chat_service = service(database, indexer)

    first = chat_service.index_document_file(
        path,
        chat_id="chat",
        operation_id="upload-1",
    )
    second = chat_service.index_document_file(
        path,
        chat_id="chat",
        operation_id="upload-1",
    )

    assert first == second
    assert len(database.documents_for_chat("chat")) == 1
    assert database.get_operation_result("upload-1").result_ref == first.document_id  # type: ignore[union-attr]


def test_retry_after_failed_indexing_reuses_document_identity(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    path = tmp_path / "report.txt"
    path.write_text("content", encoding="utf-8")

    with pytest.raises(RuntimeError):
        service(database, CapturingIndexer(fail=True)).index_document_file(
            path,
            chat_id="chat",
            operation_id="upload-retry",
        )
    failed = database.documents_for_chat("chat")[0]

    retried = service(database, CapturingIndexer()).index_document_file(
        path,
        chat_id="chat",
        operation_id="upload-retry",
    )

    assert retried.document_id == failed.id
    assert database.get_document(failed.id).status == "Ready"  # type: ignore[union-attr]
    assert len(database.documents_for_chat("chat")) == 1


def test_ready_update_failure_leaves_truthful_indexing_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    path = tmp_path / "report.txt"
    path.write_text("content", encoding="utf-8")
    original = database.update_document_status

    def fail_ready(document_id: str, status: str, **kwargs: object) -> None:
        if status == "Ready":
            raise sqlite3.OperationalError("disk full")
        original(document_id, status, **kwargs)

    monkeypatch.setattr(database, "update_document_status", fail_ready)
    with pytest.raises(sqlite3.OperationalError, match="disk full"):
        service(database, CapturingIndexer()).index_document_file(
            path,
            chat_id="chat",
            operation_id="upload-ready-failure",
        )

    assert database.documents_for_chat("chat")[0].status == "Indexing"


def test_ready_document_without_candidates_returns_no_false_evidence(
    tmp_path: Path,
) -> None:
    class EmptyRetriever:
        def __init__(self) -> None:
            self.calls = 0

        def retrieve(self, chat_id, source_plan):  # type: ignore[no-untyped-def]
            del chat_id, source_plan
            self.calls += 1
            return []

    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat")
    upload(tmp_path, database, "chat", "report.txt")
    retriever = EmptyRetriever()
    dispatcher = RetrieverDispatcher(
        database,
        retrievers={"document_memory": retriever},
    )

    candidates = dispatcher.retrieve(
        "chat",
        RoutePlan(
            query="according to the document",
            sources=[
                SourcePlan(
                    source="document_memory",
                    query="according to the document",
                )
            ],
        ),
    )

    assert candidates == []
    assert retriever.calls == 2


def test_scoped_retrieval_rejects_chunks_with_incomplete_metadata() -> None:
    class IncompleteMetadataRetriever(LangChainChromaRetriever):
        def _similarity_search(  # type: ignore[no-untyped-def]
            self,
            query,
            limit,
            allowed_document_ids=None,
        ):
            del query, limit, allowed_document_ids
            return [(SimpleNamespace(page_content="orphan chunk", metadata={}), 0.9)]

    candidates = IncompleteMetadataRetriever().retrieve(
        "chat",
        SourcePlan(
            source="document_memory",
            query="question",
            filters={"allowed_document_ids": ["expected-document"]},
        ),
    )

    assert candidates == []
