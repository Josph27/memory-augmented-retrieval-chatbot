from __future__ import annotations

import asyncio

from chainlit.types import Pagination, ThreadFilter

from src.chainlit_data_layer import SQLiteChainlitDataLayer
from src.database import Database


def run_async(coro):
    return asyncio.run(coro)


def test_chainlit_data_layer_lists_and_loads_threads(tmp_path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat-1", title="First chat")
    database.save_message("chat-1", "user", "hello")
    database.save_message("chat-1", "assistant", "hi")
    database.create_chat("empty-placeholder", title="First chat")
    data_layer = SQLiteChainlitDataLayer(database)

    page = run_async(
        data_layer.list_threads(
            Pagination(first=10, cursor=None),
            ThreadFilter(feedback=None, userId=None, search=None),
        )
    )
    thread = run_async(data_layer.get_thread("chat-1"))

    assert [thread["id"] for thread in page.data] == ["chat-1"]
    assert page.data[0]["id"] == "chat-1"
    assert page.data[0]["name"] == "First chat"
    assert page.pageInfo.hasNextPage is False
    assert thread is not None
    assert [step["type"] for step in thread["steps"]] == [
        "user_message",
        "assistant_message",
    ]
    assert [step["output"] for step in thread["steps"]] == ["hello", "hi"]
    assert run_async(data_layer.get_thread_author("chat-1")) == "local-user"
    user = run_async(data_layer.get_user("local-user"))
    assert user is not None
    assert user.id == "local-user"
    assert user.identifier == "local-user"


def test_chainlit_data_layer_update_and_delete_thread(tmp_path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("chat-1", title="Old")
    database.save_message("chat-1", "user", "hello")
    data_layer = SQLiteChainlitDataLayer(database)

    run_async(data_layer.update_thread("chat-1", name="Renamed"))

    assert database.get_chat("chat-1").title == "Renamed"  # type: ignore[union-attr]

    run_async(data_layer.delete_thread("chat-1"))

    assert database.get_chat("chat-1") is None
    assert database.messages_for_chat("chat-1") == []
