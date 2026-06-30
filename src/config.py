from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.memory.constants import MEMORY_UPDATE_BATCH_SIZE, RAW_MESSAGE_LIMIT


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration loaded from environment variables."""

    openai_api_key: str
    openai_base_url: str
    model_name: str
    database_path: Path
    raw_message_limit: int
    memory_update_batch_size: int
    document_retrieval_mode: str
    embedding_model_name: str
    document_top_k: int
    document_chunker: str
    document_chunk_size: int
    document_chunk_overlap: int
    langchain_chroma_persist_dir: Path
    langchain_chunk_size: int
    langchain_chunk_overlap: int
    routing_mode: str
    reranker_mode: str
    reranker_llm_top_k: int
    reranker_llm_min_confidence: float
    structured_memory_retrieval_mode: str
    long_term_memory_chroma_persist_dir: Path
    long_term_memory_collection: str
    previous_chat_gist_generation_enabled: bool
    previous_chat_gist_retrieval_enabled: bool
    query_augmentation_enabled: bool
    cross_encoder_model_name: str
    cross_encoder_top_k: int
    cross_encoder_mem_k: int
    cross_encoder_doc_k: int
    cross_encoder_timeout_ms: int
    context_placement_mode: str
    lt_mem_embedding_chunk_size: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load local `.env` values and fall back to a local Ollama-compatible setup."""
        load_dotenv()

        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "dummy"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
            model_name=os.getenv("MODEL_NAME", "google/gemma-4-31B-it"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/chatbot.db")),
            raw_message_limit=int(os.getenv("RAW_MESSAGE_LIMIT", str(RAW_MESSAGE_LIMIT))),
            memory_update_batch_size=int(
                os.getenv(
                    "MEMORY_UPDATE_BATCH_SIZE",
                    os.getenv("SUMMARY_BATCH_SIZE", str(MEMORY_UPDATE_BATCH_SIZE)),
                )
            ),
            document_retrieval_mode=os.getenv("DOCUMENT_RETRIEVAL_MODE", "langchain_chroma"),
            embedding_model_name=os.getenv(
                "EMBEDDING_MODEL_NAME",
                "sentence-transformers/all-MiniLM-L6-v2",
            ),
            document_top_k=int(os.getenv("DOCUMENT_TOP_K", "4")),
            document_chunker=os.getenv("DOCUMENT_CHUNKER", "custom"),
            document_chunk_size=int(os.getenv("DOCUMENT_CHUNK_SIZE", "1000")),
            document_chunk_overlap=int(os.getenv("DOCUMENT_CHUNK_OVERLAP", "150")),
            langchain_chroma_persist_dir=Path(
                os.getenv("LANGCHAIN_CHROMA_PERSIST_DIR", "data/chroma")
            ),
            langchain_chunk_size=int(os.getenv("LANGCHAIN_CHUNK_SIZE", "1000")),
            langchain_chunk_overlap=int(os.getenv("LANGCHAIN_CHUNK_OVERLAP", "150")),
            routing_mode=os.getenv("ROUTING_MODE", "rule").strip().lower(),
            reranker_mode=os.getenv(
                "RERANKER_MODE",
                "deterministic",
            )
            .strip()
            .lower(),
            reranker_llm_top_k=int(os.getenv("RERANKER_LLM_TOP_K", "10")),
            reranker_llm_min_confidence=float(os.getenv("RERANKER_LLM_MIN_CONFIDENCE", "0.55")),
            structured_memory_retrieval_mode=os.getenv(
                "STRUCTURED_MEMORY_RETRIEVAL_MODE",
                "sqlite",
            )
            .strip()
            .lower(),
            long_term_memory_chroma_persist_dir=Path(
                os.getenv(
                    "LONG_TERM_MEMORY_CHROMA_PERSIST_DIR",
                    os.getenv("LANGCHAIN_CHROMA_PERSIST_DIR", "data/chroma"),
                )
            ),
            long_term_memory_collection=os.getenv(
                "LONG_TERM_MEMORY_COLLECTION",
                "long_term_memory",
            ),
            previous_chat_gist_generation_enabled=env_bool(
                "PREVIOUS_CHAT_GIST_GENERATION_ENABLED",
                default=True,
            ),
            previous_chat_gist_retrieval_enabled=env_bool(
                "PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED",
                default=True,
            ),
            query_augmentation_enabled=env_bool("QUERY_AUGMENTATION_ENABLED", default=True),
            cross_encoder_model_name=os.getenv(
                "CROSS_ENCODER_MODEL_NAME",
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
            ),
            cross_encoder_top_k=int(os.getenv("CROSS_ENCODER_TOP_K", "20")),
            cross_encoder_mem_k=int(os.getenv("CROSS_ENCODER_MEM_K", "8")),
            cross_encoder_doc_k=int(os.getenv("CROSS_ENCODER_DOC_K", "4")),
            cross_encoder_timeout_ms=int(os.getenv("CROSS_ENCODER_TIMEOUT_MS", "2000")),
            context_placement_mode=os.getenv("CONTEXT_PLACEMENT_MODE", "budget_fitting"),
            lt_mem_embedding_chunk_size=int(os.getenv("LT_MEM_EMBEDDING_CHUNK_SIZE", "256")),
        )


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean-like environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
