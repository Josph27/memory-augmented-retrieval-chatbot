from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from evals.longmemeval_adapter.schema import (
    HistoryMessage,
    HistorySession,
    LongMemEvalCase,
)


def load_longmemeval_cases(
    path: Path,
    limit: int | None = None,
) -> list[LongMemEvalCase]:
    """Load JSON/JSONL records and normalize common LongMemEval-style fields."""
    records = load_records(path)
    cases: list[LongMemEvalCase] = []
    for index, record in enumerate(records):
        cases.append(normalize_record(record, index=index))
        if limit is not None and len(cases) >= limit:
            break
    return cases


def load_records(path: Path) -> list[dict[str, Any]]:
    """Read either a JSON array or newline-delimited JSON objects."""
    if not path.exists():
        raise FileNotFoundError(f"Benchmark dataset does not exist: {path}")
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return []
    if path.suffix.casefold() == ".json":
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("LongMemEval JSON input must contain a list of records.")
        return [require_mapping(row, path, index + 1) for index, row in enumerate(payload)]

    records = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        records.append(require_mapping(json.loads(line), path, line_number))
    return records


def normalize_record(record: dict[str, Any], index: int = 0) -> LongMemEvalCase:
    """Convert normalized or common LongMemEval-style fields into one case."""
    case_id = first_text(record, "case_id", "question_id", "id") or f"case-{index + 1}"
    question = first_text(record, "question", "query")
    gold_answer = normalize_answer(
        first_present(record, "gold_answer", "answer", "ground_truth")
    )
    question_type = first_text(record, "question_type", "ability_type", "task_type")
    raw_sessions = first_present(record, "sessions", "history", "haystack_sessions")
    sessions = normalize_sessions(
        raw_sessions,
        session_ids=record.get("haystack_session_ids"),
        session_dates=record.get("haystack_dates"),
    )
    evidence = normalize_text_list(
        first_present(record, "expected_evidence", "gold_evidence", "evidence")
    )
    expected_abstain = bool(
        first_present(record, "expected_abstain", "should_abstain") or False
    )
    mock_answer = first_text(record, "mock_answer")
    consumed = {
        "case_id",
        "question_id",
        "id",
        "question",
        "query",
        "gold_answer",
        "answer",
        "ground_truth",
        "question_type",
        "ability_type",
        "task_type",
        "sessions",
        "history",
        "haystack_sessions",
        "expected_evidence",
        "gold_evidence",
        "evidence",
        "expected_abstain",
        "should_abstain",
        "mock_answer",
        "metadata",
    }
    metadata = dict(record.get("metadata") or {})
    metadata.update({key: value for key, value in record.items() if key not in consumed})
    return LongMemEvalCase(
        case_id=case_id,
        question=question,
        gold_answer=gold_answer,
        question_type=question_type,
        sessions=tuple(sessions),
        expected_evidence=tuple(evidence),
        expected_abstain=expected_abstain,
        mock_answer=mock_answer,
        metadata=metadata,
    )


def normalize_sessions(
    raw_sessions: Any,
    session_ids: Any = None,
    session_dates: Any = None,
) -> list[HistorySession]:
    """Normalize nested sessions and flat message histories."""
    if not isinstance(raw_sessions, list) or not raw_sessions:
        raise ValueError("LongMemEval record requires non-empty sessions/history.")
    if all(is_message_like(item) for item in raw_sessions):
        raw_sessions = [{"session_id": "session-1", "messages": raw_sessions}]

    sessions = []
    for index, raw_session in enumerate(raw_sessions):
        session_id = parallel_text(session_ids, index) or f"session-{index + 1}"
        metadata: dict[str, Any] = {}
        session_date = parallel_text(session_dates, index)
        if session_date:
            metadata["date"] = session_date
        messages_raw = raw_session
        if isinstance(raw_session, dict):
            session_id = str(
                raw_session.get("session_id")
                or raw_session.get("id")
                or raw_session.get("date")
                or session_id
            )
            messages_raw = (
                raw_session.get("messages")
                or raw_session.get("turns")
                or raw_session.get("conversation")
            )
            metadata.update(dict(raw_session.get("metadata") or {}))
        if not isinstance(messages_raw, list):
            raise ValueError(f"Session {session_id!r} must contain a message list.")
        messages = tuple(
            message
            for message in (
                normalize_message(raw_message) for raw_message in messages_raw
            )
            if message is not None
        )
        if not messages:
            raise ValueError(f"Session {session_id!r} has no non-empty messages.")
        sessions.append(
            HistorySession(
                session_id=session_id,
                messages=messages,
                metadata=metadata,
            )
        )
    return sessions


def normalize_message(raw_message: Any) -> HistoryMessage | None:
    """Normalize role/content aliases used by conversation datasets."""
    if isinstance(raw_message, str):
        return HistoryMessage(role="user", content=raw_message)
    if not isinstance(raw_message, dict):
        raise ValueError("History messages must be objects or strings.")
    role = str(
        raw_message.get("role")
        or raw_message.get("speaker")
        or raw_message.get("from")
        or "user"
    ).casefold()
    role_aliases = {
        "human": "user",
        "person": "user",
        "bot": "assistant",
        "ai": "assistant",
        "agent": "assistant",
    }
    role = role_aliases.get(role, role)
    content = str(
        raw_message.get("content")
        or raw_message.get("text")
        or raw_message.get("message")
        or ""
    )
    if not content.strip():
        return None
    created_at = ""
    for key in ("created_at", "timestamp", "time", "datetime", "date"):
        value = raw_message.get(key)
        if value is not None and str(value).strip():
            created_at = str(value)
            break
    return HistoryMessage(
        role=role,
        content=content,
        created_at=created_at or None,
    )


def normalize_answer(value: Any) -> str:
    """Return one textual gold answer without claiming official scoring."""
    if isinstance(value, list):
        return str(next((item for item in value if str(item).strip()), ""))
    return str(value or "")


def normalize_text_list(value: Any) -> list[str]:
    """Normalize optional evidence strings."""
    if value is None:
        return []
    values: Iterable[Any] = value if isinstance(value, list) else [value]
    return [str(item) for item in values if str(item).strip()]


def first_present(record: dict[str, Any], *keys: str) -> Any:
    """Return the first present field, including false values."""
    for key in keys:
        if key in record:
            return record[key]
    return None


def first_text(record: dict[str, Any], *keys: str) -> str:
    """Return the first non-empty textual field."""
    for key in keys:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return ""


def is_message_like(value: Any) -> bool:
    """Return whether a value resembles one message rather than a session."""
    return isinstance(value, str) or (
        isinstance(value, dict)
        and any(key in value for key in ("role", "speaker", "content", "text", "message"))
    )


def require_mapping(value: Any, path: Path, line_number: int) -> dict[str, Any]:
    """Validate one source record."""
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object at {path}:{line_number}")
    return value


def parallel_text(values: Any, index: int) -> str:
    """Read one textual value from an optional parallel metadata list."""
    if not isinstance(values, list) or index >= len(values):
        return ""
    value = values[index]
    return str(value) if value is not None else ""
