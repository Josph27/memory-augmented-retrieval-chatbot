from __future__ import annotations

from src.core.contracts import MemoryCandidate, SourcePlan


class PreviousChatRetriever:
    """Placeholder for future long-term previous-chat retrieval."""

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        del chat_id, source_plan
        return []
