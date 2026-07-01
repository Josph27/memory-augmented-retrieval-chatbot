from __future__ import annotations

import re
from collections import Counter
from dataclasses import replace
from typing import Any

from evals.memory_agent_bench.schemas import MABenchExample


TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
TEMPORAL_OR_CONFLICT_CUES = (
    " latest ",
    " current ",
    " changed ",
    " updated ",
    " before ",
    " after ",
    " previously ",
    " most recent ",
)
MULTI_EVIDENCE_CUES = (
    " both ",
    " same nationality ",
    " relationship between ",
    " compare ",
    " respectively ",
)
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "did",
    "do",
    "does",
    "for",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "the",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
}


def filter_likely_single_evidence(
    examples: list[MABenchExample],
) -> tuple[list[MABenchExample], dict[str, Any]]:
    """Select eval questions with one literal, lexically related evidence chunk."""
    selected: list[MABenchExample] = []
    reasons: Counter[str] = Counter()
    input_questions = 0
    for example in examples:
        kept_questions: list[str] = []
        kept_answers: list[tuple[str, ...]] = []
        for question, answers in zip(
            example.questions,
            example.answers,
            strict=True,
        ):
            input_questions += 1
            reason = single_evidence_rejection_reason(
                example,
                question=question,
                answers=answers,
            )
            if reason is not None:
                reasons[reason] += 1
                continue
            kept_questions.append(question)
            kept_answers.append(answers)
        if kept_questions:
            selected.append(
                replace(
                    example,
                    questions=tuple(kept_questions),
                    answers=tuple(kept_answers),
                    metadata={
                        **example.metadata,
                        "adapter_selection": "likely_single_evidence",
                    },
                )
            )
    return selected, {
        "likely_single_evidence_filter": True,
        "heuristic_input_examples": len(examples),
        "heuristic_input_questions": input_questions,
        "heuristic_selected_examples": len(selected),
        "heuristic_selected_questions": sum(
            len(example.questions) for example in selected
        ),
        "heuristic_filtered_questions": input_questions
        - sum(len(example.questions) for example in selected),
        "heuristic_filter_reasons": dict(sorted(reasons.items())),
    }


def single_evidence_rejection_reason(
    example: MABenchExample,
    *,
    question: str,
    answers: tuple[str, ...],
) -> str | None:
    """Return why one question is not a conservative single-evidence case."""
    normalized_question = f" {' '.join(question.lower().split())} "
    if any(cue in normalized_question for cue in TEMPORAL_OR_CONFLICT_CUES):
        return "temporal_or_conflict_cue"
    if any(cue in normalized_question for cue in MULTI_EVIDENCE_CUES):
        return "multi_evidence_cue"

    normalized_answers = {
        " ".join(answer.lower().split())
        for answer in answers
        if answer.strip()
    }
    matching_chunks = [
        chunk
        for session in example.sessions
        for chunk in session.chunks
        if any(
            answer in " ".join(chunk.lower().split())
            for answer in normalized_answers
        )
    ]
    if not matching_chunks:
        return "gold_not_literal_in_replay"
    if len(matching_chunks) != 1:
        return "gold_not_unique_to_one_chunk"

    query_terms = lexical_terms(question)
    evidence_terms = lexical_terms(matching_chunks[0])
    if not query_terms.intersection(evidence_terms):
        return "no_question_evidence_lexical_overlap"
    return None


def lexical_terms(value: str) -> set[str]:
    return {
        token
        for token in TOKEN_PATTERN.findall(value.lower())
        if token not in STOPWORDS and len(token) > 1
    }
