"""Shared inference provider settings for chat and structured memory.

Edit the Git-ignored root local_settings.py for local provider settings and keys.
Environment variables override local settings; legacy OPENAI_* values only apply
to the custom provider, so an old university URL cannot redirect DeepSeek calls.
"""

from __future__ import annotations

import os
import runpy
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

PROVIDER = "custom"  # custom | deepseek; overridden by local_settings.py
DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-flash"
LOCAL_SETTINGS_PATH = Path(__file__).resolve().parents[1] / "local_settings.py"


@dataclass(frozen=True)
class ProviderSettings:
    provider: str
    api_key: str = field(repr=False)
    base_url: str
    model_name: str


def load_provider_settings() -> ProviderSettings:
    """Resolve one provider for all inference paths without mutating env values."""
    load_dotenv()
    local = runpy.run_path(str(LOCAL_SETTINGS_PATH)) if LOCAL_SETTINGS_PATH.is_file() else {}
    provider = os.getenv("LLM_PROVIDER", local.get("PROVIDER", PROVIDER)).strip().lower()
    if provider == "custom":
        from src import settings as app_settings

        return ProviderSettings(
            provider=provider,
            api_key=os.getenv(
                "OPENAI_API_KEY", local.get("CUSTOM_API_KEY", app_settings.OPENAI_API_KEY)
            ),
            base_url=os.getenv(
                "OPENAI_BASE_URL", local.get("CUSTOM_BASE_URL", app_settings.OPENAI_BASE_URL)
            ),
            model_name=os.getenv("MODEL_NAME", local.get("CUSTOM_MODEL", app_settings.MODEL_NAME)),
        )
    if provider == "deepseek":
        return ProviderSettings(
            provider=provider,
            api_key=os.getenv("DEEPSEEK_API_KEY", local.get("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY)),
            base_url=os.getenv(
                "DEEPSEEK_BASE_URL", local.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL)
            ),
            model_name=os.getenv("DEEPSEEK_MODEL", local.get("DEEPSEEK_MODEL", DEEPSEEK_MODEL)),
        )
    raise ValueError(f"Unknown LLM provider {provider!r}; choose 'custom' or 'deepseek'.")


def provider_client_options(provider: str, api_key: str) -> dict:
    """Keep DeepSeek tool extraction in non-thinking mode in both SDK clients."""
    if provider == "deepseek":
        if not api_key.strip():
            raise ValueError(
                "DeepSeek API key missing: set DEEPSEEK_API_KEY in local_settings.py "
                "or the environment."
            )
        return {"extra_body": {"thinking": {"type": "disabled"}}}
    return {}
