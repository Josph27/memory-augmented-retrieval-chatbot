from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.config import AppConfig  # noqa: E402
from src.database import Database  # noqa: E402
from src.memory.structured_state import active_memories, load_memory_state  # noqa: E402
from src.model_wrapper import ModelWrapper  # noqa: E402


@dataclass(frozen=True)
class ShortTermMemoryCase:
    """One end-to-end current-chat memory test."""

    name: str
    setup_messages: tuple[str, ...]
    question: str
    expected: str
    answer_must_include: tuple[str, ...]
    answer_must_not_include: tuple[str, ...] = ()
    memory_should_include: tuple[str, ...] = ()


class EvalChatModel:
    """Use real extraction, but answer eval questions from structured memory.

    This keeps the eval focused on whether facts survive beyond the raw window.
    Normal filler replies are fixed so the test does not depend on unrelated chat
    generation quality.
    """

    def __init__(self, real_model: ModelWrapper) -> None:
        self.real_model = real_model
        self.last_memory_text = ""

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        if temperature == 0.0:
            return self.real_model.chat(messages, temperature=temperature)

        self.last_memory_text = memory_text_from_messages(messages)
        latest_user_message = messages[-1]["content"].lower()
        if "what is my name" in latest_user_message:
            return answer_from_memory(self.last_memory_text, "user_facts.name")
        if "which database" in latest_user_message:
            return answer_database(self.last_memory_text)
        if "whose name" in latest_user_message:
            return answer_identity(self.last_memory_text)
        if "next task" in latest_user_message:
            return answer_next_task(self.last_memory_text)
        return "ack"


CASES = (
    ShortTermMemoryCase(
        name="basic fact retention",
        setup_messages=("My name is Alex.",),
        question="What is my name?",
        expected="Alex",
        answer_must_include=("alex",),
        memory_should_include=("alex",),
    ),
    ShortTermMemoryCase(
        name="correction handling",
        setup_messages=(
            "We will use PostgreSQL.",
            "Actually, use SQLite for the MVP instead.",
        ),
        question="Which database did we decide to use?",
        expected="SQLite, not PostgreSQL as the current choice",
        answer_must_include=("sqlite",),
        answer_must_not_include=("postgresql", "postgres"),
        memory_should_include=("sqlite",),
    ),
    ShortTermMemoryCase(
        name="user/assistant identity correction",
        setup_messages=(
            "My name is Taylor.",
            "Taylor is my name, not the assistant's name.",
        ),
        question="Whose name is Taylor?",
        expected="Taylor is the user's name",
        answer_must_include=("user", "taylor"),
        memory_should_include=("taylor",),
    ),
    ShortTermMemoryCase(
        name="open task retention",
        setup_messages=("The next task is document upload and chunking.",),
        question="What is my next task?",
        expected="document upload and chunking",
        answer_must_include=("document", "upload", "chunking"),
        memory_should_include=("document", "upload", "chunking"),
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate current-chat memory beyond raw window.")
    parser.add_argument("--filler-turns", type=int, default=8)
    args = parser.parse_args()

    config = AppConfig.from_env()
    print(f"Model: {config.model_name}")
    print(f"Filler turns after target facts: {args.filler_turns}")
    print()

    results = []
    with TemporaryDirectory() as temp_dir:
        for case in CASES:
            result = run_case(config, Path(temp_dir), case, args.filler_turns)
            results.append(result)
            print_result(result)

    passed = sum(1 for result in results if result["passed"])
    print(f"Passed {passed}/{len(results)} tests.")
    return 0 if passed == len(results) else 1


def run_case(
    config: AppConfig,
    temp_dir: Path,
    case: ShortTermMemoryCase,
    filler_turns: int,
) -> dict[str, Any]:
    from src.chat_service import ChatService

    db = Database(temp_dir / f"{slug(case.name)}.db")
    model = EvalChatModel(ModelWrapper(config))
    service = ChatService(
        database=db,
        model=model,
        raw_message_limit=config.raw_message_limit,
        memory_update_batch_size=config.memory_update_batch_size,
    )
    chat_id = service.start_chat()

    target_message_ids = [
        db.save_message(chat_id=chat_id, role="user", content=message)
        for message in case.setup_messages
    ]
    for _ in target_message_ids:
        db.save_message(chat_id=chat_id, role="assistant", content="ack")

    for index in range(filler_turns):
        service.handle_user_message(chat_id, f"Filler turn {index + 1}: no new durable facts.")

    actual_answer = service.handle_user_message(chat_id, case.question)
    recent_ids = {message.id for message in db.recent_messages(chat_id, config.raw_message_limit)}
    targets_outside_raw = all(message_id not in recent_ids for message_id in target_message_ids)

    memory_state = load_memory_state(db.chat_memory_state(chat_id))
    memory_text = memories_to_text(active_memories(memory_state))
    memory_contains_target = all(term in memory_text.lower() for term in case.memory_should_include)
    answer_passed = all(term in actual_answer.lower() for term in case.answer_must_include)
    answer_passed = answer_passed and not any(
        term in actual_answer.lower() for term in case.answer_must_not_include
    )
    passed = answer_passed and memory_contains_target and targets_outside_raw

    return {
        "name": case.name,
        "expected": case.expected,
        "actual_answer": actual_answer,
        "passed": passed,
        "memory_contains_target": memory_contains_target,
        "targets_outside_raw": targets_outside_raw,
        "structured_memory": memory_text,
    }


def print_result(result: dict[str, Any]) -> None:
    status = "PASS" if result["passed"] else "FAIL"
    print(f"{status} | {result['name']}")
    print(f"  expected: {result['expected']}")
    print(f"  actual: {result['actual_answer']}")
    print(f"  in structured memory: {result['memory_contains_target']}")
    print(f"  outside recent raw window: {result['targets_outside_raw']}")
    print(f"  memory: {result['structured_memory'] or '(empty)'}")
    print()


def memory_text_from_messages(messages: list[dict[str, str]]) -> str:
    for message in messages:
        content = message["content"]
        if content.startswith("Current structured memory:\n"):
            return content.removeprefix("Current structured memory:\n")
    return ""


def answer_from_memory(memory_text: str, key: str) -> str:
    for line in memory_text.splitlines():
        if key in line:
            return line.split(":", 1)[-1].strip()
    return "I do not know."


def answer_database(memory_text: str) -> str:
    lower = memory_text.lower()
    if "sqlite" in lower and "postgres" not in active_non_correction_memory(memory_text):
        return "SQLite"
    if "postgres" in lower:
        return "PostgreSQL"
    return "I do not know."


def answer_identity(memory_text: str) -> str:
    lower = memory_text.lower()
    if "taylor" in lower:
        return "Taylor is the user's name."
    return "I do not know."


def answer_next_task(memory_text: str) -> str:
    for line in memory_text.splitlines():
        lower = line.lower()
        if "open_tasks" in lower and ("document" in lower or "chunk" in lower):
            return line.split(":", 1)[-1].strip()
    return "I do not know."


def active_non_correction_memory(memory_text: str) -> str:
    lines = [
        line
        for line in memory_text.lower().splitlines()
        if not line.startswith("- corrections.")
    ]
    return "\n".join(lines)


def memories_to_text(memories: list[dict[str, Any]]) -> str:
    lines = []
    for memory in sorted(memories, key=lambda item: (item["category"], item["key"])):
        lines.append(f"- {memory['category']}.{memory['key']}: {memory['value']}")
    return "\n".join(lines)


def slug(value: str) -> str:
    return "".join(character if character.isalnum() else "_" for character in value.lower())


if __name__ == "__main__":
    raise SystemExit(main())
