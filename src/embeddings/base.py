from __future__ import annotations

from typing import Protocol


class EmbedderUnavailableError(RuntimeError):
    """Raised when an optional embedding backend cannot be used."""


class TextEmbedder(Protocol):
    """Minimal embedding interface for document retrieval."""

    @property
    def model_name(self) -> str:
        """Return embedding model name."""
        ...

    @property
    def dimension(self) -> int | None:
        """Return vector dimension when known."""
        ...

    def embed_text(self, text: str) -> list[float]:
        """Embed one text string."""
        ...

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple text strings."""
        ...
