from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from src.connection_guard import (
    ConnectionGuard,
    InferenceServerUnreachable,
    connection_guard_from_env,
)
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
)


StructuredMemoryCategory = Literal[
    "past_events",
    "user_experiences",
    "user_facts",
    "user_state",
    "user_preferences",
    "upcoming",
    "procedural",
    "corrections",
]

StructuredMemoryStatus = Literal["active", "superseded", "deleted"]

# ── TTL: system-assigned expiration computed post-extraction ──────────────
# The model never sees datetimes — it only categorizes. The system assigns
# expires_at = now() + TTL[category] after LangMem returns.
_CATEGORY_TTL_DAYS: dict[str, int | None] = {
    "past_events": None,  # permanent — only explicit supersession removes
    "user_experiences": None,  # permanent — accumulated skills don't expire
    "user_facts": 365,  # slowly-changing biographical facts
    "user_state": 90,  # transient emotional/situational states
    "user_preferences": 365,  # interaction/tool/style preferences
    "upcoming": 40,  # imminent future events
    "procedural": 365,  # reusable methods/instructions
    "corrections": 365,  # audit trail of corrections
}


def _compute_expires_at(category: str) -> str:
    """Return an ISO-8601 expiration timestamp or empty string for indefinite."""
    ttl_days = _CATEGORY_TTL_DAYS.get(category)
    if ttl_days is None:
        return ""
    from datetime import datetime, timedelta, timezone

    return (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat(timespec="seconds")


LANGMEM_STRUCTURED_MEMORY_INSTRUCTIONS = """Extract durable structured memory for this chat.

**CORE RULE — Atomicity**: ONE fact per memory. Split distinct, unrelated
claims into separate records. When unsure, split — granular records are
always safer than merged ones.

ONLY merge when the user expresses a single concept through explicit
contrast ("I'm not X, I'm very much Y"). In that case alone, capture the
priority as one memory:

WRONG (split):  [{"value": "not concerned about flavor"},
                  {"value": "concerned about health"}]
RIGHT (merged): [{"value": "The user prioritizes health over flavor
                    and eating experience"}]

Otherwise: split every distinct claim. "I'm a TUM student, this exam is
stressing me out, and I'll take it later this month" → three separate
memories, each with its own key.

Every memory must be self-contained enough to be understood without
re-reading the conversation. Preserve qualifiers ("compared to X", "about
the same as Y"), numbers, names, and concrete details. When in doubt,
extract.

**Categories — choose the single best fit**:

- **past_events**: Something that happened — a completed event, a historical
  fact. These are permanently true. "I took the ML exam in August 2024."
  "We deployed the feature last Tuesday." "I visited Japan in 2019."
  ONLY for events that already occurred.

- **user_experiences**: Accumulated skills, expertise, or lived experience
  that defines who the user is. "I have 5 years of Python experience."
  "I studied at TUM." "I've been using Kubernetes since v1.12."
  Different from past_events: experiences are durable identity traits,
  not specific occurrences.

- **user_facts**: Slowly-changing biographical facts and durable plans.
  "I live in Munich." "I'm a TUM student." "I work at Acme Corp."
  Also: future events more than ~40 days away or without a specific date.
  "I'm starting a PhD next year." "We're launching the product in Q3."

- **user_state**: Transient emotional, physical, or situational state.
  "I'm stressed about the exam." "I'm tired today." "I'm in the middle
  of a move." These will pass. Use this instead of user_facts when the
  condition is clearly temporary.

- **user_preferences**: How the user likes things done — communication
  style, tool choices, interaction format. "User prefers concise answers."
  "User likes dark mode." "User prefers Python over TypeScript."
  Distinguisher: preferences are "I like X" / "do X for me";
  user_facts are "I am X" / "X is true about me".

- **upcoming**: Imminent future events with a specific timeframe.
  "I have an exam later this month." "Meeting at 3pm tomorrow."
  "I fly out next Monday." ONLY when the event is within ~40 days.
  If explicitly further out, use user_facts instead.

- **procedural**: Reusable step-by-step methods or instructions.
  "To deploy: run docker compose up then access port 8080."
  "The build process: npm install, npm run build, npm test."

- **corrections**: ONLY when the user explicitly contradicts a
  previously-stated fact. Always output TWO records: the correction AND
  an upsert with the corrected value in the original category.
  "User corrected vitamin B claim from 'similar to meat' to 'more than
  meat'."

**Temporal awareness**: Choose the category that matches the expected
lifetime of the fact. Transient states go to user_state (cleans up
automatically). Historical events go to past_events (permanent). Future
events within a month go to upcoming (cleans up after they pass).

**Implicit inference**: Connect explicit evidence to draw reasonable
conclusions. "This is my exam sheet from last year" + document context
→ "User took the ML for Graphs exam in August 2024" (past_events).
"I'll be sitting this exam later this month" → "User has the ML for
Graphs exam this month" (upcoming). This is inference from evidence,
not hallucination. Do NOT guess without supporting evidence.

**Keys**: Stable snake_case keys reflecting the TOPIC, not the phrasing.
Same concept = same key across turns. Examples: "ml_graphs_exam_stress",
"prefers_concise_answers", "tum_student_status", "database_choice".

**Corrections and supersession**:

When the user corrects a previous statement: update the original memory in
its existing category using the same key AND output a separate corrections
entry noting what changed. Set the original's status to "superseded",
the corrected value to "active".

When the user strengthens a previous claim with new evidence without
contradicting it: update the value and optionally recategorize (e.g. from
user_state to user_facts if it turns out to be durable). Use the same key.
Do NOT output a corrections entry — the foundation changed, not the claim.

Include source_message_ids for every memory when you can identify which
messages support it. Include a confidence score (0.0–1.0) reflecting how
certain you are the memory is correct and durable.
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
        *,
        connection_guard: ConnectionGuard | None = None,
    ) -> None:
        self._manager = manager
        self._config = config or LangMemBackendConfig.from_env()
        self._long_term_store = long_term_store
        self._guard = connection_guard or connection_guard_from_env()
        self.last_saved_records: list[LongTermMemoryWrite] = []
        self.last_drops: list[dict[str, Any]] = []

    def update(
        self,
        existing_memory: dict[str, list[dict[str, Any]]],
        messages: list[StoredMessage],
    ) -> MemoryUpdateResult:
        """Use LangMem output and normalize it into this app's memory record format."""
        normalized_memory = normalize_memory_state(existing_memory)
        self.last_saved_records = []
        self.last_drops: list[dict[str, Any]] = []
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
            self._guard.check()
        except InferenceServerUnreachable as exc:
            return MemoryUpdateResult(
                memory_state={"memories": combined_existing_records},
                accepted=False,
                rejection_reason=f"langmem_update_failed:{exc.__class__.__name__}",
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

        records, drops = normalize_langmem_outputs(
            extracted=extracted,
            allowed_source_ids=allowed_source_ids,
            source_text_by_id=source_text_by_id,
        )
        self.last_drops = drops
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

    _langmem_timeout = float(os.environ.get("MODEL_REQUEST_TIMEOUT", "35"))
    model = ChatOpenAI(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
        model=config.model_name,
        temperature=0.0,
        request_timeout=_langmem_timeout,
        max_retries=0,
        stream_chunk_timeout=_langmem_timeout,
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Normalize LangMem outputs. Returns (records, drops)."""
    records: list[dict[str, Any]] = []
    drops: list[dict[str, Any]] = []
    for item in extracted:
        memory = extract_memory_content(item)
        if memory is None:
            drops.append(_make_drop_entry(item, "empty_content"))
            continue

        record, drop_reason = normalize_langmem_memory(memory, allowed_source_ids, source_text_by_id)
        if record is not None:
            upsert_normalized_record(records, record)
        else:
            data = memory_to_dict(memory) if not isinstance(memory, dict) else dict(memory)
            drops.append({
                "category": data.get("category", "unknown"),
                "key": str(data.get("key", "")),
                "value": str(data.get("value", ""))[:200],
                "drop_reason": drop_reason or "unknown",
            })
    return records, drops


def _make_drop_entry(item: Any, reason: str) -> dict[str, Any]:
    data = memory_to_dict(item) if not isinstance(item, dict) else dict(item)
    return {
        "category": data.get("category", "unknown"),
        "key": str(data.get("key", "")),
        "value": str(data.get("value", ""))[:200],
        "drop_reason": reason,
    }


def extract_memory_content(item: Any) -> Any | None:
    """Read memory content from LangMem ExtractedMemory, Pydantic models, or dicts."""
    if hasattr(item, "content"):
        return getattr(item, "content")
    return item


def normalize_langmem_memory(
    memory: Any,
    allowed_source_ids: set[int],
    source_text_by_id: dict[int, str],
) -> tuple[dict[str, Any] | None, str | None]:
    """Validate one LangMem memory.

    Returns (record, None) if valid, (None, drop_reason) if dropped.
    """
    data = memory_to_dict(memory)
    category = data.get("category")
    key = normalize_key(data.get("key"))
    value = data.get("value")
    if category not in MEMORY_CATEGORIES:
        return None, "invalid_category"
    if not key or not isinstance(value, str) or not value.strip():
        return None, "missing_key_or_value"

    cleaned_value = clean_text(strip_message_id_markers(value))
    if looks_like_transcript_text(cleaned_value):
        return None, "transcript_text"
    if is_vague_memory(cleaned_value):
        return None, "vague_memory"

    source_ids = [
        source_id
        for source_id in data.get("source_message_ids", [])
        if isinstance(source_id, int) and source_id in allowed_source_ids
    ]
    if not source_ids:
        source_ids = list(allowed_source_ids)

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
    }, None


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
