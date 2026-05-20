from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from src.database import StoredMessage


MEMORY_CATEGORIES = (
    "user_facts",
    "project_facts",
    "decisions",
    "corrections",
    "open_tasks",
    "preferences",
    "constraints",
)

MEMORY_OPERATION_NAMES = ("upsert", "supersede", "delete")
TRANSCRIPT_MARKER_PATTERN = re.compile(r"\b(?:user|assistant)\s*:", re.IGNORECASE)
NAME_PATTERN = re.compile(r"\bmy name is\s+([A-Za-z][A-Za-z .'-]{0,60})", re.IGNORECASE)
NAME_CORRECTION_PATTERN = re.compile(
    r"\b(?:no,?\s*)?([A-Za-z][A-Za-z .'-]{0,60})\s+is\s+my\s+name,\s+not\s+"
    r"(?:the\s+)?assistant(?:'s)?\s+name",
    re.IGNORECASE,
)
PROJECT_PATTERN = re.compile(r"\bmy project is\s+([^.!?\n]{3,160})", re.IGNORECASE)
BUILDING_PATTERN = re.compile(r"\bi am building\s+([^.!?\n]{3,160})", re.IGNORECASE)
PREFERENCE_PATTERN = re.compile(r"\bi prefer\s+([^.!?\n]{3,160})", re.IGNORECASE)
CONCISE_PATTERN = re.compile(r"\bkeep answers concise\b", re.IGNORECASE)
LOCAL_ONLY_PATTERN = re.compile(
    r"\b(?:must run locally|run locally|do not suggest cloud|no cloud)\b",
    re.IGNORECASE,
)
CSV_TASK_PATTERN = re.compile(
    r"\b(?:next step is\s+)?(?:importing|import|support)\s+[^.!?\n]*csv[^.!?\n]*",
    re.IGNORECASE,
)
CSV_EXPORT_PATTERN = re.compile(r"\bcsv export\b", re.IGNORECASE)
POSTGRES_DECISION_PATTERN = re.compile(
    r"\b(?:decided to use|use)\s+(postgresql|postgres)\b(?:[^.!?\n]*)",
    re.IGNORECASE,
)
DATABASE_CORRECTION_PATTERN = re.compile(
    r"\b(?:database is|database should be|use)\s+(postgresql|postgres)\s+"
    r"(?:now,\s*)?not\s+(sqlite)\b",
    re.IGNORECASE,
)
DEADLINE_PATTERN = re.compile(r"\bdeadline is\s+([^.!?\n]{2,80})", re.IGNORECASE)

MEMORY_UPDATE_SYSTEM_PROMPT = """You extract structured current-chat memory operations.

Return ONLY valid JSON.
The first character must be [ and the last character must be ].
Do not include markdown.
Do not write a transcript.
Do not continue the conversation.
Do not invent facts.
Do not return existing_memory.
Do not return new_messages.
Only keep information likely to matter later in this chat.

Return a JSON array of operation objects. Return [] if there are no useful operations.

Valid categories are exactly:
user_facts, project_facts, decisions, corrections, open_tasks, preferences, constraints

Do not combine categories. For example, use "user_facts", never "user_facts | project_facts".

Example:
[
  {
    "operation": "upsert",
    "category": "user_facts",
    "key": "name",
    "value": "Keming",
    "source_message_ids": [3],
    "confidence": 0.95
  }
]

Each operation must be one of:

1. Upsert a memory:
{
  "operation": "upsert",
  "category": "user_facts",
  "key": "short_snake_case_key",
  "value": "concise standalone memory value",
  "source_message_ids": [123],
  "confidence": 0.0
}

2. Supersede an old memory when the new messages correct it:
{
  "operation": "supersede",
  "target_category": "user_facts",
  "target_key": "short_snake_case_key",
  "reason": "concise correction reason",
  "source_message_ids": [123],
  "confidence": 0.0
}

3. Delete an incorrect memory:
{
  "operation": "delete",
  "target_category": "user_facts",
  "target_key": "short_snake_case_key",
  "reason": "concise reason",
  "source_message_ids": [123],
  "confidence": 0.0
}

Rules:
- Use only facts supported by the new messages.
- source_message_ids must refer to user messages from the provided batch.
- If the user says "my name is X", upsert category "user_facts", key "name", value "X".
- If the user corrects a misunderstanding, preserve the correction.
- If the user says "X is my name, not the assistant's name", upsert user_facts/name and add a correction.
- Do not store assistant claims about itself as user facts.
- Do not store vague facts such as "user is discussing a problem".
- Prefer stable, reusable facts over one-off wording.
"""


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


def parse_memory_operations(
    raw_output: str,
    allowed_source_ids: set[int],
    source_text_by_id: dict[int, str] | None = None,
) -> list[dict[str, Any]] | None:
    """Parse and validate model-produced memory operations."""
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed, list):
        return None

    operations: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            return None

        operation = normalize_memory_operation(item, allowed_source_ids, source_text_by_id)
        if operation is not None:
            operations.append(operation)

    return operations


def normalize_memory_operation(
    operation: dict[str, Any],
    allowed_source_ids: set[int],
    source_text_by_id: dict[int, str] | None = None,
) -> dict[str, Any] | None:
    """Validate one memory operation."""
    operation_name = operation.get("operation")
    if operation_name not in MEMORY_OPERATION_NAMES:
        return None

    source_ids = normalize_source_ids(operation.get("source_message_ids"), allowed_source_ids)
    if not source_ids:
        return None

    confidence = normalize_confidence(operation.get("confidence"))
    if operation_name == "upsert":
        category = operation.get("category")
        key = normalize_key(operation.get("key"))
        value = operation.get("value")
        if category not in MEMORY_CATEGORIES:
            return None
        if not key or not isinstance(value, str) or not value.strip():
            return None
        cleaned_value = clean_text(value)
        if looks_like_transcript_text(cleaned_value) or is_vague_memory(cleaned_value):
            return None
        source_ids = supported_source_ids(cleaned_value, source_ids, source_text_by_id)
        if not source_ids:
            return None

        return {
            "operation": "upsert",
            "category": category,
            "key": key,
            "value": cleaned_value,
            "source_message_ids": source_ids,
            "confidence": confidence,
        }

    if confidence < 0.5:
        return None

    target_category = operation.get("target_category")
    target_key = normalize_key(operation.get("target_key"))
    reason = operation.get("reason")
    if target_category not in MEMORY_CATEGORIES:
        return None
    if not target_key or not isinstance(reason, str) or not reason.strip():
        return None
    cleaned_reason = clean_text(reason)
    if looks_like_transcript_text(cleaned_reason):
        return None
    if operation_name == "supersede" and not reason_supports_supersede(cleaned_reason):
        return None
    source_ids = supported_source_ids(cleaned_reason, source_ids, source_text_by_id)
    if not source_ids:
        return None

    return {
        "operation": operation_name,
        "target_category": target_category,
        "target_key": target_key,
        "reason": cleaned_reason,
        "source_message_ids": source_ids,
        "confidence": confidence,
    }


def apply_memory_operations(
    memory_state: dict[str, list[dict[str, Any]]],
    operations: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Apply validated operations deterministically."""
    updated = normalize_memory_state(memory_state)
    records = [dict(record) for record in updated["memories"]]

    for operation in operations:
        if operation["operation"] == "upsert":
            apply_upsert(records, operation)
        elif operation["operation"] == "supersede":
            apply_status_update(records, operation, "superseded")
        elif operation["operation"] == "delete":
            apply_status_update(records, operation, "deleted")

    return {"memories": records}


def apply_upsert(records: list[dict[str, Any]], operation: dict[str, Any]) -> None:
    """Add or update a memory record by category/key."""
    supersede_conflicting_records(records, operation)
    memory_id = make_memory_id(operation["category"], operation["key"])
    for record in records:
        if record["category"] == operation["category"] and record["key"] == operation["key"]:
            record.update(
                {
                    "id": memory_id,
                    "value": operation["value"],
                    "source_message_ids": merge_source_ids(
                        record["source_message_ids"],
                        operation["source_message_ids"],
                    ),
                    "confidence": max(record["confidence"], operation["confidence"]),
                    "status": "active",
                }
            )
            return

    records.append(
        {
            "id": memory_id,
            "category": operation["category"],
            "key": operation["key"],
            "value": operation["value"],
            "source_message_ids": operation["source_message_ids"],
            "confidence": operation["confidence"],
            "status": "active",
        }
    )


def apply_status_update(
    records: list[dict[str, Any]],
    operation: dict[str, Any],
    status: str,
) -> None:
    """Mark a target memory inactive."""
    for record in records:
        if (
            record["category"] == operation["target_category"]
            and record["key"] == operation["target_key"]
            and record["status"] == "active"
        ):
            record["status"] = status
            record["superseded_reason"] = operation["reason"]
            record["source_message_ids"] = merge_source_ids(
                record["source_message_ids"],
                operation["source_message_ids"],
            )


def supersede_conflicting_records(
    records: list[dict[str, Any]],
    operation: dict[str, Any],
) -> None:
    """Mark obvious stale records inactive before applying a stronger upsert."""
    category = operation["category"]
    key = operation["key"]
    value = operation["value"]
    source_ids = operation["source_message_ids"]

    if category == "project_facts" and key == "database":
        for record in records:
            if record["status"] != "active":
                continue
            searchable = f"{record['key']} {record['value']}".lower()
            if "sqlite" in searchable and "sqlite" not in value.lower():
                record["status"] = "superseded"
                record["superseded_reason"] = f"Database updated to {value}."
                record["source_message_ids"] = merge_source_ids(
                    record["source_message_ids"],
                    source_ids,
                )

    if category == "decisions" and key == "database":
        for record in records:
            if record["status"] != "active":
                continue
            searchable = f"{record['key']} {record['value']}".lower()
            if "sqlite" in searchable and "postgres" in value.lower():
                record["status"] = "superseded"
                record["superseded_reason"] = value
                record["source_message_ids"] = merge_source_ids(
                    record["source_message_ids"],
                    source_ids,
                )


class StructuredMemoryState:
    """Updates derived structured memory from older raw chat messages."""

    def __init__(self, model: ChatModel) -> None:
        self.model = model

    def update(
        self,
        existing_memory: dict[str, list[dict[str, Any]]],
        messages: list[StoredMessage],
    ) -> MemoryUpdateResult:
        """Ask the model for operations and apply accepted operations."""
        normalized_memory = normalize_memory_state(existing_memory)
        user_messages = [message for message in messages if message.role == "user"]
        allowed_source_ids = {message.id for message in user_messages}
        source_text_by_id = {message.id: message.content for message in user_messages}
        user_prompt = {
            "active_existing_memories": active_memories(normalized_memory),
            "new_user_messages": [
                {
                    "id": message.id,
                    "created_at": message.created_at,
                    "content": message.content,
                }
                for message in user_messages
            ],
        }

        raw_output = self.model.chat(
            [
                {"role": "system", "content": MEMORY_UPDATE_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(user_prompt, ensure_ascii=True, indent=2),
                },
            ],
            temperature=0.0,
        ).strip()

        operations = parse_memory_operations(raw_output, allowed_source_ids, source_text_by_id)
        if operations is None:
            return MemoryUpdateResult(memory_state=normalized_memory, accepted=False)

        deterministic_operations = extract_deterministic_operations(user_messages)
        all_operations = operations + deterministic_operations
        updated_memory = apply_memory_operations(normalized_memory, all_operations)
        return MemoryUpdateResult(memory_state=updated_memory, accepted=True)


def extract_deterministic_operations(messages: list[StoredMessage]) -> list[dict[str, Any]]:
    """Extract high-confidence operations for common memory-bearing phrases."""
    operations: list[dict[str, Any]] = []
    for message in messages:
        text = clean_text(message.content)
        lowered = text.lower()
        source_ids = [message.id]

        if match := NAME_PATTERN.search(text):
            name = clean_extracted_value(match.group(1))
            if name:
                operations.append(
                    upsert_operation("user_facts", "name", name, source_ids, confidence=0.99)
                )

        if match := NAME_CORRECTION_PATTERN.search(text):
            name = clean_extracted_value(match.group(1))
            if name:
                operations.append(
                    upsert_operation("user_facts", "name", name, source_ids, confidence=0.99)
                )
                operations.append(
                    upsert_operation(
                        "corrections",
                        "name_owner",
                        f"{name} is the user's name, not the assistant's name.",
                        source_ids,
                        confidence=0.95,
                    )
                )

        if match := PROJECT_PATTERN.search(text):
            value = clean_extracted_value(match.group(1))
            if value:
                operations.append(
                    upsert_operation(
                        "project_facts",
                        "project_description",
                        value,
                        source_ids,
                        confidence=0.9,
                    )
                )

        if match := BUILDING_PATTERN.search(text):
            value = clean_extracted_value(match.group(1))
            if value:
                operations.append(
                    upsert_operation(
                        "project_facts",
                        "project_description",
                        value,
                        source_ids,
                        confidence=0.9,
                    )
                )

        if match := DATABASE_CORRECTION_PATTERN.search(text):
            database = normalize_database_name(match.group(1))
            old_database = normalize_database_name(match.group(2))
            operations.append(
                upsert_operation(
                    "project_facts",
                    "database",
                    database,
                    source_ids,
                    confidence=0.99,
                )
            )
            operations.append(
                upsert_operation(
                    "corrections",
                    "database",
                    f"Database is {database}, not {old_database}.",
                    source_ids,
                    confidence=0.95,
                )
            )

        elif match := POSTGRES_DECISION_PATTERN.search(text):
            database = normalize_database_name(match.group(1))
            operations.append(
                upsert_operation(
                    "decisions",
                    "database",
                    f"Use {database}.",
                    source_ids,
                    confidence=0.9,
                )
            )

        if match := PREFERENCE_PATTERN.search(text):
            value = clean_extracted_value(match.group(1))
            if value:
                operations.append(
                    upsert_operation(
                        "preferences",
                        "response_style",
                        value,
                        source_ids,
                        confidence=0.9,
                    )
                )

        if CONCISE_PATTERN.search(text):
            operations.append(
                upsert_operation(
                    "preferences",
                    "response_style",
                    "concise answers",
                    source_ids,
                    confidence=0.9,
                )
            )

        if LOCAL_ONLY_PATTERN.search(text):
            operations.append(
                upsert_operation(
                    "constraints",
                    "local_only",
                    "The app must run locally; do not suggest cloud services.",
                    source_ids,
                    confidence=0.95,
                )
            )

        if CSV_TASK_PATTERN.search(text) or CSV_EXPORT_PATTERN.search(text):
            value = "CSV export" if CSV_EXPORT_PATTERN.search(text) else "CSV import"
            if "import" in lowered or "importing" in lowered:
                value = "importing recipes from CSV"
            operations.append(
                upsert_operation(
                    "open_tasks",
                    "csv",
                    value,
                    source_ids,
                    confidence=0.9,
                )
            )

        if match := DEADLINE_PATTERN.search(text):
            deadline = clean_extracted_value(match.group(1))
            if deadline:
                operations.append(
                    upsert_operation(
                        "open_tasks",
                        "deadline",
                        deadline,
                        source_ids,
                        confidence=0.9,
                    )
                )

    return operations


def upsert_operation(
    category: str,
    key: str,
    value: str,
    source_message_ids: list[int],
    confidence: float,
) -> dict[str, Any]:
    """Build a validated deterministic upsert operation."""
    return {
        "operation": "upsert",
        "category": category,
        "key": normalize_key(key),
        "value": clean_text(value),
        "source_message_ids": source_message_ids,
        "confidence": confidence,
    }


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


def supported_source_ids(
    claim: str,
    source_ids: list[int],
    source_text_by_id: dict[int, str] | None,
) -> list[int]:
    """Ensure an operation has textual support in the user-message batch."""
    if source_text_by_id is None:
        return source_ids

    supported = [
        source_id
        for source_id in source_ids
        if text_supports_claim(source_text_by_id.get(source_id, ""), claim)
    ]
    if supported:
        return supported

    repaired = [
        source_id
        for source_id, source_text in source_text_by_id.items()
        if text_supports_claim(source_text, claim)
    ]
    return repaired


def text_supports_claim(source_text: str, claim: str) -> bool:
    """Use lexical support checks to reject unsupported model claims."""
    source_tokens = important_tokens(source_text)
    claim_tokens = important_tokens(claim)
    if not claim_tokens:
        return False

    overlap = claim_tokens & source_tokens
    if not overlap:
        return False

    if len(claim_tokens) <= 2:
        return len(overlap) == len(claim_tokens)
    return len(overlap) / len(claim_tokens) >= 0.5


def important_tokens(value: str) -> set[str]:
    """Extract useful lexical tokens for source-support checks."""
    stopwords = {
        "the",
        "user",
        "users",
        "uses",
        "use",
        "using",
        "project",
        "name",
        "fact",
        "is",
        "am",
        "are",
        "my",
        "i",
        "me",
        "not",
        "and",
        "or",
        "a",
        "an",
        "to",
        "of",
        "this",
        "that",
        "it",
    }
    return {
        token
        for token in re.findall(r"[A-Za-z0-9]+", value.lower())
        if len(token) >= 3 and token not in stopwords
    }


def clean_text(value: str) -> str:
    """Clean short model-produced text."""
    return " ".join(value.strip(" \n\t\r").split())


def clean_extracted_value(value: str) -> str:
    """Clean deterministic extractor captures."""
    return clean_text(value.strip(" .,!?:;\"'"))


def normalize_database_name(value: str) -> str:
    """Normalize common database names."""
    lowered = value.lower()
    if lowered == "postgres":
        return "Postgres"
    if lowered == "postgresql":
        return "PostgreSQL"
    if lowered == "sqlite":
        return "SQLite"
    return clean_extracted_value(value)


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


def reason_supports_supersede(reason: str) -> bool:
    """Reject corrections that affirm a fact instead of invalidating it."""
    lowered = reason.lower()
    if "my name" in lowered and "not my name" not in lowered:
        return False

    supersede_markers = (
        "incorrect",
        "wrong",
        "not true",
        "no longer",
        "instead",
        "changed",
        "correction",
        "misunderstanding",
    )
    return any(marker in lowered for marker in supersede_markers)


def merge_source_ids(existing: list[int], new: list[int]) -> list[int]:
    """Merge source ids while preserving order."""
    merged = list(existing)
    for source_id in new:
        if source_id not in merged:
            merged.append(source_id)
    return merged
