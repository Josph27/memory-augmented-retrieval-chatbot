from __future__ import annotations

from dataclasses import replace
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
from src.core.contracts import (
    AgentTurnResult,
    OrchestrationResult,
    SourcePlan,
    WorkflowTrace,
)
from src.database import Database
from src.memory.memory_trace import (
    document_memory_candidate_trace_rows,
    structured_memory_candidate_trace_rows,
)
from src.orchestration.demo_orchestration import (
    LANGGRAPH_DEMO,
    NATIVE,
    compare_orchestration,
    normalize_orchestration_mode,
    run_read_only_langgraph_orchestration,
)
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner
from src.routing.routing_agent import RoutingAgent, RoutingDecision
from src.routing.retrieval_query import retrieval_query_for_reranking


TERMINATION_RESPONSE_SAVED = "response_generated_and_messages_saved"
TERMINATION_ANSWER_FAILED = "answer_generation_failed"


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

    def run_turn(
        self,
        chat_id: str,
        content: str,
        orchestration_mode: str = NATIVE,
        task_context: str | None = None,
        persisted_user_message_id: int | None = None,
        perform_memory_update: bool = True,
    ) -> AgentTurnResult:
        """Run one user turn while preserving the existing runtime behavior."""
        requested_orchestration_mode = normalize_orchestration_mode(orchestration_mode)
        total_started = perf_counter()
        timings: dict[str, float] = {}
        trace_id = str(uuid4())
        stage_started = perf_counter()
        routing_decision = self.routing_agent.route(content)
        if task_context == "document_qa":
            routing_decision = require_document_memory(routing_decision)
        route_plan = routing_decision.route_plan
        timings["route_planning"] = elapsed_ms(stage_started)
        stage_started = perf_counter()
        user_message_id = persisted_user_message_id
        if user_message_id is None:
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
        retrieval_errors = list(
            getattr(self.retriever_dispatcher, "last_errors", [])
        )
        timings["retrieval"] = elapsed_ms(stage_started)
        stage_started = perf_counter()
        rerank_result = self.memory_reranker.rank_with_trace(
            candidates=retrieved_candidates,
            ranking_profile=route_plan.ranking_profile,
            query=retrieval_query_for_reranking(
                route_plan,
                fallback=content,
            ),
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
        native_orchestration = OrchestrationResult(
            context_packet=trace_context_packet,
            trace=WorkflowTrace(
                trace_id=trace_id,
                chat_id=chat_id,
                route_plan=route_plan,
                retrieved_candidates=retrieved_candidates,
                ranked_candidates=ranked_candidates,
                context_budget=context_budget,
                context_packet=trace_context_packet,
                metadata={
                    "routing_decision": routing_decision.to_trace_dict(),
                    "reranker": reranker_metadata,
                    "context_manager": context_manager_metadata,
                },
            ),
            mode=NATIVE,
        )
        authoritative_orchestration = native_orchestration
        langgraph_orchestration: OrchestrationResult | None = None
        orchestration_error: str | None = None
        orchestration_comparison: dict[str, object] | None = None
        orchestration_fallback_used = False
        if requested_orchestration_mode != NATIVE:
            stage_started = perf_counter()
            try:
                langgraph_orchestration = run_read_only_langgraph_orchestration(
                    chat_id=chat_id,
                    query=content,
                    dispatcher=self.retriever_dispatcher,
                    reranker=self.memory_reranker,
                    context_manager=context_manager,
                    system_prompt=self.system_prompt,
                    run_id=f"{trace_id}:langgraph",
                    task_context=task_context,
                )
                if langgraph_orchestration.error:
                    raise RuntimeError(langgraph_orchestration.error)
            except Exception as error:
                orchestration_error = bounded_error(error)
                orchestration_fallback_used = (
                    requested_orchestration_mode == LANGGRAPH_DEMO
                )
            else:
                orchestration_comparison = compare_orchestration(
                    native_orchestration,
                    langgraph_orchestration,
                ).to_dict()
                if requested_orchestration_mode == LANGGRAPH_DEMO:
                    authoritative_orchestration = langgraph_orchestration
            timings["langgraph_orchestration"] = elapsed_ms(stage_started)

        trace_context_packet = authoritative_orchestration.context_packet
        authoritative_trace = authoritative_orchestration.trace
        if authoritative_trace.route_plan is not None:
            route_plan = authoritative_trace.route_plan
        retrieved_candidates = list(authoritative_trace.retrieved_candidates)
        ranked_candidates = list(authoritative_trace.ranked_candidates)
        context_budget = trace_context_packet.budget or context_budget
        if authoritative_orchestration.mode == LANGGRAPH_DEMO:
            graph_metadata = authoritative_trace.metadata
            reranker_metadata = dict(graph_metadata.get("reranker", {}))
            context_manager_metadata = dict(
                graph_metadata.get("context_manager", {})
            )

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
        if orchestration_error:
            errors.append(orchestration_error)
        errors.extend(
            f"{item.get('source')}: {item.get('type')}: {item.get('message')}"
            for item in retrieval_errors
        )
        insufficient_evidence = bool(
            authoritative_trace.metadata.get("insufficient_evidence")
        )
        answer_failed = False
        if authoritative_orchestration.mode == LANGGRAPH_DEMO and insufficient_evidence:
            reason = authoritative_trace.metadata.get(
                "insufficient_evidence_reason"
            ) or "required evidence was not available"
            response = f"I do not have sufficient grounded evidence: {reason}."
            timings["main_model_call"] = 0.0
        else:
            try:
                stage_started = perf_counter()
                response = self.chat_agent.generate(final_model_messages)
                timings["main_model_call"] = elapsed_ms(stage_started)
            except (OpenAIError, TimeoutError) as error:
                timings["main_model_call"] = elapsed_ms(stage_started)
                errors.append(str(error))
                answer_failed = True
                response = (
                    "The answer could not be generated. Your message was saved and "
                    "you can retry this turn."
                )

        stage_started = perf_counter()
        assistant_message_id = None
        if not answer_failed:
            assistant_message_id = self.database.save_message(
                chat_id=chat_id,
                role="assistant",
                content=response,
            )
        timings["save_assistant_message"] = elapsed_ms(stage_started)
        if perform_memory_update:
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
        effective_orchestration_mode = (
            authoritative_orchestration.mode
            if requested_orchestration_mode == LANGGRAPH_DEMO
            else requested_orchestration_mode
        )
        orchestration_metadata = {
            "requested_mode": requested_orchestration_mode,
            "effective_mode": effective_orchestration_mode,
            "authoritative_context": (
                "langgraph" if authoritative_orchestration.mode == LANGGRAPH_DEMO else "native"
            ),
            "fallback_used": orchestration_fallback_used,
            "error": orchestration_error,
            "comparison": orchestration_comparison,
            "langgraph_trace": (
                langgraph_orchestration.trace.metadata.get("langgraph")
                if langgraph_orchestration is not None
                else None
            ),
            "task_context": task_context,
        }

        termination_reason = (
            TERMINATION_ANSWER_FAILED if answer_failed else TERMINATION_RESPONSE_SAVED
        )
        trace = WorkflowTrace(
            trace_id=trace_id,
            chat_id=chat_id,
            route_plan=route_plan,
            retrieved_candidates=retrieved_candidates,
            ranked_candidates=ranked_candidates,
            context_budget=context_budget,
            context_packet=trace_context_packet,
            termination_reason=termination_reason,
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
                "orchestration": orchestration_metadata,
                "saved_memory_rows": saved_memory_rows,
                "retrieved_memory_rows": retrieved_memory_rows,
                "retrieved_document_rows": retrieved_document_rows,
                "retrieval_errors": retrieval_errors,
            },
        )
        self._log_trace(trace)
        return AgentTurnResult(
            answer=response,
            chat_id=chat_id,
            trace_id=trace_id,
            termination_reason=termination_reason,
            trace=trace,
            assistant_message_id=assistant_message_id,
            metadata={
                "saved_memory_rows": saved_memory_rows,
                "retrieved_memory_rows": retrieved_memory_rows,
                "retrieved_document_rows": retrieved_document_rows,
                "routing_decision": routing_decision.to_trace_dict(),
                "reranker": reranker_metadata,
                "context_manager": context_manager_metadata,
                "orchestration": orchestration_metadata,
                "answer_status": "failed" if answer_failed else "completed",
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


def require_document_memory(decision: RoutingDecision) -> RoutingDecision:
    """Enable scoped document retrieval when the current turn uploaded a document."""
    route_plan = decision.route_plan
    document_found = False
    sources: list[SourcePlan] = []
    for source in route_plan.sources:
        if source.source != "document_memory":
            sources.append(source)
            continue
        document_found = True
        sources.append(
            replace(
                source,
                enabled=True,
                reason="Same-turn attachment requires scoped document retrieval.",
                query=source.query or route_plan.query,
                filters={
                    **source.filters,
                    "same_turn_attachment": True,
                },
            )
        )
    if not document_found:
        sources.append(
            SourcePlan(
                source="document_memory",
                enabled=True,
                reason="Same-turn attachment requires scoped document retrieval.",
                query=route_plan.query,
                filters={"same_turn_attachment": True},
            )
        )
    updated_plan = replace(
        route_plan,
        intent="document_question",
        requires_retrieval=True,
        sources=sources,
        context_profile="document_question",
        metadata={
            **route_plan.metadata,
            "same_turn_attachment": True,
        },
    )
    return replace(
        decision,
        route_plan=updated_plan,
        use_document_memory=True,
        reason="Same-turn attachment requires scoped document retrieval.",
        metadata={
            **(decision.metadata or {}),
            "same_turn_attachment": True,
        },
    )


def elapsed_ms(started: float) -> float:
    """Return elapsed milliseconds rounded for compact timing logs."""
    return round((perf_counter() - started) * 1000, 2)


def bounded_error(error: Exception, limit: int = 240) -> str:
    """Return a trace-safe error without a traceback or unbounded payload."""
    detail = str(error).strip() or type(error).__name__
    value = f"{type(error).__name__}: {detail}"
    return value if len(value) <= limit else f"{value[: limit - 3]}..."
