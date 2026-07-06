from __future__ import annotations

from typing import Any

from chainlit.data.base import BaseDataLayer
from chainlit.step import StepDict
from chainlit.types import PageInfo, PaginatedResponse, Pagination, ThreadDict, ThreadFilter
from chainlit.user import PersistedUser, User

from src.database import Database, StoredChat, StoredMessage


DEFAULT_USER_ID = "local-user"


class SQLiteChainlitDataLayer(BaseDataLayer):
    """Chainlit history adapter backed by the project's existing SQLite tables."""

    def __init__(self, database: Database) -> None:
        self.database = database

    async def get_user(self, identifier: str) -> PersistedUser | None:
        return persisted_user(identifier)

    async def create_user(self, user: User) -> PersistedUser | None:
        return persisted_user(user.identifier)

    async def delete_feedback(self, feedback_id: str) -> bool:
        del feedback_id
        return True

    async def upsert_feedback(self, feedback: Any) -> str:
        return str(getattr(feedback, "id", None) or "feedback")

    async def create_element(self, element: Any) -> None:
        del element

    async def get_element(self, thread_id: str, element_id: str) -> dict | None:
        del thread_id, element_id
        return None

    async def delete_element(self, element_id: str, thread_id: str | None = None) -> None:
        del element_id, thread_id

    async def create_step(self, step_dict: StepDict) -> None:
        del step_dict

    async def update_step(self, step_dict: StepDict) -> None:
        del step_dict

    async def delete_step(self, step_id: str) -> None:
        del step_id

    async def get_thread_author(self, thread_id: str) -> str:
        del thread_id
        return DEFAULT_USER_ID

    async def delete_thread(self, thread_id: str) -> None:
        self.database.delete_chat(thread_id)

    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        limit = max(1, pagination.first)
        chats = self.database.list_chats(
            limit=limit + 1,
            cursor=pagination.cursor,
            search=filters.search,
            require_messages=False,
        )
        has_next_page = len(chats) > limit
        page_chats = chats[:limit]
        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=has_next_page,
                startCursor=page_chats[0].id if page_chats else None,
                endCursor=page_chats[-1].id if page_chats else None,
            ),
            data=[thread_from_chat(chat, steps=[]) for chat in page_chats],
        )

    async def get_thread(self, thread_id: str) -> ThreadDict | None:
        chat = self.database.get_chat(thread_id)
        if chat is None:
            return None
        messages = self.database.messages_for_chat(thread_id)
        steps = [step_from_message(message, thread_id=thread_id) for message in messages]
        return thread_from_chat(chat, steps=steps)

    async def update_thread(
        self,
        thread_id: str,
        name: str | None = None,
        user_id: str | None = None,
        metadata: dict | None = None,
        tags: list[str] | None = None,
    ) -> None:
        del user_id, metadata, tags
        if self.database.get_chat(thread_id) is None:
            self.database.create_chat(thread_id, title=name or "Chainlit chat")
        elif name:
            self.database.update_chat_title(thread_id, name)

    def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        return None

    async def get_favorite_steps(self, user_id: str) -> list[StepDict]:
        del user_id
        return []


def persisted_user(identifier: str = DEFAULT_USER_ID) -> PersistedUser:
    """Return a stable local user so Chainlit can attach thread history."""
    return PersistedUser(
        id=DEFAULT_USER_ID,
        createdAt="1970-01-01T00:00:00+00:00",
        identifier=identifier or DEFAULT_USER_ID,
        display_name="Local user",
        metadata={},
    )


def thread_from_chat(chat: StoredChat, steps: list[StepDict]) -> ThreadDict:
    """Convert one project chat row into Chainlit's thread shape."""
    metadata: dict[str, object] = {
        "model_name": chat.model_name,
        "active": chat.active,
    }
    if not chat.active:
        metadata["status"] = "Ended"
    return ThreadDict(
        id=chat.id,
        createdAt=chat.created_at,
        name=thread_display_name(chat),
        userId=DEFAULT_USER_ID,
        userIdentifier=DEFAULT_USER_ID,
        tags=[],
        metadata=metadata,
        steps=steps,
        elements=[],
    )


def thread_display_name(chat: StoredChat) -> str:
    """Decorate ended threads for navigation without changing persisted titles."""
    title = chat.title or "Chainlit chat"
    return title if chat.active else f"{title} · Ended"


def step_from_message(message: StoredMessage, thread_id: str) -> StepDict:
    """Convert one raw chat message into Chainlit's step shape."""
    role_type = {
        "user": "user_message",
        "assistant": "assistant_message",
        "system": "system_message",
    }.get(message.role, "undefined")
    return StepDict(
        name=message.role,
        type=role_type,
        id=f"message:{message.id}",
        threadId=thread_id,
        parentId=None,
        command=None,
        streaming=False,
        waitForAnswer=None,
        isError=False,
        metadata={"message_id": message.id, "summarized": message.summarized},
        tags=[],
        input="",
        output=message.content,
        createdAt=message.created_at,
        start=message.created_at,
        end=message.created_at,
        generation=None,
        showInput=False,
        defaultOpen=None,
        autoCollapse=None,
        language=None,
        icon=None,
        feedback=None,
    )
