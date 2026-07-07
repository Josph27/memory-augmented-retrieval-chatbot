from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from src.database import Database, StoredDocument


IMPLICIT_DOCUMENT_REFERENCES = (
    "this report",
    "this document",
    "this file",
    "that document",
    "that file",
    "that report",
    "the document",
    "the file",
    "the uploaded file",
    "the file i uploaded",
    "the uploaded document",
    "the previous document",
    "the file from before",
    "summarize it",
    "look at that report",
    "according to this report",
)


class DocumentScopeError(RuntimeError):
    """Base class for truthful document-scope failures."""


class DocumentAmbiguityError(DocumentScopeError):
    """Raised when a document reference has multiple valid targets."""


class DocumentNotReadyError(DocumentScopeError):
    """Raised when associated documents are not ready for retrieval."""


@dataclass(frozen=True)
class DocumentResolution:
    """Deterministic resolution of a query to chat-associated documents."""

    document_ids: tuple[str, ...]
    file_names: tuple[str, ...]
    reason: str


class DocumentRegistry:
    """Persist lifecycle metadata and resolve document references per chat."""

    def __init__(self, database: Database) -> None:
        self.database = database

    def resolve(self, chat_id: str, query: str) -> DocumentResolution:
        documents = self.database.documents_for_chat(chat_id)
        if not documents:
            return DocumentResolution((), (), "no_associated_documents")

        normalized = query.casefold()
        explicit = [
            document
            for document in documents
            if filename_mentioned(normalized, document.file_name)
        ]
        if explicit:
            return self._ready_resolution(explicit, "explicit_filename")

        ready = [document for document in documents if document.status == "Ready"]
        pending = [
            document
            for document in documents
            if document.status in {"Uploading", "Indexing"}
        ]
        if pending and is_implicit_document_reference(normalized):
            names = ", ".join(document.file_name for document in pending)
            raise DocumentNotReadyError(f"Document is still being indexed: {names}")

        if len(ready) == 1:
            return self._ready_resolution(ready, "single_ready_document")
        if len(ready) > 1 and is_implicit_document_reference(normalized):
            names = ", ".join(document.file_name for document in ready)
            raise DocumentAmbiguityError(
                f"Multiple documents match this request; select one: {names}"
            )
        if len(ready) > 1:
            return self._ready_resolution(ready, "all_ready_documents")
        failed = [document.file_name for document in documents if document.status == "Failed"]
        if failed:
            raise DocumentScopeError(
                "Document indexing failed: " + ", ".join(failed)
            )
        return DocumentResolution((), (), "no_ready_documents")

    @staticmethod
    def _ready_resolution(
        documents: list[StoredDocument],
        reason: str,
    ) -> DocumentResolution:
        not_ready = [document for document in documents if document.status != "Ready"]
        if not_ready:
            names = ", ".join(document.file_name for document in not_ready)
            raise DocumentNotReadyError(f"Document is not ready: {names}")
        return DocumentResolution(
            tuple(document.id for document in documents),
            tuple(document.file_name for document in documents),
            reason,
        )


def filename_mentioned(normalized_query: str, file_name: str) -> bool:
    """Match an explicit filename without interpreting arbitrary substrings."""
    normalized_name = Path(file_name).name.casefold()
    if not normalized_name:
        return False
    return re.search(rf"(?<![\w.-]){re.escape(normalized_name)}(?![\w.-])", normalized_query) is not None


def is_implicit_document_reference(normalized_query: str) -> bool:
    """Return whether a query refers to an already-associated document."""
    return any(phrase in normalized_query for phrase in IMPLICIT_DOCUMENT_REFERENCES)
