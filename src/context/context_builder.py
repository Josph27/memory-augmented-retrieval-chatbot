from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.context.token_estimator import ApproximateTokenEstimator, TokenEstimator
from src.core.contracts import ContextBudget, ContextPacket, MemoryCandidate, RoutePlan


CONTEXT_SOURCE_ORDER = (
    "structured_memory",
    "current_chat_gist",
    "previous_chat_gist",
    "document_memory",
    "raw_message_span",
    # Backward-compatible aliases for older route plans/tests.
    "current_chat_chunks",
    "previous_chat_memory",
    "recent_messages",
)

DROPPABLE_OVERFLOW_SOURCES = (
    "structured_memory",
    "current_chat_gist",
    "previous_chat_gist",
    "document_memory",
    "raw_message_span",
    "current_chat_chunks",
    "previous_chat_memory",
)


@dataclass(frozen=True)
class SelectedContext:
    """Selected and dropped candidates for one source."""

    selected: list[MemoryCandidate]
    dropped: list[dict[str, Any]]
    used_tokens: int


class ContextBuilder:
    """Build a trace-only context packet from ranked candidates and budgets."""

    def __init__(
        self,
        token_estimator: TokenEstimator | None = None,
        placement_mode: str = "budget_fitting",
    ) -> None:
        self.token_estimator = token_estimator or ApproximateTokenEstimator()
        self.placement_mode = placement_mode

    def build(
        self,
        system_prompt: str,
        latest_user_message: dict[str, str],
        ranked_candidates: list[MemoryCandidate],
        context_budget: ContextBudget,
        route_plan: RoutePlan,
    ) -> ContextPacket:
        """Build a ContextPacket; dispatch to ordered or budget-fitting strategy."""
        if self.placement_mode == "ordered":
            return self._build_ordered(
                system_prompt=system_prompt,
                latest_user_message=latest_user_message,
                ranked_candidates=ranked_candidates,
                context_budget=context_budget,
                route_plan=route_plan,
            )
        return self._build_budget_fitting(
            system_prompt=system_prompt,
            latest_user_message=latest_user_message,
            ranked_candidates=ranked_candidates,
            context_budget=context_budget,
            route_plan=route_plan,
        )

    def _build_budget_fitting(
        self,
        system_prompt: str,
        latest_user_message: dict[str, str],
        ranked_candidates: list[MemoryCandidate],
        context_budget: ContextBudget,
        route_plan: RoutePlan,
    ) -> ContextPacket:
        """Build a budget-aware ContextPacket without affecting the model call."""
        grouped = group_candidates_by_source(ranked_candidates)
        selected_by_source: dict[str, SelectedContext] = {}
        selected_candidates: list[MemoryCandidate] = []
        dropped_candidates: list[dict[str, Any]] = []

        for source in CONTEXT_SOURCE_ORDER:
            source_candidates = grouped.get(source, [])
            if source == "recent_messages":
                source_candidates, latest_drops = prepare_recent_candidates(
                    source_candidates,
                    latest_user_message,
                )
                dropped_candidates.extend(latest_drops)

            selected = self.select_for_source(
                source=source,
                candidates=source_candidates,
                budget=context_budget.source_token_budgets.get(source, 0),
            )
            selected_by_source[source] = selected
            selected_candidates.extend(selected.selected)
            dropped_candidates.extend(selected.dropped)

        overflow_drops = self.drop_non_recent_candidates_for_overflow(
            selected_by_source=selected_by_source,
            context_budget=context_budget,
            system_prompt=system_prompt,
            latest_user_message=latest_user_message,
        )
        dropped_candidates.extend(overflow_drops)
        selected_candidates = [
            candidate
            for source in CONTEXT_SOURCE_ORDER
            for candidate in selected_by_source[source].selected
        ]

        model_messages = self.build_trace_messages(
            system_prompt=system_prompt,
            selected_by_source=selected_by_source,
            latest_user_message=latest_user_message,
        )
        token_accounting = self.build_token_accounting(
            system_prompt=system_prompt,
            selected_by_source=selected_by_source,
            latest_user_message=latest_user_message,
            model_messages=model_messages,
            context_budget=context_budget,
        )
        estimated_tokens = token_accounting["total_prompt_tokens"]
        dropped_candidate_ids = [
            item["record_id"] for item in dropped_candidates if item.get("record_id") is not None
        ]
        return ContextPacket(
            chat_id=first_chat_id(ranked_candidates),
            system_prompt=system_prompt,
            structured_memory=format_source_section(
                "structured_memory",
                selected_by_source["structured_memory"].selected,
            ),
            recent_message_ids=[
                source_id
                for candidate in selected_by_source["recent_messages"].selected
                for source_id in candidate.source_message_ids
            ],
            candidates=selected_candidates,
            budget=context_budget,
            model_messages=model_messages,
            metadata={
                "trace_only": True,
                "route_intent": route_plan.intent,
                "context_profile": context_budget.metadata.get("context_profile"),
                "estimated_token_usage": estimated_tokens,
                "estimated_prompt_tokens": estimated_tokens,
                "token_estimator": "approximate",
                "context_limit": token_accounting["context_limit"],
                "answer_reserve": token_accounting["answer_reserve"],
                "safety_margin": token_accounting["safety_margin"],
                "overflow_detected": token_accounting["overflow_detected"],
                "overflow_tokens": token_accounting["overflow_tokens"],
                "token_accounting": token_accounting,
                "source_token_usage": {
                    source: selected.used_tokens for source, selected in selected_by_source.items()
                },
                "dropped_candidates": dropped_candidates,
                "dropped_candidate_ids": dropped_candidate_ids,
                "dropped_candidate_reasons": [
                    {
                        "record_id": item.get("record_id"),
                        "source": item.get("source"),
                        "reason": item.get("reason"),
                    }
                    for item in dropped_candidates
                ],
                "section_order": [
                    "system",
                    "structured_memory",
                    "retrieved_memory",
                    "recent_messages",
                    "latest_user_message",
                ],
            },
        )

    def _build_ordered(
        self,
        system_prompt: str,
        latest_user_message: dict[str, str],
        ranked_candidates: list[MemoryCandidate],
        context_budget: ContextBudget,
        route_plan: RoutePlan,
    ) -> ContextPacket:
        """Build with 'lost in the middle' placement: docs(hi→lo), mem(lo→hi), recent, query."""
        grouped = group_candidates_by_source(ranked_candidates)
        dropped_candidates: list[dict[str, Any]] = []

        # --- system prompt ---
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        # --- document_memory: hi→lo score ---
        doc_candidates = sorted(
            grouped.get("document_memory", []),
            key=lambda c: c.score or 0.0,
            reverse=True,
        )
        selected_docs, doc_drops = self._fit_ordered(
            candidates=doc_candidates,
            budget=context_budget.source_token_budgets.get("document_memory", 0),
            reason="ordered_budget_exceeded",
        )
        dropped_candidates.extend(doc_drops)
        doc_section = format_source_section("document_memory", selected_docs)
        if doc_section:
            messages.append({"role": "system", "content": doc_section})

        # --- structured_memory + gists: lo→hi score (middle — trim first on overflow) ---
        mid_candidates: list[MemoryCandidate] = []
        for source in (
            "structured_memory",
            "current_chat_gist",
            "previous_chat_gist",
            "raw_message_span",
            "current_chat_chunks",
            "previous_chat_memory",
        ):
            mid_candidates.extend(grouped.get(source, []))
        mid_candidates.sort(key=lambda c: c.score or 0.0)  # lo→hi
        mid_budget = sum(
            context_budget.source_token_budgets.get(source, 0)
            for source in (
                "structured_memory",
                "current_chat_gist",
                "previous_chat_gist",
                "raw_message_span",
                "current_chat_chunks",
                "previous_chat_memory",
            )
        )
        selected_mid, mid_drops = self._fit_ordered(
            candidates=mid_candidates,
            budget=mid_budget,
            reason="ordered_budget_exceeded",
        )
        dropped_candidates.extend(mid_drops)
        mid_section = "\n\n".join(
            section
            for section in (
                format_source_section(
                    "structured_memory",
                    [c for c in selected_mid if c.source == "structured_memory"],
                ),
                format_source_section(
                    "current_chat_gist",
                    [
                        c
                        for c in selected_mid
                        if c.source in ("current_chat_gist", "current_chat_chunks")
                    ],
                ),
                format_source_section(
                    "previous_chat_gist",
                    [
                        c
                        for c in selected_mid
                        if c.source in ("previous_chat_gist", "previous_chat_memory")
                    ],
                ),
                format_source_section(
                    "raw_message_span", [c for c in selected_mid if c.source == "raw_message_span"]
                ),
            )
            if section
        )
        if mid_section:
            messages.append({"role": "system", "content": mid_section})

        # --- recent messages (chronological, then latest user message) ---
        recent_raw = grouped.get("recent_messages", [])
        recent_candidates, recent_drops = prepare_recent_candidates(
            recent_raw,
            latest_user_message,
        )
        dropped_candidates.extend(recent_drops)
        recent_selected, recent_over_drops = self._fit_ordered(
            candidates=recent_candidates,
            budget=context_budget.source_token_budgets.get("recent_messages", 0),
            reason="ordered_budget_exceeded",
        )
        dropped_candidates.extend(recent_over_drops)
        messages.extend(format_recent_message(candidate) for candidate in recent_selected)
        messages.append(latest_user_message)

        # --- overflow trim from middle ---
        overflow_drops = self._drop_mid_for_ordered_overflow(
            messages=messages,
            system_prompt=system_prompt,
            latest_user_message=latest_user_message,
            mid_candidates=selected_mid,
            context_budget=context_budget,
        )
        dropped_candidates.extend(overflow_drops)
        # Re-filter middle after overflow drops
        kept_mid = [
            c
            for c in selected_mid
            if c not in {d["_candidate"] for d in overflow_drops if d.get("_candidate")}
        ]
        selected_candidates = selected_docs + kept_mid + recent_selected

        token_accounting = self.build_token_accounting(
            system_prompt=system_prompt,
            selected_by_source={
                "document_memory": SelectedContext(
                    selected=selected_docs,
                    dropped=[],
                    used_tokens=0,
                ),
                "structured_memory": SelectedContext(
                    selected=[c for c in kept_mid if c.source == "structured_memory"],
                    dropped=[],
                    used_tokens=0,
                ),
                "current_chat_gist": SelectedContext(
                    selected=[
                        c
                        for c in kept_mid
                        if c.source in ("current_chat_gist", "current_chat_chunks")
                    ],
                    dropped=[],
                    used_tokens=0,
                ),
                "previous_chat_gist": SelectedContext(
                    selected=[
                        c
                        for c in kept_mid
                        if c.source in ("previous_chat_gist", "previous_chat_memory")
                    ],
                    dropped=[],
                    used_tokens=0,
                ),
                "raw_message_span": SelectedContext(
                    selected=[c for c in kept_mid if c.source == "raw_message_span"],
                    dropped=[],
                    used_tokens=0,
                ),
                "current_chat_chunks": SelectedContext(selected=[], dropped=[], used_tokens=0),
                "previous_chat_memory": SelectedContext(selected=[], dropped=[], used_tokens=0),
                "recent_messages": SelectedContext(
                    selected=recent_selected,
                    dropped=[],
                    used_tokens=0,
                ),
            },
            latest_user_message=latest_user_message,
            model_messages=messages,
            context_budget=context_budget,
        )
        estimated_tokens = token_accounting["total_prompt_tokens"]
        dropped_candidate_ids = [
            item["record_id"] for item in dropped_candidates if item.get("record_id") is not None
        ]
        return ContextPacket(
            chat_id=first_chat_id(ranked_candidates),
            system_prompt=system_prompt,
            structured_memory=format_source_section(
                "structured_memory",
                [c for c in kept_mid if c.source == "structured_memory"],
            ),
            recent_message_ids=[
                source_id
                for candidate in recent_selected
                for source_id in candidate.source_message_ids
            ],
            candidates=selected_candidates,
            budget=context_budget,
            model_messages=messages,
            metadata={
                "trace_only": True,
                "placement_mode": "ordered",
                "route_intent": route_plan.intent,
                "context_profile": context_budget.metadata.get("context_profile"),
                "estimated_token_usage": estimated_tokens,
                "estimated_prompt_tokens": estimated_tokens,
                "token_estimator": "approximate",
                "context_limit": token_accounting["context_limit"],
                "answer_reserve": token_accounting["answer_reserve"],
                "safety_margin": token_accounting["safety_margin"],
                "overflow_detected": token_accounting["overflow_detected"],
                "overflow_tokens": token_accounting["overflow_tokens"],
                "token_accounting": token_accounting,
                "dropped_candidates": dropped_candidates,
                "dropped_candidate_ids": dropped_candidate_ids,
                "dropped_candidate_reasons": [
                    {
                        "record_id": item.get("record_id"),
                        "source": item.get("source"),
                        "reason": item.get("reason"),
                    }
                    for item in dropped_candidates
                ],
                "section_order": [
                    "system",
                    "document_memory",
                    "mid_memory",
                    "recent_messages",
                    "latest_user_message",
                ],
            },
        )

    def _fit_ordered(
        self,
        candidates: list[MemoryCandidate],
        budget: int,
        reason: str,
    ) -> tuple[list[MemoryCandidate], list[dict[str, Any]]]:
        """Fit candidates into a token budget, preserving caller's sort order."""
        selected: list[MemoryCandidate] = []
        dropped: list[dict[str, Any]] = []
        used = 0
        for candidate in candidates:
            tokens = self.token_estimator.estimate_text(candidate.content)
            if budget <= 0 or used + tokens <= budget:
                selected.append(candidate)
                used += tokens
            else:
                dropped.append(
                    {
                        "record_id": candidate.record_id,
                        "source": candidate.source,
                        "reason": reason,
                        "estimated_tokens": tokens,
                        "source_budget": budget,
                    }
                )
        return selected, dropped

    def _drop_mid_for_ordered_overflow(
        self,
        messages: list[dict[str, str]],
        system_prompt: str,
        latest_user_message: dict[str, str],
        mid_candidates: list[MemoryCandidate],
        context_budget: ContextBudget,
    ) -> list[dict[str, Any]]:
        """Drop memory candidates from the middle when ordered prompt overflows."""
        dropped: list[dict[str, Any]] = []
        limit = context_budget.max_tokens or 0
        reserve = context_budget.reserved_response_tokens or 0
        safety = int(context_budget.metadata.get("safety_margin_tokens", 0) or 0)
        if limit <= 0:
            return dropped
        while True:
            total = self.token_estimator.estimate_messages(messages)
            if total + reserve + safety <= limit:
                return dropped
            if not mid_candidates:
                return dropped
            # Remove from middle: drop the first (lowest-score) mid candidate
            drop_candidate = mid_candidates.pop(0)
            drop_content = format_source_section(drop_candidate.source, [drop_candidate])
            # Remove its contribution from messages
            messages = [
                m
                for m in messages
                if not (
                    m.get("role") == "system"
                    and drop_content
                    and drop_content in m.get("content", "")
                )
            ]
            dropped.append(
                {
                    "record_id": drop_candidate.record_id,
                    "source": drop_candidate.source,
                    "reason": "ordered_overflow_mid_trim",
                    "estimated_tokens": self.token_estimator.estimate_text(drop_candidate.content),
                    "_candidate": drop_candidate,
                }
            )
            if not messages:
                return dropped

    def select_for_source(
        self,
        source: str,
        candidates: list[MemoryCandidate],
        budget: int,
    ) -> SelectedContext:
        """Select highest-ranked candidates that fit in one source budget."""
        selected: list[MemoryCandidate] = []
        dropped: list[dict[str, Any]] = []
        used_tokens = 0
        for candidate in candidates:
            candidate_tokens = self.token_estimator.estimate_text(candidate.content)
            if candidate_tokens + used_tokens <= budget:
                selected.append(candidate)
                used_tokens += candidate_tokens
                continue

            dropped.append(
                {
                    "record_id": candidate.record_id,
                    "source": candidate.source,
                    "reason": "source_budget_exceeded",
                    "estimated_tokens": candidate_tokens,
                    "source_budget": budget,
                }
            )
        return SelectedContext(selected=selected, dropped=dropped, used_tokens=used_tokens)

    def build_trace_messages(
        self,
        system_prompt: str,
        selected_by_source: dict[str, SelectedContext],
        latest_user_message: dict[str, str],
    ) -> list[dict[str, str]]:
        """Create trace-only model-shaped messages in the target ordering."""
        messages = [{"role": "system", "content": system_prompt}]
        structured_memory = format_source_section(
            "structured_memory",
            selected_by_source["structured_memory"].selected,
        )
        if structured_memory:
            messages.append({"role": "system", "content": structured_memory})

        retrieved_memory = "\n\n".join(
            section
            for section in (
                format_source_section(
                    "current_chat_gist",
                    selected_by_source["current_chat_gist"].selected,
                ),
                format_source_section(
                    "previous_chat_gist",
                    selected_by_source["previous_chat_gist"].selected,
                ),
                format_source_section(
                    "document_memory",
                    selected_by_source["document_memory"].selected,
                ),
                format_source_section(
                    "raw_message_span",
                    selected_by_source["raw_message_span"].selected,
                ),
                format_source_section(
                    "current_chat_chunks",
                    selected_by_source["current_chat_chunks"].selected,
                ),
                format_source_section(
                    "previous_chat_memory",
                    selected_by_source["previous_chat_memory"].selected,
                ),
            )
            if section
        )
        if retrieved_memory:
            messages.append({"role": "system", "content": retrieved_memory})

        recent_messages = selected_by_source["recent_messages"].selected
        messages.extend(format_recent_message(candidate) for candidate in recent_messages)
        messages.append(latest_user_message)
        return messages

    def drop_non_recent_candidates_for_overflow(
        self,
        selected_by_source: dict[str, SelectedContext],
        context_budget: ContextBudget,
        system_prompt: str,
        latest_user_message: dict[str, str],
    ) -> list[dict[str, Any]]:
        """Drop lowest-ranked non-recent candidates if the whole prompt overflows."""
        dropped: list[dict[str, Any]] = []
        while True:
            model_messages = self.build_trace_messages(
                system_prompt=system_prompt,
                selected_by_source=selected_by_source,
                latest_user_message=latest_user_message,
            )
            accounting = self.build_token_accounting(
                system_prompt=system_prompt,
                selected_by_source=selected_by_source,
                latest_user_message=latest_user_message,
                model_messages=model_messages,
                context_budget=context_budget,
            )
            if not accounting["overflow_detected"]:
                return dropped

            next_drop = lowest_ranked_non_recent_candidate(selected_by_source)
            if next_drop is None:
                return dropped

            source, candidate = next_drop
            selected = selected_by_source[source]
            candidate_tokens = self.token_estimator.estimate_text(candidate.content)
            selected.selected.remove(candidate)
            selected_by_source[source] = SelectedContext(
                selected=selected.selected,
                dropped=selected.dropped,
                used_tokens=max(0, selected.used_tokens - candidate_tokens),
            )
            dropped.append(
                {
                    "record_id": candidate.record_id,
                    "source": candidate.source,
                    "reason": "context_overflow",
                    "estimated_tokens": candidate_tokens,
                    "overflow_tokens_before_drop": accounting["overflow_tokens"],
                }
            )

    def build_token_accounting(
        self,
        system_prompt: str,
        selected_by_source: dict[str, SelectedContext],
        latest_user_message: dict[str, str],
        model_messages: list[dict[str, str]],
        context_budget: ContextBudget,
    ) -> dict[str, Any]:
        """Estimate token usage for each prompt section and overflow metadata."""
        structured_memory = format_source_section(
            "structured_memory",
            selected_by_source["structured_memory"].selected,
        )
        retrieved_sections = {
            source: format_source_section(source, selected_by_source[source].selected)
            for source in (
                "current_chat_gist",
                "previous_chat_gist",
                "document_memory",
                "raw_message_span",
                "current_chat_chunks",
                "previous_chat_memory",
            )
        }
        recent_messages = [
            format_recent_message(candidate)
            for candidate in selected_by_source["recent_messages"].selected
        ]
        recent_message_tokens = self.token_estimator.estimate_messages(recent_messages)
        latest_user_message_tokens = self.token_estimator.estimate_messages([latest_user_message])
        source_memory_tokens = {
            source: self.token_estimator.estimate_text(section)
            for source, section in retrieved_sections.items()
        }
        retrieved_memory_tokens = sum(source_memory_tokens.values())
        total_prompt_tokens = self.token_estimator.estimate_messages(model_messages)
        answer_reserve = context_budget.reserved_response_tokens or 0
        safety_margin = int(context_budget.metadata.get("safety_margin_tokens", 0) or 0)
        context_limit = context_budget.max_tokens or 0
        total_with_reserves = total_prompt_tokens + answer_reserve + safety_margin
        overflow_tokens = max(0, total_with_reserves - context_limit) if context_limit > 0 else 0
        estimator_info = estimator_metadata(self.token_estimator)
        return {
            "token_estimator": estimator_info,
            "system_tokens": self.token_estimator.estimate_text(system_prompt),
            "structured_memory_tokens": self.token_estimator.estimate_text(structured_memory),
            "retrieved_memory_tokens": retrieved_memory_tokens,
            "source_memory_tokens": source_memory_tokens,
            "recent_message_tokens": recent_message_tokens,
            "latest_user_message_tokens": latest_user_message_tokens,
            "total_prompt_tokens": total_prompt_tokens,
            "answer_reserve": answer_reserve,
            "safety_margin": safety_margin,
            "context_limit": context_limit,
            "total_with_reserves": total_with_reserves,
            "overflow_detected": overflow_tokens > 0,
            "overflow_tokens": overflow_tokens,
        }


def group_candidates_by_source(
    candidates: list[MemoryCandidate],
) -> dict[str, list[MemoryCandidate]]:
    """Group ranked candidates by source while preserving rank order."""
    grouped: dict[str, list[MemoryCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.source, []).append(candidate)
    return grouped


def prepare_recent_candidates(
    candidates: list[MemoryCandidate],
    latest_user_message: dict[str, str],
) -> tuple[list[MemoryCandidate], list[dict[str, Any]]]:
    """Exclude the latest user query and sort recent messages chronologically."""
    kept: list[MemoryCandidate] = []
    dropped: list[dict[str, Any]] = []
    for candidate in candidates:
        if is_latest_user_candidate(candidate, latest_user_message):
            dropped.append(
                {
                    "record_id": candidate.record_id,
                    "source": candidate.source,
                    "reason": "latest_user_message_excluded",
                    "estimated_tokens": 0,
                    "source_budget": None,
                }
            )
            continue
        kept.append(candidate)

    return sorted(kept, key=recent_message_sort_key), dropped


def is_latest_user_candidate(
    candidate: MemoryCandidate,
    latest_user_message: dict[str, str],
) -> bool:
    """Return whether a recent candidate is the current user query."""
    return (
        candidate.source == "recent_messages"
        and str(candidate.metadata.get("role", "user")) == latest_user_message.get("role")
        and candidate.content == latest_user_message.get("content")
    )


def recent_message_sort_key(candidate: MemoryCandidate) -> tuple[int, str, int]:
    """Sort recent raw messages by persisted order instead of reranker score."""
    source_ids = [source_id for source_id in candidate.source_message_ids if source_id >= 0]
    if source_ids:
        return (min(source_ids), "", 0)

    if isinstance(candidate.record_id, int):
        return (candidate.record_id, "", 0)

    created_at = str(candidate.metadata.get("created_at", ""))
    order = candidate.metadata.get("order")
    if not isinstance(order, int):
        order = 0
    return (10**12, created_at, order)


def format_source_section(source: str, candidates: list[MemoryCandidate]) -> str:
    """Format non-recent candidates into a section."""
    if not candidates:
        return ""

    if source == "structured_memory":
        lines = ["Current structured memory:"]
        for candidate in candidates:
            category = candidate.metadata.get("category")
            key = candidate.metadata.get("key")
            if category and key:
                lines.append(f"- {category}.{key}: {candidate.content}")
            else:
                label = candidate.record_id if candidate.record_id is not None else "candidate"
                lines.append(f"- [{label}] {candidate.content}")
        return "\n".join(lines)

    title = source.replace("_", " ").title()
    lines = [f"{title}:"]
    for candidate in candidates:
        label = candidate.record_id if candidate.record_id is not None else "candidate"
        lines.append(f"- [{label}] {candidate.content}")
    return "\n".join(lines)


def format_recent_message(candidate: MemoryCandidate) -> dict[str, str]:
    """Convert a recent-message candidate back to a chat-shaped message."""
    role = str(candidate.metadata.get("role", "user"))
    return {"role": role, "content": candidate.content}


def lowest_ranked_non_recent_candidate(
    selected_by_source: dict[str, SelectedContext],
) -> tuple[str, MemoryCandidate] | None:
    """Return the lowest-scored selected non-recent candidate."""
    candidates: list[tuple[float, str, MemoryCandidate]] = []
    for source in DROPPABLE_OVERFLOW_SOURCES:
        selected = selected_by_source[source].selected
        if not selected:
            continue
        candidate = selected[-1]
        candidates.append((candidate.score or 0.0, source, candidate))
    if not candidates:
        return None
    _, source, candidate = min(candidates, key=lambda item: item[0])
    return source, candidate


def estimator_metadata(token_estimator: TokenEstimator) -> dict[str, Any]:
    """Return debug metadata for the estimator without requiring a concrete class."""
    info_method = getattr(token_estimator, "info", None)
    if callable(info_method):
        info = info_method()
        return {
            "backend": getattr(info, "backend", None),
            "model_name": getattr(info, "model_name", None),
            "approximate": getattr(info, "approximate", None),
        }
    return {
        "backend": getattr(token_estimator, "backend", "unknown"),
        "model_name": getattr(token_estimator, "model_name", None),
        "approximate": None,
    }


def first_chat_id(candidates: list[MemoryCandidate]) -> str:
    """Return the first available chat id for the packet."""
    for candidate in candidates:
        if candidate.chat_id:
            return candidate.chat_id
    return ""
