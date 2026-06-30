"""Semantic query expansion: injects relevant keywords into sub-queries."""

from __future__ import annotations

from src.core.contracts import SubQuery
from src.model_wrapper import ModelWrapper


EXPANSION_PROMPT = (
    "Add up to 5 relevant search keywords to the following query to improve retrieval. "
    "Return only the expanded query text, nothing else.\n\n"
    "Query: {query}\n"
    "Expanded:"
)


class SemanticExpander:
    """LLM-prompt-based keyword injection. No dictionaries."""

    def __init__(self, model: ModelWrapper) -> None:
        self._model = model

    def expand(self, sub_query: SubQuery) -> str:
        """Inject up to 5 relevant keywords into the sub-query text."""
        try:
            response = self._model.chat(
                [{"role": "user", "content": EXPANSION_PROMPT.format(query=sub_query.text)}],
                temperature=0,
            )
            expanded = response.strip()
            if expanded and len(expanded) > len(sub_query.text):
                return expanded
            return sub_query.text
        except Exception:
            return sub_query.text
