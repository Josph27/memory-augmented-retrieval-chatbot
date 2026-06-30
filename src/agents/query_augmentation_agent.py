"""Query augmentation agent: decomposes and expands queries for retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.contracts import SubQuery
from src.routing.query_decomposer import QueryDecomposer
from src.routing.semantic_expander import SemanticExpander


@dataclass(frozen=True)
class AugmentedQuery:
    """Result of query augmentation: decomposed sub-queries with expanded text."""

    sub_queries: list[SubQuery] = field(default_factory=list)
    original: str = ""


class QueryAugmentationAgent:
    """Wraps QueryDecomposer + SemanticExpander for retrieval enhancement."""

    def __init__(self, decomposer: QueryDecomposer, expander: SemanticExpander) -> None:
        self._decomposer = decomposer
        self._expander = expander

    def augment(self, query: str) -> AugmentedQuery:
        """Decompose, expand each sub-query, return AugmentedQuery."""
        sub_queries = self._decomposer.decompose(query)
        expanded_queries = [
            SubQuery(
                text=self._expander.expand(sq),
                intent=sq.intent,
                sources=sq.sources,
            )
            for sq in sub_queries
        ]
        return AugmentedQuery(sub_queries=expanded_queries, original=query)
