from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol


MEMORY_CATEGORIES = (
    "past_events",
    "user_experiences",
    "user_facts",
    "user_state",
    "user_preferences",
    "upcoming",
    "procedural",
    "corrections",
    "third_party_facts",
    "opinions",
)

TRANSCRIPT_MARKER_PATTERN = re.compile(r"\b(?:user|assistant)\s*:", re.IGNORECASE)


class ChatModel(Protocol):
    """Small protocol for any OpenAI-compatible model wrapper."""

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Return assistant text for the supplied chat-completions messages."""
        ...


@dataclass(frozen=True)
class MemoryUpdateResult:
    """Result of a structured memory update attempt."""

    memory_state: dict[str, list[dict[str, Any]]]
    accepted: bool
    rejection_reason: str | None = None
    drops: list[dict[str, Any]] = field(default_factory=list)


def empty_memory_state() -> dict[str, list[dict[str, Any]]]:
    """Return a fresh empty memory state."""
    return {"memories": []}


def dumps_memory_state(memory_state: dict[str, list[dict[str, Any]]]) -> str:
    """Serialize memory state consistently for storage and prompting."""
    normalized = normalize_memory_state(memory_state)
    return json.dumps(normalized, ensure_ascii=True, sort_keys=True, indent=2)


def memory_state_is_empty(memory_state: dict[str, list[dict[str, Any]]]) -> bool:
    """Return whether there are any active memory records."""
    return not active_memories(memory_state)


def load_memory_state(memory_json: str | None) -> dict[str, list[dict[str, Any]]]:
    """Parse stored memory JSON, migrating older array schemas when needed."""
    if not memory_json:
        return empty_memory_state()

    try:
        parsed = json.loads(memory_json)
    except json.JSONDecodeError:
        return empty_memory_state()

    return normalize_memory_state(parsed)


def normalize_memory_state(value: Any) -> dict[str, list[dict[str, Any]]]:
    """Normalize current and legacy memory JSON into record format."""
    if not isinstance(value, dict):
        return empty_memory_state()

    if isinstance(value.get("memories"), list):
        records = [
            normalize_memory_record(record)
            for record in value["memories"]
            if isinstance(record, dict)
        ]
        return {"memories": [record for record in records if record is not None]}

    migrated: list[dict[str, Any]] = []
    for category in MEMORY_CATEGORIES:
        items = value.get(category, [])
        if not isinstance(items, list):
            continue

        for index, item in enumerate(items, start=1):
            if not isinstance(item, str) or not item.strip():
                continue
            migrated.append(
                {
                    "id": make_memory_id(category, f"legacy_{index}_{item}"),
                    "category": category,
                    "key": f"legacy_{index}",
                    "value": item.strip(),
                    "source_message_ids": [],
                    "confidence": 0.5,
                    "status": "active",
                }
            )

    return {"memories": migrated}


def normalize_memory_record(record: dict[str, Any]) -> dict[str, Any] | None:
    """Validate one stored memory record."""
    category = record.get("category")
    key = normalize_key(record.get("key"))
    value = record.get("value")
    status = record.get("status", "active")

    if category not in MEMORY_CATEGORIES:
        return None
    if not key or not isinstance(value, str) or not value.strip():
        return None
    if status not in {"active", "superseded", "deleted"}:
        status = "active"

    return {
        "id": str(record.get("id") or make_memory_id(category, key)),
        "category": category,
        "key": key,
        "value": clean_text(value),
        "source_message_ids": normalize_source_ids(record.get("source_message_ids"), None),
        "confidence": normalize_confidence(record.get("confidence")),
        "status": status,
    }


def active_memories(memory_state: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Return active memory records."""
    return [
        record
        for record in normalize_memory_state(memory_state)["memories"]
        if record["status"] == "active"
    ]


def format_memory_for_prompt(memory_state: dict[str, list[dict[str, Any]]]) -> str:
    """Format memory compactly for the chat model context."""
    memories = active_memories(memory_state)
    if not memories:
        return ""

    lines = []
    for record in sorted(memories, key=lambda item: (item["category"], item["key"])):
        lines.append(f"- {record['category']}.{record['key']}: {record['value']}")
    return "\n".join(lines)


def make_memory_id(category: str, key: str) -> str:
    """Create a stable memory id from category/key."""
    return f"{category}:{normalize_key(key)}"


def normalize_key(value: Any) -> str:
    """Normalize a model-provided key to short snake case."""
    if not isinstance(value, str):
        return ""

    key = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    key = re.sub(r"_+", "_", key)
    return key[:80]


def normalize_source_ids(value: Any, allowed_source_ids: set[int] | None) -> list[int]:
    """Validate source message ids."""
    if not isinstance(value, list):
        return []

    source_ids: list[int] = []
    for item in value:
        if not isinstance(item, int):
            continue
        if allowed_source_ids is not None and item not in allowed_source_ids:
            continue
        if item not in source_ids:
            source_ids.append(item)
    return source_ids


def normalize_confidence(value: Any) -> float:
    """Clamp confidence to [0.0, 1.0]."""
    if isinstance(value, int | float):
        return max(0.0, min(1.0, float(value)))
    return 0.5


def clean_text(value: str) -> str:
    """Clean short model-produced text."""
    return " ".join(value.strip(" \n\t\r").split())


def looks_like_transcript_text(value: str) -> bool:
    """Return whether a value appears to be copied transcript text."""
    return len(TRANSCRIPT_MARKER_PATTERN.findall(value)) >= 1


def is_vague_memory(value: str) -> bool:
    """Reject low-value generic memories."""
    lowered = value.lower()
    vague_phrases = (
        "the user is discussing",
        "the user asked a question",
        "the user has a problem",
        "the user wants help",
        "the user needs advice",
    )
    return any(phrase in lowered for phrase in vague_phrases)
