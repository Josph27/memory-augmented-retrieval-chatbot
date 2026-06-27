from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from src.database import Database, StoredMessage
from src.memory.constants import (
    GIST_KEEP_RECENT_MESSAGES,
    GIST_MAX_MESSAGES_PER_GIST,
    GIST_MIN_MESSAGES_TO_SUMMARIZE,
)
from src.memory.structured_state import ChatModel, TRANSCRIPT_MARKER_PATTERN


CURRENT_CHAT_GIST_SOURCE = "current_chat_gist"

GIST_SUMMARY_SYSTEM_PROMPT = """You create compact current-chat gists.

Return ONLY valid JSON.
Do not include markdown.
Do not write a transcript.
Do not continue the conversation.
Do not invent facts.
Only summarize information supported by the provided messages.
Keep information likely to matter later in this chat.

Return exactly this object shape:
{
  "summary": "concise paragraph",
  "topics": ["short topic"],
  "decisions": ["decision made"],
  "open_tasks": ["unfinished task"],
  "important_facts": ["fact likely to matter later"],
  "corrections": ["correction made by the user"]
}

Use [] for empty lists.
"""


@dataclass(frozen=True)
class ChatGistSummary:
    """Validated output from a current-chat gist extractor."""

    summary: str
    topics: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    open_tasks: list[str] = field(default_factory=list)
    important_facts: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ChatGistCreationResult:
    """Result of one explicit current-chat gist creation attempt."""

    created: bool
    gist_id: int | None = None
    summarized_message_ids: list[int] = field(default_factory=list)
    skipped_reason: str | None = None


class ChatGistExtractor(Protocol):
    """Protocol for LLM or deterministic gist extraction."""

    def summarize(self, messages: list[StoredMessage]) -> ChatGistSummary | None:
        """Return a validated gist summary or None when no gist should be stored."""
        ...


class LLMChatGistExtractor:
    """LLM-backed extractor for current-chat gist JSON."""

    def __init__(self, model: ChatModel) -> None:
        self.model = model

    def summarize(self, messages: list[StoredMessage]) -> ChatGistSummary | None:
        """Ask the configured chat model for one compact gist."""
        output = self.model.chat(
            [
                {"role": "system", "content": GIST_SUMMARY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": format_messages_for_gist_prompt(messages),
                },
            ],
            temperature=0.0,
        )
        return parse_gist_summary(output)


class CurrentChatGistSummarizer:
    """Explicit service for compacting older current-chat messages into gists."""

    def __init__(
        self,
        database: Database,
        extractor: ChatGistExtractor | None = None,
        model: ChatModel | None = None,
        min_messages_to_summarize: int = GIST_MIN_MESSAGES_TO_SUMMARIZE,
        keep_recent_messages: int = GIST_KEEP_RECENT_MESSAGES,
        max_messages_per_gist: int = GIST_MAX_MESSAGES_PER_GIST,
    ) -> None:
        self.database = database
        self.extractor = extractor or (LLMChatGistExtractor(model) if model else None)
        self.min_messages_to_summarize = min_messages_to_summarize
        self.keep_recent_messages = keep_recent_messages
        self.max_messages_per_gist = max_messages_per_gist

    def create_gist_if_needed(self, chat_id: str) -> ChatGistCreationResult:
        """Create one current-chat gist from old unsummarized messages when eligible."""
        if self.extractor is None:
            return ChatGistCreationResult(
                created=False,
                skipped_reason="no_gist_extractor_configured",
            )

        messages = self.database.old_unsummarized_messages(
            chat_id=chat_id,
            raw_message_limit=self.keep_recent_messages,
            batch_size=self.max_messages_per_gist,
        )
        latest_user_id = latest_user_message_id(self.database.messages_for_chat(chat_id))
        if latest_user_id is not None:
            messages = [message for message in messages if message.id != latest_user_id]
        if len(messages) < self.min_messages_to_summarize:
            return ChatGistCreationResult(
                created=False,
                skipped_reason="not_enough_old_unsummarized_messages",
            )

        summary = self.extractor.summarize(messages)
        if summary is None or not summary.summary.strip():
            return ChatGistCreationResult(
                created=False,
                skipped_reason="invalid_or_empty_gist",
            )

        message_ids = [message.id for message in messages]
        gist_id = self.database.insert_chat_gist(
            chat_id=chat_id,
            source_type=CURRENT_CHAT_GIST_SOURCE,
            gist_text=summary.summary,
            topics=summary.topics,
            decisions=summary.decisions,
            open_tasks=summary.open_tasks,
            start_message_id=min(message_ids),
            end_message_id=max(message_ids),
            metadata={
                "important_facts": summary.important_facts,
                "corrections": summary.corrections,
                "source_message_count": len(messages),
                "summarizer": self.extractor.__class__.__name__,
                "status": "active",
            },
        )
        self.database.mark_messages_summarized(message_ids)
        return ChatGistCreationResult(
            created=True,
            gist_id=gist_id,
            summarized_message_ids=message_ids,
        )


def format_messages_for_gist_prompt(messages: list[StoredMessage]) -> str:
    """Format source messages with ids for gist extraction."""
    lines = ["Messages to summarize:"]
    for message in messages:
        lines.append(f"{message.id} {message.role}: {message.content}")
    return "\n".join(lines)


def latest_user_message_id(messages: list[StoredMessage]) -> int | None:
    """Return the newest user message id in a chat transcript."""
    for message in reversed(messages):
        if message.role == "user":
            return message.id
    return None


def parse_gist_summary(raw_output: str) -> ChatGistSummary | None:
    """Parse and validate model output for a current-chat gist."""
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None

    summary = clean_string(parsed.get("summary"))
    if not summary or transcript_marker_count(summary) >= 3:
        return None

    return ChatGistSummary(
        summary=summary,
        topics=clean_string_list(parsed.get("topics")),
        decisions=clean_string_list(parsed.get("decisions")),
        open_tasks=clean_string_list(parsed.get("open_tasks")),
        important_facts=clean_string_list(parsed.get("important_facts")),
        corrections=clean_string_list(parsed.get("corrections")),
    )


def clean_string(value: Any) -> str:
    """Normalize one model-produced string."""
    if not isinstance(value, str):
        return ""
    return " ".join(value.strip().split())


def clean_string_list(value: Any) -> list[str]:
    """Normalize a model-produced string list."""
    if not isinstance(value, list):
        return []
    cleaned = [clean_string(item) for item in value]
    return [item for item in cleaned if item]


def transcript_marker_count(value: str) -> int:
    """Count transcript-like role markers in gist text."""
    return len(TRANSCRIPT_MARKER_PATTERN.findall(value))
