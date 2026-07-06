from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder
from src.context.dynamic_budget import (
    LONG_DOCUMENT_TASK_CONTEXTS,
    DynamicWorkingMemoryBudgetPlanner,
    MemoryBudgetPolicy,
)
from src.context.evidence_selector import (
    EvidenceConstrainedContextSelector,
    SelectionResult,
    SelectorPolicy,
)
from src.context.model_profile import (
    DEFAULT_GEMMA_APPLICATION_CONTEXT_CAP,
    ResolvedContextWindow,
    model_profile_for,
    resolve_context_window,
)
from src.context.token_estimator import (
    ProcessorLoader,
    build_token_estimator,
    count_messages,
    count_text,
)
from src.core.contracts import ContextBudget, ContextPacket, MemoryCandidate, RoutePlan


@dataclass(frozen=True)
class ContextManagerResult:
    """Context orchestration result produced by ContextManagerAgent."""

    context_budget: ContextBudget
    context_packet: ContextPacket
    metadata: dict[str, Any]


class ContextManagerAgent:
    """Responsibility wrapper for deterministic context budgeting and packet building."""

    def __init__(
        self,
        budget_allocator: ContextBudgetAllocator | None = None,
        context_builder: ContextBuilder | None = None,
        context_window: ResolvedContextWindow | None = None,
        output_reserve: int | None = None,
        selector: EvidenceConstrainedContextSelector | None = None,
        budget_planner: DynamicWorkingMemoryBudgetPlanner | None = None,
    ) -> None:
        self.budget_allocator = budget_allocator or ContextBudgetAllocator()
        self.context_builder = context_builder or ContextBuilder()
        self.context_window = context_window
        self.output_reserve = output_reserve
        self.selector = selector or EvidenceConstrainedContextSelector()
        self.budget_planner = budget_planner or DynamicWorkingMemoryBudgetPlanner()

    @classmethod
    def for_model(
        cls,
        model_id: str,
        *,
        endpoint_context_window: int | None = None,
        application_context_cap: int | None = DEFAULT_GEMMA_APPLICATION_CONTEXT_CAP,
        endpoint_limit_source: str | None = None,
        processor_loader: ProcessorLoader | None = None,
        tokenizer_loader: ProcessorLoader | None = None,
        memory_budget_policy: MemoryBudgetPolicy | None = None,
        minimum_optional_candidate_utility: float = 0.15,
        raw_span_overlap_threshold: float = 0.7,
    ) -> "ContextManagerAgent":
        """Construct one shared model-aware allocator/builder pair."""
        profile = model_profile_for(model_id)
        resolved = resolve_context_window(
            profile,
            endpoint_context_window=endpoint_context_window,
            application_context_cap=application_context_cap,
            endpoint_limit_source=endpoint_limit_source,
        )
        estimator = build_token_estimator(
            model_name=model_id,
            tokenizer_id=profile.tokenizer_id,
            processor_loader=processor_loader,
            tokenizer_loader=tokenizer_loader,
        )
        return cls(
            budget_allocator=ContextBudgetAllocator(token_estimator=estimator),
            context_builder=ContextBuilder(token_estimator=estimator),
            context_window=resolved,
            output_reserve=profile.default_output_reserve,
            selector=EvidenceConstrainedContextSelector(
                SelectorPolicy(
                    minimum_optional_utility=minimum_optional_candidate_utility,
                    overlap_threshold=raw_span_overlap_threshold,
                )
            ),
            budget_planner=DynamicWorkingMemoryBudgetPlanner(memory_budget_policy),
        )

    def build_context_packet(
        self,
        *,
        system_prompt: str,
        latest_user_message: dict[str, str],
        ranked_candidates: list[MemoryCandidate],
        route_plan: RoutePlan,
    ) -> ContextManagerResult:
        """Allocate budget and build a ContextPacket without changing prompt behavior."""
        context_budget = self.budget_allocator.allocate(
            route_plan=route_plan,
            ranked_candidates=ranked_candidates,
            model_context_limit=(
                self.context_window.effective_context_window
                if self.context_window is not None
                else None
            ),
            answer_reserve=self.output_reserve,
            system_prompt=system_prompt,
        )
        if self.context_window is not None:
            context_budget.metadata.update(self.context_window.to_metadata())
        safety_reserve = int(
            context_budget.metadata.get("safety_margin_tokens", 0) or 0
        )
        output_reserve = context_budget.reserved_response_tokens or 0
        hard_input_budget = max(
            0,
            (context_budget.max_tokens or 0) - output_reserve - safety_reserve,
        )
        system_tokens = count_text(
            self.context_builder.token_estimator,
            system_prompt,
        )
        query_tokens = count_text(
            self.context_builder.token_estimator,
            latest_user_message.get("content", ""),
        )
        fixed_prompt_tokens = count_messages(
            self.context_builder.token_estimator,
            [
                {"role": "system", "content": system_prompt},
                latest_user_message,
            ],
            add_generation_prompt=True,
        )
        fixed_formatting_overhead = max(
            0,
            fixed_prompt_tokens - system_tokens - query_tokens,
        )
        available_memory_budget = max(
            0,
            hard_input_budget
            - system_tokens
            - query_tokens
            - fixed_formatting_overhead,
        )
        budget_started = perf_counter()
        required_preflight = self.selector.select(
            candidates=ranked_candidates,
            route_plan=route_plan,
            token_budget=2**62,
            token_counter=self.context_builder.token_estimator,
            latest_user_message=latest_user_message,
        )
        floor_candidates = required_floor_candidates(
            required_preflight,
            route_plan=route_plan,
        )
        required_floor = required_floor_token_cost(
            context_builder=self.context_builder,
            candidates=floor_candidates,
            system_prompt=system_prompt,
            latest_user_message=latest_user_message,
            ranked_candidates=ranked_candidates,
            context_budget=context_budget,
            route_plan=route_plan,
            fixed_prompt_tokens=fixed_prompt_tokens,
        )
        budget_plan = self.budget_planner.plan(
            route_plan=route_plan,
            available_memory_budget=available_memory_budget,
            required_evidence_floor=required_floor,
        )
        working_memory_budget = budget_plan.working_memory_budget
        budget_planning_ms = (perf_counter() - budget_started) * 1000
        context_budget.metadata.update(
            {
                **budget_plan.to_metadata(),
                "hard_input_budget": hard_input_budget,
                "fixed_input_tokens": fixed_prompt_tokens,
                "system_prompt_tokens": system_tokens,
                "current_query_tokens": query_tokens,
                "chat_template_and_fixed_formatting_overhead": (
                    fixed_formatting_overhead
                ),
                "source_budgets_advisory_only": True,
                "context_profile": route_plan.context_profile,
                "effective_memory_budget": working_memory_budget,
                "budget_planning_ms": round(budget_planning_ms, 3),
            }
        )
        selection_started = perf_counter()
        selection = self.selector.select(
            candidates=ranked_candidates,
            route_plan=route_plan,
            token_budget=working_memory_budget,
            token_counter=self.context_builder.token_estimator,
            latest_user_message=latest_user_message,
        )
        selection_ms = (perf_counter() - selection_started) * 1000
        context_budget.metadata["selection_ms"] = round(selection_ms, 3)
        context_packet = self._build_selected_packet(
            system_prompt=system_prompt,
            latest_user_message=latest_user_message,
            ranked_candidates=ranked_candidates,
            context_budget=context_budget,
            route_plan=route_plan,
            selection=selection,
            hard_input_budget=hard_input_budget,
            working_memory_budget=working_memory_budget,
        )
        context_packet.metadata["budget_planning_ms"] = round(
            budget_planning_ms,
            3,
        )
        context_packet.metadata["selection_ms"] = round(selection_ms, 3)
        return ContextManagerResult(
            context_budget=context_budget,
            context_packet=context_packet,
            metadata=context_manager_metadata(context_budget, context_packet),
        )

    def _build_selected_packet(
        self,
        *,
        system_prompt: str,
        latest_user_message: dict[str, str],
        ranked_candidates: list[MemoryCandidate],
        context_budget: ContextBudget,
        route_plan: RoutePlan,
        selection: SelectionResult,
        hard_input_budget: int,
        working_memory_budget: int,
    ) -> ContextPacket:
        budget_trace = {
            key: context_budget.metadata.get(key)
            for key in (
                "base_memory_budget",
                "route_specific_cap",
                "route_cap_reason",
                "requested_memory_budget",
                "budget_reserve_tokens",
                "required_evidence_floor",
                "required_headroom",
                "required_target",
                "available_memory_budget",
                "budget_expanded_for_required_evidence",
                "fixed_input_tokens",
            )
        }
        while True:
            selection_metadata = {
                **selection.metadata(),
                **budget_trace,
                "working_memory_budget": working_memory_budget,
                "hard_input_budget": hard_input_budget,
            }
            packet = self.context_builder.build(
                system_prompt=system_prompt,
                latest_user_message=latest_user_message,
                ranked_candidates=ranked_candidates,
                context_budget=context_budget,
                route_plan=route_plan,
                preselected_candidates=selection.selected_candidates,
                selection_drops=selection.dropped_candidates,
                selection_metadata=selection_metadata,
            )
            final_tokens = int(packet.metadata.get("final_prompt_tokens", 0) or 0)
            if final_tokens <= hard_input_budget:
                break
            removable = removable_overflow_candidate(selection)
            if removable is None:
                if "hard_input_budget" not in selection.missing_requirements:
                    selection.missing_requirements.append("hard_input_budget")
                selection.evidence_contract_satisfied = False
                removable = required_overflow_candidate(selection)
                if removable is None:
                    break
            selection.selected_candidates.remove(removable)
            trace_id = selection.trace_id_by_object[id(removable)]
            annotation = next(
                item
                for item in selection.candidate_annotations
                if item.trace_id == trace_id
            )
            selection.token_usage = max(
                0,
                selection.token_usage - annotation.token_cost,
            )
            selection.selection_reasons.pop(trace_id, None)
            selection.utility_by_trace_id.pop(trace_id, None)
            selection.dropped_candidates.append(
                {
                    "record_id": removable.record_id,
                    "candidate_id": annotation.candidate_id,
                    "trace_id": trace_id,
                    "source": removable.source,
                    "reason": "hard_limit_overflow",
                    "estimated_tokens": annotation.token_cost,
                }
            )

        packet.metadata["evidence_selection"] = {
            **selection.metadata(),
            **budget_trace,
            "working_memory_budget": working_memory_budget,
            "hard_input_budget": hard_input_budget,
            "final_prompt_tokens": packet.metadata.get("final_prompt_tokens"),
        }
        packet.metadata["working_memory_budget"] = working_memory_budget
        packet.metadata["effective_memory_budget"] = working_memory_budget
        packet.metadata["context_profile"] = route_plan.context_profile
        packet.metadata["hard_input_budget"] = hard_input_budget
        packet.metadata["evidence_contract_satisfied"] = (
            selection.evidence_contract_satisfied
        )
        packet.metadata["missing_requirements"] = list(
            selection.missing_requirements
        )
        packet.metadata.update(budget_trace)
        packet.metadata["selected_memory_tokens"] = selection.token_usage
        packet.metadata["unused_working_budget"] = max(
            0,
            working_memory_budget - selection.token_usage,
        )
        packet.metadata["optional_selection_stopped_by"] = (
            selection.optional_selection_stopped_by
        )
        return packet


def required_floor_candidates(
    preflight: SelectionResult,
    *,
    route_plan: RoutePlan,
) -> list[MemoryCandidate]:
    candidates = [
        candidate
        for candidate in preflight.selected_candidates
        if preflight.selection_reasons.get(
            preflight.trace_id_by_object[id(candidate)]
        )
        in {
            "required_raw_evidence",
            "required_scope_evidence",
            "protected_recent_suffix",
        }
    ]
    task_context = str(route_plan.metadata.get("task_context") or "")
    if task_context in LONG_DOCUMENT_TASK_CONTEXTS:
        candidates.extend(
            candidate
            for candidate in preflight.selected_candidates
            if candidate.source == "document_memory"
            and candidate not in candidates
        )
    return candidates


def required_floor_token_cost(
    *,
    context_builder: ContextBuilder,
    candidates: list[MemoryCandidate],
    system_prompt: str,
    latest_user_message: dict[str, str],
    ranked_candidates: list[MemoryCandidate],
    context_budget: ContextBudget,
    route_plan: RoutePlan,
    fixed_prompt_tokens: int,
) -> int:
    if not candidates:
        return 0
    preview = context_builder.build(
        system_prompt=system_prompt,
        latest_user_message=latest_user_message,
        ranked_candidates=ranked_candidates,
        context_budget=context_budget,
        route_plan=route_plan,
        preselected_candidates=candidates,
    )
    return max(
        0,
        int(preview.metadata.get("final_prompt_tokens", 0) or 0)
        - fixed_prompt_tokens,
    )


def removable_overflow_candidate(
    selection: SelectionResult,
) -> MemoryCandidate | None:
    optional_non_recent = [
        candidate
        for candidate in selection.selected_candidates
        if candidate.source != "recent_messages"
        and selection.trace_id_by_object[id(candidate)]
        not in selection.required_trace_ids
    ]
    if optional_non_recent:
        return min(
            optional_non_recent,
            key=lambda item: (
                selection.utility_by_trace_id.get(
                    selection.trace_id_by_object[id(item)],
                    0.0,
                ),
                -next(
                    annotation.rank
                    for annotation in selection.candidate_annotations
                    if annotation.trace_id
                    == selection.trace_id_by_object[id(item)]
                ),
            ),
        )
    recent = [
        candidate
        for candidate in selection.selected_candidates
        if candidate.source == "recent_messages"
    ]
    return min(recent, key=lambda item: recent_message_order(item)) if recent else None


def required_overflow_candidate(
    selection: SelectionResult,
) -> MemoryCandidate | None:
    required = [
        candidate
        for candidate in selection.selected_candidates
        if selection.trace_id_by_object[id(candidate)] in selection.required_trace_ids
    ]
    if not required:
        return None
    return max(
        required,
        key=lambda item: next(
            annotation.rank
            for annotation in selection.candidate_annotations
            if annotation.trace_id == selection.trace_id_by_object[id(item)]
        ),
    )


def recent_message_order(candidate: MemoryCandidate) -> int:
    if candidate.source_message_ids:
        return min(candidate.source_message_ids)
    return int(candidate.record_id) if isinstance(candidate.record_id, int) else 0


def context_manager_metadata(
    context_budget: ContextBudget,
    context_packet: ContextPacket,
) -> dict[str, Any]:
    """Return trace metadata for context-manager decisions."""
    dropped = context_packet.metadata.get("dropped_candidates", [])
    if not isinstance(dropped, list):
        dropped = []
    return {
        "context_manager_used": True,
        "source_budgets": dict(context_budget.source_token_budgets),
        "source_budgets_advisory_only": True,
        "context_profile": context_packet.metadata.get("context_profile"),
        "requested_memory_budget": context_packet.metadata.get(
            "requested_memory_budget"
        ),
        "effective_memory_budget": context_packet.metadata.get(
            "effective_memory_budget"
        ),
        "budget_reserve_tokens": context_packet.metadata.get(
            "budget_reserve_tokens"
        ),
        "working_memory_budget": context_packet.metadata.get(
            "working_memory_budget"
        ),
        "hard_input_budget": context_packet.metadata.get("hard_input_budget"),
        "evidence_selection": dict(
            context_packet.metadata.get("evidence_selection", {})
        ),
        "included_candidate_counts_by_source": candidate_counts_by_source(
            context_packet.candidates
        ),
        "dropped_candidate_counts_by_source": dropped_counts_by_source(dropped),
        "final_prompt_sections": list(context_packet.metadata.get("section_order", [])),
        "token_accounting": {
            key: context_packet.metadata.get(key)
            for key in (
                "model_id",
                "tokenizer_id",
                "tokenizer_mode",
                "native_context_window",
                "sliding_window",
                "endpoint_context_window",
                "endpoint_limit_verified",
                "application_context_cap",
                "effective_context_window",
                "output_reserve",
                "system_tokens",
                "query_tokens",
                "memory_tokens",
                "final_prompt_tokens",
                "limit_source",
                "effective_limit_source",
                "fallback_reason",
            )
        },
    }


def candidate_counts_by_source(
    candidates: list[MemoryCandidate],
) -> dict[str, int]:
    """Count selected candidates by source."""
    counts: dict[str, int] = {}
    for candidate in candidates:
        counts[candidate.source] = counts.get(candidate.source, 0) + 1
    return counts


def dropped_counts_by_source(dropped_candidates: list[object]) -> dict[str, int]:
    """Count dropped candidates by source from ContextPacket metadata."""
    counts: dict[str, int] = {}
    for item in dropped_candidates:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        if not isinstance(source, str):
            continue
        counts[source] = counts.get(source, 0) + 1
    return counts
