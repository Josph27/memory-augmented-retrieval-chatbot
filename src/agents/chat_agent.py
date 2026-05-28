from __future__ import annotations

from src.model_wrapper import ModelWrapper


class ChatAgent:
    """Thin chat-model agent around the existing OpenAI-compatible wrapper."""

    def __init__(self, model: ModelWrapper) -> None:
        self.model = model

    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Generate an assistant response from model-ready messages."""
        return self.model.chat(messages, temperature=temperature)
