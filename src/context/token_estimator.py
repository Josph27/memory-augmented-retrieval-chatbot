from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Protocol, Sequence


class TokenEstimator(Protocol):
    """Replaceable token estimator interface.

    Implementations may be approximate or backed by a model-specific tokenizer.
    The chat pipeline only depends on this protocol so a real tokenizer can be
    plugged in without changing context construction.
    """

    model_name: str | None
    backend: str

    def count_text(self, text: str) -> int:
        """Count tokens for plain text."""
        ...

    def count_messages(
        self,
        messages: Sequence[dict[str, str]],
        *,
        add_generation_prompt: bool,
    ) -> int:
        """Count a complete chat template."""
        ...

    def estimate_text(self, text: str) -> int:
        """Estimate tokens for plain text."""
        ...

    def estimate_messages(self, messages: list[dict[str, str]]) -> int:
        """Estimate tokens for chat messages."""
        ...


@dataclass(frozen=True)
class TokenEstimatorInfo:
    """Debug metadata describing the tokenizer backend in use."""

    backend: str
    model_name: str | None
    approximate: bool


class ApproximateTokenEstimator:
    """Small tokenizer-free estimator.

    This intentionally overestimates a little and can later be replaced with a
    model-specific tokenizer behind the same interface.
    """

    backend = "approximate_chars"

    def __init__(
        self,
        chars_per_token: float = 4.0,
        per_message_overhead: int = 4,
        model_name: str | None = None,
    ) -> None:
        self.chars_per_token = chars_per_token
        self.per_message_overhead = per_message_overhead
        self.model_name = model_name

    def estimate_text(self, text: str) -> int:
        """Estimate tokens from character length."""
        if not text:
            return 0
        return max(1, int(len(text) / self.chars_per_token) + 1)

    def count_text(self, text: str) -> int:
        return self.estimate_text(text)

    def estimate_messages(self, messages: list[dict[str, str]]) -> int:
        """Estimate chat message tokens including small per-message overhead."""
        total = 0
        for message in messages:
            total += self.per_message_overhead
            total += self.estimate_text(str(message.get("role", "")))
            total += self.estimate_text(str(message.get("content", "")))
        return total

    def count_messages(
        self,
        messages: Sequence[dict[str, str]],
        *,
        add_generation_prompt: bool,
    ) -> int:
        del add_generation_prompt
        return self.estimate_messages(list(messages))

    def info(self) -> TokenEstimatorInfo:
        """Return compact debug metadata about this estimator."""
        return TokenEstimatorInfo(
            backend=self.backend,
            model_name=self.model_name,
            approximate=True,
        )


ProcessorLoader = Callable[[str], Any]
TokenizerLoader = Callable[[str], Any]
_PROCESSOR_CACHE: dict[str, Any] = {}
_PROCESSOR_FAILURES: dict[str, str] = {}
_TOKENIZER_CACHE: dict[str, Any] = {}
_TOKENIZER_FAILURES: dict[str, str] = {}
_TOKENIZER_CACHE_LOCK = Lock()


class GemmaTokenEstimator:
    """Lazy processor/tokenizer counter with a non-fatal approximate fallback."""

    backend = "huggingface_gemma_processor"

    def __init__(
        self,
        tokenizer_id: str,
        *,
        processor_loader: ProcessorLoader | None = None,
        tokenizer_loader: TokenizerLoader | None = None,
        fallback: TokenEstimator | None = None,
    ) -> None:
        self.model_name = tokenizer_id
        self.tokenizer_id = tokenizer_id
        self._processor_loader = processor_loader
        self._tokenizer_loader = tokenizer_loader
        self._fallback = fallback or ApproximateTokenEstimator(model_name=tokenizer_id)
        self._processor: Any | None = None
        self._tokenizer: Any | None = None
        self._processor_load_attempted = False
        self._tokenizer_load_attempted = False
        self._processor_failure: str | None = None
        self._tokenizer_failure: str | None = None
        self._last_call_fallback_events: list[str] = []

    @property
    def tokenizer_mode(self) -> str:
        if self._processor is not None:
            return "model_template"
        if self._tokenizer is not None:
            return "text_tokenizer"
        if self._processor_load_attempted and self._tokenizer_load_attempted:
            return "approximate"
        return "model_template"

    @property
    def fallback_reason(self) -> str | None:
        reasons = [
            reason
            for reason in (self._processor_failure, self._tokenizer_failure)
            if reason
        ]
        return "; ".join(reasons)[:600] or None

    def count_text(self, text: str) -> int:
        self._last_call_fallback_events = []
        if not text:
            return 0
        processor = self._resolve_processor()
        if processor is not None:
            try:
                tokenizer = getattr(processor, "tokenizer", processor)
                return count_tokenizer_text(tokenizer, text)
            except Exception as error:
                self._record_call_fallback("processor_text", error)

        tokenizer = self._resolve_tokenizer()
        if tokenizer is not None:
            try:
                return count_tokenizer_text(tokenizer, text)
            except Exception as error:
                self._record_call_fallback("tokenizer_text", error)
        return self._fallback.count_text(text)

    def count_messages(
        self,
        messages: Sequence[dict[str, str]],
        *,
        add_generation_prompt: bool,
    ) -> int:
        self._last_call_fallback_events = []
        if not messages:
            return 0
        processor = self._resolve_processor()
        if processor is not None:
            try:
                return count_chat_template(
                    processor,
                    messages,
                    add_generation_prompt=add_generation_prompt,
                )
            except Exception as error:
                self._record_call_fallback("processor_template", error)

        tokenizer = self._resolve_tokenizer()
        if tokenizer is not None:
            try:
                return count_chat_template(
                    tokenizer,
                    messages,
                    add_generation_prompt=add_generation_prompt,
                )
            except Exception as error:
                self._record_call_fallback("tokenizer_template", error)
                try:
                    return count_tokenizer_text(
                        tokenizer,
                        serialize_messages(
                            messages,
                            add_generation_prompt=add_generation_prompt,
                        ),
                    )
                except Exception as serialization_error:
                    self._record_call_fallback(
                        "tokenizer_serialization",
                        serialization_error,
                    )
        return self._fallback.count_messages(
            messages,
            add_generation_prompt=add_generation_prompt,
        )

    def estimate_text(self, text: str) -> int:
        return self.count_text(text)

    def estimate_messages(self, messages: list[dict[str, str]]) -> int:
        return self.count_messages(messages, add_generation_prompt=False)

    def info(self) -> TokenEstimatorInfo:
        return TokenEstimatorInfo(
            backend=(
                self.backend
                if self.tokenizer_mode == "model_template"
                else (
                    "huggingface_text_tokenizer"
                    if self.tokenizer_mode == "text_tokenizer"
                    else self._fallback.backend
                )
            ),
            model_name=self.tokenizer_id,
            approximate=self.tokenizer_mode == "approximate",
        )

    def trace_metadata(self) -> dict[str, object]:
        return {
            "tokenizer_id": self.tokenizer_id,
            "tokenizer_mode": self.tokenizer_mode,
            "fallback_reason": self.fallback_reason,
            "last_call_fallback_events": list(self._last_call_fallback_events),
        }

    def _resolve_processor(self) -> Any | None:
        if self._processor is not None:
            return self._processor
        if self._processor_load_attempted:
            return None
        self._processor_load_attempted = True
        try:
            if self._processor_loader is not None:
                self._processor = self._processor_loader(self.tokenizer_id)
            else:
                self._processor = cached_auto_processor(self.tokenizer_id)
            return self._processor
        except Exception as error:
            self._processor_failure = bounded_failure("processor_load", error)
            return None

    def _resolve_tokenizer(self) -> Any | None:
        if self._tokenizer is not None:
            return self._tokenizer
        if self._tokenizer_load_attempted:
            return None
        self._tokenizer_load_attempted = True
        try:
            if self._tokenizer_loader is not None:
                self._tokenizer = self._tokenizer_loader(self.tokenizer_id)
            else:
                self._tokenizer = cached_auto_tokenizer(self.tokenizer_id)
            return self._tokenizer
        except Exception as error:
            self._tokenizer_failure = bounded_failure("tokenizer_load", error)
            return None

    def _record_call_fallback(self, stage: str, error: Exception) -> None:
        self._last_call_fallback_events.append(bounded_failure(stage, error))


def cached_auto_processor(tokenizer_id: str) -> Any:
    """Load processor assets once per process; cache failures as well as successes."""
    with _TOKENIZER_CACHE_LOCK:
        if tokenizer_id in _PROCESSOR_CACHE:
            return _PROCESSOR_CACHE[tokenizer_id]
        if tokenizer_id in _PROCESSOR_FAILURES:
            raise RuntimeError(_PROCESSOR_FAILURES[tokenizer_id])
        try:
            processor = load_auto_processor(tokenizer_id)
        except Exception as error:
            reason = f"{type(error).__name__}: {error}"[:300]
            _PROCESSOR_FAILURES[tokenizer_id] = reason
            raise
        _PROCESSOR_CACHE[tokenizer_id] = processor
        return processor


def cached_auto_tokenizer(tokenizer_id: str) -> Any:
    """Load tokenizer assets once per process, independently of processor state."""
    with _TOKENIZER_CACHE_LOCK:
        if tokenizer_id in _TOKENIZER_CACHE:
            return _TOKENIZER_CACHE[tokenizer_id]
        if tokenizer_id in _TOKENIZER_FAILURES:
            raise RuntimeError(_TOKENIZER_FAILURES[tokenizer_id])
        try:
            tokenizer = load_auto_tokenizer(tokenizer_id)
        except Exception as error:
            reason = f"{type(error).__name__}: {error}"[:300]
            _TOKENIZER_FAILURES[tokenizer_id] = reason
            raise
        _TOKENIZER_CACHE[tokenizer_id] = tokenizer
        return tokenizer


def load_auto_processor(tokenizer_id: str) -> Any:
    """Load only tokenizer/processor assets through the mature HF abstraction."""
    from transformers import AutoProcessor

    return AutoProcessor.from_pretrained(tokenizer_id)


def load_auto_tokenizer(tokenizer_id: str) -> Any:
    """Load tokenizer-only assets without loading model weights."""
    from transformers import AutoTokenizer

    return AutoTokenizer.from_pretrained(tokenizer_id)


def clear_processor_cache() -> None:
    """Clear processor and tokenizer process caches for deterministic tests."""
    with _TOKENIZER_CACHE_LOCK:
        _PROCESSOR_CACHE.clear()
        _PROCESSOR_FAILURES.clear()
        _TOKENIZER_CACHE.clear()
        _TOKENIZER_FAILURES.clear()


def count_tokenizer_text(tokenizer: Any, text: str) -> int:
    encoded = tokenizer(text, add_special_tokens=False)
    return token_length(encoded)


def count_chat_template(
    template_owner: Any,
    messages: Sequence[dict[str, str]],
    *,
    add_generation_prompt: bool,
) -> int:
    encoded = template_owner.apply_chat_template(
        list(messages),
        tokenize=True,
        add_generation_prompt=add_generation_prompt,
    )
    return token_length(encoded)


def serialize_messages(
    messages: Sequence[dict[str, str]],
    *,
    add_generation_prompt: bool,
) -> str:
    """Serialize messages only for a per-call tokenizer fallback."""
    parts = [
        f"{message.get('role', '')}: {message.get('content', '')}"
        for message in messages
    ]
    if add_generation_prompt:
        parts.append("assistant:")
    return "\n".join(parts)


def bounded_failure(stage: str, error: Exception) -> str:
    return f"{stage}: {type(error).__name__}: {error}"[:300]


def token_length(encoded: Any) -> int:
    """Read token length from processor/tokenizer return conventions."""
    if isinstance(encoded, dict) or hasattr(encoded, "get"):
        encoded = encoded.get("input_ids")
    if hasattr(encoded, "shape"):
        shape = encoded.shape
        return int(shape[-1])
    if (
        isinstance(encoded, Sequence)
        and encoded
        and isinstance(encoded[0], Sequence)
        and not isinstance(encoded[0], str | bytes)
    ):
        return len(encoded[0])
    return len(encoded)


def count_text(estimator: TokenEstimator, text: str) -> int:
    """Count text while supporting older deterministic injected estimators."""
    method = getattr(estimator, "count_text", None)
    return method(text) if callable(method) else estimator.estimate_text(text)


def count_messages(
    estimator: TokenEstimator,
    messages: Sequence[dict[str, str]],
    *,
    add_generation_prompt: bool,
) -> int:
    """Count messages while supporting older deterministic injected estimators."""
    method = getattr(estimator, "count_messages", None)
    if callable(method):
        return method(messages, add_generation_prompt=add_generation_prompt)
    return estimator.estimate_messages(list(messages))


def tokenizer_trace_metadata(estimator: TokenEstimator) -> dict[str, object]:
    method = getattr(estimator, "trace_metadata", None)
    if callable(method):
        return method()
    info = estimator.info() if hasattr(estimator, "info") else None
    return {
        "tokenizer_id": getattr(estimator, "model_name", None),
        "tokenizer_mode": (
            "approximate" if info is None or info.approximate else "exact"
        ),
        "fallback_reason": None,
    }


def build_token_estimator(
    model_name: str | None = None,
    *,
    tokenizer_id: str | None = None,
    processor_loader: ProcessorLoader | None = None,
    tokenizer_loader: TokenizerLoader | None = None,
) -> TokenEstimator:
    """Build the supported exact counter, retaining the established fallback."""
    selected_tokenizer = tokenizer_id or model_name
    if selected_tokenizer == "google/gemma-4-31B-it":
        return GemmaTokenEstimator(
            selected_tokenizer,
            processor_loader=processor_loader,
            tokenizer_loader=tokenizer_loader,
        )
    return ApproximateTokenEstimator(model_name=model_name)
