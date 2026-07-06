from __future__ import annotations

import pytest

from src.core.contracts import RoutePlan
from src.routing.retrieval_query import (
    retrieval_query_for_reranking,
    simplify_retrieval_query,
)


def test_entity_age_comparison_is_compact_and_preserves_direction() -> None:
    result = simplify_retrieval_query(
        "Based on all the information above, who is older, "
        "Annie Morton or Terry Richardson?"
    )

    assert result.retrieval_query == (
        "Annie Morton age born Terry Richardson age born older"
    )
    assert result.reason == "entity_age_comparison"


@pytest.mark.parametrize(
    "query",
    (
        "Who founded Acme Labs?",
        "Who led Acme Labs on 14 March 2024?",
        "Which person did not lead Acme Labs?",
        'What did I call "Project Cobalt"?',
        "Choose one:\nA. Alpha\nB. Beta",
    ),
)
def test_unsafe_or_already_compact_queries_fall_back_to_original(query: str) -> None:
    result = simplify_retrieval_query(query)

    assert result.retrieval_query == " ".join(query.strip().split())
    assert result.applied is False


def test_global_summary_query_retains_scope() -> None:
    result = simplify_retrieval_query(
        "Now summarize the book.",
        context_profile="global_summary",
    )

    assert result.retrieval_query == (
        "global summary complete book chronological content"
    )
    assert result.applied is True


def test_long_boilerplate_is_removed_deterministically() -> None:
    query = (
        "Based on all the information above, which university educated "
        "Joan Didion?"
    )

    first = simplify_retrieval_query(query)
    second = simplify_retrieval_query(query)

    assert first == second
    assert first.retrieval_query == "which university educated Joan Didion?"


def test_capitalized_comparison_is_simplified_for_birth_date_retrieval() -> None:
    result = simplify_retrieval_query(
        "Who is older, Annie Morton or Terry Richardson?"
    )

    assert result.applied is True
    assert result.retrieval_query == (
        "Annie Morton age born Terry Richardson age born older"
    )


def test_reranking_uses_retrieval_query_without_mutating_original_query() -> None:
    route_plan = RoutePlan(
        query="Who is older, Annie Morton or Terry Richardson?",
        metadata={
            "retrieval_query": (
                "Annie Morton age born Terry Richardson age born older"
            )
        },
    )

    assert retrieval_query_for_reranking(
        route_plan,
        fallback=route_plan.query,
    ) == "Annie Morton age born Terry Richardson age born older"
    assert route_plan.query == "Who is older, Annie Morton or Terry Richardson?"
