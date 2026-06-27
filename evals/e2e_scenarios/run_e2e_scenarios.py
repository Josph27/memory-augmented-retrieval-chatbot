from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evals.document_qa.answer_generation import answer_is_unknown  # noqa: E402
from src.agents.chat_agent import ChatAgent  # noqa: E402
from src.agents.context_builder_agent import ContextBuilderAgent  # noqa: E402
from src.agents.coordinator_agent import CoordinatorAgent  # noqa: E402
from src.agents.short_term_memory_agent import ShortTermMemoryAgent  # noqa: E402
from src.config import AppConfig  # noqa: E402
from src.core.contracts import (  # noqa: E402
    AgentTurnResult,
    MemoryCandidate,
    RoutePlan,
    SourcePlan,
)
from src.database import Database  # noqa: E402
from src.memory.long_term_store import (  # noqa: E402
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
    category_namespace,
    structured_memory_namespaces,
)
from src.memory.long_term_vector_index import (  # noqa: E402
    LongTermMemorySearchResult,
)
from src.memory.short_term import ShortTermMemory  # noqa: E402
from src.memory.structured_state import MemoryUpdateResult  # noqa: E402
from src.model_wrapper import ModelWrapper  # noqa: E402
from src.retrieval.current_chat_gist_retriever import (  # noqa: E402
    CurrentChatGistRetriever,
)
from src.retrieval.previous_chat_gist_retriever import (  # noqa: E402
    PreviousChatGistRetriever,
)
from src.retrieval.raw_message_span_retriever import (  # noqa: E402
    RawMessageSpanRetriever,
)
from src.retrieval.recent_messages_retriever import RecentMessagesRetriever  # noqa: E402
from src.retrieval.reranker import MemoryReranker  # noqa: E402
from src.retrieval.retriever_dispatcher import RetrieverDispatcher  # noqa: E402
from src.retrieval.structured_memory_retriever import (  # noqa: E402
    StructuredMemoryRetriever,
)
from src.routing.routing_agent import RoutingAgent  # noqa: E402


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "e2e_scenarios.jsonl"
ALL_SOURCE_LABELS = (
    "recent_messages",
    "structured_memory",
    "document_memory",
    "current_chat_gist",
    "previous_chat_gist",
    "raw_message_span",
)
SYSTEM_PROMPT = (
    "Answer using the supplied memory and retrieved context. "
    "If the answer is unsupported, say I don't know."
)


class ModelModeUnavailable(RuntimeError):
    """Raised when optional model mode is not configured."""


@dataclass(frozen=True)
class E2EScenarioResult:
    """Metrics and exported trace for one integration scenario."""

    case_id: str
    expected_source_present: bool
    expected_context_included: bool
    reranker_top_source_correct: bool
    answer_contains_expected: bool
    forbidden_claim_violations: list[str]
    abstain_correct: bool | None
    scenario_pass: bool
    failed_reasons: list[str]
    trace: dict[str, Any]


class FakeAnswerModel:
    """Deterministic answer model used by mock scenarios."""

    model_name = "e2e-fake-answer-model"

    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[list[dict[str, str]]] = []

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del temperature
        self.calls.append([dict(message) for message in messages])
        return self.answer


class NoopStructuredUpdater:
    """Offline updater that should remain unused in short scenarios."""

    def update(self, existing_memory, messages):  # type: ignore[no-untyped-def]
        del messages
        return MemoryUpdateResult(
            memory_state=existing_memory,
            accepted=False,
            rejection_reason="e2e_noop_updater",
        )


class FixtureRetriever:
    """Deterministic retriever for document or other injected candidates."""

    def __init__(self, candidates: list[MemoryCandidate]) -> None:
        self.candidates = candidates

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        del chat_id
        return self.candidates[: source_plan.limit or len(self.candidates)]


class FixtureVectorIndex:
    """Deterministic semantic index referencing real SQLite records."""

    def __init__(self, results: list[LongTermMemorySearchResult]) -> None:
        self.results = results

    def search(self, query: str, limit: int = 10) -> list[LongTermMemorySearchResult]:
        del query
        return self.results[:limit]


class ScenarioRoutePlanner:
    """Route planner returning one controlled scenario route."""

    def __init__(self, route_plan: RoutePlan) -> None:
        self.route_plan = route_plan

    def plan(self, query: str) -> RoutePlan:
        return replace(self.route_plan, query=query)


class ScenarioRerankerModel:
    """Fake structured reranker ordering candidates by desired source."""

    model_name = "e2e-fake-reranker-model"

    def __init__(self, source_order: list[str]) -> None:
        self.source_order = source_order

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del temperature
        payload_text = messages[-1]["content"].split("Candidates:\n", maxsplit=1)[1]
        candidates = json.loads(payload_text)
        source_priority = {
            source: index for index, source in enumerate(self.source_order)
        }
        ordered = sorted(
            candidates,
            key=lambda item: (
                source_priority.get(item["source"], len(source_priority)),
                item["id"],
            ),
        )
        return json.dumps(
            {
                "ranked_candidate_ids": [item["id"] for item in ordered],
                "confidence": 0.95,
                "reason": "Controlled source ordering for E2E mock scenario.",
            }
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run controlled end-to-end memory/RAG scenarios."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--mode", choices=("mock", "model"), default="mock")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", type=Path, help="Optional JSON report output.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    return parser.parse_args()


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Load controlled E2E scenarios."""
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {error}") from error
            validate_case(case, path, line_number)
            cases.append(case)
            if limit is not None and len(cases) >= limit:
                break
    return cases


def validate_case(case: object, path: Path, line_number: int) -> None:
    """Validate fields required by the integration harness."""
    required = {
        "case_id",
        "query",
        "enabled_sources",
        "expected_sources",
        "expected_context_contains",
        "expected_answer_contains",
        "forbidden_answer_contains",
        "should_abstain",
    }
    if not isinstance(case, dict):
        raise ValueError(f"Expected object at {path}:{line_number}")
    missing = sorted(required - set(case))
    if missing:
        raise ValueError(f"Missing fields at {path}:{line_number}: {missing}")


def run_cases(
    cases: list[dict[str, Any]],
    mode: str = "mock",
    model: object | None = None,
) -> list[E2EScenarioResult]:
    """Run controlled scenarios through isolated real coordinator pipelines."""
    if mode == "model" and model is None:
        model = configured_model()
    return [run_case(case, mode=mode, model=model) for case in cases]


def run_case(
    case: dict[str, Any],
    mode: str = "mock",
    model: object | None = None,
) -> E2EScenarioResult:
    """Run one scenario through CoordinatorAgent and score its trace."""
    with tempfile.TemporaryDirectory(prefix="memory_rag_e2e_") as temp_dir:
        database = Database(Path(temp_dir) / "scenario.db")
        chat_id = f"{case['case_id']}-current"
        database.create_chat(chat_id)
        setup = case.get("setup") if isinstance(case.get("setup"), dict) else {}
        seed_recent_messages(database, chat_id, setup)
        store = SQLiteLongTermMemoryStore(database)
        seed_long_term_memories(store, chat_id, setup)
        span_filters = seed_previous_chat(database, setup)
        span_filters.update(seed_direct_raw_span(database, setup))

        structured_mode = str(
            (case.get("retrieval_modes") or {}).get("structured_memory", "sqlite")
        )
        vector_index = vector_index_for_store(store, chat_id)
        retrievers = {
            "recent_messages": RecentMessagesRetriever(database, default_limit=8),
            "structured_memory": StructuredMemoryRetriever(
                database,
                mode=structured_mode,
                vector_index=vector_index,
            ),
            "document_memory": FixtureRetriever(document_candidates(setup)),
            "current_chat_gist": CurrentChatGistRetriever(database),
            "previous_chat_gist": PreviousChatGistRetriever(database),
            "raw_message_span": RawMessageSpanRetriever(database),
        }
        route_plan = route_plan_for_case(case, span_filters=span_filters)
        routing_agent = RoutingAgent(
            route_planner=ScenarioRoutePlanner(route_plan),  # type: ignore[arg-type]
            mode="rule",
        )

        answer_model = model
        if mode == "mock":
            answer_model = FakeAnswerModel(str(case.get("mock_answer") or ""))
        if answer_model is None:
            raise ModelModeUnavailable("E2E model mode requires a configured model.")

        reranker_mode = str(case.get("reranker_mode") or "deterministic")
        reranker_model = None
        if reranker_mode in {"hybrid", "llm"}:
            if mode == "mock":
                reranker_model = ScenarioRerankerModel(
                    [str(source) for source in case.get("mock_reranker_order", [])]
                )
            else:
                reranker_model = answer_model

        short_term = ShortTermMemory(
            database=database,
            model=cast(Any, answer_model),
            raw_message_limit=8,
            memory_update_batch_size=1000,
            structured_memory_updater=NoopStructuredUpdater(),
        )
        coordinator = CoordinatorAgent(
            database=database,
            memory_agent=ShortTermMemoryAgent(short_term),
            context_builder=ContextBuilderAgent(short_term),
            chat_agent=ChatAgent(cast(Any, answer_model)),
            system_prompt=SYSTEM_PROMPT,
            retriever_dispatcher=RetrieverDispatcher(
                database=database,
                retrievers=retrievers,
            ),
            routing_agent=routing_agent,
            memory_reranker=MemoryReranker(
                mode=reranker_mode,
                model=cast(Any, reranker_model),
                llm_top_k=10,
                llm_min_confidence=0.55,
            ),
        )
        turn_result = coordinator.run_turn(chat_id=chat_id, content=str(case["query"]))
        return score_scenario(case, turn_result, mode=mode)


def seed_recent_messages(
    database: Database,
    chat_id: str,
    setup: dict[str, Any],
) -> None:
    """Seed optional current-chat messages."""
    for message in setup.get("recent_messages", []):
        database.save_message(
            chat_id,
            str(message.get("role") or "user"),
            str(message.get("content") or ""),
        )


def seed_long_term_memories(
    store: SQLiteLongTermMemoryStore,
    chat_id: str,
    setup: dict[str, Any],
) -> None:
    """Seed source-of-truth SQLite long-term memory rows."""
    for item in setup.get("long_term_memories", []):
        category = str(item["category"])
        key = str(item["key"])
        store.upsert(
            LongTermMemoryWrite(
                namespace=category_namespace(category, chat_id),
                memory_id=str(item.get("memory_id") or f"{category}:{key}"),
                category=category,
                key=key,
                value=str(item["value"]),
                confidence=float(item.get("confidence", 0.8)),
                status=str(item.get("status", "active")),
                source_chat_id=str(item.get("source_chat_id") or "fixture-chat"),
                source_message_ids=[
                    value
                    for value in item.get("source_message_ids", [])
                    if isinstance(value, int)
                ],
                metadata={"fixture": "e2e_scenario"},
            )
        )


def seed_previous_chat(
    database: Database,
    setup: dict[str, Any],
) -> dict[str, object]:
    """Seed an old transcript and linked previous-chat gist."""
    previous = setup.get("previous_chat")
    if not isinstance(previous, dict):
        return {}
    chat_id = str(previous.get("chat_id") or "e2e-old-chat")
    database.create_chat(chat_id)
    message_ids = [
        database.save_message(
            chat_id,
            str(message.get("role") or "user"),
            str(message.get("content") or ""),
        )
        for message in previous.get("messages", [])
    ]
    if not message_ids:
        return {}
    gist_id = database.insert_chat_gist(
        chat_id=chat_id,
        source_type="previous_chat_gist",
        gist_text=str(previous.get("gist_text") or ""),
        topics=list(previous.get("topics") or []),
        start_message_id=message_ids[0],
        end_message_id=message_ids[-1],
        metadata={"status": "active", "fixture": "e2e_scenario"},
    )
    return {"gist_id": gist_id}


def seed_direct_raw_span(
    database: Database,
    setup: dict[str, Any],
) -> dict[str, object]:
    """Seed a raw span that does not require a gist row."""
    direct = setup.get("raw_span_direct")
    if not isinstance(direct, dict):
        return {}
    chat_id = str(direct.get("chat_id") or "e2e-raw-chat")
    database.create_chat(chat_id)
    message_ids = [
        database.save_message(
            chat_id,
            str(message.get("role") or "user"),
            str(message.get("content") or ""),
        )
        for message in direct.get("messages", [])
    ]
    if not message_ids:
        return {}
    return {
        "chat_id": chat_id,
        "start_message_id": message_ids[0],
        "end_message_id": message_ids[-1],
    }


def vector_index_for_store(
    store: SQLiteLongTermMemoryStore,
    chat_id: str,
) -> FixtureVectorIndex:
    """Build a fake vector index referencing current SQLite records."""
    results = []
    for namespace in structured_memory_namespaces(chat_id):
        for record in store.list(namespace):
            results.append(
                LongTermMemorySearchResult(
                    memory_id=record.memory_id,
                    namespace=record.namespace,
                    score=0.95,
                    metadata={"fixture": "e2e_vector_index"},
                )
            )
    return FixtureVectorIndex(results)


def document_candidates(setup: dict[str, Any]) -> list[MemoryCandidate]:
    """Convert deterministic document fixtures to MemoryCandidate objects."""
    candidates = []
    for item in setup.get("document_candidates", []):
        candidates.append(
            MemoryCandidate(
                source="document_memory",
                content=str(item.get("content") or ""),
                score=float(item.get("score", 0.8)),
                record_id=item.get("record_id"),
                metadata={
                    "retrieval_backend": "e2e_fixture_document",
                    "status": "active",
                    **dict(item.get("metadata") or {}),
                },
            )
        )
    return candidates


def route_plan_for_case(
    case: dict[str, Any],
    span_filters: dict[str, object],
) -> RoutePlan:
    """Build controlled source plans consumed by the real RoutingAgent wrapper."""
    enabled_sources = {str(source) for source in case.get("enabled_sources", [])}
    query = str(case["query"])
    sources = [
        SourcePlan(
            source=cast(Any, source),
            enabled=source in enabled_sources,
            reason="Controlled E2E scenario source plan.",
            query=query if source in enabled_sources else None,
            limit=8,
            filters=(
                dict(span_filters)
                if source == "raw_message_span" and source in enabled_sources
                else {}
            ),
        )
        for source in ALL_SOURCE_LABELS
    ]
    context_profile = "general_chat"
    if "document_memory" in enabled_sources:
        context_profile = "document_question"
    if enabled_sources & {"previous_chat_gist", "raw_message_span"}:
        context_profile = "mixed_memory_document"
    elif "structured_memory" in enabled_sources:
        context_profile = (
            "mixed_memory_document"
            if "document_memory" in enabled_sources
            else "memory_recall"
        )
    return RoutePlan(
        query=query,
        sources=sources,
        intent=str(case["case_id"]),
        confidence=1.0,
        requires_retrieval=True,
        ranking_profile="e2e_scenario",
        context_profile=context_profile,
        fallback_policy="e2e_controlled",
        update_policy="disabled_for_e2e",
        termination_policy="response_generated_and_messages_saved",
        metadata={"scenario_id": str(case["case_id"])},
    )


def score_scenario(
    case: dict[str, Any],
    result: AgentTurnResult,
    mode: str,
) -> E2EScenarioResult:
    """Score orchestration output and build a JSON-ready integration trace."""
    retrieved_sources = {
        candidate.source for candidate in result.trace.retrieved_candidates
    }
    expected_sources = {str(source) for source in case.get("expected_sources", [])}
    expected_source_present = expected_sources.issubset(retrieved_sources)

    packet = result.trace.context_packet
    context_text = ""
    if packet is not None:
        context_text = "\n".join(message["content"] for message in packet.model_messages)
    expected_context = [
        str(value) for value in case.get("expected_context_contains", [])
    ]
    expected_context_included = all(
        normalize_text(value) in normalize_text(context_text)
        for value in expected_context
    )

    expected_top_source = case.get("expected_top_source")
    semantic_ranked_candidates = [
        candidate
        for candidate in result.trace.ranked_candidates
        if candidate.source != "recent_messages"
    ]
    actual_top_source = (
        semantic_ranked_candidates[0].source
        if semantic_ranked_candidates
        else None
    )
    reranker_top_source_correct = (
        expected_top_source is None or actual_top_source == expected_top_source
    )
    answer = result.answer
    answer_contains_expected = all(
        normalize_text(str(value)) in normalize_text(answer)
        for value in case.get("expected_answer_contains", [])
    )
    forbidden_claim_violations = [
        str(value)
        for value in case.get("forbidden_answer_contains", [])
        if normalize_text(str(value)) in normalize_text(answer)
    ]
    should_abstain = bool(case.get("should_abstain"))
    abstain_correct = answer_is_unknown(answer) if should_abstain else None

    failed_reasons = []
    if not expected_source_present:
        failed_reasons.append("expected_source_missing")
    if not expected_context_included:
        failed_reasons.append("expected_context_missing")
    if not reranker_top_source_correct:
        failed_reasons.append("reranker_top_source_mismatch")
    if not answer_contains_expected:
        failed_reasons.append("expected_answer_missing")
    if forbidden_claim_violations:
        failed_reasons.append("forbidden_claim_present")
    if abstain_correct is False:
        failed_reasons.append("abstain_failed")

    return E2EScenarioResult(
        case_id=str(case["case_id"]),
        expected_source_present=expected_source_present,
        expected_context_included=expected_context_included,
        reranker_top_source_correct=reranker_top_source_correct,
        answer_contains_expected=answer_contains_expected,
        forbidden_claim_violations=forbidden_claim_violations,
        abstain_correct=abstain_correct,
        scenario_pass=not failed_reasons,
        failed_reasons=failed_reasons,
        trace=trace_to_dict(
            case=case,
            result=result,
            mode=mode,
            actual_top_source=actual_top_source,
        ),
    )


def trace_to_dict(
    case: dict[str, Any],
    result: AgentTurnResult,
    mode: str,
    actual_top_source: str | None,
) -> dict[str, Any]:
    """Serialize relevant WorkflowTrace fields for integration reports."""
    trace = result.trace
    route_plan = trace.route_plan
    packet = trace.context_packet
    return {
        "case_id": str(case["case_id"]),
        "mode": mode,
        "query": str(case["query"]),
        "active_sources": [
            source.source
            for source in (route_plan.sources if route_plan else [])
            if source.enabled
        ],
        "source_plans": [
            {
                "source": source.source,
                "enabled": source.enabled,
                "reason": source.reason,
                "filters": dict(source.filters),
            }
            for source in (route_plan.sources if route_plan else [])
        ],
        "retrieved_candidates": [
            candidate_trace(candidate) for candidate in trace.retrieved_candidates
        ],
        "reranked_candidates": [
            candidate_trace(candidate) for candidate in trace.ranked_candidates
        ],
        "reranker_top_source": actual_top_source,
        "context_packet": {
            "sections": list(
                packet.metadata.get("section_order", []) if packet else []
            ),
            "candidate_sources": [
                candidate.source for candidate in (packet.candidates if packet else [])
            ],
            "model_messages": list(packet.model_messages if packet else []),
        },
        "answer": result.answer,
        "workflow_metadata": json_safe(trace.metadata),
        "errors": list(trace.errors),
        "notes": case.get("notes"),
    }


def candidate_trace(candidate: MemoryCandidate) -> dict[str, Any]:
    """Serialize one MemoryCandidate for report output."""
    return {
        "source": candidate.source,
        "record_id": candidate.record_id,
        "chat_id": candidate.chat_id,
        "score": candidate.score,
        "content": candidate.content,
        "source_message_ids": list(candidate.source_message_ids),
        "metadata": json_safe(candidate.metadata),
    }


def json_safe(value: Any) -> Any:
    """Round-trip values through JSON with a safe string fallback."""
    return json.loads(json.dumps(value, default=str))


def normalize_text(value: str) -> str:
    """Normalize whitespace/case for deterministic checks."""
    return " ".join(value.casefold().split())


def summarize_results(results: list[E2EScenarioResult]) -> dict[str, Any]:
    """Return aggregate integration metrics."""
    abstain_values = [
        result.abstain_correct
        for result in results
        if result.abstain_correct is not None
    ]
    return {
        "total_scenarios": len(results),
        "expected_source_present": rate(
            result.expected_source_present for result in results
        ),
        "expected_context_included": rate(
            result.expected_context_included for result in results
        ),
        "reranker_top_source_correct": rate(
            result.reranker_top_source_correct for result in results
        ),
        "answer_contains_expected": rate(
            result.answer_contains_expected for result in results
        ),
        "forbidden_claim_violations": sum(
            len(result.forbidden_claim_violations) for result in results
        ),
        "abstain_correctness": rate(abstain_values),
        "scenario_pass_rate": rate(result.scenario_pass for result in results),
        "failed_scenario_ids": [
            result.case_id for result in results if not result.scenario_pass
        ],
    }


def rate(values: Any) -> float:
    """Return truthy fraction, or zero for empty input."""
    items = list(values)
    if not items:
        return 0.0
    return sum(1 for item in items if item) / len(items)


def report_payload(
    results: list[E2EScenarioResult],
    mode: str,
) -> dict[str, Any]:
    """Build JSON-ready E2E report."""
    return {
        "eval_name": "end_to_end_memory_rag_scenarios",
        "mode": mode,
        "summary": summarize_results(results),
        "scenarios": [
            {
                "case_id": result.case_id,
                "expected_source_present": result.expected_source_present,
                "expected_context_included": result.expected_context_included,
                "reranker_top_source_correct": result.reranker_top_source_correct,
                "answer_contains_expected": result.answer_contains_expected,
                "forbidden_claim_violations": result.forbidden_claim_violations,
                "abstain_correct": result.abstain_correct,
                "scenario_pass": result.scenario_pass,
                "failed_reasons": result.failed_reasons,
                "trace": result.trace,
            }
            for result in results
        ],
    }


def write_report(path: Path, payload: dict[str, Any]) -> None:
    """Write integration report JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def print_summary(
    results: list[E2EScenarioResult],
    mode: str,
    json_output: bool,
) -> None:
    """Print readable or JSON integration results."""
    payload = report_payload(results, mode=mode)
    if json_output:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    print(f"e2e_memory_rag_scenarios mode={mode}")
    for key, value in payload["summary"].items():
        print(f"{key}={value}")
    for result in results:
        status = "PASS" if result.scenario_pass else "FAIL"
        print(
            "scenario_result "
            f"case_id={result.case_id} "
            f"status={status} "
            f"active_sources={result.trace['active_sources']} "
            f"retrieved_sources="
            f"{[row['source'] for row in result.trace['retrieved_candidates']]} "
            f"reranker_top_source={result.trace['reranker_top_source']} "
            f"failed_reasons={result.failed_reasons}"
        )


def configured_model() -> ModelWrapper:
    """Build optional configured model or fail clearly."""
    load_dotenv()
    required = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "MODEL_NAME")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise ModelModeUnavailable(
            "E2E model mode skipped: missing " + ", ".join(missing)
        )
    return ModelWrapper(AppConfig.from_env())


def main() -> int:
    args = parse_args()
    cases = load_jsonl(args.dataset, limit=args.limit)
    try:
        results = run_cases(cases, mode=args.mode)
    except ModelModeUnavailable as error:
        print(error)
        return 2
    payload = report_payload(results, mode=args.mode)
    if args.output:
        write_report(args.output, payload)
        print(f"wrote_report={args.output}")
    print_summary(results, mode=args.mode, json_output=args.json)
    return 1 if payload["summary"]["failed_scenario_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
