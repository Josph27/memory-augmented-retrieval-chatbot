from __future__ import annotations

from openai import OpenAI

from src.config import AppConfig


class ModelWrapper:
    """OpenAI-compatible chat model client.

    The same wrapper can call OpenAI, Ollama, LM Studio, vLLM, or another compatible
    `/v1/chat/completions` endpoint by changing environment variables.
    """

    def __init__(self, config: AppConfig, model_name: str | None = None) -> None:
        self.model_name = model_name or config.model_name
        self.client = OpenAI(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Send messages to the configured model and return assistant text."""
        kwargs = {}
        if temperature is not None:
            kwargs["temperature"] = temperature

        completion = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            **kwargs,
        )
        content = completion.choices[0].message.content
        return content or ""
