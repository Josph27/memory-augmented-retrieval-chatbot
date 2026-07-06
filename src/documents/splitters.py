from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol


DEFAULT_CHUNKER = "custom"
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_TARGET_CHARS = 800
DEFAULT_MAX_CHARS = 1000


@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration for document text splitting."""

    chunker: str = DEFAULT_CHUNKER
    chunk_size: int = DEFAULT_CHUNK_SIZE
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP
    target_chars: int = DEFAULT_TARGET_CHARS
    max_chars: int = DEFAULT_MAX_CHARS

    @classmethod
    def from_env(
        cls,
        target_chars: int = DEFAULT_TARGET_CHARS,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> "ChunkingConfig":
        """Load splitter configuration from environment variables."""
        chunker = os.getenv("DOCUMENT_CHUNKER", DEFAULT_CHUNKER).strip()
        chunk_size = int(os.getenv("DOCUMENT_CHUNK_SIZE", str(target_chars)))
        chunk_overlap = int(os.getenv("DOCUMENT_CHUNK_OVERLAP", str(DEFAULT_CHUNK_OVERLAP)))
        return cls(
            chunker=chunker,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            target_chars=chunk_size,
            max_chars=max(max_chars, chunk_size),
        )


@dataclass(frozen=True)
class DocumentChunk:
    """One split document chunk and its storage metadata."""

    text: str
    chunk_index: int
    metadata: dict


class TextSplitter(Protocol):
    """Text splitter contract for ingestion."""

    splitter_name: str

    def split(self, text: str) -> list[DocumentChunk]:
        """Split text into document chunks."""


def split_document_text(text: str, config: ChunkingConfig | None = None) -> list[DocumentChunk]:
    """Split document text with configured splitter and custom fallback."""
    active_config = config or ChunkingConfig.from_env()
    splitter = splitter_for_config(active_config)
    return splitter.split(text)


def split_text_into_chunks(
    text: str,
    target_chars: int = DEFAULT_TARGET_CHARS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[str]:
    """Backward-compatible custom chunking helper."""
    splitter = CustomParagraphSplitter(
        ChunkingConfig(
            chunker="custom",
            target_chars=target_chars,
            max_chars=max_chars,
            chunk_size=max_chars,
            chunk_overlap=0,
        )
    )
    return [chunk.text for chunk in splitter.split(text)]


def splitter_for_config(config: ChunkingConfig) -> TextSplitter:
    """Create a splitter for the configured chunking mode."""
    if config.chunker == "langchain_recursive":
        try:
            return LangChainRecursiveSplitter(config)
        except LangChainSplitterUnavailable:
            return CustomParagraphSplitter(config, requested_splitter="langchain_recursive")
    return CustomParagraphSplitter(config)


class CustomParagraphSplitter:
    """Paragraph-preserving custom splitter used as stable fallback."""

    splitter_name = "custom_paragraph"

    def __init__(
        self,
        config: ChunkingConfig,
        requested_splitter: str | None = None,
    ) -> None:
        self.config = config
        self.requested_splitter = requested_splitter

    def split(self, text: str) -> list[DocumentChunk]:
        """Split plain text into paragraph-preserving chunks."""
        chunk_texts = split_text_custom(
            text=text,
            target_chars=self.config.target_chars,
            max_chars=self.config.max_chars,
        )
        return chunks_with_metadata(
            original_text=text,
            chunk_texts=chunk_texts,
            splitter_name=self.splitter_name,
            chunk_size=self.config.target_chars,
            chunk_overlap=0,
            fallback_used=self.requested_splitter is not None,
            requested_splitter=self.requested_splitter,
        )


class LangChainSplitterUnavailable(RuntimeError):
    """Raised when optional LangChain splitter support is unavailable."""


class LangChainRecursiveSplitter:
    """Adapter around LangChain's RecursiveCharacterTextSplitter."""

    splitter_name = "langchain_recursive"

    def __init__(self, config: ChunkingConfig) -> None:
        self.config = config
        splitter_class = import_recursive_character_splitter()
        chunk_size = max(1, config.chunk_size)
        chunk_overlap = min(max(0, config.chunk_overlap), max(0, chunk_size - 1))
        self._splitter = splitter_class(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            add_start_index=True,
        )

    def split(self, text: str) -> list[DocumentChunk]:
        """Split text with LangChain's recursive character splitter."""
        documents = self._splitter.create_documents([text])
        chunks: list[DocumentChunk] = []
        for index, document in enumerate(documents):
            chunk_text = document.page_content.strip()
            if not chunk_text:
                continue
            start_index = document.metadata.get("start_index")
            end_index = None
            if isinstance(start_index, int):
                end_index = start_index + len(chunk_text)
            chunks.append(
                DocumentChunk(
                    text=chunk_text,
                    chunk_index=len(chunks),
                    metadata={
                        "splitter_name": self.splitter_name,
                        "chunk_size": self.config.chunk_size,
                        "chunk_overlap": self.config.chunk_overlap,
                        "fallback_used": False,
                        "start_char": start_index,
                        "end_char": end_index,
                        "source_chunk_index": index,
                    },
                )
            )
        return chunks


def import_recursive_character_splitter() -> type:
    """Import LangChain's recursive splitter from either package layout."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        return RecursiveCharacterTextSplitter
    except ImportError:
        try:
            from langchain.text_splitter import RecursiveCharacterTextSplitter

            return RecursiveCharacterTextSplitter
        except ImportError as error:
            msg = (
                "LangChain text splitters are unavailable. Install "
                "langchain-text-splitters to use DOCUMENT_CHUNKER=langchain_recursive."
            )
            raise LangChainSplitterUnavailable(msg) from error


def split_text_custom(
    text: str,
    target_chars: int = DEFAULT_TARGET_CHARS,
    max_chars: int = DEFAULT_MAX_CHARS,
) -> list[str]:
    """Split plain text into paragraph-preserving chunks."""
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_length = 0

    for paragraph in paragraphs:
        paragraph_parts = split_long_paragraph(paragraph, max_chars=max_chars)
        for part in paragraph_parts:
            separator_length = 2 if current else 0
            would_exceed = current_length + separator_length + len(part) > target_chars
            if current and would_exceed:
                chunks.append("\n\n".join(current))
                current = []
                current_length = 0

            current.append(part)
            current_length += (2 if current_length else 0) + len(part)

    if current:
        chunks.append("\n\n".join(current))

    return chunks or ([text.strip()] if text.strip() else [])


def split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    """Split one long paragraph on sentence-ish boundaries when possible."""
    if len(paragraph) <= max_chars:
        return [paragraph]

    parts: list[str] = []
    remaining = paragraph.strip()
    while len(remaining) > max_chars:
        split_at = best_split_index(remaining, max_chars=max_chars)
        parts.append(remaining[:split_at].strip())
        remaining = remaining[split_at:].strip()
    if remaining:
        parts.append(remaining)
    return parts


def best_split_index(text: str, max_chars: int) -> int:
    """Find a readable split point before max_chars."""
    candidates = [
        text.rfind(". ", 0, max_chars),
        text.rfind("? ", 0, max_chars),
        text.rfind("! ", 0, max_chars),
        text.rfind(" ", 0, max_chars),
    ]
    split_at = max(candidates)
    if split_at <= 0:
        return max_chars
    return split_at + 1


def chunks_with_metadata(
    original_text: str,
    chunk_texts: list[str],
    splitter_name: str,
    chunk_size: int,
    chunk_overlap: int,
    fallback_used: bool,
    requested_splitter: str | None = None,
) -> list[DocumentChunk]:
    """Attach standard splitter metadata to chunk texts."""
    chunks: list[DocumentChunk] = []
    search_from = 0
    for index, chunk_text in enumerate(chunk_texts):
        start_char = original_text.find(chunk_text, search_from)
        if start_char < 0:
            start_char = None
            end_char = None
        else:
            end_char = start_char + len(chunk_text)
            search_from = end_char
        metadata = {
            "splitter_name": splitter_name,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "fallback_used": fallback_used,
            "start_char": start_char,
            "end_char": end_char,
        }
        if requested_splitter:
            metadata["requested_splitter"] = requested_splitter
        chunks.append(
            DocumentChunk(
                text=chunk_text,
                chunk_index=index,
                metadata=metadata,
            )
        )
    return chunks
