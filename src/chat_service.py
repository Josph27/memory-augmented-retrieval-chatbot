from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from src.agents.chat_agent import ChatAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.core.contracts import AgentTurnResult
from src.database import Database
from src.documents.loaders import index_file_document
from src.memory.short_term import ShortTermMemory
from src.model_wrapper import ModelWrapper
from src.retrieval.langchain_chroma_retriever import LangChainChromaRetriever
from src.retrieval.retriever_dispatcher import RetrieverDispatcher


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
    ) -> None:
        self.database = database
        self.model = model
        self.document_indexer = document_indexer
        self.memory = ShortTermMemory(
            database=database,
            model=model,
            raw_message_limit=raw_message_limit,
            memory_update_batch_size=memory_update_batch_size,
        )
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
        )

    def start_chat(self, chat_id: str | None = None) -> str:
        """Create a chat id for a Chainlit session."""
        chat_id = chat_id or str(uuid4())
        self.database.create_chat(
            chat_id=chat_id,
            title="Chainlit chat",
            model_name=getattr(self.model, "model_name", None),
        )
        return chat_id

    def ensure_chat_title_from_message(self, chat_id: str, content: str) -> None:
        """Use the first user message as a lightweight thread title."""
        title = content.strip()
        if not title or self.database.message_count(chat_id) > 0:
            return
        if len(title) > 60:
            title = f"{title[:57].rstrip()}..."
        self.database.update_chat_title(chat_id=chat_id, title=title)

    def index_document_file(self, path: str | Path) -> DocumentFileIndexResult:
        """Load and index an uploaded local file into document memory."""
        file_path = Path(path)
        indexer = self.document_indexer or LangChainChromaRetriever.from_env(
            database=self.database
        )
        result = index_file_document(file_path, indexer)
        document_id = str(getattr(result, "document_id", ""))
        chunk_count = int(getattr(result, "chunk_count", 0))
        if isinstance(result, dict):
            document_id = str(result.get("document_id", document_id))
            chunk_count = int(result.get("chunk_count", chunk_count))
        return DocumentFileIndexResult(
            file_name=file_path.name,
            document_id=document_id,
            chunk_count=chunk_count,
        )

    def handle_user_message(self, chat_id: str, content: str) -> str:
        """Save a user message, call the model, and save the assistant response."""
        return self.handle_user_turn(chat_id=chat_id, content=content).answer

    def handle_user_turn(self, chat_id: str, content: str) -> AgentTurnResult:
        """Run one user turn and return the agent-shaped result."""
        self.ensure_chat_title_from_message(chat_id=chat_id, content=content)
        return self.coordinator.run_turn(chat_id=chat_id, content=content)
