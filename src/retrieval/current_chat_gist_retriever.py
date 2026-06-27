from __future__ import annotations

import json

from src.core.contracts import MemoryCandidate, SourcePlan
from src.database import Database, StoredChatGist


class CurrentChatGistRetriever:
    """Retrieve stored current-chat gists.

    This is an infrastructure stub for future gist retrieval. It reads stored
    gists when they exist, but it does not generate gists or run vector search.
    """

    def __init__(self, database: Database) -> None:
        self.database = database

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Return matching current-chat gist candidates for one chat."""
        limit = source_plan.limit or 4
        gists = self.database.chat_gists_for_chat(
            chat_id=chat_id,
            source_type="current_chat_gist",
        )
        candidates = [
            gist_to_candidate(gist, score=gist_score(gist, source_plan.query))
            for gist in gists
            if gist_matches_query(gist, source_plan.query)
        ]
        return sorted(candidates, key=lambda candidate: candidate.score or 0.0, reverse=True)[
            :limit
        ]


def gist_to_candidate(gist: StoredChatGist, score: float) -> MemoryCandidate:
    """Convert a stored gist row into the shared memory candidate contract."""
    metadata = parse_json_object(gist.metadata_json)
    metadata.update(
        {
            "source_type": gist.source_type,
            "topics": parse_json_list(gist.topics_json),
            "decisions": parse_json_list(gist.decisions_json),
            "open_tasks": parse_json_list(gist.open_tasks_json),
            "start_message_id": gist.start_message_id,
            "end_message_id": gist.end_message_id,
            "created_at": gist.created_at,
            "updated_at": gist.updated_at,
            "status": metadata.get("status", "active"),
            "retrieval_mode": "stored_gist_placeholder",
        }
    )
    source_ids = [
        source_id
        for source_id in (gist.start_message_id, gist.end_message_id)
        if source_id is not None
    ]
    return MemoryCandidate(
        source=gist.source_type,
        content=gist.gist_text,
        score=score,
        record_id=gist.id,
        chat_id=gist.chat_id,
        source_message_ids=source_ids,
        metadata=metadata,
    )


def gist_matches_query(gist: StoredChatGist, query: str | None) -> bool:
    """Temporary lexical matching until gist vector retrieval exists."""
    if not query:
        return True
    return gist_score(gist, query) > 0.0


def gist_score(gist: StoredChatGist, query: str | None) -> float:
    """Return a small lexical overlap score for stored-gist stubs."""
    if not query:
        return 0.5
    query_terms = set(tokenize(query))
    if not query_terms:
        return 0.5
    gist_terms = set(tokenize(gist.gist_text))
    overlap = len(query_terms & gist_terms)
    return min(1.0, overlap / max(1, len(query_terms)))


def tokenize(text: str) -> list[str]:
    """Tokenize text for temporary substring scoring."""
    return [
        token.strip(".,:;!?()[]{}\"'").lower()
        for token in text.split()
        if token.strip(".,:;!?()[]{}\"'")
    ]


def parse_json_list(value: str) -> list[object]:
    """Parse a JSON list with a safe fallback."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def parse_json_object(value: str) -> dict[str, object]:
    """Parse a JSON object with a safe fallback."""
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
