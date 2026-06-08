from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class AnswerGenerator(Protocol):
    """Small interface for document QA answer generation."""

    @property
    def model_name(self) -> str | None:
        """Return the model name if available."""
        ...

    def generate(self, question: str, contexts: list[str]) -> str:
        """Generate an answer from retrieved contexts."""
        ...


@dataclass
class ModelWrapperAnswerGenerator:
    """Grounded QA generator using the project's OpenAI-compatible ModelWrapper."""

    model_wrapper: object

    @property
    def model_name(self) -> str | None:
        """Return the configured model name if the wrapper exposes one."""
        value = getattr(self.model_wrapper, "model_name", None)
        return str(value) if value is not None else None

    def generate(self, question: str, contexts: list[str]) -> str:
        """Generate a concise answer using only retrieved contexts."""
        messages = build_grounded_qa_messages(question=question, contexts=contexts)
        chat = getattr(self.model_wrapper, "chat")
        return str(chat(messages, temperature=0.0)).strip()


def build_grounded_qa_messages(question: str, contexts: list[str]) -> list[dict[str, str]]:
    """Build a strict grounded QA prompt for eval-only answer generation."""
    context_text = format_contexts(contexts)
    return [
        {
            "role": "system",
            "content": (
                "Answer the question using only the provided contexts.\n"
                "If the answer is not contained in the contexts, say \"I don't know.\"\n"
                "Keep the answer concise.\n"
                "Do not use outside knowledge."
            ),
        },
        {
            "role": "user",
            "content": f"Contexts:\n{context_text}\n\nQuestion: {question}\n\nAnswer:",
        },
    ]


def format_contexts(contexts: list[str]) -> str:
    """Format retrieved contexts for a grounded QA prompt."""
    if not contexts:
        return "No contexts were retrieved."
    return "\n\n".join(
        f"[{index}] {context.strip()}"
        for index, context in enumerate(contexts, start=1)
        if context.strip()
    ) or "No contexts were retrieved."


def build_default_answer_generator() -> ModelWrapperAnswerGenerator:
    """Create the default model-backed answer generator from project config."""
    from src.config import AppConfig
    from src.model_wrapper import ModelWrapper

    return ModelWrapperAnswerGenerator(ModelWrapper(AppConfig.from_env()))


def answer_is_unknown(answer: str) -> bool:
    """Return whether the model explicitly declined due to missing context."""
    normalized = " ".join(answer.casefold().split())
    return "i don't know" in normalized or "i do not know" in normalized
