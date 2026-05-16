from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration loaded from environment variables."""

    openai_api_key: str
    openai_base_url: str
    model_name: str
    database_path: Path
    recent_message_limit: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load local `.env` values and fall back to a local Ollama-compatible setup."""
        load_dotenv()

        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "dummy"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
            model_name=os.getenv("MODEL_NAME", "qwen2.5:3b"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/chatbot.db")),
            recent_message_limit=int(os.getenv("RECENT_MESSAGE_LIMIT", "12")),
        )
