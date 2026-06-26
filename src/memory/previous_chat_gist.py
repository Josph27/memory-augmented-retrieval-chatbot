from __future__ import annotations

from dataclasses import dataclass, field

from src.database import Database, StoredChat, StoredMessage
from src.memory.chat_gist_summarizer import (
    ChatGistExtractor,
    ChatGistSummary,
    LLMChatGistExtractor,
)
from src.memory.structured_state import ChatModel


PREVIOUS_CHAT_GIST_SOURCE = "previous_chat_gist"


@dataclass(frozen=True)
class PreviousChatGistResult:
    """Result from generating previous-chat gists."""

    created_count: int
    skipped_count: int
    gist_ids: list[int] = field(default_factory=list)
    skipped_reasons: dict[str, str] = field(default_factory=dict)


class DeterministicPreviousChatGistExtractor:
    """Small deterministic gist extractor for tests and offline CLI use."""

    def summarize(self, messages: list[StoredMessage]) -> ChatGistSummary | None:
        """Create a compact extractive gist without model calls."""
        if not messages:
            return None
        first_user = next((message.content for message in messages if message.role == "user"), "")
        last_user = next(
            (message.content for message in reversed(messages) if message.role == "user"),
            "",
        )
        summary_parts = []
        if first_user:
            summary_parts.append(f"Earlier user request: {compact_text(first_user)}")
        if last_user and last_user != first_user:
            summary_parts.append(f"Later user request: {compact_text(last_user)}")
        if not summary_parts:
            summary_parts.append(compact_text(messages[-1].content))
        return ChatGistSummary(
            summary=" ".join(summary_parts),
            topics=extract_keywords(" ".join(message.content for message in messages)),
        )


class PreviousChatGistGenerator:
    """Generate previous-chat gist rows from existing chat transcripts."""

    def __init__(
        self,
        database: Database,
        extractor: ChatGistExtractor | None = None,
        model: ChatModel | None = None,
        min_messages: int = 2,
        max_messages_per_gist: int = 80,
    ) -> None:
        self.database = database
        self.extractor = extractor or (LLMChatGistExtractor(model) if model else None)
        self.min_messages = min_messages
        self.max_messages_per_gist = max_messages_per_gist

    def generate_for_existing_chats(
        self,
        active_chat_id: str | None = None,
        limit: int = 50,
    ) -> PreviousChatGistResult:
        """Create previous-chat gists for chats that do not already have one."""
        if self.extractor is None:
            return PreviousChatGistResult(
                created_count=0,
                skipped_count=0,
                skipped_reasons={"all": "no_gist_extractor_configured"},
            )

        created: list[int] = []
        skipped_reasons: dict[str, str] = {}
        chats = self.database.list_chats(limit=limit, require_messages=True)
        for chat in chats:
            if chat.id == active_chat_id:
                skipped_reasons[chat.id] = "active_chat"
                continue
            if self.database.chat_gists_for_chat(
                chat.id,
                source_type=PREVIOUS_CHAT_GIST_SOURCE,
            ):
                skipped_reasons[chat.id] = "already_has_previous_chat_gist"
                continue
            result = self.generate_for_chat(chat)
            if result is None:
                skipped_reasons[chat.id] = "not_enough_or_empty_messages"
            else:
                created.append(result)
        return PreviousChatGistResult(
            created_count=len(created),
            skipped_count=len(skipped_reasons),
            gist_ids=created,
            skipped_reasons=skipped_reasons,
        )

    def generate_for_chat(self, chat: StoredChat) -> int | None:
        """Create one previous-chat gist for a single chat if eligible."""
        messages = self.database.messages_for_chat(chat.id)[: self.max_messages_per_gist]
        if len(messages) < self.min_messages:
            return None
        summary = self.extractor.summarize(messages) if self.extractor else None
        if summary is None or not summary.summary.strip():
            return None
        message_ids = [message.id for message in messages]
        return self.database.insert_chat_gist(
            chat_id=chat.id,
            source_type=PREVIOUS_CHAT_GIST_SOURCE,
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
                "summarizer": self.extractor.__class__.__name__ if self.extractor else "",
                "status": "active",
                "chat_title": chat.title,
                "gist_scope": "previous_chat",
            },
        )


def compact_text(text: str, limit: int = 180) -> str:
    """Normalize and truncate text for deterministic gist summaries."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 3].rstrip()}..."


def extract_keywords(text: str, limit: int = 5) -> list[str]:
    """Extract simple stable keywords for deterministic gist metadata."""
    stopwords = {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "you",
        "are",
        "was",
        "were",
        "from",
        "have",
        "chat",
        "please",
    }
    keywords = []
    for token in text.lower().replace("/", " ").replace("-", " ").split():
        cleaned = token.strip(".,:;!?()[]{}\"'")
        if len(cleaned) < 4 or cleaned in stopwords or cleaned in keywords:
            continue
        keywords.append(cleaned)
        if len(keywords) >= limit:
            break
    return keywords


def previous_chat_gist_generation_enabled() -> bool:
    """Return whether automatic previous-chat gist generation is enabled."""
    import os

    return os.getenv("PREVIOUS_CHAT_GIST_GENERATION_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
