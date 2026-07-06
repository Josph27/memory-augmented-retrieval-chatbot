from __future__ import annotations

from pathlib import Path

from src.context.evidence_selector import EvidenceConstrainedContextSelector
from src.context.token_estimator import ApproximateTokenEstimator
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.retrieval.gist_raw_span_expander import GistRawSpanExpander
from src.retrieval.raw_message_span_retriever import RawMessageSpanRetriever


class WordCounter(ApproximateTokenEstimator):
    def count_text(self, text: str) -> int:
        return len(text.split())


def raw_plan(query: str, *, profile: str = "memory_recall", limit: int = 12) -> SourcePlan:
    return SourcePlan(
        source="raw_message_span",
        query=query,
        limit=limit,
        filters={"context_profile": profile},
    )


def test_direct_raw_finds_fact_omitted_from_gist(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("history")
    database.save_message(
        "history",
        "user",
        "The uncommon launch code is QUARTZ-7719.",
    )
    database.save_message("history", "assistant", "Acknowledged.")
    database.mark_chat_inactive("history")
    database.insert_chat_gist(
        chat_id="history",
        source_type="previous_chat_gist",
        gist_text="The conversation discussed launch planning.",
        topics=[],
        decisions=[],
        open_tasks=[],
        start_message_id=1,
        end_message_id=2,
    )

    candidates = RawMessageSpanRetriever(database).retrieve(
        "question-chat",
        raw_plan("What was the QUARTZ-7719 launch code?"),
    )

    assert len(candidates) == 1
    assert "QUARTZ-7719" in candidates[0].content
    assert candidates[0].metadata["retrieval_path"] == "direct_raw"
    assert candidates[0].metadata["similarity_score"] == candidates[0].score
    assert candidates[0].metadata["lexical_retrieval_score"] == candidates[0].score


def test_direct_raw_order_and_limit_are_deterministic(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("history")
    for index in range(20):
        database.save_message(
            "history",
            "user",
            f"Entity Cobalt record number {index}.",
        )
    database.mark_chat_inactive("history")
    retriever = RawMessageSpanRetriever(database)
    plan = raw_plan("Cobalt record number", limit=3)

    first = retriever.retrieve("question", plan)
    second = retriever.retrieve("question", plan)

    assert [item.record_id for item in first] == [
        item.record_id for item in second
    ]
    assert len(first) <= 3


def test_direct_raw_respects_explicit_chat_scope(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("allowed-history")
    database.save_message(
        "allowed-history",
        "user",
        "The scoped launch code is ALLOWED-42.",
    )
    database.mark_chat_inactive("allowed-history")
    database.create_chat("unrelated-history")
    database.save_message(
        "unrelated-history",
        "user",
        "The scoped launch code is PRIVATE-99.",
    )
    database.mark_chat_inactive("unrelated-history")
    plan = raw_plan("scoped launch code", limit=12)
    plan.filters["allowed_chat_ids"] = ["allowed-history"]

    candidates = RawMessageSpanRetriever(database).retrieve("question", plan)

    assert candidates
    assert {candidate.chat_id for candidate in candidates} == {
        "allowed-history"
    }
    assert all("PRIVATE-99" not in candidate.content for candidate in candidates)


def test_global_summary_exposes_complete_timeline_beyond_focused_limit(
    tmp_path: Path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("history")
    for index in range(15):
        database.save_message(
            "history",
            "user",
            f"Chronological segment {index}.",
        )
    database.mark_chat_inactive("history")
    retriever = RawMessageSpanRetriever(
        database,
        max_chars=80,
        direct_limit=3,
    )

    candidates = retriever.retrieve(
        "question",
        raw_plan("summarize", profile="global_summary", limit=3),
    )

    assert len(candidates) > 3
    assert candidates[0].metadata["timeline_index"] == 0
    assert candidates[-1].metadata["coverage_chunk_index"] == len(candidates) - 1
    assert all(
        candidate.metadata["coverage_chunk_count"] == len(candidates)
        for candidate in candidates
    )


def test_explicit_raw_span_rejects_chat_outside_scope(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("unrelated-history")
    message_id = database.save_message(
        "unrelated-history",
        "user",
        "Private scoped evidence.",
    )
    database.mark_chat_inactive("unrelated-history")
    plan = SourcePlan(
        source="raw_message_span",
        query="private evidence",
        filters={
            "chat_id": "unrelated-history",
            "start_message_id": message_id,
            "end_message_id": message_id,
            "allowed_chat_ids": ["allowed-history"],
        },
    )

    assert RawMessageSpanRetriever(database).retrieve("question", plan) == []


def test_gist_and_direct_duplicate_merge_retrieval_paths(tmp_path: Path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("history")
    first_id = database.save_message("history", "user", "The code is COBALT-42.")
    second_id = database.save_message("history", "assistant", "Confirmed.")
    database.mark_chat_inactive("history")
    gist = MemoryCandidate(
        source="previous_chat_gist",
        content="A code was recorded.",
        record_id="gist-1",
        chat_id="history",
        source_message_ids=[first_id, second_id],
        metadata={"start_message_id": first_id, "end_message_id": second_id},
    )
    expanded = GistRawSpanExpander(database).expand([gist], "COBALT-42")[0]
    direct = RawMessageSpanRetriever(database).retrieve(
        "question",
        raw_plan("COBALT-42"),
    )[0]
    route = RoutePlan(
        query="COBALT-42",
        sources=[
            SourcePlan(source="previous_chat_gist", enabled=True),
            SourcePlan(source="raw_message_span", enabled=True),
        ],
    )

    result = EvidenceConstrainedContextSelector().select(
        candidates=[expanded, direct],
        route_plan=route,
        token_budget=100,
        token_counter=WordCounter(),
    )

    assert len(result.selected_candidates) == 1
    assert set(result.selected_candidates[0].metadata["retrieval_paths"]) == {
        "gist_expansion",
        "direct_raw",
    }
