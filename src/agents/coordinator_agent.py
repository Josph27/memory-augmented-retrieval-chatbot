from __future__ import annotations

from uuid import uuid4

from openai import OpenAIError

from src.agents.chat_agent import ChatAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder as TraceContextBuilder
from src.context.context_comparator import ContextComparator
from src.context.prompt_messages import context_packet_to_model_messages
from src.core.contracts import AgentTurnResult, WorkflowTrace
from src.database import Database
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner


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
        route_planner: RoutePlanner | None = None,
        retriever_dispatcher: RetrieverDispatcher | None = None,
        memory_reranker: MemoryReranker | None = None,
        context_budget_allocator: ContextBudgetAllocator | None = None,
        trace_context_builder: TraceContextBuilder | None = None,
        context_comparator: ContextComparator | None = None,
    ) -> None:
        self.database = database
        self.memory_agent = memory_agent
        self.context_builder = context_builder
        self.chat_agent = chat_agent
        self.system_prompt = system_prompt
        self.route_planner = route_planner or RoutePlanner()
        self.retriever_dispatcher = retriever_dispatcher or RetrieverDispatcher(database)
        self.memory_reranker = memory_reranker or MemoryReranker()
        self.context_budget_allocator = context_budget_allocator or ContextBudgetAllocator()
        self.trace_context_builder = trace_context_builder or TraceContextBuilder()
        self.context_comparator = context_comparator or ContextComparator()

    def run_turn(self, chat_id: str, content: str) -> AgentTurnResult:
        """Run one user turn while preserving the existing runtime behavior."""
        trace_id = str(uuid4())
        route_plan = self.route_planner.plan(content)
        user_message_id = self.database.save_message(
            chat_id=chat_id,
            role="user",
            content=content,
        )
        retrieved_candidates = self.retriever_dispatcher.retrieve(
            chat_id=chat_id,
            route_plan=route_plan,
        )
        ranked_candidates = self.memory_reranker.rank(
            candidates=retrieved_candidates,
            ranking_profile=route_plan.ranking_profile,
        )
        context_budget = self.context_budget_allocator.allocate(
            route_plan=route_plan,
            ranked_candidates=ranked_candidates,
            system_prompt=self.system_prompt,
        )
        latest_user_message = {"role": "user", "content": content}
        trace_context_packet = self.trace_context_builder.build(
            system_prompt=self.system_prompt,
            latest_user_message=latest_user_message,
            ranked_candidates=ranked_candidates,
            context_budget=context_budget,
            route_plan=route_plan,
        )

        context = self.memory_agent.build_context(
            chat_id=chat_id,
            latest_user_message_id=user_message_id,
        )
        model_messages, _actual_context_packet = self.context_builder.build(
            chat_id=chat_id,
            system_prompt=self.system_prompt,
            context=context,
            latest_user_message=latest_user_message,
        )
        context_comparison = self.context_comparator.compare(
            old_model_messages=model_messages,
            new_context_packet=trace_context_packet,
            latest_user_message=latest_user_message,
        )
        prompt_assembly = context_packet_to_model_messages(
            packet=trace_context_packet,
            latest_user_message=latest_user_message,
            context_comparison=context_comparison.to_dict(),
        )
        prompt_source = "context_packet"
        fallback_reason = None
        final_model_messages = prompt_assembly.messages
        if not prompt_assembly.valid:
            prompt_source = "legacy_short_term_memory_fallback"
            fallback_reason = prompt_assembly.fallback_reason
            final_model_messages = model_messages

        errors: list[str] = []
        try:
            response = self.chat_agent.generate(final_model_messages)
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
            route_plan=route_plan,
            retrieved_candidates=retrieved_candidates,
            ranked_candidates=ranked_candidates,
            context_budget=context_budget,
            context_packet=trace_context_packet,
            termination_reason=TERMINATION_RESPONSE_SAVED,
            errors=errors,
            metadata={
                "context_comparison": context_comparison.to_dict(),
                "prompt_source": prompt_source,
                "fallback_reason": fallback_reason,
            },
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
        route_intent = None
        active_sources = []
        if trace.route_plan is not None:
            route_intent = trace.route_plan.intent
            active_sources = [
                source.source for source in trace.route_plan.sources if source.enabled
            ]
        context_profile = None
        if trace.context_budget is not None:
            context_profile = trace.context_budget.metadata.get("context_profile")
        comparison_warnings = []
        comparison = trace.metadata.get("context_comparison")
        if isinstance(comparison, dict):
            comparison_warnings = comparison.get("warnings", [])
        prompt_source = trace.metadata.get("prompt_source")
        fallback_reason = trace.metadata.get("fallback_reason")
        print(
            "workflow_trace "
            f"trace_id={trace.trace_id} "
            f"chat_id={trace.chat_id} "
            f"intent={route_intent} "
            f"active_sources={active_sources} "
            f"retrieved_candidates={len(trace.retrieved_candidates)} "
            f"ranked_candidates={len(trace.ranked_candidates)} "
            f"context_profile={context_profile} "
            f"context_comparison_warnings={comparison_warnings} "
            f"prompt_source={prompt_source} "
            f"fallback_reason={fallback_reason} "
            f"termination_reason={trace.termination_reason} "
            f"recent_message_ids={recent_ids}"
        )
