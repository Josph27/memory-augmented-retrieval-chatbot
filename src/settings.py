"""Canonical application settings — the single source of truth.

Edit this file to change application configuration.  Secrets and per-developer
values (API keys, URLs, credentials) live in .env; everything else is set here
and pushed into os.environ so the rest of the codebase picks it up.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _setenv(name: str, value: str) -> None:
    """Set an env var if not already present (env overrides settings)."""
    os.environ.setdefault(name, value)


# ═══════════════════════════════════════════════════════════════════════════════
# Secrets — read from environment only (set in .env, not here).
# ═══════════════════════════════════════════════════════════════════════════════

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "dummy")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
MODEL_NAME: str = os.getenv("MODEL_NAME", "google/gemma-4-31B-it")

# ═══════════════════════════════════════════════════════════════════════════════
# Database
# ═══════════════════════════════════════════════════════════════════════════════

DATABASE_PATH: str = "data/chatbot.db"

# ═══════════════════════════════════════════════════════════════════════════════
# Message / Short-Term Memory Limits
# ═══════════════════════════════════════════════════════════════════════════════

RAW_MESSAGE_LIMIT: int = 8
RECENT_MESSAGES_MAX_COUNT: int = 8

# ═══════════════════════════════════════════════════════════════════════════════
# Structured Memory Update Scheduling
# ═══════════════════════════════════════════════════════════════════════════════

MEMORY_UPDATE_POLICY: str = "agentic_each_turn"  # scheduled | agentic_each_turn | chat_end_only
MEMORY_UPDATE_BATCH_SIZE: int = 6
MEMORY_UPDATE_TRIGGER_TOKENS: int = 1000
MEMORY_UPDATE_MAX_INPUT_TOKENS: int = 4000
MEMORY_UPDATE_MAX_MESSAGES: int = 64
MEMORY_RECENT_PROTECTION_TOKENS: int = 1500
MEMORY_REPLAY_TRIGGER_TOKENS: int = 4000
MEMORY_REPLAY_MAX_INPUT_TOKENS: int = 8000
MEMORY_REPLAY_MAX_MESSAGES: int = 128

# ═══════════════════════════════════════════════════════════════════════════════
# Document Ingestion & Retrieval
# ═══════════════════════════════════════════════════════════════════════════════

DOCUMENT_RETRIEVAL_MODE: str = "langchain_chroma"
DOCUMENT_CHUNKER: str = "custom"
DOCUMENT_CHUNK_SIZE: int = 256
DOCUMENT_CHUNK_OVERLAP: int = 56
DOCUMENT_TOP_K: int = 40
EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"

# Chroma storage
LANGCHAIN_CHROMA_PERSIST_DIR: str = "data/chroma"
LANGCHAIN_CHUNK_SIZE: int = 256
LANGCHAIN_CHUNK_OVERLAP: int = 56

# ═══════════════════════════════════════════════════════════════════════════════
# Structured Memory Retrieval
# ═══════════════════════════════════════════════════════════════════════════════

STRUCTURED_MEMORY_RETRIEVAL_MODE: str = "hybrid"  # sqlite | vector | hybrid
LONG_TERM_MEMORY_CHROMA_PERSIST_DIR: str = "data/chroma"
LONG_TERM_MEMORY_COLLECTION: str = "long_term_memory"

# ═══════════════════════════════════════════════════════════════════════════════
# Reranker
# ═══════════════════════════════════════════════════════════════════════════════

RERANKER_MODE: str = "cross_encoder"  # deterministic | cross_encoder | hybrid | llm
RERANKER_CROSS_ENCODER_MODEL: str = "BAAI/bge-reranker-v2-m3"
RERANKER_CROSS_ENCODER_TOP_K: int = 10
RERANKER_CROSS_ENCODER_WEIGHT: float = 0.65
RERANKER_HYBRID_BACKEND: str = "auto"  # auto | cross_encoder | llm
RERANKER_LLM_TOP_K: int = 10
RERANKER_LLM_MIN_CONFIDENCE: float = 0.55
RERANKER_LLM_AMBIGUITY_MARGIN: float = 0.15
RERANKER_LLM_REQUIRE_CROSS_SOURCE_CONFLICT: bool = True
RERANKER_LLM_PROVENANCE_QUERIES: bool = True

# ═══════════════════════════════════════════════════════════════════════════════
# Routing
# ═══════════════════════════════════════════════════════════════════════════════

ROUTING_MODE: str = "hybrid"  # rule | llm | hybrid
ORCHESTRATION_MODE: str = "langgraph_demo"  # native | langgraph_demo | compare

# ═══════════════════════════════════════════════════════════════════════════════
# Context Budget
# ═══════════════════════════════════════════════════════════════════════════════

BASE_MEMORY_BUDGET: int = 4096
MEMORY_RECALL_BUDGET_TOKENS: int = 8192
CHAT_MEMORY_CAP: int = 8192
DOCUMENT_MEMORY_CAP: int = 16_384
MULTI_SCOPE_MEMORY_CAP: int = 16_384
LONG_DOCUMENT_MEMORY_CAP: int = 32_768
GLOBAL_SUMMARY_BUDGET_TOKENS: int = 65_536
GLOBAL_SUMMARY_MAX_BUDGET_TOKENS: int = 131_072
GLOBAL_SUMMARY_RESERVED_TOKENS: int = 4096
REQUIRED_EVIDENCE_HEADROOM_RATIO: float = 0.25
MINIMUM_OPTIONAL_CANDIDATE_UTILITY: float = 0.15

# ═══════════════════════════════════════════════════════════════════════════════
# Gist Retrieval
# ═══════════════════════════════════════════════════════════════════════════════

GIST_RETRIEVAL_CANDIDATES: int = 8

# ═══════════════════════════════════════════════════════════════════════════════
# Raw Message Span Retrieval
# ═══════════════════════════════════════════════════════════════════════════════

DIRECT_RAW_RETRIEVAL_CANDIDATES: int = 12
RAW_SPAN_OVERLAP_THRESHOLD: float = 0.7
ENABLE_RETRIEVAL_QUERY_SIMPLIFICATION: bool = True

# ═══════════════════════════════════════════════════════════════════════════════
# Gist Generation
# ═══════════════════════════════════════════════════════════════════════════════

CURRENT_CHAT_GIST_GENERATION_ENABLED: bool = False
PREVIOUS_CHAT_GIST_GENERATION_ENABLED: bool = True
PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED: bool = True
PREVIOUS_CHAT_GIST_EXTRACTOR: str = "llm"  # deterministic | llm
PREVIOUS_CHAT_GIST_MAX_MESSAGES_PER_GIST: int = 5

# ═══════════════════════════════════════════════════════════════════════════════
# Demo / Debug
# ═══════════════════════════════════════════════════════════════════════════════

DEMO_MEMORY_TRACE: bool = False

# ═══════════════════════════════════════════════════════════════════════════════
# Push all settings into os.environ so downstream os.getenv() calls see them.
# .env values take priority (setdefault does not override existing vars).
# ═══════════════════════════════════════════════════════════════════════════════

_setenv("DATABASE_PATH", DATABASE_PATH)
_setenv("RAW_MESSAGE_LIMIT", str(RAW_MESSAGE_LIMIT))
_setenv("RECENT_MESSAGES_MAX_COUNT", str(RECENT_MESSAGES_MAX_COUNT))
_setenv("MEMORY_UPDATE_POLICY", MEMORY_UPDATE_POLICY)
_setenv("MEMORY_UPDATE_BATCH_SIZE", str(MEMORY_UPDATE_BATCH_SIZE))
_setenv("MEMORY_UPDATE_TRIGGER_TOKENS", str(MEMORY_UPDATE_TRIGGER_TOKENS))
_setenv("MEMORY_UPDATE_MAX_INPUT_TOKENS", str(MEMORY_UPDATE_MAX_INPUT_TOKENS))
_setenv("MEMORY_UPDATE_MAX_MESSAGES", str(MEMORY_UPDATE_MAX_MESSAGES))
_setenv("MEMORY_RECENT_PROTECTION_TOKENS", str(MEMORY_RECENT_PROTECTION_TOKENS))
_setenv("MEMORY_REPLAY_TRIGGER_TOKENS", str(MEMORY_REPLAY_TRIGGER_TOKENS))
_setenv("MEMORY_REPLAY_MAX_INPUT_TOKENS", str(MEMORY_REPLAY_MAX_INPUT_TOKENS))
_setenv("MEMORY_REPLAY_MAX_MESSAGES", str(MEMORY_REPLAY_MAX_MESSAGES))
_setenv("DOCUMENT_RETRIEVAL_MODE", DOCUMENT_RETRIEVAL_MODE)
_setenv("DOCUMENT_CHUNKER", DOCUMENT_CHUNKER)
_setenv("DOCUMENT_CHUNK_SIZE", str(DOCUMENT_CHUNK_SIZE))
_setenv("DOCUMENT_CHUNK_OVERLAP", str(DOCUMENT_CHUNK_OVERLAP))
_setenv("DOCUMENT_TOP_K", str(DOCUMENT_TOP_K))
_setenv("EMBEDDING_MODEL_NAME", EMBEDDING_MODEL_NAME)
_setenv("LANGCHAIN_CHROMA_PERSIST_DIR", LANGCHAIN_CHROMA_PERSIST_DIR)
_setenv("LANGCHAIN_CHUNK_SIZE", str(LANGCHAIN_CHUNK_SIZE))
_setenv("LANGCHAIN_CHUNK_OVERLAP", str(LANGCHAIN_CHUNK_OVERLAP))
_setenv("STRUCTURED_MEMORY_RETRIEVAL_MODE", STRUCTURED_MEMORY_RETRIEVAL_MODE)
_setenv("LONG_TERM_MEMORY_CHROMA_PERSIST_DIR", LONG_TERM_MEMORY_CHROMA_PERSIST_DIR)
_setenv("LONG_TERM_MEMORY_COLLECTION", LONG_TERM_MEMORY_COLLECTION)
_setenv("RERANKER_MODE", RERANKER_MODE)
_setenv("RERANKER_CROSS_ENCODER_MODEL", RERANKER_CROSS_ENCODER_MODEL)
_setenv("RERANKER_CROSS_ENCODER_TOP_K", str(RERANKER_CROSS_ENCODER_TOP_K))
_setenv("RERANKER_CROSS_ENCODER_WEIGHT", str(RERANKER_CROSS_ENCODER_WEIGHT))
_setenv("RERANKER_HYBRID_BACKEND", RERANKER_HYBRID_BACKEND)
_setenv("RERANKER_LLM_TOP_K", str(RERANKER_LLM_TOP_K))
_setenv("RERANKER_LLM_MIN_CONFIDENCE", str(RERANKER_LLM_MIN_CONFIDENCE))
_setenv("RERANKER_LLM_AMBIGUITY_MARGIN", str(RERANKER_LLM_AMBIGUITY_MARGIN))
_setenv(
    "RERANKER_LLM_REQUIRE_CROSS_SOURCE_CONFLICT",
    "1" if RERANKER_LLM_REQUIRE_CROSS_SOURCE_CONFLICT else "0",
)
_setenv("RERANKER_LLM_PROVENANCE_QUERIES", "1" if RERANKER_LLM_PROVENANCE_QUERIES else "0")
_setenv("ROUTING_MODE", ROUTING_MODE)
_setenv("ORCHESTRATION_MODE", ORCHESTRATION_MODE)
_setenv("BASE_MEMORY_BUDGET", str(BASE_MEMORY_BUDGET))
_setenv("MEMORY_RECALL_BUDGET_TOKENS", str(MEMORY_RECALL_BUDGET_TOKENS))
_setenv("GLOBAL_SUMMARY_BUDGET_TOKENS", str(GLOBAL_SUMMARY_BUDGET_TOKENS))
_setenv("GLOBAL_SUMMARY_MAX_BUDGET_TOKENS", str(GLOBAL_SUMMARY_MAX_BUDGET_TOKENS))
_setenv("GLOBAL_SUMMARY_RESERVED_TOKENS", str(GLOBAL_SUMMARY_RESERVED_TOKENS))
_setenv("REQUIRED_EVIDENCE_HEADROOM_RATIO", str(REQUIRED_EVIDENCE_HEADROOM_RATIO))
_setenv("MINIMUM_OPTIONAL_CANDIDATE_UTILITY", str(MINIMUM_OPTIONAL_CANDIDATE_UTILITY))
_setenv("GIST_RETRIEVAL_CANDIDATES", str(GIST_RETRIEVAL_CANDIDATES))
_setenv("DIRECT_RAW_RETRIEVAL_CANDIDATES", str(DIRECT_RAW_RETRIEVAL_CANDIDATES))
_setenv("RAW_SPAN_OVERLAP_THRESHOLD", str(RAW_SPAN_OVERLAP_THRESHOLD))
_setenv(
    "ENABLE_RETRIEVAL_QUERY_SIMPLIFICATION", "1" if ENABLE_RETRIEVAL_QUERY_SIMPLIFICATION else "0"
)
_setenv(
    "CURRENT_CHAT_GIST_GENERATION_ENABLED", "1" if CURRENT_CHAT_GIST_GENERATION_ENABLED else "0"
)
_setenv(
    "PREVIOUS_CHAT_GIST_GENERATION_ENABLED", "1" if PREVIOUS_CHAT_GIST_GENERATION_ENABLED else "0"
)
_setenv(
    "PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED", "1" if PREVIOUS_CHAT_GIST_RETRIEVAL_ENABLED else "0"
)
_setenv("PREVIOUS_CHAT_GIST_EXTRACTOR", PREVIOUS_CHAT_GIST_EXTRACTOR)
_setenv("PREVIOUS_CHAT_GIST_MAX_MESSAGES_PER_GIST", str(PREVIOUS_CHAT_GIST_MAX_MESSAGES_PER_GIST))
_setenv("DEMO_MEMORY_TRACE", "1" if DEMO_MEMORY_TRACE else "0")
_setenv("CHAT_DOCUMENT_SCOPE_STICKY", "true")
