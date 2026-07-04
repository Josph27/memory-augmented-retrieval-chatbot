#!/usr/bin/env python3
"""Inspect one MAB answer artifact against surviving local replay state.

This tool never resolves benchmark rows or calls a model. It reads an existing
results.jsonl file and, when available, a local SQLite replay snapshot.
"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
import json
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.memory_agent_bench.adapter import SYSTEM_PROMPT
from src.context.context_builder import ContextBuilder
from src.core.contracts import ContextBudget, MemoryCandidate
from src.database import Database
from src.retrieval.gist_raw_span_expander import GistRawSpanExpander
from src.retrieval.previous_chat_gist_retriever import PreviousChatGistRetriever
from src.retrieval.raw_message_span_retriever import RawMessageSpanRetriever
from src.retrieval.reranker import MemoryReranker
from src.routing.semantic_router import SemanticRouter


CASE_TERMS = {
    "Accurate_Retrieval:ruler_qa2_421K:row-1:q5": (
        "YG Entertainment",
        "YG",
        "2014 S/S",
        "WINNER",
        "formed by",
    ),
    "Accurate_Retrieval:ruler_qa2_421K:row-1:q8": (
        "Annie Morton",
        "Terry Richardson",
        "older",
        "age",
        "born",
        "October 8, 1970",
        "August 14, 1965",
    ),
    "Conflict_Resolution:factconsolidation_sh_6k:row-4:q2": (
        "India",
        "England",
        "rugby union",
        "invented",
        "created",
        "originated",
    ),
    "Conflict_Resolution:factconsolidation_sh_6k:row-4:q4": (
        "Joan Didion",
        "University of California",
        "Berkeley",
        "educated",
        "university",
    ),
}
MAX_MATCHES_PER_STAGE = 40
SNIPPET_RADIUS = 180


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect one MAB case using local artifacts and replay SQLite only."
    )
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--database", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    return parser.parse_args()


def load_completed_result(run_dir: Path, case_id: str) -> dict[str, Any]:
    results_path = run_dir / "results.jsonl"
    rows = [
        json.loads(line)
        for line in results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matches = [row for row in rows if row.get("case_id") == case_id]
    if not matches:
        raise SystemExit(f"case not found in {results_path}: {case_id}")
    completed = [row for row in matches if row.get("status") == "completed"]
    return completed[-1] if completed else matches[-1]


def source_chat_fragment(case_id: str) -> str:
    _, source_dataset, row_part, _ = case_id.split(":", maxsplit=3)
    row_index = int(row_part.removeprefix("row-"))
    return f"{source_dataset}-row-{row_index + 1}-session-"


def sqlite_contains_chat(path: Path, fragment: str) -> bool:
    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute(
                "SELECT 1 FROM chats WHERE id LIKE ? LIMIT 1",
                (f"%{fragment}%",),
            ).fetchone()
    except (sqlite3.Error, OSError):
        return False
    return row is not None


def discover_database(
    run_dir: Path,
    case_id: str,
    explicit: Path | None,
) -> Path | None:
    fragment = source_chat_fragment(case_id)
    if explicit is not None:
        resolved = explicit.expanduser().resolve()
        if not sqlite_contains_chat(resolved, fragment):
            raise SystemExit(
                f"database does not contain expected replay chat {fragment!r}: "
                f"{resolved}"
            )
        return resolved

    candidates = list(run_dir.rglob("*.db"))
    temp_root = Path(tempfile.gettempdir())
    candidates.extend(temp_root.glob("mab_diag_prepare_*/prepared.db"))
    candidates.extend(temp_root.glob("mab_diag_case_*/case.db"))
    compatible = sorted(
        {
            candidate.resolve()
            for candidate in candidates
            if candidate.is_file() and sqlite_contains_chat(candidate, fragment)
        },
        key=lambda path: (
            "prepare" not in path.parent.name,
            str(path),
        ),
    )
    return compatible[0] if compatible else None


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", value.casefold())).strip()


def matching_terms(text: str, terms: Sequence[str]) -> list[str]:
    normalized_text = normalized(text)
    return [
        term
        for term in terms
        if normalized(term) and normalized(term) in normalized_text
    ]


def snippet(text: str, terms: Sequence[str]) -> str:
    lowered = text.casefold()
    positions = [
        lowered.find(term.casefold())
        for term in terms
        if lowered.find(term.casefold()) >= 0
    ]
    if not positions:
        compact = " ".join(text.split())
        return compact[: SNIPPET_RADIUS * 2]
    center = min(positions)
    start = max(0, center - SNIPPET_RADIUS)
    end = min(len(text), center + SNIPPET_RADIUS)
    return " ".join(text[start:end].split())


def candidate_identity(candidate: MemoryCandidate) -> str:
    return f"{candidate.source}:{candidate.record_id}"


def candidate_matches(
    candidates: Iterable[MemoryCandidate],
    terms: Sequence[str],
    *,
    selected_ids: set[str],
    dropped: dict[str, dict[str, Any]],
    rank_by_id: dict[str, int],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for candidate in candidates:
        hits = matching_terms(candidate.content, terms)
        if not hits:
            continue
        identity = candidate_identity(candidate)
        drop = dropped.get(identity)
        matches.append(
            {
                "candidate_id": identity,
                "source": candidate.source,
                "record_id": candidate.record_id,
                "chat_id": candidate.chat_id,
                "message_ids": list(candidate.source_message_ids),
                "span_start": candidate.metadata.get("start_message_id"),
                "span_end": candidate.metadata.get("end_message_id"),
                "anchor_message_ids": candidate.metadata.get(
                    "anchor_message_ids"
                ),
                "retrieval_path": candidate.metadata.get("retrieval_path"),
                "retrieval_paths": candidate.metadata.get("retrieval_paths"),
                "rank": rank_by_id.get(identity),
                "score": candidate.score,
                "selected": identity in selected_ids,
                "drop_reason": drop.get("reason") if drop else None,
                "overlap_ratio": drop.get("overlap_ratio") if drop else None,
                "overlap_with_candidate_id": (
                    drop.get("overlap_with_candidate_id") if drop else None
                ),
                "unique_message_count": (
                    drop.get("unique_message_count") if drop else None
                ),
                "matched_terms": hits,
                "snippet": snippet(candidate.content, hits),
            }
        )
        if len(matches) >= MAX_MATCHES_PER_STAGE:
            break
    return matches


def persisted_matches(
    database: Database,
    terms: Sequence[str],
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for chat in database.list_inactive_chats():
        for message in database.messages_for_chat(str(chat["id"])):
            hits = matching_terms(message.content, terms)
            if not hits:
                continue
            matches.append(
                {
                    "chat_id": message.chat_id,
                    "message_id": message.id,
                    "role": message.role,
                    "matched_terms": hits,
                    "snippet": snippet(message.content, hits),
                }
            )
            if len(matches) >= MAX_MATCHES_PER_STAGE:
                return matches
    return matches


def selected_candidates_for_artifact(
    retrieved: Sequence[MemoryCandidate],
    selected_ids: Sequence[str],
) -> list[MemoryCandidate]:
    by_id = {candidate_identity(candidate): candidate for candidate in retrieved}
    return [
        by_id[identity]
        for identity in selected_ids
        if identity in by_id
    ]


def rendered_context(
    selected: list[MemoryCandidate],
    ranked: list[MemoryCandidate],
    question: str,
    route_plan: Any,
) -> str:
    if not selected:
        return ""
    budget = ContextBudget(
        max_tokens=262_144,
        reserved_response_tokens=512,
        source_token_budgets={source.source: 262_144 for source in route_plan.sources},
        metadata={"context_profile": route_plan.context_profile},
    )
    packet = ContextBuilder().build(
        system_prompt=SYSTEM_PROMPT,
        latest_user_message={"role": "user", "content": question},
        ranked_candidates=ranked,
        context_budget=budget,
        route_plan=route_plan,
        preselected_candidates=selected,
    )
    return "\n".join(
        message["content"]
        for message in packet.model_messages[1:-1]
    )


def inspect_case(
    run_dir: Path,
    case_id: str,
    database_path: Path | None,
) -> dict[str, Any]:
    record = load_completed_result(run_dir, case_id)
    terms = CASE_TERMS.get(
        case_id,
        tuple(record.get("reference_answer") or ()) + (str(record["question"]),),
    )
    context = record.get("context_diagnostics") or {}
    result: dict[str, Any] = {
        "case_id": case_id,
        "question": record.get("question"),
        "reference_answer": record.get("reference_answer"),
        "generated_answer": record.get("generated_answer"),
        "route_intent": context.get("route_intent"),
        "context_profile": context.get("route_context_profile"),
        "working_memory_budget": context.get("working_memory_budget"),
        "selected_memory_tokens": context.get("selected_memory_tokens"),
        "artifact_gold_candidate_present": context.get(
            "gold_candidate_present"
        ),
        "artifact_gold_context_present": context.get("gold_context_present"),
        "artifact_failure_stage": context.get("mab_failure_stage"),
        "search_terms": list(terms),
        "database": str(database_path) if database_path else None,
        "source_history_note": (
            "The original dataset row is not retained separately; persisted role-less "
            "replay messages are the exact normalized source chunks."
        ),
    }
    if database_path is None:
        result["local_state"] = "unavailable"
        return result

    database = Database(database_path)
    semantic = SemanticRouter().route(str(record["question"]), task_context="memory_qa")
    route_plan = SemanticRouter().to_route_plan(semantic)
    gist_plan = next(
        source
        for source in route_plan.sources
        if source.source == "previous_chat_gist"
    )
    raw_plan = next(
        source for source in route_plan.sources if source.source == "raw_message_span"
    )
    gists = PreviousChatGistRetriever(database).retrieve(
        "benchmark-question-1",
        gist_plan,
    )
    direct = RawMessageSpanRetriever(database).retrieve(
        "benchmark-question-1",
        raw_plan,
    )
    expanded = GistRawSpanExpander(database).expand(
        gists,
        route_plan.query,
    )
    retrieved = [*gists, *direct, *expanded]
    ranked = MemoryReranker(mode="deterministic").rank(
        retrieved,
        ranking_profile=route_plan.ranking_profile,
        query=route_plan.query,
    )
    selected_id_list = list(context.get("selected_evidence_ids") or [])
    selected_ids = set(selected_id_list)
    selected = selected_candidates_for_artifact(retrieved, selected_id_list)
    dropped_rows = context.get("dropped_candidates") or []
    dropped = {
        str(row.get("candidate_id")): row
        for row in dropped_rows
        if row.get("candidate_id")
    }
    rank_by_id = {
        candidate_identity(candidate): rank
        for rank, candidate in enumerate(ranked, start=1)
    }
    rendered = rendered_context(selected, ranked, str(record["question"]), route_plan)
    rendered_hits = matching_terms(rendered, terms)
    result.update(
        {
            "local_state": "available",
            "original_query": route_plan.metadata.get("original_query"),
            "retrieval_query": route_plan.metadata.get("retrieval_query"),
            "query_rewrite_applied": route_plan.metadata.get(
                "query_rewrite_applied"
            ),
            "source_history_matches": persisted_matches(database, terms),
            "persisted_message_matches": persisted_matches(database, terms),
            "gist_matches": candidate_matches(
                gists,
                terms,
                selected_ids=selected_ids,
                dropped=dropped,
                rank_by_id=rank_by_id,
            ),
            "direct_raw_candidate_matches": candidate_matches(
                direct,
                terms,
                selected_ids=selected_ids,
                dropped=dropped,
                rank_by_id=rank_by_id,
            ),
            "gist_expanded_candidate_matches": candidate_matches(
                expanded,
                terms,
                selected_ids=selected_ids,
                dropped=dropped,
                rank_by_id=rank_by_id,
            ),
            "ranked_candidate_matches": candidate_matches(
                ranked,
                terms,
                selected_ids=selected_ids,
                dropped=dropped,
                rank_by_id=rank_by_id,
            ),
            "selected_candidate_matches": candidate_matches(
                selected,
                terms,
                selected_ids=selected_ids,
                dropped=dropped,
                rank_by_id=rank_by_id,
            ),
            "rendered_context_matches": {
                "matched_terms": rendered_hits,
                "snippet": snippet(rendered, rendered_hits) if rendered_hits else None,
            },
            "artifact_selected_candidate_ids_not_reconstructed": sorted(
                selected_ids
                - {candidate_identity(candidate) for candidate in selected}
            ),
            "artifact_drop_decisions": dropped_rows,
        }
    )
    return result


def main() -> None:
    args = parse_args()
    run_dir = args.run_dir.expanduser().resolve()
    database_path = discover_database(run_dir, args.case_id, args.database)
    result = inspect_case(run_dir, args.case_id, database_path)
    if args.as_json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return
    for key, value in result.items():
        print(f"{key}:")
        if isinstance(value, (dict, list)):
            print(json.dumps(value, indent=2, ensure_ascii=False, default=str))
        else:
            print(value)


if __name__ == "__main__":
    main()
