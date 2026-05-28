from __future__ import annotations

from src.core.contracts import MemoryCandidate, SourcePlan


class DocumentRetriever:
    """Placeholder for future document retrieval."""

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        del chat_id, source_plan
        return []
