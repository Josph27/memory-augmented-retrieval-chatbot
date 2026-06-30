from __future__ import annotations

from dataclasses import dataclass, field

from src.context.token_estimator import ApproximateTokenEstimator, TokenEstimator
from src.core.contracts import ContextBudget, MemoryCandidate, RoutePlan


@dataclass(frozen=True)
class AllocationProfile:
    """Relative token allocation ratios for one context profile."""

    system: float
    recent_messages: float
    structured_memory: float
    current_chat_gist: float
    current_chat_span: float
    previous_chat_gist: float
    raw_message_span: float
    current_chat_chunks: float
    previous_chat_memory: float
    document_memory: float
    safety_margin: float
    answer_reserve: float


@dataclass(frozen=True)
class ContextBudgetPolicy:
    """Centralized budget allocation policy."""

    default_model_context_limit: int = 4096
    default_answer_reserve: int = 512
    minimum_candidate_source_tokens: int = 64
    profiles: dict[str, AllocationProfile] = field(
        default_factory=lambda: {
            "general_chat": AllocationProfile(
                system=0.08,
                recent_messages=0.55,
                structured_memory=0.2,
                current_chat_gist=0.0,
                current_chat_span=0.0,
                previous_chat_gist=0.0,
                raw_message_span=0.0,
                current_chat_chunks=0.0,
                previous_chat_memory=0.0,
                document_memory=0.0,
                safety_margin=0.07,
                answer_reserve=0.1,
            ),
            "memory_recall": AllocationProfile(
                system=0.08,
                recent_messages=0.35,
                structured_memory=0.35,
                current_chat_gist=0.1,
                current_chat_span=0.0,
                previous_chat_gist=0.0,
                raw_message_span=0.0,
                current_chat_chunks=0.1,
                previous_chat_memory=0.0,
                document_memory=0.0,
                safety_margin=0.07,
                answer_reserve=0.05,
            ),
            "document_question": AllocationProfile(
                system=0.08,
                recent_messages=0.2,
                structured_memory=0.1,
                current_chat_gist=0.0,
                current_chat_span=0.0,
                previous_chat_gist=0.0,
                raw_message_span=0.0,
                current_chat_chunks=0.0,
                previous_chat_memory=0.0,
                document_memory=0.5,
                safety_margin=0.07,
                answer_reserve=0.05,
            ),
            "mixed_memory_document": AllocationProfile(
                system=0.08,
                recent_messages=0.2,
                structured_memory=0.2,
                current_chat_gist=0.1,
                current_chat_span=0.0,
                previous_chat_gist=0.15,
                raw_message_span=0.05,
                current_chat_chunks=0.1,
                previous_chat_memory=0.15,
                document_memory=0.25,
                safety_margin=0.07,
                answer_reserve=0.05,
            ),
        }
    )


class ContextBudgetAllocator:
    """Allocate trace-only token budgets from route plans and ranked candidates."""

    def __init__(
        self,
        token_estimator: TokenEstimator | None = None,
        policy: ContextBudgetPolicy | None = None,
    ) -> None:
        self.token_estimator = token_estimator or ApproximateTokenEstimator()
        self.policy = policy or ContextBudgetPolicy()

    def allocate(
        self,
        route_plan: RoutePlan,
        ranked_candidates: list[MemoryCandidate],
        model_context_limit: int | None = None,
        answer_reserve: int | None = None,
        system_prompt: str | None = None,
        system_prompt_tokens: int | None = None,
    ) -> ContextBudget:
        """Return a profile-based context budget without affecting prompt construction."""
        context_limit = model_context_limit or self.policy.default_model_context_limit
        requested_answer_reserve = answer_reserve or self.policy.default_answer_reserve
        profile_name = profile_name_for(route_plan.context_profile)
        profile = self.policy.profiles.get(profile_name, self.policy.profiles["general_chat"])
        enabled_sources = enabled_source_names(route_plan)

        system_estimate = system_prompt_tokens
        if system_estimate is None:
            system_estimate = self.token_estimator.estimate_text(system_prompt or "")

        safety_tokens = ratio_tokens(context_limit, profile.safety_margin)
        profile_answer_reserve = ratio_tokens(context_limit, profile.answer_reserve)
        reserved_response_tokens = max(
            0,
            min(max(requested_answer_reserve, profile_answer_reserve), context_limit),
        )
        allocatable = max(0, context_limit - system_estimate - safety_tokens - reserved_response_tokens)

        source_ratios = enabled_source_ratios(profile, enabled_sources)
        candidate_source_minimum_budgets = candidate_source_minimum_budgets_for(
            ranked_candidates=ranked_candidates,
            enabled_sources=enabled_sources,
            token_estimator=self.token_estimator,
            minimum_tokens=self.policy.minimum_candidate_source_tokens,
            allocatable_tokens=allocatable,
        )
        ratio_allocatable = max(
            0,
            allocatable - sum(candidate_source_minimum_budgets.values()),
        )
        source_budgets = allocate_source_budgets(
            ratio_allocatable,
            source_ratios,
        )
        for source, minimum_budget in candidate_source_minimum_budgets.items():
            source_budgets[source] = (
                source_budgets.get(source, 0) + minimum_budget
            )
        recent_message_tokens = source_budgets.get("recent_messages", 0)
        structured_memory_tokens = source_budgets.get("structured_memory", 0)
        retrieval_tokens = sum(
            tokens
            for source, tokens in source_budgets.items()
            if source not in {"recent_messages", "structured_memory"}
        )

        candidate_token_estimate = sum(
            self.token_estimator.estimate_text(candidate.content)
            for candidate in ranked_candidates
        )
        return ContextBudget(
            max_tokens=context_limit,
            system_tokens=system_estimate,
            memory_tokens=structured_memory_tokens,
            recent_message_tokens=recent_message_tokens,
            retrieval_tokens=retrieval_tokens,
            reserved_response_tokens=reserved_response_tokens,
            source_token_budgets=source_budgets,
            metadata={
                "context_profile": profile_name,
                "enabled_sources": sorted(enabled_sources),
                "safety_margin_tokens": safety_tokens,
                "allocatable_tokens": allocatable,
                "candidate_count": len(ranked_candidates),
                "candidate_token_estimate": candidate_token_estimate,
                "ratio_source": "normalized_enabled_sources",
                "candidate_source_minimum_budgets": (
                    candidate_source_minimum_budgets
                ),
            },
        )


def profile_name_for(context_profile: str | None) -> str:
    """Map route-plan context profiles to allocator profile names."""
    if context_profile in {
        "general_chat",
        "memory_recall",
        "document_question",
        "mixed_memory_document",
    }:
        return context_profile
    if context_profile == "structured_memory_plus_recent_messages":
        return "memory_recall"
    return "general_chat"


def enabled_source_names(route_plan: RoutePlan) -> set[str]:
    """Return enabled source names from a route plan."""
    return {source.source for source in route_plan.sources if source.enabled}


def enabled_source_ratios(
    profile: AllocationProfile,
    enabled_sources: set[str],
) -> dict[str, float]:
    """Return normalized ratios for enabled sources only."""
    ratios = {
        "recent_messages": profile.recent_messages,
        "structured_memory": profile.structured_memory,
        "current_chat_gist": profile.current_chat_gist,
        "current_chat_span": profile.current_chat_span,
        "previous_chat_gist": profile.previous_chat_gist,
        "raw_message_span": profile.raw_message_span,
        "current_chat_chunks": profile.current_chat_chunks,
        "previous_chat_memory": profile.previous_chat_memory,
        "document_memory": profile.document_memory,
    }
    enabled_ratios = {
        source: ratio
        for source, ratio in ratios.items()
        if source in enabled_sources and ratio > 0
    }
    ratio_total = sum(enabled_ratios.values())
    if ratio_total <= 0:
        return {}
    return {source: ratio / ratio_total for source, ratio in enabled_ratios.items()}


def allocate_source_budgets(allocatable_tokens: int, ratios: dict[str, float]) -> dict[str, int]:
    """Allocate non-negative integer budgets from normalized ratios."""
    return {
        source: max(0, int(allocatable_tokens * ratio))
        for source, ratio in ratios.items()
    }


def candidate_source_minimum_budgets_for(
    *,
    ranked_candidates: list[MemoryCandidate],
    enabled_sources: set[str],
    token_estimator: TokenEstimator,
    minimum_tokens: int,
    allocatable_tokens: int,
) -> dict[str, int]:
    """Reserve bounded minimums for every candidate-bearing enabled source."""
    candidate_sizes: dict[str, list[int]] = {}
    for candidate in ranked_candidates:
        if candidate.source not in enabled_sources:
            continue
        candidate_sizes.setdefault(candidate.source, []).append(
            token_estimator.estimate_text(candidate.content)
        )

    candidate_sources = sorted(candidate_sizes)
    if not candidate_sources or allocatable_tokens <= 0:
        return {}

    requested = {
        source: max(
            1,
            minimum_tokens,
            min(candidate_sizes[source]),
        )
        for source in candidate_sources
    }
    requested_total = sum(requested.values())
    if requested_total <= allocatable_tokens:
        return requested

    available_per_source = allocatable_tokens // len(candidate_sources)
    if available_per_source <= 0:
        return {}
    return {
        source: min(requested[source], available_per_source)
        for source in candidate_sources
    }


def ratio_tokens(context_limit: int, ratio: float) -> int:
    """Convert a ratio to a non-negative token count."""
    return max(0, int(context_limit * max(0.0, ratio)))
