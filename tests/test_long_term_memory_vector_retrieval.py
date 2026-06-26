from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.core.contracts import SourcePlan
from src.database import Database
from src.memory.long_term_store import (
    DEFAULT_USER_NAMESPACE,
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
)
from src.memory.long_term_vector_index import (
    LongTermMemoryVectorIndex,
    memory_record_to_index_text,
)
from src.retrieval.langchain_chroma_retriever import LangChainChromaUnavailable
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever


@dataclass
class FakeDocument:
    page_content: str
    metadata: dict


class FakeVectorStore:
    def __init__(self) -> None:
        self.documents: list[FakeDocument] = []
        self.ids: list[str] = []

    def add_documents(self, documents: list[FakeDocument], ids: list[str]) -> None:
        self.documents.extend(documents)
        self.ids.extend(ids)

    def similarity_search_with_score(self, query: str, k: int):
        terms = {term.lower().strip("?.:,") for term in query.split()}
        scored = []
        for document in self.documents:
            content = document.page_content.lower()
            overlap = sum(1 for term in terms if term and term in content)
            score = 1.0 / max(1, overlap) if overlap else 999.0
            scored.append((document, score))
        scored.sort(key=lambda item: item[1])
        return scored[:k]


class FakeLongTermMemoryVectorIndex(LongTermMemoryVectorIndex):
    def __init__(self, vectorstore: FakeVectorStore) -> None:
        super().__init__(vectorstore=vectorstore)

    @staticmethod
    def _document_class():
        return FakeDocument


class UnavailableVectorIndex:
    def search(self, query: str, limit: int = 10):
        del query, limit
        raise LangChainChromaUnavailable("missing vector backend")


def test_memory_record_to_index_text_is_compact_and_semantic(tmp_path: Path) -> None:
    record = stored_memory_record(
        tmp_path=tmp_path,
        memory_id="preferences:libraries",
        key="libraries",
        value="User prefers mature open-source libraries.",
    )

    text = memory_record_to_index_text(record)

    assert "Memory category: preferences." in text
    assert "Key: libraries." in text
    assert "Value: User prefers mature open-source libraries." in text


def test_long_term_memory_vector_index_indexes_memory_records(tmp_path: Path) -> None:
    record = stored_memory_record(
        tmp_path=tmp_path,
        memory_id="preferences:libraries",
        key="libraries",
        value="User prefers mature open-source libraries.",
    )
    vectorstore = FakeVectorStore()
    vector_index = FakeLongTermMemoryVectorIndex(vectorstore)

    result = vector_index.index_records([record])

    assert result.indexed_count == 1
    assert result.skipped_count == 0
    assert len(vectorstore.documents) == 1
    assert vectorstore.ids == ["user::default::semantic_memory::preferences:libraries"]
    assert vectorstore.documents[0].metadata["memory_id"] == "preferences:libraries"
    assert "mature open-source libraries" in vectorstore.documents[0].page_content


def test_structured_memory_vector_retrieval_returns_expected_memory(
    tmp_path: Path,
) -> None:
    database = seeded_memory_database(tmp_path)
    vector_index = indexed_memory_vector(database)
    retriever = StructuredMemoryRetriever(
        database,
        mode="vector",
        vector_index=vector_index,
    )

    candidates = retriever.retrieve(
        chat_id="chat-2",
        source_plan=SourcePlan(
            source="structured_memory",
            query="Which stable libraries do I prefer?",
            limit=1,
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].source == "structured_memory"
    assert candidates[0].record_id == "preferences:libraries"
    assert "mature open-source libraries" in candidates[0].content
    assert candidates[0].metadata["retrieval_mode"] == "vector"
    assert candidates[0].metadata["vector_score"] is not None


def test_structured_memory_hybrid_retrieval_deduplicates_by_memory_id(
    tmp_path: Path,
) -> None:
    database = seeded_memory_database(tmp_path)
    vector_index = indexed_memory_vector(database)
    retriever = StructuredMemoryRetriever(
        database,
        mode="hybrid",
        vector_index=vector_index,
    )

    candidates = retriever.retrieve(
        chat_id="chat-2",
        source_plan=SourcePlan(
            source="structured_memory",
            query="libraries",
            limit=10,
        ),
    )

    matching = [
        candidate
        for candidate in candidates
        if candidate.record_id == "preferences:libraries"
    ]
    assert len(matching) == 1
    assert "mature open-source libraries" in matching[0].content


def test_structured_memory_vector_retrieval_falls_back_to_sqlite(
    tmp_path: Path,
) -> None:
    database = seeded_memory_database(tmp_path)
    retriever = StructuredMemoryRetriever(
        database,
        mode="vector",
        vector_index=UnavailableVectorIndex(),  # type: ignore[arg-type]
    )

    candidates = retriever.retrieve(
        chat_id="chat-2",
        source_plan=SourcePlan(
            source="structured_memory",
            query="libraries",
            limit=10,
        ),
    )

    assert any(candidate.record_id == "preferences:libraries" for candidate in candidates)
    assert all(candidate.source == "structured_memory" for candidate in candidates)


def seeded_memory_database(tmp_path: Path) -> Database:
    database = Database(tmp_path / "chatbot.db")
    store = SQLiteLongTermMemoryStore(database)
    store.upsert(
        LongTermMemoryWrite(
            namespace=DEFAULT_USER_NAMESPACE,
            memory_id="preferences:libraries",
            category="preferences",
            key="libraries",
            value="User prefers mature open-source libraries over custom infrastructure.",
            confidence=0.9,
            source_chat_id="chat-1",
            source_message_ids=[1],
        )
    )
    store.upsert(
        LongTermMemoryWrite(
            namespace=DEFAULT_USER_NAMESPACE,
            memory_id="preferences:answers",
            category="preferences",
            key="answers",
            value="User prefers concise practical answers.",
            confidence=0.8,
            source_chat_id="chat-1",
            source_message_ids=[2],
        )
    )
    return database


def indexed_memory_vector(database: Database) -> FakeLongTermMemoryVectorIndex:
    vectorstore = FakeVectorStore()
    vector_index = FakeLongTermMemoryVectorIndex(vectorstore)
    store = SQLiteLongTermMemoryStore(database)
    vector_index.index_records(store.list(DEFAULT_USER_NAMESPACE))
    return vector_index


def stored_memory_record(
    tmp_path: Path,
    memory_id: str,
    key: str,
    value: str,
):
    database = Database(tmp_path / "memory-vector-test.db")
    store = SQLiteLongTermMemoryStore(database)
    store.upsert(
        LongTermMemoryWrite(
            namespace=DEFAULT_USER_NAMESPACE,
            memory_id=memory_id,
            category="preferences",
            key=key,
            value=value,
            confidence=0.9,
            source_chat_id="chat-1",
            source_message_ids=[1],
        )
    )
    record = store.get(DEFAULT_USER_NAMESPACE, memory_id)
    assert record is not None
    return record
