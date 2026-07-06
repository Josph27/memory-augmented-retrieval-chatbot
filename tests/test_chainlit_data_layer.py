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

    assert {thread["id"] for thread in page.data} == {
        "chat-1",
        "empty-placeholder",
    }
    listed = next(item for item in page.data if item["id"] == "chat-1")
    assert listed["name"] == "First chat"
    assert listed["metadata"]["active"] is True
    assert "status" not in listed["metadata"]
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


def test_chainlit_data_layer_lists_active_and_ended_with_stable_pagination(
    tmp_path,
) -> None:
    database = Database(tmp_path / "chatbot.db")
    for chat_id in ("chat-c", "chat-b", "chat-a"):
        database.create_chat(
            chat_id,
            title=chat_id,
            created_at="2026-01-01T00:00:00+00:00",
        )
    database.mark_chat_inactive("chat-b")
    data_layer = SQLiteChainlitDataLayer(database)

    first = run_async(
        data_layer.list_threads(
            Pagination(first=2, cursor=None),
            ThreadFilter(feedback=None, userId=None, search=None),
        )
    )
    second = run_async(
        data_layer.list_threads(
            Pagination(first=2, cursor=first.pageInfo.endCursor),
            ThreadFilter(feedback=None, userId=None, search=None),
        )
    )

    assert [item["id"] for item in first.data] == ["chat-c", "chat-b"]
    assert [item["id"] for item in second.data] == ["chat-a"]
    assert first.data[0]["name"] == "chat-c"
    assert first.data[1]["name"] == "chat-b · Ended"
    assert first.data[0]["metadata"]["active"] is True
    assert "status" not in first.data[0]["metadata"]
    assert first.data[1]["metadata"]["status"] == "Ended"


def test_loading_ended_thread_returns_only_its_readable_history(tmp_path) -> None:
    database = Database(tmp_path / "chatbot.db")
    database.create_chat("selected", title="Selected")
    database.save_message("selected", "user", "selected question")
    database.save_message("selected", "assistant", "selected answer")
    database.mark_chat_inactive("selected")
    database.create_chat("other", title="Other")
    database.save_message("other", "user", "other question")
    database.save_message("other", "assistant", "other answer")
    data_layer = SQLiteChainlitDataLayer(database)

    selected = run_async(data_layer.get_thread("selected"))

    assert selected is not None
    assert selected["metadata"]["status"] == "Ended"
    assert [step["output"] for step in selected["steps"]] == [
        "selected question",
        "selected answer",
    ]
    assert all("other" not in step["output"] for step in selected["steps"])


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
