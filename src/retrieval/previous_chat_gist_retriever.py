from __future__ import annotations

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database
from src.retrieval.current_chat_gist_retriever import (
    gist_matches_query,
    gist_score,
    gist_to_candidate,
)


class PreviousChatGistRetriever:
    """Retrieve stored previous-chat gists.

    This is a disabled-by-default infrastructure retriever. It performs only
    temporary lexical filtering until cross-chat gist vector retrieval exists.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Return matching previous-chat gist candidates across stored chats."""
        del chat_id
        limit = source_plan.limit or 4
        gists = self.database.chat_gists_by_source_type("previous_chat_gist")
        candidates = [
            gist_to_candidate(gist, score=gist_score(gist, source_plan.query))
            for gist in gists
            if gist_matches_query(gist, source_plan.query)
        ]
        return sorted(candidates, key=lambda candidate: candidate.score or 0.0, reverse=True)[
            :limit
        ]
