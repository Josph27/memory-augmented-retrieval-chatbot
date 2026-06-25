from __future__ import annotations

import argparse
import sqlite3
import tempfile
import sys
from dataclasses import dataclass
from pathlib import Path

from openai import OpenAIError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.chat_service import ChatService  # noqa: E402
from src.config import AppConfig  # noqa: E402
from src.core.contracts import SourcePlan  # noqa: E402
from src.database import Database  # noqa: E402
from src.model_wrapper import ModelWrapper  # noqa: E402
from src.retrieval.structured_memory_retriever import StructuredMemoryRetriever  # noqa: E402

MEMORY_BEARING_MESSAGE = (
    "For this memory chatbot project, please remember that I prefer mature, "
    "stable open-source libraries over custom implementations for standard infrastructure."
)
CHAT2_QUERY = "What engineering style do I prefer for this memory chatbot project?"


@dataclass(frozen=True)
class DemoScenario:
    """One verification scenario with exact turn content."""

    name: str
    chat1_messages: tuple[str, ...]
    chat2_questions: tuple[str, ...]
    expected_phrases: tuple[str, ...]


SCENARIOS: dict[str, DemoScenario] = {
    "default": DemoScenario(
        name="default",
        chat1_messages=(
            MEMORY_BEARING_MESSAGE,
        ),
        chat2_questions=(CHAT2_QUERY,),
        expected_phrases=(
            "mature, stable open-source libraries",
            "concise, practical engineering explanations",
        ),
    ),
    "demo-dialogue": DemoScenario(
        name="demo-dialogue",
        chat1_messages=(
            "I’m preparing a demo for my memory chatbot project tomorrow. For this project, I strongly prefer mature, stable open-source libraries over custom infrastructure when the problem is already solved. I also prefer concise, practical engineering explanations rather than long theoretical answers. For the demo, I want to focus on cross-chat long-term memory instead of document RAG.",
            "Can you explain semantic memory in this project in simple terms?",
            "How is episodic memory different from semantic memory?",
            "Where does LangMem fit into the architecture?",
            "How does document memory differ from chat memory?",
            "How should I describe the long-term memory store in my demo?",
            "Can you summarize the current memory pipeline in three short bullet points?",
        ),
        chat2_questions=(
            "What preferences do I have for this memory chatbot project?",
            "What should my demo focus on?",
            "What engineering style do I prefer?",
        ),
        expected_phrases=(
            "mature, stable open-source libraries over custom infrastructure",
            "concise, practical engineering explanations",
            "cross-chat long-term memory instead of document RAG",
            "mature open-source libraries",
            "production-shaped components over custom infrastructure",
        ),
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify natural cross-chat long-term memory flow with real turn wiring."
    )
    parser.add_argument(
        "--filler-turns",
        type=int,
        default=6,
        help="Number of extra Chat 1 user turns after the memory-bearing turn (default: 6).",
    )
    parser.add_argument(
        "--mode",
        choices=("natural", "staged"),
        default="staged",
        help=(
            "natural: run all Chat 1/Chat 2 turns through ChatService model calls. "
            "staged: write Chat 1 filler rows directly, then run real update_memory_if_needed once."
        ),
    )
    parser.add_argument(
        "--keep-db",
        action="store_true",
        help="Keep the temporary SQLite file and print its path.",
    )
    parser.add_argument(
        "--skip-chat2-answer",
        action="store_true",
        help="Skip the final Chat 2 model call and only verify retrieval wiring.",
    )
    parser.add_argument(
        "--scenario",
        choices=tuple(SCENARIOS),
        default="default",
        help="Choose the turn sequence to verify (default: default).",
    )
    return parser.parse_args()


def require_env(config: AppConfig) -> None:
    missing: list[str] = []
    if not config.openai_base_url:
        missing.append("OPENAI_BASE_URL")
    if not config.model_name:
        missing.append("MODEL_NAME")
    if not config.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise SystemExit(
            "Missing required model settings: "
            + ", ".join(missing)
            + ". Set them in your environment or .env."
        )


def run_turn(chat_service: ChatService, chat_id: str, content: str) -> tuple[str, bool]:
    try:
        result = chat_service.handle_user_turn(chat_id=chat_id, content=content)
    except OpenAIError as exc:  # pragma: no cover - depends on local endpoint
        raise SystemExit(
            "Model endpoint request failed while running verification turns: "
            f"{exc.__class__.__name__}: {exc}"
        ) from exc
    return result.answer, "Model error:" not in result.answer


def long_term_rows(database: Database) -> list[sqlite3.Row]:
    with database.connect() as connection:
        return connection.execute(
            """
            SELECT namespace_path, memory_id, category, key, value, confidence, status, source_chat_id
            FROM long_term_memories
            ORDER BY updated_at DESC
            """
        ).fetchall()


def structured_candidates(database: Database, chat_id: str, query: str) -> list[object]:
    retriever = StructuredMemoryRetriever(database)
    return retriever.retrieve(
        chat_id=chat_id,
        source_plan=SourcePlan(
            source="structured_memory",
            query=query,
            limit=10,
        ),
    )


def print_expected_summary(
    *,
    expected_phrases: tuple[str, ...],
    long_term_text: str,
    retrieved_text: str,
    chat2_answers: list[tuple[str, str]],
) -> None:
    for phrase in expected_phrases:
        print(
            "expected_check "
            f"phrase={phrase!r} "
            f"in_long_term={phrase.lower() in long_term_text.lower()} "
            f"in_retrieved={phrase.lower() in retrieved_text.lower()} "
            f"in_chat2_answer={any(phrase.lower() in answer.lower() for _, answer in chat2_answers)}"
        )


def summarized_count(database: Database, chat_id: str) -> int:
    with database.connect() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS count FROM messages WHERE chat_id = ? AND summarized = 1",
            (chat_id,),
        ).fetchone()
    return int(row["count"] if row else 0)


def main() -> None:
    args = parse_args()
    config = AppConfig.from_env()
    require_env(config)
    scenario = SCENARIOS[args.scenario]

    with tempfile.TemporaryDirectory(prefix="memory_demo_") as tmpdir:
        db_path = Path(tmpdir) / "demo_chatbot.db"
        database = Database(db_path)
        model = ModelWrapper(config=config, model_name=config.model_name)
        chat_service = ChatService(
            database=database,
            model=model,
            raw_message_limit=config.raw_message_limit,
            memory_update_batch_size=config.memory_update_batch_size,
        )

        chat1_id = chat_service.start_chat(chat_id="demo-chat-1")
        print(f"chat1_id={chat1_id}")
        print(f"raw_message_limit={config.raw_message_limit}")
        print(f"memory_update_batch_size={config.memory_update_batch_size}")

        model_ok = True
        chat1_turns = list(scenario.chat1_messages)
        if args.mode == "natural":
            for index, content in enumerate(chat1_turns):
                _, current_ok = run_turn(chat_service, chat1_id, content)
                model_ok = model_ok and current_ok
            for index in range(args.filler_turns):
                filler = f"Filler turn {index + 1}: continue normal planning for the same project."
                _, current_ok = run_turn(chat_service, chat1_id, filler)
                model_ok = model_ok and current_ok
        else:
            for content in chat1_turns:
                database.save_message(chat1_id, "user", content)
                database.save_message(
                    chat1_id,
                    "assistant",
                    "Acknowledged. I will keep that in mind.",
                )
            for index in range(args.filler_turns):
                database.save_message(
                    chat1_id,
                    "user",
                    f"Filler turn {index + 1}: continue normal planning for the same project.",
                )
                database.save_message(
                    chat1_id,
                    "assistant",
                    "Understood. Continuing the same project planning context.",
                )
            chat_service.memory.update_memory_if_needed(chat1_id)

        rows = long_term_rows(database)
        print(f"long_term_memories_count={len(rows)}")
        for row in rows[:5]:
            print(
                "long_term_memory "
                f"namespace={row['namespace_path']} "
                f"memory_id={row['memory_id']} "
                f"category={row['category']} "
                f"key={row['key']} "
                f"status={row['status']} "
                f"source_chat_id={row['source_chat_id']} "
                f"value={row['value']}"
            )

        summarized = summarized_count(database, chat1_id)
        print(f"chat1_summarized_message_count={summarized}")

        chat2_id = chat_service.start_chat(chat_id="demo-chat-2")
        print(f"chat2_id={chat2_id}")

        candidates = structured_candidates(database, chat2_id, scenario.chat2_questions[0])
        print(f"chat2_structured_candidates_count={len(candidates)}")
        for candidate in candidates[:5]:
            print(
                "chat2_candidate "
                f"source={candidate.source} "
                f"record_id={candidate.record_id} "
                f"chat_id={candidate.chat_id} "
                f"source_message_ids={candidate.source_message_ids} "
                f"content={candidate.content}"
            )

        chat2_answers: list[tuple[str, str]] = []
        answered_with_model = False
        for index, question in enumerate(scenario.chat2_questions):
            if args.skip_chat2_answer:
                answer = "SKIPPED (--skip-chat2-answer)"
                print(f"chat2_answer[{index}]={answer}")
            else:
                chat2_result = chat_service.handle_user_turn(chat_id=chat2_id, content=question)
                structured_in_trace = [
                    candidate
                    for candidate in chat2_result.trace.retrieved_candidates
                    if candidate.source == "structured_memory"
                ]
                print(f"chat2_prompt_source[{index}]={chat2_result.trace.metadata.get('prompt_source')}")
                print(f"chat2_fallback_reason[{index}]={chat2_result.trace.metadata.get('fallback_reason')}")
                print(f"chat2_trace_structured_candidates[{index}]={len(structured_in_trace)}")
                print(f"chat2_answer[{index}]={chat2_result.answer}")
                answer = chat2_result.answer
                answered_with_model = answered_with_model or (
                    model_ok and "Model error:" not in chat2_result.answer
                )
            chat2_answers.append((question, answer))

        extraction_ran = summarized > 0
        long_term_written = len(rows) > 0
        chat2_retrieved = len(candidates) > 0
        long_term_text = "\n".join(str(row["value"]) for row in rows)
        retrieved_text = "\n".join(candidate.content for candidate in candidates)
        print_expected_summary(
            expected_phrases=scenario.expected_phrases,
            long_term_text=long_term_text,
            retrieved_text=retrieved_text,
            chat2_answers=chat2_answers,
        )
        print(
            "verification_summary "
            f"mode={args.mode} "
            f"scenario={scenario.name} "
            f"extraction_ran={extraction_ran} "
            f"long_term_written={long_term_written} "
            f"chat2_retrieved={chat2_retrieved} "
            f"answered_with_model={answered_with_model}"
        )

        if args.keep_db:
            preserved = Path.cwd() / "tmp_demo_chatbot.db"
            preserved.write_bytes(db_path.read_bytes())
            print(f"kept_db={preserved}")

        if not long_term_written or not chat2_retrieved:
            raise SystemExit(
                "Natural cross-chat memory flow did not verify. Check model endpoint availability "
                "and LangMem extraction quality in this environment."
            )


if __name__ == "__main__":
    main()
