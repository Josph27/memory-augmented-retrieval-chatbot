from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from src.database import StoredMessage
from src.memory.long_term_store import (
    LongTermMemoryRecord,
    LongTermMemoryStore,
    LongTermMemoryWrite,
    category_namespace,
    dedupe_memory_records,
    merge_memory_records,
    record_to_memory_state_record,
    record_to_write,
    structured_memory_namespaces,
)
from src.memory.memory_trace import print_saved_memory_trace
from src.memory.structured_state import (
    MEMORY_CATEGORIES,
    MemoryUpdateResult,
    active_memories,
    clean_text,
    is_vague_memory,
    looks_like_transcript_text,
    make_memory_id,
    normalize_confidence,
    normalize_key,
    normalize_memory_state,
    supported_source_ids,
)


StructuredMemoryCategory = Literal[
    "user_facts",
    "project_facts",
    "decisions",
    "corrections",
    "open_tasks",
    "preferences",
    "constraints",
    "procedural",
]

StructuredMemoryStatus = Literal["active", "superseded", "deleted"]

LANGMEM_STRUCTURED_MEMORY_INSTRUCTIONS = """Extract durable structured memory for this chat.

Use only information supported by the provided messages. Do not write a
transcript. Do not continue the conversation. Do not invent facts.

Allowed categories:
- user_facts: stable facts about the user
- project_facts: stable facts about the current project
- decisions: choices that have been made
- corrections: misunderstandings corrected by the user
- open_tasks: unfinished next steps
- preferences: user preferences about interaction or implementation
- constraints: requirements or limitations
- procedural: reusable instructions, methods, or operating steps

Prefer compact, standalone memories that will matter later. If the user
corrects or replaces a previous fact or decision, keep the corrected current
value as active and avoid preserving the outdated value as active.
"""


class LangMemStructuredMemory(BaseModel):
    """Pydantic schema LangMem should emit for structured chat memory."""

    category: StructuredMemoryCategory
    key: str = Field(description="Short snake_case key for this memory.")
    value: str = Field(description="Concise standalone memory value.")
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    status: StructuredMemoryStatus = "active"
    source_message_ids: list[int] = Field(default_factory=list)


class LangMemManager(Protocol):
    """Minimal sync LangMem manager protocol used for dependency injection."""

    def invoke(self, input: dict[str, Any]) -> list[Any]:
        """Return extracted memories for the supplied LangMem MemoryState."""
        ...


@dataclass(frozen=True)
class LangMemBackendConfig:
    """Configuration for constructing the real LangMem manager lazily."""

    openai_api_key: str
    openai_base_url: str
    model_name: str

    @classmethod
    def from_env(cls, model_name: str | None = None) -> "LangMemBackendConfig":
        """Load OpenAI-compatible model settings from the existing environment."""
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "dummy"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
            model_name=model_name or os.getenv("MODEL_NAME", "google/gemma-4-31B-it"),
        )


class LangMemStructuredMemoryState:
    """Structured memory updater backed by LangMem extraction/consolidation."""

    def __init__(
        self,
        manager: LangMemManager | None = None,
        config: LangMemBackendConfig | None = None,
        long_term_store: LongTermMemoryStore | None = None,
    ) -> None:
        self._manager = manager
        self._config = config or LangMemBackendConfig.from_env()
        self._long_term_store = long_term_store
        self.last_saved_records: list[LongTermMemoryWrite] = []

    def update(
        self,
        existing_memory: dict[str, list[dict[str, Any]]],
        messages: list[StoredMessage],
    ) -> MemoryUpdateResult:
        """Use LangMem output and normalize it into this app's memory record format."""
        normalized_memory = normalize_memory_state(existing_memory)
        self.last_saved_records = []
        user_messages = [message for message in messages if message.role == "user"]
        if not user_messages:
            return MemoryUpdateResult(
                memory_state=normalized_memory,
            accepted=False,
            rejection_reason="no_user_messages",
        )

        source_chat_id = messages[0].chat_id
        long_term_records = self._load_existing_long_term_records(source_chat_id)
        source_text_by_id = {message.id: message.content for message in user_messages}
        allowed_source_ids = set(source_text_by_id)
        combined_existing_records = merge_memory_records(
            [record_to_memory_state_record(record) for record in long_term_records],
            normalized_memory["memories"],
        )
        try:
            extracted = self.manager.invoke(
                {
                    "messages": messages_to_langchain_messages(messages),
                    "existing": existing_memories_for_langmem(
                        {"memories": combined_existing_records}
                    ),
                }
            )
        except Exception as exc:
            return MemoryUpdateResult(
                memory_state={"memories": combined_existing_records},
                accepted=False,
                rejection_reason=f"langmem_update_failed:{exc.__class__.__name__}",
            )

        records = normalize_langmem_outputs(
            extracted=extracted,
            allowed_source_ids=allowed_source_ids,
            source_text_by_id=source_text_by_id,
        )
        if not records:
            return MemoryUpdateResult(
                memory_state={"memories": combined_existing_records},
                accepted=False,
                rejection_reason="langmem_no_valid_memories",
            )

        merged_records = merge_memory_records(combined_existing_records, records)
        try:
            self._persist_long_term_records(
                source_chat_id=source_chat_id,
                records=records,
                source_message_ids=allowed_source_ids,
            )
        except Exception as exc:
            return MemoryUpdateResult(
                memory_state={"memories": combined_existing_records},
                accepted=False,
                rejection_reason=f"long_term_store_write_failed:{exc.__class__.__name__}",
            )
        return MemoryUpdateResult(memory_state={"memories": merged_records}, accepted=True)

    @property
    def manager(self) -> LangMemManager:
        """Return the injected manager or lazily construct the real LangMem manager."""
        if self._manager is None:
            self._manager = create_real_langmem_manager(self._config)
        return self._manager

    def _load_existing_long_term_records(self, chat_id: str) -> list[LongTermMemoryRecord]:
        """Load long-term records that should influence the next LangMem update."""
        if self._long_term_store is None:
            return []

        records: list[LongTermMemoryRecord] = []
        for namespace in structured_memory_namespaces(chat_id):
            records.extend(
                [
                    record
                    for record in self._long_term_store.list(namespace)
                    if record.status == "active"
                ]
            )
        return dedupe_memory_records(records)

    def _persist_long_term_records(
        self,
        source_chat_id: str,
        records: list[dict[str, Any]],
        source_message_ids: set[int],
    ) -> None:
        """Persist validated LangMem records into the long-term store."""
        if self._long_term_store is None:
            return

        try:
            for record in records:
                namespace = category_namespace(record["category"], source_chat_id)
                write = record_to_write(
                    record,
                    namespace=namespace,
                    source_chat_id=source_chat_id,
                    metadata={
                        "backend": "langmem",
                        "source_message_ids_seen": sorted(source_message_ids),
                    },
                )
                self._long_term_store.upsert(write)
                self.last_saved_records.append(write)
                print_saved_memory_trace(source_chat_id, write)
        except Exception as exc:
            raise RuntimeError(
                f"failed to persist long-term memory:{exc.__class__.__name__}"
            ) from exc


def create_real_langmem_manager(config: LangMemBackendConfig) -> LangMemManager:
    """Construct the real LangMem manager with an OpenAI-compatible LangChain model."""
    try:
        from langchain_openai import ChatOpenAI
        from langmem import create_memory_manager
    except ImportError as exc:
        raise RuntimeError(
            "LangMem structured memory requires langmem and langchain-openai."
        ) from exc

    model = ChatOpenAI(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.model_name,
        temperature=0.0,
    )
    return create_memory_manager(
        model,
        schemas=[LangMemStructuredMemory],
        instructions=LANGMEM_STRUCTURED_MEMORY_INSTRUCTIONS,
        enable_deletes=False,
    )


def messages_to_langchain_messages(messages: list[StoredMessage]) -> list[Any]:
    """Convert stored messages into LangChain message objects."""
    try:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
    except ImportError as exc:
        raise RuntimeError("LangChain core messages are required for LangMem.") from exc

    converted: list[Any] = []
    for message in messages:
        content = f"[message_id={message.id}] {message.content}"
        if message.role == "user":
            converted.append(HumanMessage(content=content))
        elif message.role == "assistant":
            converted.append(AIMessage(content=content))
        else:
            converted.append(SystemMessage(content=content))
    return converted


def existing_memories_for_langmem(
    memory_state: dict[str, list[dict[str, Any]]],
) -> list[tuple[str, LangMemStructuredMemory]]:
    """Convert current active app memory into LangMem's existing-memory shape."""
    existing: list[tuple[str, LangMemStructuredMemory]] = []
    for record in active_memories(memory_state):
        category = record.get("category")
        if category not in MEMORY_CATEGORIES:
            continue
        key = normalize_key(record.get("key"))
        value = record.get("value")
        if not key or not isinstance(value, str) or not value.strip():
            continue
        existing.append(
            (
                str(record.get("id") or make_memory_id(str(category), key)),
                LangMemStructuredMemory(
                    category=category,
                    key=key,
                    value=clean_text(value),
                    confidence=normalize_confidence(record.get("confidence")),
                    status="active",
                    source_message_ids=[
                        source_id
                        for source_id in record.get("source_message_ids", [])
                        if isinstance(source_id, int)
                    ],
                ),
            )
        )
    return existing


def normalize_langmem_outputs(
    extracted: list[Any],
    allowed_source_ids: set[int],
    source_text_by_id: dict[int, str],
) -> list[dict[str, Any]]:
    """Normalize real or fake LangMem outputs into stored memory records."""
    records: list[dict[str, Any]] = []
    for item in extracted:
        memory = extract_memory_content(item)
        if memory is None:
            continue

        record = normalize_langmem_memory(memory, allowed_source_ids, source_text_by_id)
        if record is not None:
            upsert_normalized_record(records, record)
    return records


def extract_memory_content(item: Any) -> Any | None:
    """Read memory content from LangMem ExtractedMemory, Pydantic models, or dicts."""
    if hasattr(item, "content"):
        return getattr(item, "content")
    return item


def normalize_langmem_memory(
    memory: Any,
    allowed_source_ids: set[int],
    source_text_by_id: dict[int, str],
) -> dict[str, Any] | None:
    """Validate one LangMem memory and convert it to this app's record shape."""
    data = memory_to_dict(memory)
    category = data.get("category")
    key = normalize_key(data.get("key"))
    value = data.get("value")
    if category not in MEMORY_CATEGORIES:
        return None
    if not key or not isinstance(value, str) or not value.strip():
        return None

    cleaned_value = clean_text(strip_message_id_markers(value))
    if looks_like_transcript_text(cleaned_value) or is_vague_memory(cleaned_value):
        return None

    hinted_source_ids = [
        source_id
        for source_id in data.get("source_message_ids", [])
        if isinstance(source_id, int) and source_id in allowed_source_ids
    ]
    candidate_source_ids = hinted_source_ids or list(allowed_source_ids)
    source_ids = supported_source_ids(
        cleaned_value,
        candidate_source_ids,
        source_text_by_id,
    )
    if not source_ids:
        return None

    status = data.get("status", "active")
    if status not in {"active", "superseded", "deleted"}:
        status = "active"
    return {
        "id": make_memory_id(str(category), key),
        "category": category,
        "key": key,
        "value": cleaned_value,
        "source_message_ids": source_ids,
        "confidence": normalize_confidence(data.get("confidence")),
        "status": status,
    }


def memory_to_dict(memory: Any) -> dict[str, Any]:
    """Convert Pydantic models or dict-like fake outputs into a plain dict."""
    if isinstance(memory, dict):
        return dict(memory)
    dump = getattr(memory, "model_dump", None)
    if callable(dump):
        return dict(dump())
    legacy_dump = getattr(memory, "dict", None)
    if callable(legacy_dump):
        return dict(legacy_dump())
    return {}


def upsert_normalized_record(
    records: list[dict[str, Any]],
    record: dict[str, Any],
) -> None:
    """Upsert a normalized record by category/key."""
    for index, existing in enumerate(records):
        if existing["category"] == record["category"] and existing["key"] == record["key"]:
            records[index] = record
            return
    records.append(record)


def strip_message_id_markers(value: str) -> str:
    """Remove message-id hints if the model copied them into a memory value."""
    return re.sub(r"\[?message_id=\d+\]?\s*", "", value)
