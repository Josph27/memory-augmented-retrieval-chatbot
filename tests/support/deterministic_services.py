"""Explicit service-test dependencies: real Chroma persistence, local embeddings only."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever


class DeterministicEmbeddings:
    def embed_query(self, text: str) -> list[float]:
        vector = [0.0] * 32
        vector[0] = 0.1
        for word in re.findall(r"\w+", text.lower()):
            index = int.from_bytes(hashlib.sha256(word.encode()).digest()[:2], "big") % 32
            vector[index] += 1.0
        return vector

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(text) for text in texts]


class LocalChromaRetriever(LangChainChromaRetriever):
    """Override the model dependency, retaining the real Chroma/retrieval implementation."""

    def _embeddings(self) -> DeterministicEmbeddings:
        return DeterministicEmbeddings()


def local_document_retriever(database) -> LocalChromaRetriever:
    return LocalChromaRetriever(
        persist_dir=Path(database.path).parent / "document-chroma",
        collection_name="stage5-documents",
        summary_getter=database,
    )


class RecordingGuard:
    """Explicit per-test guard substitute for an injected fake inference manager."""

    def __init__(self) -> None:
        self.calls = 0

    def check(self) -> None:
        self.calls += 1
