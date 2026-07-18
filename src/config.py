"""Runtime configuration — a frozen snapshot of all application settings.

Reads canonical defaults from src.settings and allows limited environment
overrides for secrets and operational overrides.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from src import settings
from src.context.model_profile import (
    application_context_cap_from_env,
    endpoint_context_limit_from_env,
)


@dataclass(frozen=True)
class AppConfig:
    """Frozen runtime configuration snapshot."""

    # ── secrets ──
    openai_api_key: str
    openai_base_url: str
    model_name: str

    # ── context limits ──
    endpoint_context_window: int | None
    endpoint_context_limit_source: str | None
    application_context_cap: int

    # ── memory budget ──
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

    # ── retrieval ──
    gist_retrieval_candidates: int
    direct_raw_retrieval_candidates: int
    raw_span_overlap_threshold: float
    enable_retrieval_query_simplification: bool

    # ── database ──
    database_path: Path

    # ── short-term memory ──
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

    # ── document retrieval ──
    document_retrieval_mode: str
    embedding_model_name: str
    document_top_k: int
    document_chunker: str
    document_chunk_size: int
    document_chunk_overlap: int
    langchain_chroma_persist_dir: Path
    langchain_chunk_size: int
    langchain_chunk_overlap: int

    # ── orchestration / routing ──
    orchestration_mode: str
    routing_mode: str

    # ── reranker ──
    reranker_mode: str
    reranker_llm_top_k: int
    reranker_llm_min_confidence: float
    reranker_cross_encoder_model: str
    reranker_cross_encoder_weight: float
    reranker_hybrid_backend: str
    reranker_llm_ambiguity_margin: float
    reranker_llm_require_cross_source_conflict: bool
    reranker_llm_provenance_queries: bool

    # ── structured memory ──
    structured_memory_retrieval_mode: str

    # ── gists ──
    current_chat_gist_generation_enabled: bool
    previous_chat_gist_generation_enabled: bool
    previous_chat_gist_retrieval_enabled: bool
    previous_chat_gist_extractor: str
    previous_chat_gist_max_messages_per_gist: int

    # ── debug ──
    retrieval_log_enabled: bool

    @classmethod
    def load(cls) -> "AppConfig":
        """Build a frozen config snapshot from canonical settings.

        Environment variables only override secrets and a small set of
        operational knobs (MODEL_NAME, DATABASE_PATH).  Everything else
        reads from src/settings.py — edit that file to change defaults.
        """
        endpoint_context_window, endpoint_limit_source = endpoint_context_limit_from_env()
        return cls(
            # ── secrets ──
            openai_api_key=settings.OPENAI_API_KEY,
            openai_base_url=settings.OPENAI_BASE_URL,
            model_name=settings.MODEL_NAME,
            # ── context limits ──
            endpoint_context_window=endpoint_context_window,
            endpoint_context_limit_source=endpoint_limit_source,
            application_context_cap=application_context_cap_from_env(),
            # ── memory budget ──
            base_memory_budget=settings.BASE_MEMORY_BUDGET,
            memory_recall_budget_tokens=settings.MEMORY_RECALL_BUDGET_TOKENS,
            chat_memory_cap=settings.CHAT_MEMORY_CAP,
            document_memory_cap=settings.DOCUMENT_MEMORY_CAP,
            multi_scope_memory_cap=settings.MULTI_SCOPE_MEMORY_CAP,
            long_document_memory_cap=settings.LONG_DOCUMENT_MEMORY_CAP,
            global_summary_budget_tokens=settings.GLOBAL_SUMMARY_BUDGET_TOKENS,
            global_summary_max_budget_tokens=settings.GLOBAL_SUMMARY_MAX_BUDGET_TOKENS,
            global_summary_reserved_tokens=settings.GLOBAL_SUMMARY_RESERVED_TOKENS,
            required_evidence_headroom_ratio=settings.REQUIRED_EVIDENCE_HEADROOM_RATIO,
            minimum_optional_candidate_utility=settings.MINIMUM_OPTIONAL_CANDIDATE_UTILITY,
            # ── retrieval ──
            gist_retrieval_candidates=settings.GIST_RETRIEVAL_CANDIDATES,
            direct_raw_retrieval_candidates=settings.DIRECT_RAW_RETRIEVAL_CANDIDATES,
            raw_span_overlap_threshold=settings.RAW_SPAN_OVERLAP_THRESHOLD,
            enable_retrieval_query_simplification=settings.ENABLE_RETRIEVAL_QUERY_SIMPLIFICATION,
            # ── database ──
            database_path=Path(os.getenv("DATABASE_PATH", settings.DATABASE_PATH)),
            # ── short-term memory ──
            raw_message_limit=settings.RAW_MESSAGE_LIMIT,
            memory_update_batch_size=settings.MEMORY_UPDATE_BATCH_SIZE,
            recent_messages_max_count=settings.RECENT_MESSAGES_MAX_COUNT,
            memory_update_trigger_tokens=settings.MEMORY_UPDATE_TRIGGER_TOKENS,
            memory_update_max_input_tokens=settings.MEMORY_UPDATE_MAX_INPUT_TOKENS,
            memory_update_max_messages=settings.MEMORY_UPDATE_MAX_MESSAGES,
            memory_recent_protection_tokens=settings.MEMORY_RECENT_PROTECTION_TOKENS,
            memory_update_policy=settings.MEMORY_UPDATE_POLICY,
            memory_replay_trigger_tokens=settings.MEMORY_REPLAY_TRIGGER_TOKENS,
            memory_replay_max_input_tokens=settings.MEMORY_REPLAY_MAX_INPUT_TOKENS,
            memory_replay_max_messages=settings.MEMORY_REPLAY_MAX_MESSAGES,
            # ── document retrieval ──
            document_retrieval_mode=settings.DOCUMENT_RETRIEVAL_MODE,
            embedding_model_name=settings.EMBEDDING_MODEL_NAME,
            document_top_k=settings.DOCUMENT_TOP_K,
            document_chunker=settings.DOCUMENT_CHUNKER,
            document_chunk_size=settings.DOCUMENT_CHUNK_SIZE,
            document_chunk_overlap=settings.DOCUMENT_CHUNK_OVERLAP,
            langchain_chroma_persist_dir=Path(settings.LANGCHAIN_CHROMA_PERSIST_DIR),
            langchain_chunk_size=settings.LANGCHAIN_CHUNK_SIZE,
            langchain_chunk_overlap=settings.LANGCHAIN_CHUNK_OVERLAP,
            # ── orchestration / routing ──
            orchestration_mode=settings.ORCHESTRATION_MODE,
            routing_mode=settings.ROUTING_MODE,
            # ── reranker ──
            reranker_mode=settings.RERANKER_MODE,
            reranker_llm_top_k=settings.RERANKER_LLM_TOP_K,
            reranker_llm_min_confidence=settings.RERANKER_LLM_MIN_CONFIDENCE,
            reranker_cross_encoder_model=settings.RERANKER_CROSS_ENCODER_MODEL,
            reranker_cross_encoder_weight=settings.RERANKER_CROSS_ENCODER_WEIGHT,
            reranker_hybrid_backend=settings.RERANKER_HYBRID_BACKEND,
            reranker_llm_ambiguity_margin=settings.RERANKER_LLM_AMBIGUITY_MARGIN,
            reranker_llm_require_cross_source_conflict=(
                settings.RERANKER_LLM_REQUIRE_CROSS_SOURCE_CONFLICT
            ),
            reranker_llm_provenance_queries=settings.RERANKER_LLM_PROVENANCE_QUERIES,
            # ── structured memory ──
            structured_memory_retrieval_mode=settings.STRUCTURED_MEMORY_RETRIEVAL_MODE,
            # ── gists ──
            current_chat_gist_generation_enabled=(settings.CURRENT_CHAT_GIST_GENERATION_ENABLED),
            previous_chat_gist_generation_enabled=(settings.PREVIOUS_CHAT_GIST_GENERATION_ENABLED),
            previous_chat_gist_retrieval_enabled=(settings.PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED),
            previous_chat_gist_extractor=settings.PREVIOUS_CHAT_GIST_EXTRACTOR,
            previous_chat_gist_max_messages_per_gist=(
                settings.PREVIOUS_CHAT_GIST_MAX_MESSAGES_PER_GIST
            ),
            # ── debug ──
            retrieval_log_enabled=settings.RETRIEVAL_LOG_ENABLED,
        )

    # Backward-compatible alias — some callers may still reference from_env.
    from_env = load
