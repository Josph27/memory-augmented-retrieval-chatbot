from __future__ import annotations

from uuid import uuid4

from openai import OpenAIError

from src.agents.chat_agent import ChatAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.core.contracts import AgentTurnResult, WorkflowTrace
from src.database import Database


TERMINATION_RESPONSE_SAVED = "response_generated_and_messages_saved"


class CoordinatorAgent:
    """Coordinates the existing one-turn chat workflow behind an agent-shaped API."""

    def __init__(
        self,
        database: Database,
        memory_agent: ShortTermMemoryAgent,
        context_builder: ContextBuilderAgent,
        chat_agent: ChatAgent,
        system_prompt: str,
    ) -> None:
        self.database = database
        self.memory_agent = memory_agent
        self.context_builder = context_builder
        self.chat_agent = chat_agent
        self.system_prompt = system_prompt

    def run_turn(self, chat_id: str, content: str) -> AgentTurnResult:
        """Run one user turn while preserving the existing runtime behavior."""
        trace_id = str(uuid4())
        user_message_id = self.database.save_message(
            chat_id=chat_id,
            role="user",
            content=content,
        )

        context = self.memory_agent.build_context(
            chat_id=chat_id,
            latest_user_message_id=user_message_id,
        )
        model_messages, context_packet = self.context_builder.build(
            chat_id=chat_id,
            system_prompt=self.system_prompt,
            context=context,
            latest_user_message={"role": "user", "content": content},
        )

        errors: list[str] = []
        try:
            response = self.chat_agent.generate(model_messages)
        except OpenAIError as error:
            errors.append(str(error))
            response = (
                "I could not reach the configured OpenAI-compatible model endpoint. "
                "Check OPENAI_BASE_URL, MODEL_NAME, and whether the local model server is running.\n\n"
                f"Model error: {error}"
            )

        assistant_message_id = self.database.save_message(
            chat_id=chat_id,
            role="assistant",
            content=response,
        )
        try:
            self.memory_agent.update_memory_if_needed(chat_id)
        except OpenAIError as error:
            errors.append(str(error))
            # Memory updates should not break the visible chat response. The next
            # successful turn can retry because messages remain unprocessed.

        trace = WorkflowTrace(
            trace_id=trace_id,
            chat_id=chat_id,
            route_plan=None,
            context_packet=context_packet,
            termination_reason=TERMINATION_RESPONSE_SAVED,
            errors=errors,
        )
        self._log_trace(trace)
        return AgentTurnResult(
            answer=response,
            chat_id=chat_id,
            trace_id=trace_id,
            termination_reason=TERMINATION_RESPONSE_SAVED,
            trace=trace,
            assistant_message_id=assistant_message_id,
        )

    def _log_trace(self, trace: WorkflowTrace) -> None:
        """Emit a compact console trace until trace persistence exists."""
        recent_ids = []
        if trace.context_packet is not None:
            recent_ids = trace.context_packet.recent_message_ids
        print(
            "workflow_trace "
            f"trace_id={trace.trace_id} "
            f"chat_id={trace.chat_id} "
            f"termination_reason={trace.termination_reason} "
            f"recent_message_ids={recent_ids}"
        )
