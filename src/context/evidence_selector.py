from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence

from src.context.context_builder import recent_message_sort_key
from src.context.token_estimator import TokenEstimator, count_text
from src.core.contracts import MemoryCandidate, RoutePlan


RAW_SOURCES = frozenset({"raw_message_span", "current_chat_span"})
GIST_SOURCES = frozenset({"previous_chat_gist", "current_chat_gist"})
SCOPE_SOURCE_PREFERENCES = {
    "document": ("document_memory",),
    "current_chat": ("current_chat_span",),
    "previous_chat": ("raw_message_span", "previous_chat_gist"),
    "durable": ("structured_memory",),
}


@dataclass(frozen=True)
class SelectorPolicy:
    """Small deterministic controls; none are source token quotas."""

    overlap_threshold: float = 0.7
    minimum_required_score: float = 0.55
    minimum_optional_utility: float = 0.15
    max_token_cost_penalty: float = 0.03


@dataclass(frozen=True)
class CandidateAnnotation:
    trace_id: str
    candidate_id: str
    source: str
    rank: int
    score: float
    token_cost: int
    source_message_ids: tuple[int, ...]
    document_id: str | None
    chunk_id: str | int | None
    parent_gist_id: str | int | None
    anchor_message_ids: tuple[int, ...]
    required_scope_matches: tuple[str, ...]
    exact_raw_evidence: bool

    def to_metadata(self) -> dict[str, object]:
        return {
            "trace_id": self.trace_id,
            "candidate_id": self.candidate_id,
            "source": self.source,
            "rank": self.rank,
            "score": self.score,
            "token_cost": self.token_cost,
            "source_message_ids": list(self.source_message_ids),
            "document_id": self.document_id,
            "chunk_id": self.chunk_id,
            "parent_gist_id": self.parent_gist_id,
            "anchor_message_ids": list(self.anchor_message_ids),
            "required_scope_matches": list(self.required_scope_matches),
            "exact_raw_evidence": self.exact_raw_evidence,
        }


@dataclass
class SelectionResult:
    selected_candidates: list[MemoryCandidate]
    dropped_candidates: list[dict[str, Any]]
    token_usage: int
    evidence_contract_satisfied: bool
    required_evidence_selected: list[str]
    missing_requirements: list[str]
    duplicate_decisions: list[dict[str, Any]]
    selection_reasons: dict[str, str]
    candidate_annotations: list[CandidateAnnotation]
    utility_by_trace_id: dict[str, float]
    required_trace_ids: set[str]
    trace_id_by_object: dict[int, str]
    optional_selection_stopped_by: str
    coverage_strategy: str = "relevance_ranked"
    eligible_history_tokens: int = 0
    selected_history_tokens: int = 0
    coverage_ratio: float = 0.0
    selected_time_range_count: int = 0

    def metadata(self) -> dict[str, object]:
        return {
            "token_usage": self.token_usage,
            "evidence_contract_satisfied": self.evidence_contract_satisfied,
            "required_evidence_selected": list(self.required_evidence_selected),
            "missing_requirements": list(self.missing_requirements),
            "duplicate_decisions": list(self.duplicate_decisions),
            "selection_reasons": dict(self.selection_reasons),
            "candidate_token_costs": [
                annotation.to_metadata() for annotation in self.candidate_annotations
            ],
            "global_utility": dict(self.utility_by_trace_id),
            "optional_selection_stopped_by": self.optional_selection_stopped_by,
            "coverage_strategy": self.coverage_strategy,
            "eligible_history_tokens": self.eligible_history_tokens,
            "selected_history_tokens": self.selected_history_tokens,
            "coverage_ratio": self.coverage_ratio,
            "selected_time_range_count": self.selected_time_range_count,
            "selection_decisions": [
                {
                    **annotation.to_metadata(),
                    "global_utility": self.utility_by_trace_id.get(annotation.trace_id),
                    "redundancy_penalty": 0.0,
                    "selected_by": self.selection_reasons.get(annotation.trace_id),
                }
                for annotation in self.candidate_annotations
            ],
        }


class EvidenceConstrainedContextSelector:
    """Select ranked typed evidence under one shared deterministic token budget."""

    def __init__(self, policy: SelectorPolicy | None = None) -> None:
        self.policy = policy or SelectorPolicy()

    def select(
        self,
        *,
        candidates: Sequence[MemoryCandidate],
        route_plan: RoutePlan,
        token_budget: int,
        token_counter: TokenEstimator,
        latest_user_message: dict[str, str] | None = None,
    ) -> SelectionResult:
        ranked = list(candidates)
        enabled_sources = {source.source for source in route_plan.sources if source.enabled}
        eligible = [
            candidate for candidate in ranked if candidate_is_enabled(candidate, enabled_sources)
        ]
        trace_ids = {
            id(candidate): candidate_trace_id(candidate, rank)
            for rank, candidate in enumerate(ranked, start=1)
        }
        required_scopes = required_scopes_for(route_plan)
        requires_raw = requires_raw_span(route_plan)
        annotations = annotate_candidates(
            ranked,
            ranked=ranked,
            trace_ids=trace_ids,
            required_scopes=required_scopes,
            token_counter=token_counter,
        )
        annotation_by_object = {
            id(candidate): annotation
            for candidate, annotation in zip(ranked, annotations, strict=True)
        }

        non_recent = [candidate for candidate in eligible if candidate.source != "recent_messages"]
        recent = [candidate for candidate in eligible if candidate.source == "recent_messages"]
        deduplicated, dropped, duplicate_decisions = deduplicate_candidates(
            non_recent,
            annotation_by_object=annotation_by_object,
            trace_ids=trace_ids,
            overlap_threshold=self.policy.overlap_threshold,
        )
        eligible_ids = {id(candidate) for candidate in eligible}
        dropped = [
            *[
                drop_record(
                    candidate,
                    annotation_by_object[id(candidate)],
                    reason="source_disabled",
                )
                for candidate in ranked
                if id(candidate) not in eligible_ids
            ],
            *dropped,
        ]

        selected: list[MemoryCandidate] = []
        selected_ids: set[int] = set()
        required_trace_ids: set[str] = set()
        reasons: dict[str, str] = {}
        utilities: dict[str, float] = {}
        required_selected: list[str] = []
        missing: list[str] = []
        used_tokens = 0

        requirements = []
        if requires_raw:
            requirements.append(("raw_span", tuple(RAW_SOURCES)))
        requirements.extend(
            (scope, SCOPE_SOURCE_PREFERENCES[scope])
            for scope in ("document", "current_chat", "previous_chat", "durable")
            if scope in required_scopes
        )
        for requirement, preferred_sources in requirements:
            existing = next(
                (item for item in selected if item.source in preferred_sources),
                None,
            )
            if existing is not None:
                annotation = annotation_by_object[id(existing)]
                required_trace_ids.add(annotation.trace_id)
                required_selected.append(requirement)
                continue
            candidate = best_required_candidate(
                deduplicated,
                preferred_sources=preferred_sources,
                annotation_by_object=annotation_by_object,
                already_selected=selected_ids,
                policy=self.policy,
            )
            if candidate is None:
                missing.append(requirement)
                continue
            annotation = annotation_by_object[id(candidate)]
            if used_tokens + annotation.token_cost > token_budget:
                missing.append(requirement)
                dropped.append(
                    drop_record(
                        candidate,
                        annotation,
                        reason="global_budget_exceeded",
                        requirement=requirement,
                    )
                )
                continue
            selected.append(candidate)
            selected_ids.add(id(candidate))
            used_tokens += annotation.token_cost
            required_trace_ids.add(annotation.trace_id)
            required_selected.append(requirement)
            reasons[annotation.trace_id] = (
                "required_raw_evidence" if requirement == "raw_span" else "required_scope_evidence"
            )
            utilities[annotation.trace_id] = required_utility(candidate)
            used_tokens, folded = fold_parent_gist(
                candidate,
                selected=selected,
                selected_ids=selected_ids,
                annotation_by_object=annotation_by_object,
                trace_ids=trace_ids,
                reasons=reasons,
                used_tokens=used_tokens,
            )
            dropped.extend(folded)
            duplicate_decisions.extend(folded)

        remaining_budget = max(0, token_budget - used_tokens)
        recent_suffix, recent_drops = newest_recent_suffix(
            recent,
            budget=remaining_budget,
            token_counter=token_counter,
            latest_user_message=latest_user_message,
            route_query=route_plan.query,
            annotation_by_object=annotation_by_object,
        )
        for candidate in recent_suffix:
            annotation = annotation_by_object[id(candidate)]
            selected.append(candidate)
            selected_ids.add(id(candidate))
            used_tokens += annotation.token_cost
            reasons[annotation.trace_id] = "protected_recent_suffix"
            utilities[annotation.trace_id] = 0.2
        dropped.extend(recent_drops)

        remaining = [candidate for candidate in deduplicated if id(candidate) not in selected_ids]
        remaining, initially_folded = fold_unselected_parent_gists(
            remaining,
            selected=selected,
            annotation_by_object=annotation_by_object,
            trace_ids=trace_ids,
        )
        dropped.extend(initially_folded)
        duplicate_decisions.extend(initially_folded)
        selected_sources = {candidate.source for candidate in selected}
        optional_stop_reason = "required_evidence_only" if selected else "no_candidates"
        had_optional_candidates = bool(remaining)
        had_non_fitting_candidate = False
        coverage_strategy = "relevance_ranked"
        eligible_history_tokens = sum(
            annotation_by_object[id(candidate)].token_cost
            for candidate in deduplicated
            if candidate.source in RAW_SOURCES | GIST_SOURCES
        )
        if route_plan.context_profile == "global_summary":
            coverage_strategy = "chronological_complete_or_timeline_sample"
            summary_order = global_summary_selection_order(
                remaining,
                annotation_by_object=annotation_by_object,
                available_tokens=max(0, token_budget - used_tokens),
            )
            for candidate in summary_order:
                annotation = annotation_by_object[id(candidate)]
                remaining.remove(candidate)
                if used_tokens + annotation.token_cost > token_budget:
                    had_non_fitting_candidate = True
                    dropped.append(
                        drop_record(
                            candidate,
                            annotation,
                            reason="global_budget_exceeded",
                        )
                    )
                    continue
                selected.append(candidate)
                selected_ids.add(id(candidate))
                used_tokens += annotation.token_cost
                selected_sources.add(candidate.source)
                reasons[annotation.trace_id] = "global_summary_chronological_coverage"
                utilities[annotation.trace_id] = required_utility(candidate)
                used_tokens, folded = fold_parent_gist(
                    candidate,
                    selected=selected,
                    selected_ids=selected_ids,
                    annotation_by_object=annotation_by_object,
                    trace_ids=trace_ids,
                    reasons=reasons,
                    used_tokens=used_tokens,
                )
                dropped.extend(folded)
                duplicate_decisions.extend(folded)
            dropped.extend(
                drop_record(
                    candidate,
                    annotation_by_object[id(candidate)],
                    reason="global_budget_exceeded",
                )
                for candidate in remaining
            )
            remaining.clear()
            optional_stop_reason = (
                "no_fitting_candidate" if had_non_fitting_candidate else "no_candidates"
            )
        while remaining:
            scored = [
                (
                    marginal_utility(
                        candidate,
                        annotation_by_object[id(candidate)],
                        token_budget=token_budget,
                        policy=self.policy,
                    ),
                    annotation_by_object[id(candidate)].rank,
                    candidate,
                )
                for candidate in remaining
            ]
            scored.sort(key=lambda item: (-item[0], item[1]))
            utility, _, candidate = scored[0]
            annotation = annotation_by_object[id(candidate)]
            remaining.remove(candidate)
            if utility < self.policy.minimum_optional_utility:
                dropped.extend(
                    drop_record(
                        remaining_candidate,
                        annotation_by_object[id(remaining_candidate)],
                        reason="lower_marginal_utility",
                        utility=marginal_utility(
                            remaining_candidate,
                            annotation_by_object[id(remaining_candidate)],
                            token_budget=token_budget,
                            policy=self.policy,
                        ),
                    )
                    for remaining_candidate in [candidate, *remaining]
                )
                optional_stop_reason = "below_minimum_utility"
                remaining.clear()
                break
            if used_tokens + annotation.token_cost > token_budget:
                had_non_fitting_candidate = True
                dropped.append(
                    drop_record(
                        candidate,
                        annotation,
                        reason="global_budget_exceeded",
                        utility=utility,
                    )
                )
                continue
            selected.append(candidate)
            selected_ids.add(id(candidate))
            used_tokens += annotation.token_cost
            selected_sources.add(candidate.source)
            reasons[annotation.trace_id] = "global_marginal_utility"
            utilities[annotation.trace_id] = utility
            used_tokens, folded = fold_parent_gist(
                candidate,
                selected=selected,
                selected_ids=selected_ids,
                annotation_by_object=annotation_by_object,
                trace_ids=trace_ids,
                reasons=reasons,
                used_tokens=used_tokens,
            )
            dropped.extend(folded)
            duplicate_decisions.extend(folded)
            remaining, newly_folded = fold_unselected_parent_gists(
                remaining,
                selected=selected,
                annotation_by_object=annotation_by_object,
                trace_ids=trace_ids,
            )
            dropped.extend(newly_folded)
            duplicate_decisions.extend(newly_folded)
            optional_stop_reason = "no_candidates"

        if optional_stop_reason != "below_minimum_utility":
            if used_tokens >= token_budget and had_optional_candidates:
                optional_stop_reason = "working_budget_reached"
            elif had_non_fitting_candidate:
                optional_stop_reason = "no_fitting_candidate"
            elif not had_optional_candidates:
                optional_stop_reason = "required_evidence_only" if selected else "no_candidates"

        if route_plan.context_profile == "global_summary":
            selected.sort(
                key=lambda item: global_summary_chronological_key(
                    item,
                    annotation_by_object[id(item)].rank,
                )
            )
        else:
            selected.sort(key=lambda item: annotation_by_object[id(item)].rank)
        dropped.extend(
            {
                "record_id": None,
                "candidate_id": None,
                "trace_id": None,
                "source": None,
                "reason": "missing_required_evidence",
                "requirement": requirement,
                "estimated_tokens": 0,
            }
            for requirement in dict.fromkeys(missing)
        )
        selected_history_tokens = sum(
            annotation_by_object[id(candidate)].token_cost
            for candidate in selected
            if candidate.source in RAW_SOURCES | GIST_SOURCES
        )
        return SelectionResult(
            selected_candidates=selected,
            dropped_candidates=dropped,
            token_usage=used_tokens,
            evidence_contract_satisfied=not missing,
            required_evidence_selected=required_selected,
            missing_requirements=missing,
            duplicate_decisions=duplicate_decisions,
            selection_reasons=reasons,
            candidate_annotations=annotations,
            utility_by_trace_id=utilities,
            required_trace_ids=required_trace_ids,
            trace_id_by_object=trace_ids,
            optional_selection_stopped_by=optional_stop_reason,
            coverage_strategy=coverage_strategy,
            eligible_history_tokens=eligible_history_tokens,
            selected_history_tokens=selected_history_tokens,
            coverage_ratio=(
                min(1.0, selected_history_tokens / eligible_history_tokens)
                if eligible_history_tokens
                else 0.0
            ),
            selected_time_range_count=selected_time_range_count(selected),
        )


def annotate_candidates(
    candidates: list[MemoryCandidate],
    *,
    ranked: list[MemoryCandidate],
    trace_ids: dict[int, str],
    required_scopes: set[str],
    token_counter: TokenEstimator,
) -> list[CandidateAnnotation]:
    rank_by_object = {id(candidate): rank for rank, candidate in enumerate(ranked, 1)}
    return [
        CandidateAnnotation(
            trace_id=trace_ids[id(candidate)],
            candidate_id=f"{candidate.source}:{candidate.record_id}",
            source=candidate.source,
            rank=rank_by_object[id(candidate)],
            score=float(candidate.score or 0.0),
            token_cost=count_text(token_counter, candidate.content),
            source_message_ids=tuple(candidate.source_message_ids),
            document_id=string_or_none(candidate.metadata.get("document_id")),
            chunk_id=candidate.metadata.get("chunk_id"),
            parent_gist_id=candidate.metadata.get("parent_gist_id"),
            anchor_message_ids=tuple(
                integer_list(
                    candidate.metadata.get("anchor_message_ids")
                    or candidate.metadata.get("matched_message_ids")
                )
            ),
            required_scope_matches=tuple(sorted(scope_matches(candidate) & required_scopes)),
            exact_raw_evidence=candidate.source in RAW_SOURCES,
        )
        for candidate in candidates
    ]


def deduplicate_candidates(
    candidates: list[MemoryCandidate],
    *,
    annotation_by_object: dict[int, CandidateAnnotation],
    trace_ids: dict[int, str],
    overlap_threshold: float,
) -> tuple[list[MemoryCandidate], list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[MemoryCandidate] = []
    dropped: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    normalized_keeper: dict[str, MemoryCandidate] = {}
    for candidate in candidates:
        normalized = normalize_text(candidate.content)
        duplicate = normalized_keeper.get(normalized)
        if normalized and duplicate is not None:
            merge_retrieval_paths(duplicate, candidate)
            annotation = annotation_by_object[id(candidate)]
            record = drop_record(
                candidate,
                annotation,
                reason="exact_duplicate",
                merged_into=trace_ids[id(duplicate)],
                merged_source_message_ids=sorted(
                    set(duplicate.source_message_ids) | set(candidate.source_message_ids)
                ),
                merged_document_ids=sorted(
                    {
                        str(value)
                        for value in (
                            duplicate.metadata.get("document_id"),
                            candidate.metadata.get("document_id"),
                        )
                        if value is not None
                    }
                ),
            )
            dropped.append(record)
            decisions.append(record)
            continue
        normalized_keeper[normalized] = candidate

        overlapping = next(
            (
                existing
                for existing in kept
                if should_fold_overlapping_span(
                    existing,
                    candidate,
                    threshold=overlap_threshold,
                )
            ),
            None,
        )
        if overlapping is not None:
            overlap_ratio = spans_overlap(overlapping, candidate)
            unique_ids = sorted(
                set(candidate.source_message_ids) - set(overlapping.source_message_ids)
            )
            merge_retrieval_paths(overlapping, candidate)
            annotation = annotation_by_object[id(candidate)]
            record = drop_record(
                candidate,
                annotation,
                reason="overlapping_selected_span",
                merged_into=trace_ids[id(overlapping)],
                overlap_ratio=overlap_ratio,
                overlap_with_candidate_id=(f"{overlapping.source}:{overlapping.record_id}"),
                unique_message_count=len(unique_ids),
                merged_source_message_ids=sorted(
                    set(overlapping.source_message_ids) | set(candidate.source_message_ids)
                ),
            )
            dropped.append(record)
            decisions.append(record)
            continue
        kept.append(candidate)
    return kept, dropped, decisions


def best_required_candidate(
    candidates: list[MemoryCandidate],
    *,
    preferred_sources: tuple[str, ...],
    annotation_by_object: dict[int, CandidateAnnotation],
    already_selected: set[int],
    policy: SelectorPolicy,
) -> MemoryCandidate | None:
    for source in preferred_sources:
        matches = [
            candidate
            for candidate in candidates
            if candidate.source == source
            and id(candidate) not in already_selected
            and candidate_is_relevant(candidate, policy)
        ]
        if matches:
            return min(matches, key=lambda item: annotation_by_object[id(item)].rank)
    return None


def newest_recent_suffix(
    candidates: list[MemoryCandidate],
    *,
    budget: int,
    token_counter: TokenEstimator,
    latest_user_message: dict[str, str] | None,
    route_query: str,
    annotation_by_object: dict[int, CandidateAnnotation],
) -> tuple[list[MemoryCandidate], list[dict[str, Any]]]:
    excluded = [
        candidate
        for candidate in candidates
        if is_latest_query_candidate(candidate, latest_user_message, route_query)
    ]
    filtered = [
        candidate
        for candidate in candidates
        if not is_latest_query_candidate(candidate, latest_user_message, route_query)
    ]
    ordered = sorted(filtered, key=recent_message_sort_key)
    selected_reversed: list[MemoryCandidate] = []
    used = 0
    first_dropped = -1
    for index in range(len(ordered) - 1, -1, -1):
        candidate = ordered[index]
        cost = count_text(token_counter, candidate.content)
        if used + cost > budget:
            first_dropped = index
            break
        selected_reversed.append(candidate)
        used += cost
    selected = list(reversed(selected_reversed))
    dropped = [
        drop_record(
            candidate,
            annotation_by_object[id(candidate)],
            reason="global_budget_exceeded",
        )
        for candidate in ordered[: first_dropped + 1]
    ]
    dropped.extend(
        drop_record(
            candidate,
            annotation_by_object[id(candidate)],
            reason="latest_user_message_excluded",
        )
        for candidate in excluded
    )
    return selected, dropped


def marginal_utility(
    candidate: MemoryCandidate,
    annotation: CandidateAnnotation,
    *,
    token_budget: int,
    policy: SelectorPolicy,
) -> float:
    """Pure relevance-minus-cost utility.  Source preference and
    diversity are handled upstream by the reranker."""
    relevance = float(candidate.score or 0.0)
    cost_ratio = annotation.token_cost / max(1, token_budget)
    cost_penalty = min(
        policy.max_token_cost_penalty,
        cost_ratio * policy.max_token_cost_penalty,
    )
    return relevance - cost_penalty


def fold_parent_gist(
    candidate: MemoryCandidate,
    *,
    selected: list[MemoryCandidate],
    selected_ids: set[int],
    annotation_by_object: dict[int, CandidateAnnotation],
    trace_ids: dict[int, str],
    reasons: dict[str, str],
    used_tokens: int,
) -> tuple[int, list[dict[str, Any]]]:
    if candidate.source != "raw_message_span":
        return used_tokens, []
    parent_id = candidate.metadata.get("parent_gist_id")
    if parent_id is None:
        return used_tokens, []
    parent = next(
        (item for item in selected if item.source in GIST_SOURCES and item.record_id == parent_id),
        None,
    )
    if parent is None:
        return used_tokens, []
    selected.remove(parent)
    selected_ids.discard(id(parent))
    parent_annotation = annotation_by_object[id(parent)]
    used_tokens = max(0, used_tokens - parent_annotation.token_cost)
    reasons.pop(trace_ids[id(parent)], None)
    return used_tokens, [
        drop_record(
            parent,
            parent_annotation,
            reason="folded_into_raw_child",
            folded_into=trace_ids[id(candidate)],
        )
    ]


def fold_unselected_parent_gists(
    candidates: list[MemoryCandidate],
    *,
    selected: list[MemoryCandidate],
    annotation_by_object: dict[int, CandidateAnnotation],
    trace_ids: dict[int, str],
) -> tuple[list[MemoryCandidate], list[dict[str, Any]]]:
    selected_parent_ids = {
        candidate.metadata.get("parent_gist_id")
        for candidate in selected
        if candidate.source == "raw_message_span"
        and candidate.metadata.get("parent_gist_id") is not None
    }
    kept: list[MemoryCandidate] = []
    folded: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.source in GIST_SOURCES and candidate.record_id in selected_parent_ids:
            child = next(
                item
                for item in selected
                if item.source == "raw_message_span"
                and item.metadata.get("parent_gist_id") == candidate.record_id
            )
            folded.append(
                drop_record(
                    candidate,
                    annotation_by_object[id(candidate)],
                    reason="folded_into_raw_child",
                    folded_into=trace_ids[id(child)],
                )
            )
            continue
        kept.append(candidate)
    return kept, folded


def required_scopes_for(route_plan: RoutePlan) -> set[str]:
    value = route_plan.metadata.get("required_scopes", [])
    scopes = {str(scope) for scope in value} if isinstance(value, list | tuple | set) else set()
    if not scopes and route_plan.intent == "document_question":
        scopes.add("document")
    return scopes


def requires_raw_span(route_plan: RoutePlan) -> bool:
    return bool(route_plan.metadata.get("requires_raw_span") or route_plan.intent == "EXACT_QUOTE")


def candidate_is_enabled(
    candidate: MemoryCandidate,
    enabled_sources: set[str],
) -> bool:
    if candidate.source in enabled_sources:
        return True
    parent_source = candidate.metadata.get("derived_from_source")
    return (
        candidate.source == "raw_message_span"
        and isinstance(parent_source, str)
        and parent_source in enabled_sources
    )


def candidate_is_relevant(
    candidate: MemoryCandidate,
    policy: SelectorPolicy,
) -> bool:
    breakdown = candidate.metadata.get("score_breakdown", {})
    features = breakdown.get("features", {}) if isinstance(breakdown, dict) else {}
    lexical = float(features.get("lexical_overlap", 0.0) or 0.0)
    source_boost = float(features.get("query_source_boost", 0.0) or 0.0)
    return (
        lexical > 0.0
        or source_boost > 0.0
        or float(candidate.score or 0.0) >= policy.minimum_required_score
    )


def scope_matches(candidate: MemoryCandidate) -> set[str]:
    mapping = {
        "document_memory": {"document"},
        "current_chat_span": {"current_chat"},
        "recent_messages": {"current_chat"},
        "raw_message_span": {"previous_chat"},
        "previous_chat_gist": {"previous_chat"},
        "structured_memory": {"durable"},
    }
    return mapping.get(candidate.source, set())


def spans_overlap(first: MemoryCandidate, second: MemoryCandidate) -> float:
    if first.source not in RAW_SOURCES or second.source not in RAW_SOURCES:
        return 0.0
    first_ids = set(first.source_message_ids)
    second_ids = set(second.source_message_ids)
    if not first_ids or not second_ids:
        return 0.0
    return len(first_ids & second_ids) / min(len(first_ids), len(second_ids))


def should_fold_overlapping_span(
    keeper: MemoryCandidate,
    candidate: MemoryCandidate,
    *,
    threshold: float,
) -> bool:
    overlap = spans_overlap(keeper, candidate)
    if overlap < threshold:
        return False
    unique_ids = set(candidate.source_message_ids) - set(keeper.source_message_ids)
    anchors = set(
        integer_list(
            candidate.metadata.get("anchor_message_ids")
            or candidate.metadata.get("matched_message_ids")
        )
    )
    return not (anchors & unique_ids)


def merge_retrieval_paths(
    keeper: MemoryCandidate,
    duplicate: MemoryCandidate,
) -> None:
    paths: list[str] = []
    for candidate in (keeper, duplicate):
        values = candidate.metadata.get("retrieval_paths")
        if isinstance(values, list):
            paths.extend(str(value) for value in values)
        path = candidate.metadata.get("retrieval_path")
        if isinstance(path, str):
            paths.append(path)
    merged = list(dict.fromkeys(paths))
    if merged:
        keeper.metadata["retrieval_paths"] = merged
        keeper.metadata["retrieval_path"] = merged[0] if len(merged) == 1 else "multiple"


def global_summary_selection_order(
    candidates: list[MemoryCandidate],
    *,
    annotation_by_object: dict[int, CandidateAnnotation],
    available_tokens: int,
) -> list[MemoryCandidate]:
    gists = sorted(
        (candidate for candidate in candidates if candidate.source in GIST_SOURCES),
        key=lambda item: global_summary_chronological_key(
            item,
            annotation_by_object[id(item)].rank,
        ),
    )
    raw = sorted(
        (candidate for candidate in candidates if candidate.source in RAW_SOURCES),
        key=lambda item: global_summary_chronological_key(
            item,
            annotation_by_object[id(item)].rank,
        ),
    )
    other = sorted(
        (
            candidate
            for candidate in candidates
            if candidate.source not in GIST_SOURCES | RAW_SOURCES
        ),
        key=lambda item: annotation_by_object[id(item)].rank,
    )
    gist_tokens = sum(annotation_by_object[id(item)].token_cost for item in gists)
    raw_tokens = sum(annotation_by_object[id(item)].token_cost for item in raw)
    if gist_tokens + raw_tokens <= available_tokens:
        return [*gists, *raw, *other]
    raw_coverage = [raw[index] for index in timeline_coverage_order(len(raw))]
    return [*gists, *raw_coverage, *other]


def timeline_coverage_order(count: int) -> list[int]:
    if count <= 0:
        return []
    selected = [0]
    if count > 1:
        selected.append(count - 1)
    if count > 2:
        selected.append(count // 2)
    remaining = [index for index in range(count) if index not in selected]
    while remaining:
        next_index = max(
            remaining,
            key=lambda index: (
                min(abs(index - chosen) for chosen in selected),
                -index,
            ),
        )
        selected.append(next_index)
        remaining.remove(next_index)
    return selected


def global_summary_chronological_key(
    candidate: MemoryCandidate,
    rank: int,
) -> tuple[int, str, int, int]:
    source_group = 0 if candidate.source in GIST_SOURCES else 1
    return (
        source_group,
        str(candidate.metadata.get("created_at") or candidate.chat_id or ""),
        int(
            candidate.metadata.get("timeline_index")
            or candidate.metadata.get("start_message_id")
            or 0
        ),
        rank,
    )


def selected_time_range_count(
    candidates: Sequence[MemoryCandidate],
) -> int:
    """Count disjoint selected raw-message ranges across source chats."""
    ranges_by_chat: dict[str, list[tuple[int, int]]] = {}
    unbounded = 0
    for candidate in candidates:
        if candidate.source not in RAW_SOURCES:
            continue
        message_ids = sorted(set(candidate.source_message_ids))
        if not message_ids:
            unbounded += 1
            continue
        chat_key = str(candidate.metadata.get("source_chat_id") or candidate.chat_id or "")
        ranges_by_chat.setdefault(chat_key, []).append((message_ids[0], message_ids[-1]))
    return unbounded + sum(len(merge_ranges(ranges)) for ranges in ranges_by_chat.values())


def merge_ranges(
    ranges: Sequence[tuple[int, int]],
) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if not merged or start > merged[-1][1] + 1:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return merged


def is_latest_query_candidate(
    candidate: MemoryCandidate,
    latest_user_message: dict[str, str] | None,
    route_query: str,
) -> bool:
    expected = (
        latest_user_message.get("content", "") if latest_user_message is not None else route_query
    )
    return str(candidate.metadata.get("role", "user")) == "user" and candidate.content == expected


def drop_record(
    candidate: MemoryCandidate,
    annotation: CandidateAnnotation,
    *,
    reason: str,
    **metadata: object,
) -> dict[str, Any]:
    return {
        "record_id": candidate.record_id,
        "candidate_id": annotation.candidate_id,
        "trace_id": annotation.trace_id,
        "source": candidate.source,
        "reason": reason,
        "estimated_tokens": annotation.token_cost,
        **metadata,
    }


def candidate_trace_id(candidate: MemoryCandidate, rank: int) -> str:
    record = candidate.record_id if candidate.record_id is not None else "none"
    return f"{candidate.source}:{record}:r{rank}"


def required_utility(candidate: MemoryCandidate) -> float:
    return 1.0 + float(candidate.score or 0.0)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def integer_list(value: object) -> list[int]:
    if not isinstance(value, list | tuple | set):
        return []
    return [int(item) for item in value if isinstance(item, int)]


def string_or_none(value: object) -> str | None:
    return str(value) if value is not None else None
