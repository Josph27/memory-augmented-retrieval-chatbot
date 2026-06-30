"""GistingAgent creates GIST summaries from (query, answer) pairs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from src.database import Database
from src.model_wrapper import ModelWrapper


GIST_PROMPT = (
    "Summarize the following conversation turn into 1–3 sentences. "
    "Focus on key facts, decisions, and important context. "
    "Do not repeat the query verbatim. Keep it concise.\n\n"
    "User query: {query}\n\n"
    "Assistant answer: {answer}\n\n"
    "Gist:"
)

MAX_GIST_CHARS = 250

# Source type for turn-level gists used by retrieval.
TURN_GIST_SOURCE_TYPE = "turn_gist"


@dataclass(frozen=True)
class GistResult:
    """Result of creating one GIST from a conversation turn."""

    gist_id: int
    gist_text: str
    topics_json: str
    retrieved_lt_mem_ids: list[int] = field(default_factory=list)
    new_memories_json: str = "[]"


class GistingAgent:
    """Creates a GIST from a (query, answer) pair and persists it into chat_gists."""

    def __init__(self, database: Database, model: ModelWrapper) -> None:
        self.database = database
        self.model = model

    def create_gist(
        self,
        *,
        chat_id: str,
        query: str,
        answer: str,
        retrieved_memory_ids: list[int] | None = None,
        new_memory_entries: list[dict[str, str]] | None = None,
    ) -> GistResult:
        """Generate and persist a GIST record for one conversation turn."""
        gist_text = self._generate_gist_text(query=query, answer=answer)
        new_memories_json = json.dumps(new_memory_entries or [], ensure_ascii=True)
        gist_id = self.database.insert_chat_gist(
            chat_id=chat_id,
            source_type=TURN_GIST_SOURCE_TYPE,
            gist_text=gist_text,
            topics=[],
            decisions=[],
            open_tasks=[],
            metadata={
                "retrieved_lt_mem_ids": retrieved_memory_ids or [],
                "new_memories_json": new_memories_json,
            },
        )
        return GistResult(
            gist_id=gist_id,
            gist_text=gist_text,
            topics_json="[]",
            retrieved_lt_mem_ids=list(retrieved_memory_ids or []),
            new_memories_json=new_memories_json,
        )

    def _generate_gist_text(self, *, query: str, answer: str) -> str:
        """Call the model for a concise gist; fall back to raw query on failure."""
        prompt = GIST_PROMPT.format(query=query, answer=answer)
        try:
            response = self.model.chat(
                [{"role": "user", "content": prompt}],
                temperature=0,
            )
            gist = response.strip()
            if not gist or len(gist) < 3:
                return self._fallback_gist(query)
            if len(gist) > MAX_GIST_CHARS:
                gist = gist[:MAX_GIST_CHARS].rstrip() + "..."
            return gist
        except Exception:
            return self._fallback_gist(query)

    @staticmethod
    def _fallback_gist(query: str) -> str:
        """Return a fallback gist from the raw query text."""
        fallback = query.strip()
        if len(fallback) > MAX_GIST_CHARS:
            fallback = fallback[:MAX_GIST_CHARS].rstrip() + "..."
        return fallback
