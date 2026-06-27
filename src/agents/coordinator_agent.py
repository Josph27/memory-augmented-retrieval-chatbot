from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from openai import OpenAIError

from src.agents.chat_agent import ChatAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.context_manager_agent import ContextManagerAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder as TraceContextBuilder
from src.context.context_comparator import ContextComparator
from src.context.prompt_messages import context_packet_to_model_messages
from src.core.contracts import AgentTurnResult, WorkflowTrace
from src.database import Database
from src.memory.memory_trace import (
    document_memory_candidate_trace_rows,
    structured_memory_candidate_trace_rows,
)
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner
from src.routing.routing_agent import RoutingAgent


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
        routing_agent: RoutingAgent | None = None,
        context_manager_agent: ContextManagerAgent | None = None,
    ) -> None:
        self.database = database
        self.memory_agent = memory_agent
        self.context_builder = context_builder
        self.chat_agent = chat_agent
        self.system_prompt = system_prompt
        self.routing_agent = routing_agent or RoutingAgent(route_planner or RoutePlanner())
        self.retriever_dispatcher = retriever_dispatcher or RetrieverDispatcher(database)
        self.memory_reranker = memory_reranker or MemoryReranker()
        self.context_budget_allocator = context_budget_allocator or ContextBudgetAllocator()
        self.trace_context_builder = trace_context_builder or TraceContextBuilder()
        self.context_manager_agent = context_manager_agent
        self.context_comparator = context_comparator or ContextComparator()

    def run_turn(self, chat_id: str, content: str) -> AgentTurnResult:
        """Run one user turn while preserving the existing runtime behavior."""
        total_started = perf_counter()
        timings: dict[str, float] = {}
        trace_id = str(uuid4())
        stage_started = perf_counter()
        routing_decision = self.routing_agent.route(content)
        route_plan = routing_decision.route_plan
        timings["route_planning"] = elapsed_ms(stage_started)
        stage_started = perf_counter()
        user_message_id = self.database.save_message(
            chat_id=chat_id,
            role="user",
            content=content,
        )
        timings["save_user_message"] = elapsed_ms(stage_started)
        stage_started = perf_counter()
        retrieved_candidates = self.retriever_dispatcher.retrieve(
            chat_id=chat_id,
            route_plan=route_plan,
        )
        timings["retrieval"] = elapsed_ms(stage_started)
        stage_started = perf_counter()
        rerank_result = self.memory_reranker.rank_with_trace(
            candidates=retrieved_candidates,
            ranking_profile=route_plan.ranking_profile,
            query=content,
        )
        ranked_candidates = rerank_result.candidates
        reranker_metadata = rerank_result.metadata
        timings["reranking"] = elapsed_ms(stage_started)
        latest_user_message = {"role": "user", "content": content}
        stage_started = perf_counter()
        context_manager = self.context_manager_agent or ContextManagerAgent(
            budget_allocator=self.context_budget_allocator,
            context_builder=self.trace_context_builder,
        )
        context_manager_result = context_manager.build_context_packet(
            system_prompt=self.system_prompt,
            latest_user_message=latest_user_message,
            ranked_candidates=ranked_candidates,
            route_plan=route_plan,
        )
        context_budget = context_manager_result.context_budget
        trace_context_packet = context_manager_result.context_packet
        context_manager_metadata = context_manager_result.metadata
        elapsed_context_manager = elapsed_ms(stage_started)
        timings["context_budget_allocation"] = elapsed_context_manager
        timings["context_packet_building"] = elapsed_context_manager

        stage_started = perf_counter()
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
        timings["legacy_context_building"] = elapsed_ms(stage_started)
        stage_started = perf_counter()
        context_comparison = self.context_comparator.compare(
            old_model_messages=model_messages,
            new_context_packet=trace_context_packet,
            latest_user_message=latest_user_message,
        )
        timings["context_comparison"] = elapsed_ms(stage_started)
        stage_started = perf_counter()
        prompt_assembly = context_packet_to_model_messages(
            packet=trace_context_packet,
            latest_user_message=latest_user_message,
            context_comparison=context_comparison.to_dict(),
        )
        timings["context_packet_validation"] = elapsed_ms(stage_started)
        prompt_source = "context_packet"
        fallback_reason = None
        final_model_messages = prompt_assembly.messages
        if not prompt_assembly.valid:
            prompt_source = "legacy_short_term_memory_fallback"
            fallback_reason = prompt_assembly.fallback_reason
            final_model_messages = model_messages

        errors: list[str] = []
        try:
            stage_started = perf_counter()
            response = self.chat_agent.generate(final_model_messages)
            timings["main_model_call"] = elapsed_ms(stage_started)
        except OpenAIError as error:
            timings["main_model_call"] = elapsed_ms(stage_started)
            errors.append(str(error))
            response = (
                "I could not reach the configured OpenAI-compatible model endpoint. "
                "Check OPENAI_BASE_URL, MODEL_NAME, and whether the local model server is running.\n\n"
                f"Model error: {error}"
            )

        stage_started = perf_counter()
        assistant_message_id = self.database.save_message(
            chat_id=chat_id,
            role="assistant",
            content=response,
        )
        timings["save_assistant_message"] = elapsed_ms(stage_started)
        try:
            stage_started = perf_counter()
            self.memory_agent.update_memory_if_needed(chat_id)
            timings["update_memory_if_needed"] = elapsed_ms(stage_started)
        except OpenAIError as error:
            timings["update_memory_if_needed"] = elapsed_ms(stage_started)
            errors.append(str(error))
            # Memory updates should not break the visible chat response. The next
            # successful turn can retry because messages remain unprocessed.
        timings["total_turn"] = elapsed_ms(total_started)
        saved_memory_rows = list(
            getattr(self.memory_agent.memory, "last_saved_memory_rows", [])
        )
        retrieved_memory_rows = structured_memory_candidate_trace_rows(retrieved_candidates)
        retrieved_document_rows = document_memory_candidate_trace_rows(retrieved_candidates)

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
                "routing_decision": routing_decision.to_trace_dict(),
                "reranker": reranker_metadata,
                "context_manager": context_manager_metadata,
                "prompt_source": prompt_source,
                "fallback_reason": fallback_reason,
                "estimated_prompt_tokens": trace_context_packet.metadata.get(
                    "estimated_prompt_tokens"
                ),
                "token_estimator": trace_context_packet.metadata.get("token_estimator"),
                "context_limit": trace_context_packet.metadata.get("context_limit"),
                "answer_reserve": trace_context_packet.metadata.get("answer_reserve"),
                "safety_margin": trace_context_packet.metadata.get("safety_margin"),
                "overflow_detected": trace_context_packet.metadata.get(
                    "overflow_detected"
                ),
                "overflow_tokens": trace_context_packet.metadata.get("overflow_tokens"),
                "dropped_candidate_ids": trace_context_packet.metadata.get(
                    "dropped_candidate_ids"
                ),
                "dropped_candidate_reasons": trace_context_packet.metadata.get(
                    "dropped_candidate_reasons"
                ),
                "timings_ms": timings,
                "saved_memory_rows": saved_memory_rows,
                "retrieved_memory_rows": retrieved_memory_rows,
                "retrieved_document_rows": retrieved_document_rows,
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
            metadata={
                "saved_memory_rows": saved_memory_rows,
                "retrieved_memory_rows": retrieved_memory_rows,
                "retrieved_document_rows": retrieved_document_rows,
                "routing_decision": routing_decision.to_trace_dict(),
                "reranker": reranker_metadata,
                "context_manager": context_manager_metadata,
            },
        )

    def _log_trace(self, trace: WorkflowTrace) -> None:
        """Emit a compact console trace until trace persistence exists."""
        recent_ids = []
        if trace.context_packet is not None:
            recent_ids = trace.context_packet.recent_message_ids
        route_intent = None
        routing_reason = None
        routing_fallback = None
        reranker_mode = None
        reranker_fallback = None
        active_sources = []
        if trace.route_plan is not None:
            route_intent = trace.route_plan.intent
            active_sources = [
                source.source for source in trace.route_plan.sources if source.enabled
            ]
        routing_decision = trace.metadata.get("routing_decision")
        if isinstance(routing_decision, dict):
            routing_reason = routing_decision.get("reason")
            routing_fallback = routing_decision.get("fallback_mode")
        reranker = trace.metadata.get("reranker")
        if isinstance(reranker, dict):
            reranker_mode = reranker.get("reranker_mode")
            reranker_fallback = reranker.get("fallback_used")
        context_profile = None
        if trace.context_budget is not None:
            context_profile = trace.context_budget.metadata.get("context_profile")
        comparison_warnings = []
        comparison = trace.metadata.get("context_comparison")
        if isinstance(comparison, dict):
            comparison_warnings = comparison.get("warnings", [])
        prompt_source = trace.metadata.get("prompt_source")
        fallback_reason = trace.metadata.get("fallback_reason")
        overflow_detected = trace.metadata.get("overflow_detected")
        overflow_tokens = trace.metadata.get("overflow_tokens")
        estimated_prompt_tokens = trace.metadata.get("estimated_prompt_tokens")
        token_estimator = trace.metadata.get("token_estimator")
        print(
            "workflow_trace "
            f"trace_id={trace.trace_id} "
            f"chat_id={trace.chat_id} "
            f"intent={route_intent} "
            f"active_sources={active_sources} "
            f"routing_fallback={routing_fallback} "
            f"routing_reason={routing_reason!r} "
            f"reranker_mode={reranker_mode} "
            f"reranker_fallback={reranker_fallback} "
            f"retrieved_candidates={len(trace.retrieved_candidates)} "
            f"ranked_candidates={len(trace.ranked_candidates)} "
            f"context_profile={context_profile} "
            f"context_comparison_warnings={comparison_warnings} "
            f"token_estimator={token_estimator} "
            f"estimated_prompt_tokens={estimated_prompt_tokens} "
            f"overflow_detected={overflow_detected} "
            f"overflow_tokens={overflow_tokens} "
            f"prompt_source={prompt_source} "
            f"fallback_reason={fallback_reason} "
            f"termination_reason={trace.termination_reason} "
            f"recent_message_ids={recent_ids}"
        )
        timings = trace.metadata.get("timings_ms", {})
        if isinstance(timings, dict):
            print(
                "turn_timing "
                f"trace_id={trace.trace_id} "
                f"route_planning_ms={timings.get('route_planning')} "
                f"save_user_message_ms={timings.get('save_user_message')} "
                f"retrieval_ms={timings.get('retrieval')} "
                f"reranking_ms={timings.get('reranking')} "
                f"context_budget_allocation_ms={timings.get('context_budget_allocation')} "
                f"context_packet_building_ms={timings.get('context_packet_building')} "
                f"context_packet_validation_ms={timings.get('context_packet_validation')} "
                f"main_model_call_ms={timings.get('main_model_call')} "
                f"save_assistant_message_ms={timings.get('save_assistant_message')} "
                f"update_memory_if_needed_ms={timings.get('update_memory_if_needed')} "
                f"total_turn_ms={timings.get('total_turn')}"
            )


def elapsed_ms(started: float) -> float:
    """Return elapsed milliseconds rounded for compact timing logs."""
    return round((perf_counter() - started) * 1000, 2)
