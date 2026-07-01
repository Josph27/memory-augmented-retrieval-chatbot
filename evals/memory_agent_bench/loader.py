from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from evals.memory_agent_bench.schemas import MABenchExample, MABenchSession


def load_examples(path: Path, limit: int | None = None) -> list[MABenchExample]:
    """Load normalized or common MemoryAgentBench-style JSON/JSONL records."""
    records = _load_records(path)
    examples = [normalize_record(record) for record in records]
    return examples[:limit] if limit is not None else examples


def normalize_record(
    record: dict[str, Any],
    *,
    competency: str | None = None,
    example_index: int | None = None,
    question_limit: int | None = None,
    context_chunk_chars: int = 4000,
) -> MABenchExample:
    """Normalize a flexible external record into the internal adapter schema."""
    record_metadata = record.get("metadata")
    metadata = dict(record_metadata) if isinstance(record_metadata, dict) else {}
    source = str(metadata.get("source") or "memory-agent-bench")
    example_id = str(
        record.get("example_id")
        or record.get("id")
        or record.get("question_id")
        or (
            f"{source}-row-{example_index + 1}"
            if example_index is not None
            else ""
        )
    )
    selected_competency = str(
        competency
        or record.get("competency")
        or record.get("ability")
        or record.get("question_type")
        or "unknown"
    )
    sessions = _normalize_sessions(record, context_chunk_chars=context_chunk_chars)
    questions = _as_string_tuple(record.get("questions") or record.get("question"))
    raw_answers = record.get("answers")
    if raw_answers is None:
        raw_answers = record.get("answer")
    answers = _normalize_answers(raw_answers, len(questions))
    if question_limit is not None:
        questions = questions[:question_limit]
        answers = answers[:question_limit]
    metadata.update(
        {
            "adapter_context_chunk_chars": context_chunk_chars,
            "adapter_context_chunk_count": sum(
                len(session.chunks) for session in sessions
            ),
        }
    )
    return MABenchExample(
        example_id=example_id,
        competency=selected_competency,
        sessions=sessions,
        questions=questions,
        answers=answers,
        metadata=metadata,
    )


def load_huggingface_examples(
    dataset_name: str,
    *,
    split: str = "Conflict_Resolution",
    limit: int | None = None,
    question_limit: int | None = None,
    context_chunk_chars: int = 4000,
) -> list[MABenchExample]:
    """Stream a bounded external subset without a hard dependency."""
    try:
        from datasets import load_dataset
    except ImportError as error:
        raise RuntimeError(
            "Hugging Face dataset loading requires the optional 'datasets' package."
        ) from error

    dataset = load_dataset(dataset_name, split=split, streaming=True)
    examples: list[MABenchExample] = []
    for index, row in enumerate(dataset):
        examples.append(
            normalize_record(
                dict(row),
                competency=split,
                example_index=index,
                question_limit=question_limit,
                context_chunk_chars=context_chunk_chars,
            )
        )
        if limit is not None and len(examples) >= limit:
            break
    return examples


def _load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        records: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError(f"Expected object at {path}:{line_number}")
                records.append(value)
        return records

    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("examples") or value.get("data") or [value]
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"Expected a JSON object or list of objects in {path}")
    return list(value)


def _normalize_sessions(
    record: dict[str, Any],
    *,
    context_chunk_chars: int,
) -> tuple[MABenchSession, ...]:
    raw_sessions = record.get("sessions")
    if raw_sessions is None:
        chunks = record.get("chunks")
        if chunks is None and isinstance(record.get("context"), str):
            chunks = split_context(
                record["context"],
                max_chars=context_chunk_chars,
            )
        raw_sessions = [{"session_id": "session-1", "chunks": chunks or []}]
    if not isinstance(raw_sessions, list):
        raise ValueError("MemoryAgentBench sessions must be a list.")

    sessions: list[MABenchSession] = []
    for index, raw_session in enumerate(raw_sessions):
        if isinstance(raw_session, dict):
            session_id = str(raw_session.get("session_id") or f"session-{index + 1}")
            chunks = raw_session.get("chunks") or raw_session.get("history") or []
        else:
            session_id = f"session-{index + 1}"
            chunks = raw_session
        sessions.append(
            MABenchSession(
                session_id=session_id,
                chunks=_chunks_to_strings(chunks),
            )
        )
    return tuple(sessions)


def split_context(context: str, max_chars: int = 4000) -> list[str]:
    """Split official long contexts into bounded incremental replay chunks."""
    if max_chars < 100:
        raise ValueError("context_chunk_chars must be at least 100")
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", context)
        if paragraph.strip()
    ]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        remaining = paragraph
        while remaining:
            available = max_chars - len(current) - (2 if current else 0)
            if available <= 0:
                chunks.append(current)
                current = ""
                continue
            if len(remaining) <= available:
                current = f"{current}\n\n{remaining}".strip()
                remaining = ""
                continue
            if current:
                chunks.append(current)
                current = ""
                continue
            chunks.append(remaining[:max_chars])
            remaining = remaining[max_chars:].lstrip()
    if current:
        chunks.append(current)
    return chunks


def _chunks_to_strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, list):
        raise ValueError("MemoryAgentBench chunks must be a string or list.")
    chunks: list[str] = []
    for chunk in value:
        if isinstance(chunk, str):
            chunks.append(chunk)
        elif isinstance(chunk, dict):
            role = str(chunk.get("role") or "user")
            content = str(chunk.get("content") or chunk.get("text") or "")
            chunks.append(f"{role}: {content}" if role != "user" else content)
        else:
            chunks.append(str(chunk))
    return tuple(chunks)


def _as_string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable) and not isinstance(value, dict):
        return tuple(str(item) for item in value)
    return ()


def _normalize_answers(value: Any, question_count: int) -> tuple[tuple[str, ...], ...]:
    if question_count == 1:
        if isinstance(value, str):
            return ((value,),)
        if isinstance(value, list) and all(isinstance(item, str) for item in value):
            return (tuple(value),)
    if not isinstance(value, list):
        return ()
    normalized = []
    for answer in value:
        if isinstance(answer, str):
            normalized.append((answer,))
        elif isinstance(answer, list):
            normalized.append(tuple(str(item) for item in answer))
        else:
            normalized.append((str(answer),))
    return tuple(normalized)
