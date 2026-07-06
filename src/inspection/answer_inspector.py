from __future__ import annotations

import json
from typing import Any

from src.core.contracts import AgentTurnResult, MemoryCandidate
from src.database import Database


MAX_EXCERPT_CHARS = 280
MAX_SELECTED_ITEMS = 24
MAX_DROPPED_ITEMS = 24

SOURCE_LABELS = {
    "recent_messages": "Current/recent chat message",
    "current_chat_span": "Current/recent chat message",
    "structured_memory": "Structured memory",
    "previous_chat_gist": "Previous-chat gist",
    "current_chat_gist": "Previous-chat gist",
    "raw_message_span": "Raw-message span",
    "document_memory": "Document memory",
}


def build_answer_inspection(
    result: AgentTurnResult,
    database: Database,
) -> dict[str, Any]:
    """Serialize existing turn diagnostics into a bounded read-only payload."""
    trace = result.trace
    packet = trace.context_packet
    route_plan = trace.route_plan
    trace_metadata = trace.metadata if isinstance(trace.metadata, dict) else {}
    orchestration = object_dict(trace_metadata.get("orchestration"))
    graph_trace = object_dict(orchestration.get("langgraph_trace"))
    context_manager = object_dict(trace_metadata.get("context_manager"))
    packet_metadata = (
        packet.metadata if packet is not None and isinstance(packet.metadata, dict) else {}
    )
    selected = list(packet.candidates) if packet is not None else []
    allowed_document_ids = {
        document.id for document in database.documents_for_chat(result.chat_id)
    }
    selected_rows = [
        serialize_candidate(
            candidate,
            database=database,
            current_chat_id=result.chat_id,
            allowed_document_ids=allowed_document_ids,
            rank=index,
        )
        for index, candidate in enumerate(selected[:MAX_SELECTED_ITEMS], start=1)
    ]
    selected_rows = [row for row in selected_rows if row is not None]
    dropped = bounded_drop_rows(packet_metadata.get("dropped_candidates"))
    retrieval_errors = bounded_strings(trace_metadata.get("retrieval_errors"))
    selected_document_ids = {
        str(row["document_id"])
        for row in selected_rows
        if row.get("document_id")
    }
    considered_document_ids = {
        str(candidate.metadata.get("document_id"))
        for candidate in trace.retrieved_candidates
        if candidate.source == "document_memory"
        and candidate.metadata.get("document_id") in allowed_document_ids
    }
    document_ids = sorted(selected_document_ids | considered_document_ids)
    documents = []
    for document_id in document_ids:
        document = database.get_document(document_id)
        if document is None or document.id not in allowed_document_ids:
            continue
        documents.append(
            {
                "document_id": document.id,
                "filename": document.file_name,
                "status": document.status,
                "chunk_count": document.chunk_count,
                "selected": document.id in selected_document_ids,
            }
        )

    effective_mode = safe_scalar(orchestration.get("effective_mode"))
    requested_mode = safe_scalar(orchestration.get("requested_mode"))
    authoritative = safe_scalar(orchestration.get("authoritative_context"))
    graph_executed = requested_mode in {"langgraph_demo", "langgraph_shadow"}
    fallback_used = bool(orchestration.get("fallback_used"))
    evidence_validation = packet_metadata.get("evidence_contract_satisfied")
    if evidence_validation is None and graph_trace:
        evidence_validation = not bool(graph_trace.get("insufficient_evidence"))

    return {
        "version": 1,
        "assistant_message_id": result.assistant_message_id,
        "chat_id": result.chat_id,
        "trace_id": result.trace_id,
        "overview": {
            "requested_mode": requested_mode,
            "effective_mode": effective_mode,
            "authoritative_context": authoritative,
            "graph_executed": graph_executed,
            "native_fallback_used": fallback_used,
            "route": [
                source.source
                for source in (route_plan.sources if route_plan is not None else [])
                if source.enabled
            ],
            "route_intent": route_plan.intent if route_plan is not None else None,
            "context_profile": (
                route_plan.context_profile if route_plan is not None else None
            ),
        },
        "evidence_summary": {
            "retrieved_candidate_count": len(trace.retrieved_candidates),
            "reranked_candidate_count": len(trace.ranked_candidates),
            "selected_evidence_count": len(selected),
            "selected_context_tokens": first_int(
                context_manager.get("selected_memory_tokens"),
                context_manager.get("token_usage"),
                packet_metadata.get("selected_memory_tokens"),
                packet_metadata.get("source_token_usage_total"),
            ),
            "final_prompt_tokens": first_int(
                packet_metadata.get("final_prompt_tokens"),
                trace_metadata.get("estimated_prompt_tokens"),
                packet_metadata.get("estimated_prompt_tokens"),
            ),
            "evidence_validation": evidence_validation,
        },
        "selected_sources": selected_rows,
        "retrieval_diagnostics": {
            "document_fallback_used": (
                bool(graph_trace["document_fallback_used"])
                if "document_fallback_used" in graph_trace
                else None
            ),
            "retrieval_errors": retrieval_errors,
            "evidence_validation": evidence_validation,
            "dropped_candidate_count": len(
                packet_metadata.get("dropped_candidates", [])
                if isinstance(packet_metadata.get("dropped_candidates"), list)
                else []
            ),
            "dropped_candidates": dropped,
        },
        "documents": documents,
    }


def persist_answer_inspection(
    result: AgentTurnResult,
    database: Database,
) -> bool:
    """Best-effort persistence; observability must never block an answer."""
    if result.assistant_message_id is None:
        return False
    try:
        payload = build_answer_inspection(result, database)
        database.save_answer_inspection(
            assistant_message_id=result.assistant_message_id,
            chat_id=result.chat_id,
            trace_id=result.trace_id,
            payload=payload,
        )
    except Exception:
        return False
    return True


def inspection_rows_for_ui(database: Database, chat_id: str) -> list[dict[str, Any]]:
    """Load validated JSON records and join only their own assistant text."""
    assistant_messages = {
        message.id: message
        for message in database.messages_for_chat(chat_id)
        if message.role == "assistant"
    }
    rows: list[dict[str, Any]] = []
    for stored in database.answer_inspections_for_chat(chat_id):
        message = assistant_messages.get(stored.assistant_message_id)
        if message is None:
            continue
        try:
            payload = json.loads(stored.payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        payload = dict(payload)
        payload["assistant_message_id"] = stored.assistant_message_id
        payload["answer_text"] = message.content
        rows.append(payload)
    return rows


def serialize_candidate(
    candidate: MemoryCandidate,
    *,
    database: Database,
    current_chat_id: str,
    allowed_document_ids: set[str],
    rank: int,
) -> dict[str, Any] | None:
    """Return one selected source with scope-safe provenance."""
    metadata = candidate.metadata if isinstance(candidate.metadata, dict) else {}
    document_id = string_or_none(metadata.get("document_id"))
    if candidate.source == "document_memory":
        if document_id is None or document_id not in allowed_document_ids:
            return None
    source_chat_id = string_or_none(
        metadata.get("source_chat_id") or candidate.chat_id
    )
    if (
        candidate.source
        in {"recent_messages", "current_chat_span", "current_chat_gist"}
        and source_chat_id
        and source_chat_id != current_chat_id
    ):
        return None
    source_chat = database.get_chat(source_chat_id) if source_chat_id else None
    source_messages = (
        database.messages_for_chat_span(
            source_chat_id,
            min(candidate.source_message_ids),
            max(candidate.source_message_ids),
        )
        if source_chat_id and candidate.source_message_ids
        else []
    )
    document = database.get_document(document_id) if document_id else None
    return {
        "source": candidate.source,
        "source_label": SOURCE_LABELS.get(candidate.source, candidate.source),
        "excerpt": bounded_excerpt(candidate.content),
        "score": finite_number(candidate.score),
        "rank": first_int(metadata.get("final_rank"), rank),
        "record_id": safe_scalar(candidate.record_id),
        "source_chat_id": source_chat_id,
        "source_chat_title": source_chat.title if source_chat else None,
        "message_ids": [int(value) for value in candidate.source_message_ids[:32]],
        "message_range": (
            [min(candidate.source_message_ids), max(candidate.source_message_ids)]
            if candidate.source_message_ids
            else None
        ),
        "timestamp": source_messages[0].created_at if source_messages else None,
        "document_id": document_id,
        "filename": (
            document.file_name
            if document is not None
            else string_or_none(metadata.get("file_name") or metadata.get("title"))
        ),
        "chunk_id": safe_scalar(metadata.get("chunk_id") or candidate.record_id),
        "chunk_index": first_int(metadata.get("chunk_index")),
        "source_range": safe_scalar(
            metadata.get("source_range") or metadata.get("page")
        ),
        "document_status": document.status if document is not None else None,
        "retrieval_paths": bounded_strings(
            metadata.get("retrieval_paths")
            or ([metadata.get("retrieval_path")] if metadata.get("retrieval_path") else [])
        ),
        "current_chat": source_chat_id == current_chat_id if source_chat_id else None,
    }


def bounded_drop_rows(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, Any]] = []
    for item in value[:MAX_DROPPED_ITEMS]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "candidate_id": safe_scalar(
                    item.get("candidate_id") or item.get("trace_id")
                ),
                "source": safe_scalar(item.get("source")),
                "reason": safe_scalar(item.get("reason")),
                "overlap_ratio": finite_number(item.get("overlap_ratio")),
                "overlap_with_candidate_id": safe_scalar(
                    item.get("overlap_with_candidate_id")
                ),
            }
        )
    return rows


def bounded_excerpt(value: object) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= MAX_EXCERPT_CHARS:
        return text
    return f"{text[: MAX_EXCERPT_CHARS - 1].rstrip()}…"


def bounded_strings(value: object) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item)[:240] for item in value[:MAX_DROPPED_ITEMS] if item is not None]


def object_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def safe_scalar(value: object) -> str | int | float | bool | None:
    return value if isinstance(value, (str, int, float, bool)) else None


def string_or_none(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None


def first_int(*values: object) -> int | None:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return int(value)
    return None


def finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if number == number and abs(number) != float("inf") else None
