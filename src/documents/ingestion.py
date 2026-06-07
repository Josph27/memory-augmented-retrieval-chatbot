from __future__ import annotations

from dataclasses import dataclass

from src.database import Database


DEFAULT_TARGET_CHARS = 800
DEFAULT_MAX_CHARS = 1000


@dataclass(frozen=True)
class DocumentIngestionResult:
    """Result returned after storing a plain-text document."""

    document_id: int
    chunk_count: int


class DocumentIngestionService:
    """Store plain-text documents as local SQLite chunks."""

    def __init__(
        self,
        database: Database,
        target_chars: int = DEFAULT_TARGET_CHARS,
        max_chars: int = DEFAULT_MAX_CHARS,
    ) -> None:
        self.database = database
        self.target_chars = target_chars
        self.max_chars = max_chars

    def ingest_text_document(
        self,
        title: str,
        text: str,
        source: str = "manual",
        metadata: dict | None = None,
    ) -> DocumentIngestionResult:
        """Split and store one plain-text document."""
        chunks = split_text_into_chunks(
            text=text,
            target_chars=self.target_chars,
            max_chars=self.max_chars,
        )
        document_id = self.database.insert_document(
            title=title,
            source=source,
            metadata=metadata,
        )
        for index, chunk in enumerate(chunks):
            self.database.insert_document_chunk(
                document_id=document_id,
                chunk_index=index,
                text=chunk,
                metadata={"title": title, "source": source},
            )
        return DocumentIngestionResult(
            document_id=document_id,
            chunk_count=len(chunks),
        )


def split_text_into_chunks(
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
