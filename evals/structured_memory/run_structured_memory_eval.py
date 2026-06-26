from __future__ import annotations

import argparse
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evals.structured_memory.metrics import (  # noqa: E402
    StructuredMemoryScores,
    score_case,
    summarize_scores,
)
from src.core.contracts import SourcePlan  # noqa: E402
from src.database import Database  # noqa: E402
from src.memory.langmem_structured import LangMemStructuredMemoryState  # noqa: E402
from src.memory.long_term_store import (  # noqa: E402
    LongTermMemoryWrite,
    SQLiteLongTermMemoryStore,
    category_namespace,
    structured_memory_namespaces,
)
from src.memory.short_term import ShortTermMemory  # noqa: E402
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever  # noqa: E402


DEFAULT_DATASET = Path(__file__).parent / "datasets" / "cross_chat_sample.jsonl"


class FakeModel:
    """No-op model used by ShortTermMemory in deterministic eval mode."""

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        del messages, temperature
        return ""


class FakeLangMemManager:
    """Fake LangMem manager returning dataset-provided extraction outputs."""

    def __init__(self, output: list[dict[str, Any]]) -> None:
        self.output = output

    def invoke(self, input: dict[str, Any]) -> list[dict[str, Any]]:
        del input
        return self.output


@dataclass(frozen=True)
class EvalCaseResult:
    """Result and score for one structured-memory eval case."""

    case_id: str
    stored_memory_text: str
    retrieved_memory_text: str
    answer: str
    score: StructuredMemoryScores


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run deterministic structured cross-chat memory evaluation."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument(
        "--mode",
        choices=("mock",),
        default="mock",
        help="mock mode uses fake LangMem extraction and oracle answers.",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true", help="Print JSON summary.")
    return parser.parse_args()


def load_jsonl(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    """Load structured-memory eval cases from JSONL."""
    cases = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            cases.append(json.loads(line))
            if limit is not None and len(cases) >= limit:
                break
    return cases


def run_cases(cases: list[dict[str, Any]]) -> list[EvalCaseResult]:
    """Run all cases in deterministic mock/oracle mode."""
    return [run_case(case) for case in cases]


def run_case(case: dict[str, Any]) -> EvalCaseResult:
    """Run one case through real SQLite memory update and retrieval wiring."""
    with tempfile.TemporaryDirectory(prefix="structured_memory_eval_") as tmpdir:
        database = Database(Path(tmpdir) / "chatbot.db")
        store = SQLiteLongTermMemoryStore(database)
        chat1_id = f"{case['case_id']}-chat-1"
        chat2_id = f"{case['case_id']}-chat-2"
        database.create_chat(chat1_id)
        database.create_chat(chat2_id)
        seed_initial_memories(store, chat1_id, case.get("initial_memory_records") or [])

        for message in case.get("chat1_messages") or []:
            database.save_message(chat1_id, "user", str(message))
            database.save_message(chat1_id, "assistant", "Acknowledged.")
        database.save_message(chat1_id, "user", "Latest filler message.")

        memory = ShortTermMemory(
            database=database,
            model=FakeModel(),
            raw_message_limit=1,
            memory_update_batch_size=2,
            structured_memory_updater=LangMemStructuredMemoryState(
                manager=FakeLangMemManager(case.get("mock_langmem_outputs") or []),
                long_term_store=store,
            ),
        )
        memory.update_memory_if_needed(chat1_id)

        stored_records = []
        for namespace in structured_memory_namespaces(chat1_id):
            stored_records.extend(store.list(namespace))
        stored_memory_text = "\n".join(record.value for record in stored_records)

        candidates = StructuredMemoryRetriever(database).retrieve(
            chat_id=chat2_id,
            source_plan=SourcePlan(
                source="structured_memory",
                query=str(case.get("chat2_query") or ""),
                limit=10,
            ),
        )
        retrieved_memory_text = "\n".join(candidate.content for candidate in candidates)
        answer = str(case.get("oracle_answer") or "")
        score = score_case(
            case,
            stored_memory_text=stored_memory_text,
            retrieved_memory_text=retrieved_memory_text,
            answer=answer,
        )
        return EvalCaseResult(
            case_id=str(case.get("case_id") or ""),
            stored_memory_text=stored_memory_text,
            retrieved_memory_text=retrieved_memory_text,
            answer=answer,
            score=score,
        )


def seed_initial_memories(
    store: SQLiteLongTermMemoryStore,
    source_chat_id: str,
    records: list[dict[str, Any]],
) -> None:
    """Seed existing long-term memories for update/retrieval lifecycle cases."""
    for record in records:
        category = str(record["category"])
        key = str(record["key"])
        store.upsert(
            LongTermMemoryWrite(
                namespace=category_namespace(category, source_chat_id),
                memory_id=f"{category}:{key}",
                category=category,
                key=key,
                value=str(record["value"]),
                confidence=float(record.get("confidence", 0.7)),
                status=str(record.get("status", "active")),
                source_chat_id=source_chat_id,
                source_message_ids=[
                    source_id
                    for source_id in record.get("source_message_ids", [])
                    if isinstance(source_id, int)
                ],
                metadata={"seeded_by": "structured_memory_eval"},
            )
        )


def print_summary(results: list[EvalCaseResult], json_output: bool = False) -> None:
    """Print readable or JSON summary."""
    scores = [result.score for result in results]
    summary = summarize_scores(scores)
    if json_output:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return

    print("structured_memory_eval mode=mock")
    for key, value in summary.items():
        print(f"{key}={value}")
    for result in results:
        status = "PASS" if not result.score.failed_reasons else "FAIL"
        print(
            "case_result "
            f"case_id={result.case_id} "
            f"status={status} "
            f"failed_reasons={result.score.failed_reasons}"
        )


def main() -> int:
    args = parse_args()
    cases = load_jsonl(args.dataset, limit=args.limit)
    results = run_cases(cases)
    print_summary(results, json_output=args.json)
    return 1 if summarize_scores([result.score for result in results])["failed_case_ids"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
