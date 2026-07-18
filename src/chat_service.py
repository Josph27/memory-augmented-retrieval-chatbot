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
from src.connection_guard import InferenceServerUnreachable
from src.core.contracts import AgentTurnResult
from src.context.model_profile import DEFAULT_GEMMA_APPLICATION_CONTEXT_CAP
from src.context.dynamic_budget import MemoryBudgetPolicy
from src.database import Database
from src.inspection.answer_inspector import persist_answer_inspection
from src.lifecycle.operation_guard import guarded_chat_operation
from src.memory.chat_gist_summarizer import LLMChatGistExtractor
from src.memory.previous_chat_gist import (
    DeterministicPreviousChatGistExtractor,
    FallbackChatGistExtractor,
    PreviousChatGistGenerator,
)
from src.memory.short_term import ShortTermMemory
from src.model_wrapper import ModelWrapper
from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever
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
        memory_update_policy: str = "scheduled",
        memory_replay_trigger_tokens: int = 4000,
        memory_replay_max_input_tokens: int = 8000,
        memory_replay_max_messages: int = 128,
        document_indexer: object | None = None,
        routing_mode: str = "rule",
        reranker_mode: str = "deterministic",
        reranker_llm_top_k: int = 10,
        reranker_llm_min_confidence: float = 0.55,
        reranker_cross_encoder_model: str = "cross-encoder/ms-marco-MiniLM-L12-v2",
        reranker_cross_encoder_top_k: int = 500,  # effectively "all" — DOCUMENT_RETRIEVAL_FETCH_LIMIT is the real cap
        reranker_cross_encoder_weight: float = 0.65,
        reranker_hybrid_backend: str = "auto",
        reranker_llm_ambiguity_margin: float = 0.15,
        reranker_llm_require_cross_source_conflict: bool = True,
        reranker_llm_provenance_queries: bool = True,
        previous_chat_gist_generation_enabled: bool = False,
        previous_chat_gist_extractor: str = "deterministic",
        previous_chat_gist_max_messages_per_gist: int = 30,
        previous_chat_gist_generator: PreviousChatGistGenerator | None = None,
        endpoint_context_window: int | None = None,
        endpoint_context_limit_source: str | None = None,
        application_context_cap: int = DEFAULT_GEMMA_APPLICATION_CONTEXT_CAP,
        base_memory_budget: int = 4096,
        memory_recall_budget_tokens: int = 8192,
        chat_memory_cap: int = 8192,
        document_memory_cap: int = 49_152,
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
        self.previous_chat_gist_extractor = normalize_previous_chat_gist_extractor(
            previous_chat_gist_extractor
        )
        self.previous_chat_gist_max_messages_per_gist = max(
            1,
            previous_chat_gist_max_messages_per_gist,
        )
        self.previous_chat_gist_generator = previous_chat_gist_generator
        # Share one LangChainChromaRetriever between ingestion and retrieval
        # so the Chroma client + embedding model are initialized only once.
        _shared_doc_retriever = document_indexer or LangChainChromaRetriever.from_env(
            summary_getter=database,
        )
        self.document_ingestion_agent = DocumentIngestionAgent(
            indexer=_shared_doc_retriever,
            summary_model=model,
            summary_database=database,
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
            memory_update_policy=memory_update_policy,
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
                summary_getter=database,
                retrievers={"document_memory": _shared_doc_retriever},
            ),
            routing_agent=RoutingAgent(mode=routing_mode, model=model),
            memory_reranker=self._build_reranker(
                reranker_mode=reranker_mode,
                model=model,
                reranker_llm_top_k=reranker_llm_top_k,
                reranker_llm_min_confidence=reranker_llm_min_confidence,
                reranker_cross_encoder_model=reranker_cross_encoder_model,
                reranker_cross_encoder_top_k=reranker_cross_encoder_top_k,
                reranker_cross_encoder_weight=reranker_cross_encoder_weight,
                reranker_hybrid_backend=reranker_hybrid_backend,
                reranker_llm_ambiguity_margin=reranker_llm_ambiguity_margin,
                reranker_llm_require_cross_source_conflict=reranker_llm_require_cross_source_conflict,
                reranker_llm_provenance_queries=reranker_llm_provenance_queries,
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
                    global_summary_max_budget_tokens=(global_summary_max_budget_tokens),
                    global_summary_reserved_tokens=global_summary_reserved_tokens,
                    required_evidence_headroom_ratio=(required_evidence_headroom_ratio),
                ),
                minimum_optional_candidate_utility=(minimum_optional_candidate_utility),
                raw_span_overlap_threshold=raw_span_overlap_threshold,
            ),
        )

    @staticmethod
    def _build_reranker(
        *,
        reranker_mode: str,
        model: ModelWrapper,
        reranker_llm_top_k: int,
        reranker_llm_min_confidence: float,
        reranker_cross_encoder_model: str,
        reranker_cross_encoder_top_k: int,
        reranker_cross_encoder_weight: float,
        reranker_hybrid_backend: str,
        reranker_llm_ambiguity_margin: float,
        reranker_llm_require_cross_source_conflict: bool,
        reranker_llm_provenance_queries: bool,
    ) -> MemoryReranker:
        """Build the MemoryReranker and preload the cross-encoder eagerly."""
        reranker = MemoryReranker(
            mode=reranker_mode,
            model=model if reranker_mode in {"hybrid", "llm"} else None,
            llm_top_k=reranker_llm_top_k,
            llm_min_confidence=reranker_llm_min_confidence,
            cross_encoder_model=reranker_cross_encoder_model,
            cross_encoder_top_k=reranker_cross_encoder_top_k,
            cross_encoder_weight=reranker_cross_encoder_weight,
            hybrid_backend=reranker_hybrid_backend,
            llm_ambiguity_margin=reranker_llm_ambiguity_margin,
            llm_require_cross_source_conflict=reranker_llm_require_cross_source_conflict,
            llm_provenance_queries=reranker_llm_provenance_queries,
        )
        if reranker_mode in {"cross_encoder", "hybrid"}:
            print("cross_encoder_preload starting...")
            reranker.preload()
            print("cross_encoder_preload complete")
        return reranker

    def start_chat(self, chat_id: str | None = None) -> str:
        """Create a chat id for a Chainlit session."""
        chat_id = chat_id or str(uuid4())
        self.database.create_chat(
            chat_id=chat_id,
            title="Chainlit chat",
            model_name=getattr(self.model, "model_name", None),
        )
        if self.previous_chat_gist_generation_enabled:
            generator = self.previous_chat_gist_generator or (
                self.build_previous_chat_gist_generator()
            )
            generator.generate_for_existing_chats(active_chat_id=chat_id)
        return chat_id

    def build_previous_chat_gist_generator(self) -> PreviousChatGistGenerator:
        """Build the configured previous-chat gist finalizer/generator."""
        if self.previous_chat_gist_extractor == "llm":
            extractor = FallbackChatGistExtractor(
                primary=LLMChatGistExtractor(self.model),
                fallback=DeterministicPreviousChatGistExtractor(),
            )
        else:
            extractor = DeterministicPreviousChatGistExtractor()
        return PreviousChatGistGenerator(
            database=self.database,
            extractor=extractor,
            max_messages_per_gist=self.previous_chat_gist_max_messages_per_gist,
        )

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
        *,
        chat_id: str | None = None,
        operation_id: str | None = None,
    ) -> DocumentFileIndexResult:
        """Persist lifecycle state, index, and associate one uploaded document."""
        if chat_id is None:
            result = self.document_ingestion_agent.index_file(
                path,
                display_name=display_name,
            )
            return DocumentFileIndexResult(
                file_name=result.file_name,
                document_id=result.document_id,
                chunk_count=result.chunk_count,
            )

        with guarded_chat_operation(self.database.path, chat_id):
            file_name = display_name or Path(path).name
            previous_operation = (
                self.database.get_operation_result(operation_id) if operation_id else None
            )
            if previous_operation is not None:
                if (
                    previous_operation.operation_type != "document_upload"
                    or previous_operation.scope_id != chat_id
                ):
                    raise RuntimeError("operation id belongs to a different upload scope")
                document_id = str(previous_operation.result_ref or "")
                existing = self.database.get_document(document_id)
                if existing is None:
                    raise RuntimeError("upload retry references a missing document record")
                if existing.status == "Ready":
                    self.database.associate_document_with_chat(
                        chat_id,
                        document_id,
                    )
                    return DocumentFileIndexResult(
                        file_name=existing.file_name,
                        document_id=existing.id,
                        chunk_count=existing.chunk_count,
                    )
            else:
                document_id = str(uuid4())
                if operation_id:
                    claimed, document_id = self.database.claim_document_upload(
                        operation_id=operation_id,
                        chat_id=chat_id,
                        document_id=document_id,
                        file_name=file_name,
                        source=str(path),
                    )
                    if not claimed:
                        existing = self.database.get_document(document_id)
                        if existing is None:
                            raise RuntimeError("upload retry references a missing document record")
                        if existing.status == "Ready":
                            self.database.associate_document_with_chat(
                                chat_id,
                                document_id,
                            )
                            return DocumentFileIndexResult(
                                file_name=existing.file_name,
                                document_id=existing.id,
                                chunk_count=existing.chunk_count,
                            )
                else:
                    self.database.create_document_record(
                        document_id,
                        file_name,
                        status="Uploading",
                        source=str(path),
                    )
            self.database.update_document_status(document_id, "Indexing")
            try:
                result = self.document_ingestion_agent.index_file(
                    path,
                    display_name=display_name,
                    document_id=document_id,
                )
            except Exception as error:
                self.database.update_document_status(
                    document_id,
                    "Failed",
                    error=f"{type(error).__name__}: {error}",
                )
                self.database.associate_document_with_chat(chat_id, document_id)
                raise
            try:
                self.database.update_document_status(
                    document_id,
                    "Ready",
                    chunk_count=result.chunk_count,
                )
            except Exception:
                self.database.associate_document_with_chat(chat_id, document_id)
                raise
            self.database.associate_document_with_chat(chat_id, document_id)
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
        task_context: str | None = None,
        persisted_user_message_id: int | None = None,
        defer_post_answer_memory_update: bool = False,
    ) -> AgentTurnResult:
        """Run one user turn and return the agent-shaped result."""
        with guarded_chat_operation(self.database.path, chat_id):
            if not self.database.is_chat_active(chat_id):
                raise RuntimeError(f"Chat is inactive: {chat_id}")
            if persisted_user_message_id is None:
                self.ensure_chat_title_from_message(chat_id=chat_id, content=content)
            else:
                self._validate_persisted_user_message(
                    chat_id=chat_id,
                    message_id=persisted_user_message_id,
                    content=content,
                )
            result = self.coordinator.run_turn(
                chat_id=chat_id,
                content=content,
                orchestration_mode=orchestration_mode,
                task_context=task_context,
                persisted_user_message_id=persisted_user_message_id,
                perform_memory_update=not defer_post_answer_memory_update,
            )
            persist_answer_inspection(result, self.database)
            return result

    def persist_user_message_for_turn(self, chat_id: str, content: str) -> int:
        """Persist one user turn before synchronous attachment ingestion."""
        with guarded_chat_operation(self.database.path, chat_id):
            if not self.database.is_chat_active(chat_id):
                raise RuntimeError(f"Chat is inactive: {chat_id}")
            self.ensure_chat_title_from_message(chat_id=chat_id, content=content)
            return self.database.save_message(
                chat_id=chat_id,
                role="user",
                content=content,
            )

    def _validate_persisted_user_message(
        self,
        *,
        chat_id: str,
        message_id: int,
        content: str,
    ) -> None:
        message = next(
            (item for item in self.database.messages_for_chat(chat_id) if item.id == message_id),
            None,
        )
        if message is None or message.role != "user" or message.content != content:
            raise RuntimeError("pre-persisted user message does not match this turn")

    def finalize_post_answer_memory_update(self, chat_id: str) -> bool:
        """Run the synchronous post-answer memory update after visible answer emission."""
        try:
            return self.memory.update_memory_if_needed(chat_id)
        except (OpenAIError, InferenceServerUnreachable):
            return False


def normalize_previous_chat_gist_extractor(value: str) -> str:
    """Return a supported previous-chat gist extractor mode."""
    normalized = value.strip().lower()
    return normalized if normalized in {"deterministic", "llm"} else "deterministic"
