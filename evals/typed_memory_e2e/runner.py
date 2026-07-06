from __future__ import annotations

import json
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

from evals.typed_memory_e2e.schemas import TypedMemoryCase, TypedMemoryCaseResult
from src.actions.chat_end import ChatEndAction
from src.database import Database
from src.memory.long_term_store import (
    DEFAULT_USER_NAMESPACE,
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
)
from src.memory.short_term import ChatEndMemoryProcessingResult
from src.orchestration.langgraph_memory_pipeline import (
    build_langgraph_memory_pipeline,
    run_langgraph_memory_pipeline,
)
from src.retrieval.current_chat_span_retriever import CurrentChatSpanRetriever
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.raw_message_span_retriever import RawMessageSpanRetriever
from src.retrieval.recent_messages_retriever import RecentMessagesRetriever
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever
from src.routing.semantic_router import SemanticRouter


RAW_SOURCES = {"raw_message_span", "current_chat_span"}


class NoopChatEndMemoryProcessor:
    """Exercise gist finalization without external LangMem calls."""

    def process_all_for_chat_end(
        self,
        chat_id: str,
    ) -> ChatEndMemoryProcessingResult:
        del chat_id
        return ChatEndMemoryProcessingResult(0, 0)


def run_case(case: TypedMemoryCase) -> TypedMemoryCaseResult:
    if case.answer_mode != "mock":
        raise ValueError("typed-memory E2E currently supports mock mode only")
    with tempfile.TemporaryDirectory(prefix="typed_memory_e2e_") as temp_dir:
        database = Database(Path(temp_dir) / "case.db")
        chat_ids: dict[str, str] = {}
        message_ids: list[int] = []
        for session in case.sessions:
            chat_id = f"{case.name}:{session.chat_name}"
            database.create_chat(chat_id, title=session.chat_name)
            chat_ids[session.chat_name] = chat_id
            for message in session.messages:
                message_ids.append(
                    database.save_message(chat_id, message.role, message.content)
                )
            if session.end_chat:
                ChatEndAction(
                    database,
                    NoopChatEndMemoryProcessor(),
                ).execute(chat_id)

        query_chat_id = chat_ids.get("current") or chat_ids.get("active")
        if query_chat_id is None:
            query_chat_id = f"{case.name}:query"
            database.create_chat(query_chat_id, title="query")

        setup_case_fixtures(
            database,
            case=case,
            query_chat_id=query_chat_id,
            message_ids=message_ids,
        )
        retrievers: dict[str, object] = {
            "recent_messages": RecentMessagesRetriever(database),
            "current_chat_span": CurrentChatSpanRetriever(
                database,
                max_chars=int(case.fixture.get("current_span_max_chars", 4000)),
            ),
            "previous_chat_gist": PreviousChatGistRetriever(database),
            "raw_message_span": RawMessageSpanRetriever(database),
            "structured_memory": StructuredMemoryRetriever(database, mode="sqlite"),
        }
        graph = build_langgraph_memory_pipeline(
            routing_agent=None,
            dispatcher=RetrieverDispatcher(
                database,
                retrievers=retrievers,  # type: ignore[arg-type]
            ),
            semantic_router=SemanticRouter(),
            use_semantic_router=True,
        )
        state = run_langgraph_memory_pipeline(
            graph,
            run_id=case.name,
            chat_id=query_chat_id,
            user_query=case.query,
        )
        packet = state["context_packet"]
        candidates = packet.candidates
        sources = {candidate.source for candidate in candidates}
        context_text = "\n".join(candidate.content for candidate in candidates)
        provenance_present = any(
            candidate.chat_id
            and (
                candidate.source_message_ids
                or candidate.record_id is not None
            )
            for candidate in candidates
        )
        required_sources_present = set(case.expected_sources).issubset(sources)
        forbidden_sources_absent = not set(case.forbidden_sources).intersection(
            sources
        )
        required_text_present = all(
            text in context_text for text in case.required_text_in_context
        )
        raw_span_present = bool(RAW_SOURCES.intersection(sources))
        structured_memory_present = "structured_memory" in sources
        document_candidates = [
            candidate
            for candidate in candidates
            if candidate.source == "document_memory"
        ]
        document_citation_present = bool(document_candidates) and all(
            candidate.record_id or candidate.metadata
            for candidate in document_candidates
        )
        failures: list[str] = []
        checks = (
            (required_sources_present, "missing_required_source"),
            (forbidden_sources_absent, "forbidden_source_present"),
            (required_text_present, "required_text_missing"),
            (
                not case.requires_raw_span
                or raw_span_present
                or case.expected_insufficient_evidence,
                "required_raw_span_missing",
            ),
            (
                not case.requires_document_citation
                or document_citation_present,
                "required_document_citation_missing",
            ),
            (
                not case.requires_structured_memory
                or structured_memory_present,
                "required_structured_memory_missing",
            ),
            (
                not case.expected_provenance or provenance_present,
                "required_provenance_missing",
            ),
            (
                state["insufficient_evidence"]
                == case.expected_insufficient_evidence,
                "insufficient_evidence_mismatch",
            ),
        )
        failures.extend(reason for passed, reason in checks if not passed)
        expected_query_count = case.fixture.get("expected_query_count")
        if isinstance(expected_query_count, int):
            actual = sum(
                message.get("content") == case.query
                for message in packet.model_messages
            )
            if actual != expected_query_count:
                failures.append("current_query_count_mismatch")

        return TypedMemoryCaseResult(
            name=case.name,
            category=case.category,
            passed=not failures,
            sources_observed=tuple(sorted(sources)),
            required_sources_present=required_sources_present,
            forbidden_sources_absent=forbidden_sources_absent,
            required_text_present=required_text_present,
            raw_span_present=raw_span_present,
            document_citation_present=document_citation_present,
            structured_memory_present=structured_memory_present,
            provenance_present=provenance_present,
            insufficient_evidence=state["insufficient_evidence"],
            context_char_size=len(context_text),
            failure_reasons=tuple(failures),
            notes=case.notes,
        )


def setup_case_fixtures(
    database: Database,
    *,
    case: TypedMemoryCase,
    query_chat_id: str,
    message_ids: list[int],
) -> None:
    gist_text = case.fixture.get("gist_only_text")
    if isinstance(gist_text, str):
        gist_chat_id = f"{case.name}:gist-only"
        database.create_chat(gist_chat_id, title="gist-only")
        database.insert_chat_gist(
            chat_id=gist_chat_id,
            source_type="previous_chat_gist",
            gist_text=gist_text,
        )
    memory_text = case.fixture.get("structured_memory")
    memory_key = case.fixture.get("structured_key")
    if isinstance(memory_text, str) and isinstance(memory_key, str):
        SQLiteLongTermMemoryStore(database).upsert(
            LongTermMemoryWrite(
                namespace=DEFAULT_USER_NAMESPACE,
                memory_id=f"preferences:{memory_key}",
                category="preferences",
                key=memory_key,
                value=memory_text,
                confidence=1.0,
                source_chat_id=query_chat_id,
                source_message_ids=message_ids[:1],
            )
        )


def run_benchmark(cases: list[TypedMemoryCase]) -> dict[str, Any]:
    results = [run_case(case) for case in cases]
    by_category: dict[str, list[TypedMemoryCaseResult]] = defaultdict(list)
    for result in results:
        by_category[result.category].append(result)
    failures = Counter(
        reason
        for result in results
        for reason in result.failure_reasons
    )
    passed = sum(result.passed for result in results)
    return {
        "benchmark": "typed_memory_e2e",
        "answer_mode": "mock",
        "num_cases": len(results),
        "num_passed": passed,
        "pass_rate": passed / len(results) if results else 0.0,
        "pass_rate_by_category": {
            category: sum(result.passed for result in category_results)
            / len(category_results)
            for category, category_results in sorted(by_category.items())
        },
        "failures_by_reason": dict(sorted(failures.items())),
        "results": [asdict(result) for result in results],
    }


def write_jsonl(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    summary = {key: value for key, value in report.items() if key != "results"}
    with path.open("w", encoding="utf-8") as handle:
        handle.write(json.dumps({"summary": summary}, sort_keys=True) + "\n")
        for result in report["results"]:
            handle.write(json.dumps(result, sort_keys=True) + "\n")
