from __future__ import annotations

import argparse
import json
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
from src.memory.short_term import ShortTermMemory  # noqa: E402
from src.memory.structured_state import active_memories, load_memory_state  # noqa: E402
from src.model_wrapper import ModelWrapper  # noqa: E402


@dataclass(frozen=True)
class ExpectedMemory:
    """One expectation for active structured memory."""

    label: str
    category: str
    key_contains: str | None
    value_contains: tuple[str, ...]


@dataclass(frozen=True)
class ForbiddenMemory:
    """One assertion for information that should not be stored as active memory."""

    label: str
    value_contains: tuple[str, ...]
    category: str | None = None


@dataclass(frozen=True)
class EvalScenario:
    """A synthetic conversation with expected memory behavior."""

    name: str
    messages: tuple[tuple[str, str], ...]
    expected: tuple[ExpectedMemory, ...]
    forbidden: tuple[ForbiddenMemory, ...]


SCENARIOS = (
    EvalScenario(
        name="identity_and_project_correction",
        messages=(
            ("user", "My name is Maya."),
            ("assistant", "Nice to meet you, Maya."),
            ("user", "I am building a recipe planner app."),
            ("assistant", "That sounds useful."),
            ("user", "The app uses Chainlit and SQLite for storage."),
            ("assistant", "Got it."),
            ("user", "Actually the database is Postgres now, not SQLite."),
            ("assistant", "Thanks for the correction."),
            ("user", "Please keep answers concise."),
            ("assistant", "I will keep responses concise."),
            ("user", "Random note: I had coffee today."),
            ("assistant", "Okay."),
            ("user", "The app must run locally; do not suggest cloud services."),
            ("assistant", "Local-only constraint noted."),
            ("user", "Next step is importing recipes from CSV."),
            ("assistant", "CSV import is the next step."),
        ),
        expected=(
            ExpectedMemory("user name", "user_facts", "name", ("maya",)),
            ExpectedMemory("project app", "project_facts", None, ("recipe", "planner")),
            ExpectedMemory("database correction", "project_facts", None, ("postgres",)),
            ExpectedMemory("concise preference", "preferences", None, ("concise",)),
            ExpectedMemory("local-only constraint", "constraints", None, ("local",)),
            ExpectedMemory("csv import task", "open_tasks", None, ("csv",)),
        ),
        forbidden=(
            ForbiddenMemory("stale sqlite database", ("sqlite",), category="project_facts"),
            ForbiddenMemory("coffee noise", ("coffee",)),
        ),
    ),
    EvalScenario(
        name="user_preferences_and_name_correction",
        messages=(
            ("user", "My name is Jordan."),
            ("assistant", "Nice to meet you."),
            ("user", "I prefer bullet points over long paragraphs."),
            ("assistant", "Understood."),
            ("user", "My project is a FastAPI inventory service."),
            ("assistant", "Got it."),
            ("user", "No, Jordan is my name, not the assistant's name."),
            ("assistant", "Thanks for clarifying."),
            ("user", "The API must support CSV export."),
            ("assistant", "CSV export noted."),
            ("user", "Ignore this temporary thought: pizza sounds good."),
            ("assistant", "Okay."),
            ("user", "We decided to use PostgreSQL for inventory records."),
            ("assistant", "PostgreSQL decision noted."),
            ("user", "The deadline is Friday."),
            ("assistant", "Noted."),
        ),
        expected=(
            ExpectedMemory("user name", "user_facts", "name", ("jordan",)),
            ExpectedMemory("name correction", "corrections", None, ("jordan", "name")),
            ExpectedMemory("answer style", "preferences", None, ("bullet",)),
            ExpectedMemory("project service", "project_facts", None, ("fastapi", "inventory")),
            ExpectedMemory("csv export", "open_tasks", None, ("csv", "export")),
            ExpectedMemory("postgres decision", "decisions", None, ("postgres",)),
            ExpectedMemory("deadline", "open_tasks", None, ("friday",)),
        ),
        forbidden=(
            ForbiddenMemory("pizza noise", ("pizza",)),
        ),
    ),
)


class FastChatMemoryModel:
    """Use the real model only for memory extraction, not assistant filler turns."""

    def __init__(self, model: ModelWrapper) -> None:
        self.model = model

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        if temperature == 0.0:
            return self.model.chat(messages, temperature=temperature)
        return "assistant response"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate structured memory extraction.")
    parser.add_argument(
        "--real-chat",
        action="store_true",
        help="Use the configured model for assistant turns as well as memory extraction.",
    )
    args = parser.parse_args()

    config = AppConfig.from_env()
    base_model = ModelWrapper(config)
    model = base_model if args.real_chat else FastChatMemoryModel(base_model)

    print(f"Model: {config.model_name}")
    print(f"Mode: {'real chat + memory' if args.real_chat else 'fast chat + real memory'}")

    failures = 0
    for scenario in SCENARIOS:
        result = run_scenario(scenario, model)
        failures += result

    print()
    if failures:
        print(f"FAIL: {failures} memory expectation(s) failed.")
        return 1

    print("PASS: all memory expectations satisfied.")
    return 0


def run_scenario(scenario: EvalScenario, model: Any) -> int:
    print(f"\n=== {scenario.name} ===")
    with TemporaryDirectory() as temp_dir:
        db = Database(Path(temp_dir) / "chatbot.db")
        chat_id = scenario.name
        db.create_chat(chat_id)
        memory = ShortTermMemory(db, model, raw_message_limit=0, memory_update_batch_size=6)

        for role, content in scenario.messages:
            db.save_message(chat_id, role, content)
            memory.update_memory_if_needed(chat_id)

        memory = ShortTermMemory(db, model, raw_message_limit=0, memory_update_batch_size=1)
        while memory.update_memory_if_needed(chat_id):
            pass

        memory_state = load_memory_state(db.chat_memory_state(chat_id))
        memories = active_memories(memory_state)
        print(json.dumps(memory_state, indent=2, sort_keys=True))

        failures = 0
        for expected in scenario.expected:
            if memory_matches(memories, expected):
                print(f"PASS expected: {expected.label}")
            else:
                failures += 1
                print(f"FAIL expected: {expected.label}")

        for forbidden in scenario.forbidden:
            if memory_contains(memories, forbidden.value_contains, category=forbidden.category):
                failures += 1
                print(f"FAIL forbidden: {forbidden.label}")
            else:
                print(f"PASS forbidden: {forbidden.label}")

        return failures


def memory_matches(memories: list[dict[str, Any]], expected: ExpectedMemory) -> bool:
    for memory in memories:
        if memory["category"] != expected.category:
            continue
        if expected.key_contains and expected.key_contains not in memory["key"].lower():
            continue
        if all(term in memory["value"].lower() for term in expected.value_contains):
            return True
    return False


def memory_contains(
    memories: list[dict[str, Any]],
    terms: tuple[str, ...],
    category: str | None = None,
) -> bool:
    for memory in memories:
        if category is not None and memory["category"] != category:
            continue
        searchable = f"{memory['category']} {memory['key']} {memory['value']}".lower()
        if all(term in searchable for term in terms):
            return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
