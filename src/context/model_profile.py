from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


DEFAULT_MODEL_ID = "google/gemma-4-31B-it"
SAFE_FALLBACK_CONTEXT_WINDOW = 4096
DEFAULT_GEMMA_APPLICATION_CONTEXT_CAP = 262_144
DEFAULT_OUTPUT_RESERVE = 512


@dataclass(frozen=True)
class ModelProfile:
    """Static model metadata used by deterministic context accounting."""

    model_id: str
    tokenizer_id: str | None
    native_context_window: int | None
    sliding_window: int | None
    default_output_reserve: int


@dataclass(frozen=True)
class ResolvedContextWindow:
    """Effective context window plus traceable inputs to its resolution."""

    model_id: str
    native_context_window: int | None
    sliding_window: int | None
    endpoint_context_window: int | None
    endpoint_limit_verified: bool
    application_context_cap: int | None
    effective_context_window: int
    limit_source: str
    endpoint_limit_source: str | None = None

    def to_metadata(self) -> dict[str, object]:
        endpoint_source = (
            "environment_override"
            if self.endpoint_limit_source
            else "endpoint_metadata"
        )
        return {
            "model_id": self.model_id,
            "native_context_window": self.native_context_window,
            "sliding_window": self.sliding_window,
            "endpoint_context_window": self.endpoint_context_window,
            "endpoint_limit_verified": self.endpoint_limit_verified,
            "application_context_cap": self.application_context_cap,
            "effective_context_window": self.effective_context_window,
            "limit_source": self.limit_source,
            "effective_limit_source": self.limit_source,
            "endpoint_limit_source": self.endpoint_limit_source,
            "context_limit_inputs": {
                "native_model": self.native_context_window,
                endpoint_source: self.endpoint_context_window,
                "application_cap": self.application_context_cap,
                "safe_fallback": SAFE_FALLBACK_CONTEXT_WINDOW,
            },
        }


MODEL_PROFILES = {
    DEFAULT_MODEL_ID: ModelProfile(
        model_id=DEFAULT_MODEL_ID,
        tokenizer_id=DEFAULT_MODEL_ID,
        native_context_window=262_144,
        sliding_window=1024,
        default_output_reserve=DEFAULT_OUTPUT_RESERVE,
    )
}

ENDPOINT_CONTEXT_ENV_NAMES = (
    "ENDPOINT_CONTEXT_WINDOW",
    "MODEL_CONTEXT_WINDOW",
    "CONTEXT_LENGTH",
    "MAX_MODEL_LEN",
    "MAX_INPUT_TOKENS",
)


def model_profile_for(model_id: str) -> ModelProfile:
    """Return registered metadata or a conservative unknown-model profile."""
    return MODEL_PROFILES.get(
        model_id,
        ModelProfile(
            model_id=model_id,
            tokenizer_id=None,
            native_context_window=None,
            sliding_window=None,
            default_output_reserve=DEFAULT_OUTPUT_RESERVE,
        ),
    )


def endpoint_context_limit_from_env(
    environ: Mapping[str, str] | None = None,
) -> tuple[int | None, str | None]:
    """Resolve the first positive endpoint-limit environment override."""
    values = environ if environ is not None else os.environ
    for name in ENDPOINT_CONTEXT_ENV_NAMES:
        value = positive_int(values.get(name))
        if value is not None:
            return value, name
    return None, None


def application_context_cap_from_env(
    environ: Mapping[str, str] | None = None,
    *,
    default: int = DEFAULT_GEMMA_APPLICATION_CONTEXT_CAP,
) -> int:
    """Resolve the application cap for the primary Gemma profile."""
    values = environ if environ is not None else os.environ
    return positive_int(values.get("APPLICATION_CONTEXT_CAP")) or default


def resolve_context_window(
    profile: ModelProfile,
    *,
    endpoint_context_window: int | None = None,
    application_context_cap: int | None = DEFAULT_GEMMA_APPLICATION_CONTEXT_CAP,
    endpoint_limit_source: str | None = None,
    safe_fallback: int = SAFE_FALLBACK_CONTEXT_WINDOW,
) -> ResolvedContextWindow:
    """Take the minimum known applicable limit; sliding-window metadata is excluded."""
    limits: list[tuple[str, int]] = []
    if profile.native_context_window is not None:
        limits.append(("native_model", profile.native_context_window))
    if endpoint_context_window is not None:
        limits.append(
            (
                "environment_override"
                if endpoint_limit_source
                else "endpoint_metadata",
                endpoint_context_window,
            )
        )
    if application_context_cap is not None:
        limits.append(("application_cap", application_context_cap))
    if not limits:
        limits.append(("safe_fallback", safe_fallback))

    limit_source, effective = min(limits, key=lambda item: item[1])
    if (
        limit_source == "native_model"
        and endpoint_context_window is None
        and profile.native_context_window == effective
    ):
        limit_source = "native_model_assumption"
    return ResolvedContextWindow(
        model_id=profile.model_id,
        native_context_window=profile.native_context_window,
        sliding_window=profile.sliding_window,
        endpoint_context_window=endpoint_context_window,
        endpoint_limit_verified=endpoint_context_window is not None,
        application_context_cap=application_context_cap,
        effective_context_window=effective,
        limit_source=limit_source,
        endpoint_limit_source=endpoint_limit_source,
    )


def positive_int(value: str | int | None) -> int | None:
    """Return a positive integer or None for missing/invalid configuration."""
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
