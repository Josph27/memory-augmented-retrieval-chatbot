from __future__ import annotations

import argparse
import sqlite3
import tempfile
import sys
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
        if args.mode == "natural":
            _, model_ok = run_turn(chat_service, chat1_id, MEMORY_BEARING_MESSAGE)
            for index in range(args.filler_turns):
                run_turn(
                    chat_service,
                    chat1_id,
                    f"Filler turn {index + 1}: continue normal planning for the same project.",
                )
        else:
            database.save_message(chat1_id, "user", MEMORY_BEARING_MESSAGE)
            database.save_message(
                chat1_id,
                "assistant",
                "Acknowledged. I will keep that engineering preference in mind.",
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

        retriever = StructuredMemoryRetriever(database)
        candidates = retriever.retrieve(
            chat_id=chat2_id,
            source_plan=SourcePlan(
                source="structured_memory",
                query=CHAT2_QUERY,
                limit=10,
            ),
        )
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

        answered_with_model = False
        if args.skip_chat2_answer:
            print("chat2_answer=SKIPPED (--skip-chat2-answer)")
        else:
            chat2_result = chat_service.handle_user_turn(chat_id=chat2_id, content=CHAT2_QUERY)
            structured_in_trace = [
                candidate
                for candidate in chat2_result.trace.retrieved_candidates
                if candidate.source == "structured_memory"
            ]
            print(f"chat2_prompt_source={chat2_result.trace.metadata.get('prompt_source')}")
            print(f"chat2_fallback_reason={chat2_result.trace.metadata.get('fallback_reason')}")
            print(f"chat2_trace_structured_candidates={len(structured_in_trace)}")
            print(f"chat2_answer={chat2_result.answer}")
            answered_with_model = model_ok and "Model error:" not in chat2_result.answer

        extraction_ran = summarized > 0
        long_term_written = len(rows) > 0
        chat2_retrieved = len(candidates) > 0
        print(
            "verification_summary "
            f"mode={args.mode} "
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
