from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from openai import OpenAIError

from src.agents.chat_agent import ChatAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.context_manager_agent import ContextManagerAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.document_ingestion_agent import DocumentIngestionAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.core.contracts import AgentTurnResult
from src.context.model_profile import DEFAULT_GEMMA_APPLICATION_CONTEXT_CAP
from src.context.dynamic_budget import MemoryBudgetPolicy
from src.database import Database
from src.memory.previous_chat_gist import PreviousChatGistGenerator
from src.memory.short_term import ShortTermMemory
from src.model_wrapper import ModelWrapper
from src.retrieval.reranker import MemoryReranker
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.routing_agent import RoutingAgent


SYSTEM_PROMPT = (
    "You are a concise, helpful chatbot prototype. Use the structured current-chat memory "
    "and recent messages as short-term memory. Answer directly when the supplied context "
    "provides sufficient evidence. Use “I don't know” only when the available context does "
    "not support an answer. Do not ignore explicit contextual evidence merely because it "
    "conflicts with prior world knowledge. If supplied context contains unresolved "
    "conflicting claims, state the conflict rather than choosing arbitrarily. If evidence "
    "is partial, answer only the supported portion and state the limitation. If information "
    "is missing, say what you need "
    "instead of inventing facts."
)


@dataclass(frozen=True)
class DocumentFileIndexResult:
    """Status returned after indexing an uploaded local file."""

    file_name: str
    document_id: str
    chunk_count: int


class ChatService:
    """Coordinates database persistence, short-term memory, and model calls."""

    def __init__(
        self,
        database: Database,
        model: ModelWrapper,
        raw_message_limit: int,
        memory_update_batch_size: int,
        recent_messages_max_count: int | None = None,
        memory_update_trigger_tokens: int = 1000,
        memory_update_max_input_tokens: int = 4000,
        memory_update_max_messages: int | None = None,
        memory_recent_protection_tokens: int = 1500,
        memory_replay_trigger_tokens: int = 4000,
        memory_replay_max_input_tokens: int = 8000,
        memory_replay_max_messages: int = 128,
        document_indexer: object | None = None,
        routing_mode: str = "rule",
        reranker_mode: str = "deterministic",
        reranker_llm_top_k: int = 10,
        reranker_llm_min_confidence: float = 0.55,
        reranker_cross_encoder_model: str = "BAAI/bge-reranker-v2-m3",
        reranker_cross_encoder_top_k: int = 10,
        reranker_cross_encoder_weight: float = 0.65,
        reranker_hybrid_backend: str = "auto",
        reranker_llm_ambiguity_margin: float = 0.15,
        reranker_llm_require_cross_source_conflict: bool = True,
        reranker_llm_provenance_queries: bool = True,
        previous_chat_gist_generation_enabled: bool = False,
        previous_chat_gist_generator: PreviousChatGistGenerator | None = None,
        endpoint_context_window: int | None = None,
        endpoint_context_limit_source: str | None = None,
        application_context_cap: int = DEFAULT_GEMMA_APPLICATION_CONTEXT_CAP,
        base_memory_budget: int = 4096,
        memory_recall_budget_tokens: int = 8192,
        chat_memory_cap: int = 8192,
        document_memory_cap: int = 16_384,
        multi_scope_memory_cap: int = 16_384,
        long_document_memory_cap: int = 32_768,
        global_summary_budget_tokens: int = 65_536,
        global_summary_max_budget_tokens: int = 131_072,
        global_summary_reserved_tokens: int = 4096,
        required_evidence_headroom_ratio: float = 0.25,
        minimum_optional_candidate_utility: float = 0.15,
        direct_raw_retrieval_candidates: int = 12,
        raw_span_overlap_threshold: float = 0.7,
    ) -> None:
        self.database = database
        self.model = model
        self.document_indexer = document_indexer
        self.routing_mode = routing_mode
        self.reranker_mode = reranker_mode
        self.previous_chat_gist_generation_enabled = previous_chat_gist_generation_enabled
        self.previous_chat_gist_generator = previous_chat_gist_generator
        self.document_ingestion_agent = DocumentIngestionAgent(
            indexer=document_indexer,
        )
        self.memory = ShortTermMemory(
            database=database,
            model=model,
            raw_message_limit=raw_message_limit,
            memory_update_batch_size=memory_update_batch_size,
            recent_messages_max_count=recent_messages_max_count,
            memory_update_trigger_tokens=memory_update_trigger_tokens,
            memory_update_max_input_tokens=memory_update_max_input_tokens,
            memory_update_max_messages=memory_update_max_messages,
            memory_recent_protection_tokens=memory_recent_protection_tokens,
            memory_replay_trigger_tokens=memory_replay_trigger_tokens,
            memory_replay_max_input_tokens=memory_replay_max_input_tokens,
            memory_replay_max_messages=memory_replay_max_messages,
        )
        self.coordinator = CoordinatorAgent(
            database=database,
            memory_agent=ShortTermMemoryAgent(self.memory),
            context_builder=ContextBuilderAgent(self.memory),
            chat_agent=ChatAgent(model),
            system_prompt=SYSTEM_PROMPT,
            retriever_dispatcher=RetrieverDispatcher(
                database=database,
                raw_message_limit=(
                    recent_messages_max_count
                    if recent_messages_max_count is not None
                    else raw_message_limit
                ),
                direct_raw_candidate_limit=direct_raw_retrieval_candidates,
            ),
            routing_agent=RoutingAgent(mode=routing_mode, model=model),
            memory_reranker=MemoryReranker(
                mode=reranker_mode,
                model=model if reranker_mode in {"hybrid", "llm"} else None,
                llm_top_k=reranker_llm_top_k,
                llm_min_confidence=reranker_llm_min_confidence,
                cross_encoder_model=reranker_cross_encoder_model,
                cross_encoder_top_k=reranker_cross_encoder_top_k,
                cross_encoder_weight=reranker_cross_encoder_weight,
                hybrid_backend=reranker_hybrid_backend,
                llm_ambiguity_margin=reranker_llm_ambiguity_margin,
                llm_require_cross_source_conflict=(
                    reranker_llm_require_cross_source_conflict
                ),
                llm_provenance_queries=reranker_llm_provenance_queries,
            ),
            context_manager_agent=ContextManagerAgent.for_model(
                getattr(model, "model_name", "unknown"),
                endpoint_context_window=endpoint_context_window,
                application_context_cap=application_context_cap,
                endpoint_limit_source=endpoint_context_limit_source,
                memory_budget_policy=MemoryBudgetPolicy(
                    base_memory_budget=base_memory_budget,
                    memory_recall_budget_tokens=memory_recall_budget_tokens,
                    chat_memory_cap=chat_memory_cap,
                    document_memory_cap=document_memory_cap,
                    multi_scope_memory_cap=multi_scope_memory_cap,
                    long_document_memory_cap=long_document_memory_cap,
                    global_summary_budget_tokens=global_summary_budget_tokens,
                    global_summary_max_budget_tokens=(
                        global_summary_max_budget_tokens
                    ),
                    global_summary_reserved_tokens=global_summary_reserved_tokens,
                    required_evidence_headroom_ratio=(
                        required_evidence_headroom_ratio
                    ),
                ),
                minimum_optional_candidate_utility=(
                    minimum_optional_candidate_utility
                ),
                raw_span_overlap_threshold=raw_span_overlap_threshold,
            ),
        )

    def start_chat(self, chat_id: str | None = None) -> str:
        """Create a chat id for a Chainlit session."""
        chat_id = chat_id or str(uuid4())
        self.database.create_chat(
            chat_id=chat_id,
            title="Chainlit chat",
            model_name=getattr(self.model, "model_name", None),
        )
        if self.previous_chat_gist_generation_enabled:
            generator = self.previous_chat_gist_generator or PreviousChatGistGenerator(
                database=self.database,
                model=self.model,
            )
            generator.generate_for_existing_chats(active_chat_id=chat_id)
        return chat_id

    def ensure_chat_title_from_message(self, chat_id: str, content: str) -> None:
        """Use the first user message as a lightweight thread title."""
        title = content.strip()
        if not title or self.database.message_count(chat_id) > 0:
            return
        if len(title) > 60:
            title = f"{title[:57].rstrip()}..."
        self.database.update_chat_title(chat_id=chat_id, title=title)

    def index_document_file(
        self,
        path: str | Path,
        display_name: str | None = None,
    ) -> DocumentFileIndexResult:
        """Load and index an uploaded local file into document memory."""
        result = self.document_ingestion_agent.index_file(
            path,
            display_name=display_name,
        )
        return DocumentFileIndexResult(
            file_name=result.file_name,
            document_id=result.document_id,
            chunk_count=result.chunk_count,
        )

    def handle_user_message(self, chat_id: str, content: str) -> str:
        """Save a user message, call the model, and save the assistant response."""
        result = self.handle_user_turn(
            chat_id=chat_id,
            content=content,
            defer_post_answer_memory_update=True,
        )
        self.finalize_post_answer_memory_update(chat_id)
        return result.answer

    def handle_user_turn(
        self,
        chat_id: str,
        content: str,
        orchestration_mode: str = "native",
        defer_post_answer_memory_update: bool = False,
    ) -> AgentTurnResult:
        """Run one user turn and return the agent-shaped result."""
        self.ensure_chat_title_from_message(chat_id=chat_id, content=content)
        result = self.coordinator.run_turn(
            chat_id=chat_id,
            content=content,
            orchestration_mode=orchestration_mode,
            perform_memory_update=not defer_post_answer_memory_update,
        )
        if not defer_post_answer_memory_update:
            return result
        return result

    def finalize_post_answer_memory_update(self, chat_id: str) -> bool:
        """Run the synchronous post-answer memory update after visible answer emission."""
        try:
            return self.memory.update_memory_if_needed(chat_id)
        except OpenAIError:
            return False
