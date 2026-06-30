from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from src.agents.chat_agent import ChatAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.document_ingestion_agent import DocumentIngestionAgent
from src.agents.gisting_agent import GistingAgent
from src.agents.query_augmentation_agent import QueryAugmentationAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.core.contracts import AgentTurnResult
from src.database import Database
from src.memory.previous_chat_gist import PreviousChatGistGenerator
from src.memory.short_term import ShortTermMemory
from src.model_wrapper import ModelWrapper
from src.retrieval.reranker import MemoryReranker
from src.routing.query_decomposer import QueryDecomposer
from src.routing.semantic_expander import SemanticExpander
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.routing_agent import RoutingAgent


SYSTEM_PROMPT = (
    "You are a concise, helpful chatbot prototype. Use the structured current-chat memory "
    "and recent messages as short-term memory. If information is missing, say what you need "
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
        document_indexer: object | None = None,
        routing_mode: str = "rule",
        reranker_mode: str = "deterministic",
        reranker_llm_top_k: int = 10,
        reranker_llm_min_confidence: float = 0.55,
        previous_chat_gist_generation_enabled: bool = False,
        previous_chat_gist_generator: PreviousChatGistGenerator | None = None,
        query_augmentation_enabled: bool = True,
    ) -> None:
        self.database = database
        self.model = model
        self.document_indexer = document_indexer
        self.routing_mode = routing_mode
        self.reranker_mode = reranker_mode
        self.previous_chat_gist_generation_enabled = previous_chat_gist_generation_enabled
        self.previous_chat_gist_generator = previous_chat_gist_generator
        self.query_augmentation_enabled = query_augmentation_enabled
        self.document_ingestion_agent = DocumentIngestionAgent(
            database=database,
            indexer=document_indexer,
        )
        self.memory = ShortTermMemory(
            database=database,
            model=model,
            raw_message_limit=raw_message_limit,
            memory_update_batch_size=memory_update_batch_size,
        )
        gisting_agent = None
        if previous_chat_gist_generation_enabled:
            gisting_agent = GistingAgent(database=database, model=model)
        if query_augmentation_enabled:
            query_augmentation_agent: QueryAugmentationAgent | None = (
                QueryAugmentationAgent(
                    decomposer=QueryDecomposer(model=model),
                    expander=SemanticExpander(model=model),
                )
            )
        else:
            query_augmentation_agent = None
        self.coordinator = CoordinatorAgent(
            database=database,
            memory_agent=ShortTermMemoryAgent(self.memory),
            context_builder=ContextBuilderAgent(self.memory),
            chat_agent=ChatAgent(model),
            system_prompt=SYSTEM_PROMPT,
            retriever_dispatcher=RetrieverDispatcher(
                database=database,
                raw_message_limit=raw_message_limit,
            ),
            routing_agent=RoutingAgent(mode=routing_mode, model=model),
            memory_reranker=MemoryReranker(
                mode=reranker_mode,
                model=model if reranker_mode in {"hybrid", "llm"} else None,
                llm_top_k=reranker_llm_top_k,
                llm_min_confidence=reranker_llm_min_confidence,
            ),
            gisting_agent=gisting_agent,
            query_augmentation_agent=query_augmentation_agent,
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
        return self.handle_user_turn(chat_id=chat_id, content=content).answer

    def handle_user_turn(self, chat_id: str, content: str) -> AgentTurnResult:
        """Run one user turn and return the agent-shaped result."""
        self.ensure_chat_title_from_message(chat_id=chat_id, content=content)
        return self.coordinator.run_turn(chat_id=chat_id, content=content)
