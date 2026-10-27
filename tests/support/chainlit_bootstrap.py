"""Explicit offline dependencies, installed before importing the eager Chainlit app."""

from __future__ import annotations

import os
from pathlib import Path


def prepare_chainlit_dependencies() -> None:
    from src import settings
    from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever
    from support.deterministic_services import DeterministicEmbeddings

    database = Path(os.environ["DATABASE_PATH"]).resolve()
    chroma = Path(os.environ["LANGCHAIN_CHROMA_PERSIST_DIR"]).resolve()
    assert database.is_relative_to("/work") and chroma.is_relative_to("/work")
    settings.DATABASE_PATH = str(database)
    settings.LANGCHAIN_CHROMA_PERSIST_DIR = str(chroma)
    settings.STRUCTURED_MEMORY_RETRIEVAL_MODE = "sqlite"
    settings.ROUTING_MODE = "rule"
    settings.RERANKER_MODE = "deterministic"
    settings.PREVIOUS_CHAT_GIST_EXTRACTOR = "deterministic"
    LangChainChromaRetriever._embeddings = lambda self: DeterministicEmbeddings()
