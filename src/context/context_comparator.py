from __future__ import annotations

from dataclasses import asdict, dataclass, field

from src.context.token_estimator import ApproximateTokenEstimator, TokenEstimator
from src.core.contracts import ContextPacket


TOKEN_DIFFERENCE_RATIO_WARNING = 0.5
TOKEN_DIFFERENCE_ABSOLUTE_WARNING = 50


@dataclass(frozen=True)
class PromptShape:
    """Compact prompt-shape summary for trace comparison."""

    estimated_tokens: int
    message_count: int
    section_order: list[str] = field(default_factory=list)
    has_structured_memory: bool = False
    has_recent_messages: bool = False
    has_latest_user_message: bool = False


@dataclass(frozen=True)
class ContextComparison:
    """Comparison between legacy prompt messages and trace-only ContextPacket."""

    old_prompt: PromptShape
    new_context_packet: PromptShape
    token_difference: int
    token_difference_ratio: float
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Return a plain dict suitable for WorkflowTrace metadata."""
        return asdict(self)


class ContextComparator:
    """Compare legacy ShortTermMemory prompts with trace-only ContextPackets."""

    def __init__(self, token_estimator: TokenEstimator | None = None) -> None:
        self.token_estimator = token_estimator or ApproximateTokenEstimator()

    def compare(
        self,
        old_model_messages: list[dict[str, str]],
        new_context_packet: ContextPacket,
        latest_user_message: dict[str, str],
    ) -> ContextComparison:
        """Compare prompt shape and emit compact warnings for trace debugging."""
        old_shape = self._shape_from_messages(
            messages=old_model_messages,
            latest_user_message=latest_user_message,
        )
        new_shape = self._shape_from_packet(
            packet=new_context_packet,
            latest_user_message=latest_user_message,
        )
        token_difference = new_shape.estimated_tokens - old_shape.estimated_tokens
        baseline = max(old_shape.estimated_tokens, 1)
        token_difference_ratio = abs(token_difference) / baseline
        warnings = self._warnings(old_shape, new_shape, token_difference_ratio)

        return ContextComparison(
            old_prompt=old_shape,
            new_context_packet=new_shape,
            token_difference=token_difference,
            token_difference_ratio=round(token_difference_ratio, 3),
            warnings=warnings,
            metadata={
                "comparison_type": "legacy_short_term_vs_trace_context_packet",
                "full_prompts_included": False,
            },
        )

    def _shape_from_packet(
        self,
        packet: ContextPacket,
        latest_user_message: dict[str, str],
    ) -> PromptShape:
        shape = self._shape_from_messages(
            messages=packet.model_messages,
            latest_user_message=latest_user_message,
        )
        return PromptShape(
            estimated_tokens=shape.estimated_tokens,
            message_count=shape.message_count,
            section_order=shape.section_order,
            has_structured_memory=shape.has_structured_memory or bool(packet.structured_memory),
            has_recent_messages=shape.has_recent_messages or bool(packet.recent_message_ids),
            has_latest_user_message=shape.has_latest_user_message,
        )

    def _shape_from_messages(
        self,
        messages: list[dict[str, str]],
        latest_user_message: dict[str, str],
    ) -> PromptShape:
        latest_index = latest_message_index(messages, latest_user_message)
        section_order: list[str] = []
        has_structured_memory = False
        has_recent_messages = False

        for index, message in enumerate(messages):
            section = classify_message_section(message, index, latest_index)
            if section_order[-1:] != [section]:
                section_order.append(section)
            if section == "structured_memory":
                has_structured_memory = True
            if section == "recent_messages":
                has_recent_messages = True

        return PromptShape(
            estimated_tokens=self.token_estimator.estimate_messages(messages),
            message_count=len(messages),
            section_order=section_order,
            has_structured_memory=has_structured_memory,
            has_recent_messages=has_recent_messages,
            has_latest_user_message=latest_index is not None,
        )

    def _warnings(
        self,
        old_shape: PromptShape,
        new_shape: PromptShape,
        token_difference_ratio: float,
    ) -> list[str]:
        warnings: list[str] = []
        if old_shape.has_latest_user_message and not new_shape.has_latest_user_message:
            warnings.append("missing_latest_user_message")
        if old_shape.has_recent_messages and not new_shape.has_recent_messages:
            warnings.append("missing_recent_messages")
        if old_shape.has_structured_memory and not new_shape.has_structured_memory:
            warnings.append("missing_structured_memory")

        absolute_difference = abs(new_shape.estimated_tokens - old_shape.estimated_tokens)
        if (
            token_difference_ratio >= TOKEN_DIFFERENCE_RATIO_WARNING
            and absolute_difference >= TOKEN_DIFFERENCE_ABSOLUTE_WARNING
        ):
            warnings.append("large_token_count_difference")
        return warnings


def latest_message_index(
    messages: list[dict[str, str]],
    latest_user_message: dict[str, str],
) -> int | None:
    """Return the index of the latest user message, preferring the final match."""
    latest_content = latest_user_message.get("content", "")
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        msg_content = message.get("content", "")
        if message.get("role") == latest_user_message.get("role") and (
            msg_content == latest_content
            or (
                latest_content
                and latest_content in msg_content
                and len(latest_content) < len(msg_content)
            )
        ):
            return index
    return None


def classify_message_section(
    message: dict[str, str],
    index: int,
    latest_index: int | None,
) -> str:
    """Classify one model message into a high-level prompt section."""
    if latest_index is not None and index == latest_index:
        return "latest_user_message"

    content = message.get("content", "")
    role = message.get("role", "")
    if index == 0 and role == "system":
        return "system"
    if content.startswith("Current structured memory:") or content.startswith("Structured Memory:"):
        return "structured_memory"
    if content.startswith(
        (
            "Current Chat Chunks:",
            "Previous Chat Memory:",
            "Document Memory:",
        )
    ):
        return "retrieved_memory"
    return "recent_messages"
