from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from openai import OpenAI

from evals.mab_answer_eval.schemas import JudgeResult
from src.config import AppConfig


JUDGE_PROMPT_VERSION = "mab-correctness-judge-v2-deepseek"
JUDGE_MAX_TOKENS = 300


class JudgeClient(Protocol):
    model_name: str

    def judge(self, messages: list[dict[str, str]]) -> str:
        """Return a structured judge response."""
        ...


class OpenAIJudgeClient:
    """Small deterministic judge client using existing endpoint configuration."""

    def __init__(
        self,
        config: AppConfig,
        model_name: str,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.model_name = model_name
        self._client = OpenAI(
            api_key=api_key or config.openai_api_key,
            base_url=base_url or config.openai_base_url,
        )

    def judge(self, messages: list[dict[str, str]]) -> str:
        try:
            completion = self._client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0,
                max_tokens=JUDGE_MAX_TOKENS,
                response_format={"type": "json_object"},
            )
        except Exception as error:
            raise RuntimeError(
                f"{type(error).__name__}: judge request failed"
            ) from None
        return completion.choices[0].message.content or ""


@dataclass(frozen=True)
class JudgeEvaluation:
    result: JudgeResult | None
    attempts: int
    error: str | None


def evaluate_with_judge(
    client: JudgeClient,
    *,
    question: str,
    references: tuple[str, ...],
    generated_answer: str,
    selected_evidence: str = "",
) -> JudgeEvaluation:
    """Run one judge request and at most one structured-output repair."""
    messages = build_judge_messages(
        question=question,
        references=references,
        generated_answer=generated_answer,
    )
    raw = client.judge(messages)
    try:
        return JudgeEvaluation(parse_judge_result(raw), 1, None)
    except ValueError as first_error:
        repair_messages = [
            *messages,
            {"role": "assistant", "content": raw[:2000]},
            {
                "role": "user",
                "content": (
                    "Return only a valid JSON object matching the requested schema. "
                    "Do not add explanation outside JSON."
                ),
            },
        ]
        repaired = client.judge(repair_messages)
        try:
            return JudgeEvaluation(parse_judge_result(repaired), 2, None)
        except ValueError as second_error:
            return JudgeEvaluation(
                None,
                2,
                f"{first_error}; repair_failed: {second_error}"[:600],
            )


def build_judge_messages(
    *,
    question: str,
    references: tuple[str, ...],
    generated_answer: str,
) -> list[dict[str, str]]:
    schema = {
        "correct": True,
        "complete": True,
        "brief_reason": "Concise reason.",
    }
    payload = {
        "question": question,
        "reference_answers": list(references),
        "generated_answer": generated_answer,
    }
    return [
        {
            "role": "system",
            "content": (
                "You are a deterministic correctness evaluator. Compare the generated "
                "answer with the reference answer or task rubric. Evaluate correctness "
                "and completeness only. Do not evaluate faithfulness. Do not provide "
                "chain-of-thought. Return only a JSON object matching this structure: "
                f"{json.dumps(schema, separators=(',', ':'))}"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]


def parse_judge_result(raw: str) -> JudgeResult:
    text = raw.strip()
    if not text:
        raise ValueError("judge output is empty")
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"judge output is not valid JSON: {error.msg}") from error
    if not isinstance(value, dict):
        raise ValueError("judge output must be an object")
    required_bools = ("correct", "complete")
    for key in required_bools:
        if not isinstance(value.get(key), bool):
            raise ValueError(f"judge field {key!r} must be boolean")
    reason = value.get("brief_reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("judge brief_reason must be a non-empty string")
    return JudgeResult(
        correct=value["correct"],
        complete=value["complete"],
        brief_reason=reason.strip()[:500],
    )


def judge_parameters() -> dict[str, Any]:
    return {
        "temperature": 0,
        "max_tokens": JUDGE_MAX_TOKENS,
        "response_format": {"type": "json_object"},
        "evaluation": "correctness_only",
        "prompt_version": JUDGE_PROMPT_VERSION,
    }
