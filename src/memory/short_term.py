from __future__ import annotations

import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Literal, Protocol

from src.context.token_estimator import TokenEstimator, build_token_estimator, count_text
from src.database import Database, StoredMessage
from src.memory.constants import (
    MEMORY_REPLAY_MAX_INPUT_TOKENS,
    MEMORY_UPDATE_BATCH_SIZE,
    MEMORY_UPDATE_MAX_INPUT_TOKENS,
    RAW_MESSAGE_LIMIT,
)
from src.memory.langmem_structured import LangMemBackendConfig, LangMemStructuredMemoryState
from src.memory.long_term_store import SQLiteLongTermMemoryStore
from src.memory.memory_trace import memory_write_to_trace_row
from src.memory.structured_state import (
    ChatModel,
    MemoryUpdateResult,
    dumps_memory_state,
    format_memory_for_prompt,
    load_memory_state,
    memory_state_is_empty,
)


MEMORY_CONTEXT_ROLE = "system"
CHAT_END_NOOP_REASONS = frozenset({"langmem_no_valid_memories", "no_user_messages"})
logger = logging.getLogger(__name__)

SchedulingProfileName = Literal["online", "offline_replay"]


@dataclass(frozen=True)
class ShortTermContext:
    """Context selected for a model call."""

    memory_state: dict[str, list[dict[str, Any]]]
    raw_messages: list[StoredMessage]


@dataclass(frozen=True)
class ChatEndMemoryProcessingResult:
    """Bounded chat-end memory processing outcome."""

    processed_message_count: int
    batch_count: int


@dataclass(frozen=True)
class MemoryBatchProfile:
    """Token-aware structured-memory scheduling policy."""

    trigger_tokens: int
    max_input_tokens: int
    max_messages: int
    protected_recent_tokens: int = 0


@dataclass(frozen=True)
class SelectedMemoryBatch:
    """One selected pending batch plus compact diagnostics."""

    messages: list[StoredMessage]
    eligible_tokens: int
    assistant_only: bool = False


@dataclass(frozen=True)
class ConversationUnit:
    """Chronological conversational unit preserved across batching boundaries."""

    messages: list[StoredMessage]
    token_count: int

    @property
    def has_user(self) -> bool:
        return any(message.role == "user" for message in self.messages)

    @property
    def has_assistant(self) -> bool:
        return any(message.role == "assistant" for message in self.messages)

    @property
    def message_ids(self) -> list[int]:
        return [message.id for message in self.messages]


class ChatEndMemoryProcessingError(RuntimeError):
    """Raised when a pending chat-end memory batch cannot be accepted."""


class StructuredMemoryUpdater(Protocol):
    """Protocol for structured memory update backends."""

    def update(
        self,
        existing_memory: dict[str, list[dict[str, Any]]],
        messages: list[StoredMessage],
    ) -> MemoryUpdateResult:
        """Update structured memory from a selected raw-message batch."""
        ...


class ShortTermMemory:
    """Builds chat context and periodically updates structured memory."""

    def __init__(
        self,
        database: Database,
        model: ChatModel,
        raw_message_limit: int = RAW_MESSAGE_LIMIT,
        memory_update_batch_size: int = MEMORY_UPDATE_BATCH_SIZE,
        structured_memory_updater: StructuredMemoryUpdater | None = None,
        *,
        recent_messages_max_count: int | None = None,
        memory_update_trigger_tokens: int = 0,
        memory_update_max_input_tokens: int = MEMORY_UPDATE_MAX_INPUT_TOKENS,
        memory_update_max_messages: int | None = None,
        memory_recent_protection_tokens: int = 0,
        memory_replay_trigger_tokens: int = 0,
        memory_replay_max_input_tokens: int = MEMORY_REPLAY_MAX_INPUT_TOKENS,
        memory_replay_max_messages: int | None = None,
        token_estimator: TokenEstimator | None = None,
    ) -> None:
        self.database = database
        self.recent_messages_max_count = max(
            1,
            recent_messages_max_count
            if recent_messages_max_count is not None
            else raw_message_limit,
        )
        selected_model_name = getattr(model, "model_name", None)
        self.token_estimator = token_estimator or build_token_estimator(selected_model_name)
        self.online_profile = MemoryBatchProfile(
            trigger_tokens=max(0, memory_update_trigger_tokens),
            max_input_tokens=max(1, memory_update_max_input_tokens),
            max_messages=max(
                1,
                memory_update_max_messages
                if memory_update_max_messages is not None
                else memory_update_batch_size,
            ),
            protected_recent_tokens=max(0, memory_recent_protection_tokens),
        )
        self.offline_replay_profile = MemoryBatchProfile(
            trigger_tokens=max(0, memory_replay_trigger_tokens),
            max_input_tokens=max(1, memory_replay_max_input_tokens),
            max_messages=max(
                1,
                memory_replay_max_messages
                if memory_replay_max_messages is not None
                else memory_update_batch_size,
            ),
            protected_recent_tokens=0,
        )
        self.structured_memory = structured_memory_updater or LangMemStructuredMemoryState(
            config=LangMemBackendConfig.from_env(model_name=selected_model_name),
            long_term_store=SQLiteLongTermMemoryStore(database),
        )
        self.last_saved_memory_rows: list[dict[str, Any]] = []
        self.last_processed_message_ids: list[int] = []
        self.last_schedule_profile: SchedulingProfileName | None = None

    def build_context(
        self,
        chat_id: str,
        latest_user_message_id: int | None = None,
        token_budget: int | None = None,
    ) -> ShortTermContext:
        """Return structured memory plus recent raw messages for the current chat."""
        del token_budget
        if latest_user_message_id is None:
            raw_messages = self.database.recent_messages(
                chat_id,
                self.recent_messages_max_count,
            )
        else:
            raw_messages = self.database.recent_messages_before_id(
                chat_id=chat_id,
                before_message_id=latest_user_message_id,
                limit=self.recent_messages_max_count,
            )

        return ShortTermContext(
            memory_state=load_memory_state(self.database.chat_memory_state(chat_id)),
            raw_messages=raw_messages,
        )

    def build_model_messages(
        self,
        system_prompt: str,
        context: ShortTermContext,
        latest_user_message: dict[str, str] | None = None,
    ) -> list[dict[str, str]]:
        """Convert selected short-term memory into chat-completions messages."""
        model_messages = [{"role": "system", "content": system_prompt}]
        if not memory_state_is_empty(context.memory_state):
            model_messages.append(
                {
                    "role": MEMORY_CONTEXT_ROLE,
                    "content": (
                        "Current structured memory:\n"
                        f"{format_memory_for_prompt(context.memory_state)}"
                    ),
                }
            )

        model_messages.extend(
            {"role": message.role, "content": message.content}
            for message in context.raw_messages
        )
        if latest_user_message is not None:
            model_messages.append(latest_user_message)
        return model_messages

    def update_memory_if_needed(
        self,
        chat_id: str,
        scheduling_profile: SchedulingProfileName = "online",
    ) -> bool:
        """Update structured memory from one token-aware batch if threshold is met."""
        self.last_saved_memory_rows = []
        self.last_processed_message_ids = []
        self.last_schedule_profile = scheduling_profile
        started = perf_counter()
        profile = self._profile_for(scheduling_profile)
        selected = self._select_pending_batch(
            chat_id,
            profile=profile,
            flush_all=False,
        )
        if not selected.messages:
            print(
                "memory_update_timing "
                f"chat_id={chat_id} profile={scheduling_profile} triggered=False "
                f"eligible_tokens={selected.eligible_tokens} "
                f"duration_ms={elapsed_ms(started)}"
            )
            return False

        if selected.assistant_only:
            print(
                "memory_update_timing "
                f"chat_id={chat_id} profile={scheduling_profile} triggered=False "
                f"eligible_tokens={selected.eligible_tokens} "
                "reason=assistant_only_pending "
                f"duration_ms={elapsed_ms(started)}"
            )
            return False

        return self._apply_batch(
            chat_id=chat_id,
            messages=selected.messages,
            started=started,
            profile_name=scheduling_profile,
            allow_noop=False,
        )

    def process_replay_batches(self, chat_id: str) -> ChatEndMemoryProcessingResult:
        """Process pending replay history using the offline scheduling profile."""
        self.last_saved_memory_rows = []
        self.last_processed_message_ids = []
        self.last_schedule_profile = "offline_replay"
        processed_message_count = 0
        batch_count = 0
        while self.update_memory_if_needed(chat_id, scheduling_profile="offline_replay"):
            processed_message_count += len(self.last_processed_message_ids)
            batch_count += 1
        return ChatEndMemoryProcessingResult(
            processed_message_count=processed_message_count,
            batch_count=batch_count,
        )

    def process_all_for_chat_end(
        self,
        chat_id: str,
    ) -> ChatEndMemoryProcessingResult:
        """Process every pending message regardless of trigger threshold."""
        self.last_saved_memory_rows = []
        self.last_processed_message_ids = []
        self.last_schedule_profile = "offline_replay"
        processed_message_count = 0
        batch_count = 0

        while True:
            selected = self._select_pending_batch(
                chat_id,
                profile=self.offline_replay_profile,
                flush_all=True,
            )
            if not selected.messages:
                return ChatEndMemoryProcessingResult(
                    processed_message_count=processed_message_count,
                    batch_count=batch_count,
                )
            self._apply_batch(
                chat_id=chat_id,
                messages=selected.messages,
                started=perf_counter(),
                profile_name="offline_replay",
                allow_noop=True,
            )
            processed_message_count += len(selected.messages)
            batch_count += 1

    def _apply_batch(
        self,
        *,
        chat_id: str,
        messages: list[StoredMessage],
        started: float,
        profile_name: SchedulingProfileName,
        allow_noop: bool,
    ) -> bool:
        current_memory = load_memory_state(self.database.chat_memory_state(chat_id))
        extraction_started = perf_counter()
        result = self.structured_memory.update(
            existing_memory=current_memory,
            messages=messages,
        )
        extraction_ms = elapsed_ms(extraction_started)
        reason = result.rejection_reason or "unknown"
        valid_noop = not result.accepted and allow_noop and reason in CHAT_END_NOOP_REASONS
        if not result.accepted and not valid_noop:
            logger.warning(
                "structured memory update rejected chat_id=%s profile=%s message_ids=%s reason=%s",
                chat_id,
                profile_name,
                [message.id for message in messages],
                reason,
            )
            self.database.upsert_chat_memory_state(chat_id, dumps_memory_state(result.memory_state))
            if allow_noop:
                raise ChatEndMemoryProcessingError(
                    f"Chat-end memory processing rejected for {chat_id}: {reason}"
                )
            print(
                "memory_update_timing "
                f"chat_id={chat_id} profile={profile_name} triggered=True accepted=False "
                f"message_ids={[message.id for message in messages]} "
                f"extraction_ms={extraction_ms} "
                f"duration_ms={elapsed_ms(started)}"
            )
            return False

        self.database.upsert_chat_memory_state(chat_id, dumps_memory_state(result.memory_state))
        self.database.mark_messages_summarized([message.id for message in messages])
        saved_records = getattr(self.structured_memory, "last_saved_records", [])
        rows = [memory_write_to_trace_row(record) for record in saved_records]
        if allow_noop:
            self.last_saved_memory_rows.extend(rows)
        else:
            self.last_saved_memory_rows = rows
        self.last_processed_message_ids = [message.id for message in messages]
        if valid_noop:
            logger.info(
                "chat end memory batch skipped chat_id=%s message_ids=%s reason=%s",
                chat_id,
                [message.id for message in messages],
                reason,
            )
        print(
            "memory_update_timing "
            f"chat_id={chat_id} profile={profile_name} triggered=True accepted={result.accepted} "
            f"message_ids={[message.id for message in messages]} "
            f"extraction_ms={extraction_ms} "
            f"duration_ms={elapsed_ms(started)}"
        )
        return result.accepted

    def _select_pending_batch(
        self,
        chat_id: str,
        *,
        profile: MemoryBatchProfile,
        flush_all: bool,
    ) -> SelectedMemoryBatch:
        pending = [message for message in self.database.messages_for_chat(chat_id) if not message.summarized]
        if not pending:
            return SelectedMemoryBatch(messages=[], eligible_tokens=0)

        pending_units = self._conversation_units(pending)
        if not pending_units:
            return SelectedMemoryBatch(messages=[], eligible_tokens=0)

        protected_ids = (
            self._protected_recent_suffix_ids(pending_units, profile.protected_recent_tokens)
            if not flush_all
            else set()
        )
        eligible_units = [
            unit
            for unit in pending_units
            if not any(message.id in protected_ids for message in unit.messages)
        ]
        eligible = [message for unit in eligible_units for message in unit.messages]
        eligible_tokens = sum(self._message_tokens(message) for message in eligible)
        if not eligible:
            return SelectedMemoryBatch(messages=[], eligible_tokens=0)
        if not flush_all and eligible_tokens < profile.trigger_tokens:
            return SelectedMemoryBatch(messages=[], eligible_tokens=eligible_tokens)

        batch = self._take_oldest_fitting_batch(
            eligible_units,
            max_input_tokens=profile.max_input_tokens,
            max_messages=profile.max_messages,
        )
        if batch:
            return SelectedMemoryBatch(messages=batch, eligible_tokens=eligible_tokens)

        assistant_only = not any(unit.has_user for unit in eligible_units)
        if assistant_only and flush_all:
            return SelectedMemoryBatch(
                messages=eligible,
                eligible_tokens=eligible_tokens,
                assistant_only=True,
            )
        return SelectedMemoryBatch(
            messages=[],
            eligible_tokens=eligible_tokens,
            assistant_only=assistant_only,
        )

    def _take_oldest_fitting_batch(
        self,
        eligible_units: list[ConversationUnit],
        *,
        max_input_tokens: int,
        max_messages: int,
    ) -> list[StoredMessage]:
        if not eligible_units:
            return []

        first_user_index = next((index for index, unit in enumerate(eligible_units) if unit.has_user), None)
        if first_user_index is None:
            return []

        batch_units: list[ConversationUnit] = []
        total_tokens = 0
        total_messages = 0
        for unit in eligible_units:
            unit_message_count = len(unit.messages)
            if not batch_units and unit.token_count > max_input_tokens:
                batch_units.append(unit)
                break
            if batch_units and total_tokens + unit.token_count > max_input_tokens:
                break
            if batch_units and total_messages + unit_message_count > max_messages:
                break
            if not batch_units and total_messages + unit_message_count > max_messages:
                batch_units.append(unit)
                break
            if not batch_units and total_tokens + unit.token_count > max_input_tokens:
                break
            batch_units.append(unit)
            total_tokens += unit.token_count
            total_messages += unit_message_count

        batch = [message for unit in batch_units for message in unit.messages]
        if any(unit.has_user for unit in batch_units):
            return batch
        return []

    def _protected_recent_suffix_ids(
        self,
        units: list[ConversationUnit],
        protection_tokens: int,
    ) -> set[int]:
        if protection_tokens <= 0:
            return set()
        protected_ids: set[int] = set()
        total = 0
        for unit in reversed(units):
            for message in unit.messages:
                protected_ids.add(message.id)
            total += unit.token_count
            if total >= protection_tokens:
                break
        return protected_ids

    def _conversation_units(
        self,
        messages: list[StoredMessage],
    ) -> list[ConversationUnit]:
        units: list[ConversationUnit] = []
        current: list[StoredMessage] = []
        for message in messages:
            if not current:
                current = [message]
                continue
            previous = current[-1]
            if previous.role == "user" and message.role == "assistant":
                current.append(message)
                units.append(self._make_unit(current))
                current = []
                continue
            units.append(self._make_unit(current))
            current = [message]
        if current:
            units.append(self._make_unit(current))
        return units

    def _make_unit(self, messages: list[StoredMessage]) -> ConversationUnit:
        return ConversationUnit(
            messages=list(messages),
            token_count=sum(self._message_tokens(message) for message in messages),
        )

    def _profile_for(self, name: SchedulingProfileName) -> MemoryBatchProfile:
        if name == "offline_replay":
            return self.offline_replay_profile
        return self.online_profile

    def _message_tokens(self, message: StoredMessage) -> int:
        return max(
            1,
            count_text(
                self.token_estimator,
                f"{message.role}: {message.content}",
            ),
        )


def elapsed_ms(started: float) -> float:
    """Return elapsed milliseconds rounded for compact timing logs."""
    return round((perf_counter() - started) * 1000, 2)
