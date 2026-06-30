"""Query decomposition: splits complex queries into independent sub-queries."""

from __future__ import annotations

import json

from src.core.contracts import SubQuery
from src.model_wrapper import ModelWrapper

MAX_SUB_QUERIES = 3


class QueryDecomposer:
    """LLM-backed sub-query decomposition with deterministic fallback."""

    def __init__(self, model: ModelWrapper) -> None:
        self._model = model

    def decompose(self, query: str) -> list[SubQuery]:
        """Split a query into 1..N independent sub-queries."""
        if len(query.strip()) < 5:
            return [SubQuery(text=query.strip())]

        try:
            return self._llm_decompose(query)
        except (json.JSONDecodeError, ValueError, OSError):
            return [SubQuery(text=query.strip())]

    def _llm_decompose(self, query: str) -> list[SubQuery]:
        """Use the model to decompose, validate, and return sub-queries."""
        prompt = (
            "You are a query analyzer. Break the user query into 1-3 independent "
            "sub-queries that can be answered separately. Each sub-query should be "
            "self-contained.\n\n"
            "Return ONLY a JSON array of strings, nothing else.\n"
            "Example: ['sub-query 1', 'sub-query 2']\n\n"
            f"Query: {query}\n"
        )
        response = self._model.chat(
            [{"role": "user", "content": prompt}],
            temperature=0,
        )
        try:
            parsed = json.loads(response.strip().strip("`"))
        except json.JSONDecodeError:
            return [SubQuery(text=query.strip())]
        if isinstance(parsed, list):
            sub_queries = [
                SubQuery(text=str(item).strip())
                for item in parsed[:MAX_SUB_QUERIES]
                if isinstance(item, str) and item.strip()
            ]
            if sub_queries:
                return sub_queries
        return [SubQuery(text=query.strip())]
