from __future__ import annotations

from uuid import uuid4

from src.agents.chat_agent import ChatAgent
from src.agents.context_builder_agent import ContextBuilderAgent
from src.agents.coordinator_agent import CoordinatorAgent
from src.agents.short_term_memory_agent import ShortTermMemoryAgent
from src.core.contracts import AgentTurnResult
from src.database import Database
from src.memory.short_term import ShortTermMemory
from src.model_wrapper import ModelWrapper


SYSTEM_PROMPT = (
    "You are a concise, helpful chatbot prototype. Use the structured current-chat memory "
    "and recent messages as short-term memory. If information is missing, say what you need "
    "instead of inventing facts."
)


class ChatService:
    """Coordinates database persistence, short-term memory, and model calls."""

    def __init__(
        self,
        database: Database,
        model: ModelWrapper,
        raw_message_limit: int,
        memory_update_batch_size: int,
    ) -> None:
        self.database = database
        self.model = model
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
        )

    def start_chat(self) -> str:
        """Create a chat id for a Chainlit session."""
        chat_id = str(uuid4())
        self.database.create_chat(chat_id=chat_id, title="Chainlit chat")
        return chat_id

    def handle_user_message(self, chat_id: str, content: str) -> str:
        """Save a user message, call the model, and save the assistant response."""
        return self.handle_user_turn(chat_id=chat_id, content=content).answer

    def handle_user_turn(self, chat_id: str, content: str) -> AgentTurnResult:
        """Run one user turn and return the agent-shaped result."""
        return self.coordinator.run_turn(chat_id=chat_id, content=content)
