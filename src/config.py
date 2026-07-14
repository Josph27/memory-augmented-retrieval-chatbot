from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from src.context.model_profile import (
    application_context_cap_from_env,
    endpoint_context_limit_from_env,
)
from src.memory.constants import (
    MEMORY_REPLAY_MAX_INPUT_TOKENS,
    MEMORY_REPLAY_MAX_MESSAGES,
    MEMORY_REPLAY_TRIGGER_TOKENS,
    MEMORY_RECENT_PROTECTION_TOKENS,
    MEMORY_UPDATE_BATCH_SIZE,
    MEMORY_UPDATE_MAX_INPUT_TOKENS,
    MEMORY_UPDATE_MAX_MESSAGES,
    MEMORY_UPDATE_TRIGGER_TOKENS,
    RAW_MESSAGE_LIMIT,
    RECENT_MESSAGES_MAX_COUNT,
)


@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration loaded from environment variables."""

    openai_api_key: str
    openai_base_url: str
    model_name: str
    endpoint_context_window: int | None
    endpoint_context_limit_source: str | None
    application_context_cap: int
    base_memory_budget: int
    memory_recall_budget_tokens: int
    chat_memory_cap: int
    document_memory_cap: int
    multi_scope_memory_cap: int
    long_document_memory_cap: int
    global_summary_budget_tokens: int
    global_summary_max_budget_tokens: int
    global_summary_reserved_tokens: int
    required_evidence_headroom_ratio: float
    minimum_optional_candidate_utility: float
    gist_retrieval_candidates: int
    direct_raw_retrieval_candidates: int
    raw_span_overlap_threshold: float
    enable_retrieval_query_simplification: bool
    database_path: Path
    raw_message_limit: int
    memory_update_batch_size: int
    recent_messages_max_count: int
    memory_update_trigger_tokens: int
    memory_update_max_input_tokens: int
    memory_update_max_messages: int
    memory_recent_protection_tokens: int
    memory_update_policy: str
    memory_replay_trigger_tokens: int
    memory_replay_max_input_tokens: int
    memory_replay_max_messages: int
    document_retrieval_mode: str
    embedding_model_name: str
    document_top_k: int
    document_chunker: str
    document_chunk_size: int
    document_chunk_overlap: int
    langchain_chroma_persist_dir: Path
    langchain_chunk_size: int
    langchain_chunk_overlap: int
    orchestration_mode: str
    routing_mode: str
    reranker_mode: str
    reranker_llm_top_k: int
    reranker_llm_min_confidence: float
    reranker_cross_encoder_model: str
    reranker_cross_encoder_top_k: int
    reranker_cross_encoder_weight: float
    reranker_hybrid_backend: str
    reranker_llm_ambiguity_margin: float
    reranker_llm_require_cross_source_conflict: bool
    reranker_llm_provenance_queries: bool
    structured_memory_retrieval_mode: str
    long_term_memory_chroma_persist_dir: Path
    long_term_memory_collection: str
    current_chat_gist_generation_enabled: bool
    previous_chat_gist_generation_enabled: bool
    previous_chat_gist_retrieval_enabled: bool
    previous_chat_gist_extractor: str
    previous_chat_gist_max_messages_per_gist: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load local `.env` values and fall back to a local Ollama-compatible setup."""
        load_dotenv()

        endpoint_context_window, endpoint_limit_source = (
            endpoint_context_limit_from_env()
        )
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "dummy"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
            model_name=os.getenv("MODEL_NAME", "google/gemma-4-31B-it"),
            endpoint_context_window=endpoint_context_window,
            endpoint_context_limit_source=endpoint_limit_source,
            application_context_cap=application_context_cap_from_env(),
            base_memory_budget=int(os.getenv("BASE_MEMORY_BUDGET", "4096")),
            memory_recall_budget_tokens=int(
                os.getenv("MEMORY_RECALL_BUDGET_TOKENS", "8192")
            ),
            chat_memory_cap=int(os.getenv("CHAT_MEMORY_CAP", "8192")),
            document_memory_cap=int(os.getenv("DOCUMENT_MEMORY_CAP", "16384")),
            multi_scope_memory_cap=int(
                os.getenv("MULTI_SCOPE_MEMORY_CAP", "16384")
            ),
            long_document_memory_cap=int(
                os.getenv("LONG_DOCUMENT_MEMORY_CAP", "32768")
            ),
            global_summary_budget_tokens=int(
                os.getenv("GLOBAL_SUMMARY_BUDGET_TOKENS", "65536")
            ),
            global_summary_max_budget_tokens=int(
                os.getenv("GLOBAL_SUMMARY_MAX_BUDGET_TOKENS", "131072")
            ),
            global_summary_reserved_tokens=int(
                os.getenv("GLOBAL_SUMMARY_RESERVED_TOKENS", "4096")
            ),
            required_evidence_headroom_ratio=float(
                os.getenv("REQUIRED_EVIDENCE_HEADROOM_RATIO", "0.25")
            ),
            minimum_optional_candidate_utility=float(
                os.getenv("MIN_OPTIONAL_CANDIDATE_UTILITY", "0.15")
            ),
            gist_retrieval_candidates=int(
                os.getenv("GIST_RETRIEVAL_CANDIDATES", "8")
            ),
            direct_raw_retrieval_candidates=int(
                os.getenv("DIRECT_RAW_RETRIEVAL_CANDIDATES", "12")
            ),
            raw_span_overlap_threshold=float(
                os.getenv("RAW_SPAN_OVERLAP_THRESHOLD", "0.7")
            ),
            enable_retrieval_query_simplification=env_bool(
                "ENABLE_RETRIEVAL_QUERY_SIMPLIFICATION",
                default=True,
            ),
            database_path=Path(os.getenv("DATABASE_PATH", "data/chatbot.db")),
            raw_message_limit=int(os.getenv("RAW_MESSAGE_LIMIT", str(RAW_MESSAGE_LIMIT))),
            memory_update_batch_size=int(
                os.getenv(
                    "MEMORY_UPDATE_BATCH_SIZE",
                    os.getenv("SUMMARY_BATCH_SIZE", str(MEMORY_UPDATE_BATCH_SIZE)),
                )
            ),
            recent_messages_max_count=int(
                os.getenv(
                    "RECENT_MESSAGES_MAX_COUNT",
                    str(RECENT_MESSAGES_MAX_COUNT),
                )
            ),
            memory_update_trigger_tokens=int(
                os.getenv(
                    "MEMORY_UPDATE_TRIGGER_TOKENS",
                    str(MEMORY_UPDATE_TRIGGER_TOKENS),
                )
            ),
            memory_update_max_input_tokens=int(
                os.getenv(
                    "MEMORY_UPDATE_MAX_INPUT_TOKENS",
                    str(MEMORY_UPDATE_MAX_INPUT_TOKENS),
                )
            ),
            memory_update_max_messages=int(
                os.getenv(
                    "MEMORY_UPDATE_MAX_MESSAGES",
                    os.getenv(
                        "MEMORY_UPDATE_BATCH_SIZE",
                        os.getenv(
                            "SUMMARY_BATCH_SIZE",
                            str(MEMORY_UPDATE_MAX_MESSAGES),
                        ),
                    ),
                )
            ),
            memory_recent_protection_tokens=int(
                os.getenv(
                    "MEMORY_RECENT_PROTECTION_TOKENS",
                    str(MEMORY_RECENT_PROTECTION_TOKENS),
                )
            ),
            memory_update_policy=os.getenv(
                "MEMORY_UPDATE_POLICY",
                "scheduled",
            ).strip().lower(),
            memory_replay_trigger_tokens=int(
                os.getenv(
                    "MEMORY_REPLAY_TRIGGER_TOKENS",
                    str(MEMORY_REPLAY_TRIGGER_TOKENS),
                )
            ),
            memory_replay_max_input_tokens=int(
                os.getenv(
                    "MEMORY_REPLAY_MAX_INPUT_TOKENS",
                    str(MEMORY_REPLAY_MAX_INPUT_TOKENS),
                )
            ),
            memory_replay_max_messages=int(
                os.getenv(
                    "MEMORY_REPLAY_MAX_MESSAGES",
                    str(MEMORY_REPLAY_MAX_MESSAGES),
                )
            ),
            document_retrieval_mode=os.getenv("DOCUMENT_RETRIEVAL_MODE", "langchain_chroma"),
            embedding_model_name=os.getenv(
                "EMBEDDING_MODEL_NAME",
                "sentence-transformers/all-MiniLM-L6-v2",
            ),
            document_top_k=int(os.getenv("DOCUMENT_TOP_K", "8")),
            document_chunker=os.getenv("DOCUMENT_CHUNKER", "custom"),
            document_chunk_size=int(os.getenv("DOCUMENT_CHUNK_SIZE", "1000")),
            document_chunk_overlap=int(os.getenv("DOCUMENT_CHUNK_OVERLAP", "150")),
            langchain_chroma_persist_dir=Path(
                os.getenv("LANGCHAIN_CHROMA_PERSIST_DIR", "data/chroma")
            ),
            langchain_chunk_size=int(os.getenv("LANGCHAIN_CHUNK_SIZE", "1000")),
            langchain_chunk_overlap=int(os.getenv("LANGCHAIN_CHUNK_OVERLAP", "150")),
            orchestration_mode=os.getenv(
                "ORCHESTRATION_MODE",
                "langgraph_demo",
            ).strip().lower(),
            routing_mode=os.getenv("ROUTING_MODE", "rule").strip().lower(),
            reranker_mode=os.getenv(
                "RERANKER_MODE",
                "deterministic",
            ).strip().lower(),
            reranker_llm_top_k=int(os.getenv("RERANKER_LLM_TOP_K", "10")),
            reranker_llm_min_confidence=float(
                os.getenv("RERANKER_LLM_MIN_CONFIDENCE", "0.55")
            ),
            reranker_cross_encoder_model=os.getenv(
                "RERANKER_CROSS_ENCODER_MODEL",
                "BAAI/bge-reranker-v2-m3",
            ),
            reranker_cross_encoder_top_k=int(
                os.getenv("RERANKER_CROSS_ENCODER_TOP_K", "10")
            ),
            reranker_cross_encoder_weight=float(
                os.getenv("RERANKER_CROSS_ENCODER_WEIGHT", "0.65")
            ),
            reranker_hybrid_backend=os.getenv(
                "RERANKER_HYBRID_BACKEND",
                "auto",
            ).strip().lower(),
            reranker_llm_ambiguity_margin=float(
                os.getenv("RERANKER_LLM_AMBIGUITY_MARGIN", "0.15")
            ),
            reranker_llm_require_cross_source_conflict=env_bool(
                "RERANKER_LLM_REQUIRE_CROSS_SOURCE_CONFLICT",
                default=True,
            ),
            reranker_llm_provenance_queries=env_bool(
                "RERANKER_LLM_PROVENANCE_QUERIES",
                default=True,
            ),
            structured_memory_retrieval_mode=os.getenv(
                "STRUCTURED_MEMORY_RETRIEVAL_MODE",
                "sqlite",
            ).strip().lower(),
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
            current_chat_gist_generation_enabled=env_bool(
                "CURRENT_CHAT_GIST_GENERATION_ENABLED",
                default=False,
            ),
            previous_chat_gist_generation_enabled=env_bool(
                "PREVIOUS_CHAT_GIST_GENERATION_ENABLED",
                default=False,
            ),
            previous_chat_gist_retrieval_enabled=env_bool(
                "PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED",
                default=True,
            ),
            previous_chat_gist_extractor=normalize_previous_chat_gist_extractor(
                os.getenv("PREVIOUS_CHAT_GIST_EXTRACTOR", "deterministic")
            ),
            previous_chat_gist_max_messages_per_gist=int(
                os.getenv("PREVIOUS_CHAT_GIST_MAX_MESSAGES_PER_GIST", "30")
            ),
        )


def env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean-like environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def normalize_previous_chat_gist_extractor(value: str) -> str:
    """Return a supported previous-chat gist extractor mode."""
    normalized = value.strip().lower()
    return normalized if normalized in {"deterministic", "llm"} else "deterministic"
