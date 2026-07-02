from __future__ import annotations

import asyncio
from types import SimpleNamespace

import app


class FakeUserSession:
    def __init__(self, values: dict[str, object] | None = None) -> None:
        self.values = dict(values or {})

    def get(self, key: str) -> object | None:
        return self.values.get(key)

    def set(self, key: str, value: object) -> None:
        self.values[key] = value


class FakeMessage:
    sent: list["FakeMessage"] = []

    def __init__(self, content: str, actions: list[object] | None = None) -> None:
        self.content = content
        self.actions = actions or []

    async def send(self) -> None:
        self.sent.append(self)


def install_chainlit_fakes(monkeypatch, session: FakeUserSession) -> None:
    FakeMessage.sent = []
    monkeypatch.setattr(app.cl, "user_session", session)
    monkeypatch.setattr(app.cl, "Message", FakeMessage)


def test_end_chat_callback_uses_current_action_and_clears_session(monkeypatch) -> None:
    session = FakeUserSession({"chat_id": "chat-1", "model_name": "model-1"})
    install_chainlit_fakes(monkeypatch, session)
    calls: list[tuple[object, object, str]] = []
    memory = object()
    monkeypatch.setattr(
        app,
        "chat_service_for_model",
        lambda model_name: SimpleNamespace(memory=memory),
    )

    class FakeChatEndAction:
        def __init__(self, database, memory) -> None:
            self.database = database
            self.memory = memory

        def execute(self, chat_id: str) -> None:
            calls.append((self.database, self.memory, chat_id))

    monkeypatch.setattr(app, "ChatEndAction", FakeChatEndAction)

    asyncio.run(app.end_chat_handler(SimpleNamespace()))

    assert calls == [(app.database, memory, "chat-1")]
    assert session.get("chat_id") is None
    assert session.get("chat_ended") is True
    assert FakeMessage.sent[-1].content == "Chat ended and pending memory was finalized."


def test_fork_chat_callback_switches_to_current_action_result(monkeypatch) -> None:
    session = FakeUserSession({"chat_id": "chat-1"})
    install_chainlit_fakes(monkeypatch, session)
    calls: list[str] = []

    class FakeChatForkAction:
        def __init__(self, database) -> None:
            assert database is app.database

        def execute(self, chat_id: str) -> str:
            calls.append(chat_id)
            return "fork-1"

    monkeypatch.setattr(app, "ChatForkAction", FakeChatForkAction)

    asyncio.run(app.fork_chat_handler(SimpleNamespace()))

    assert calls == ["chat-1"]
    assert session.get("chat_id") == "fork-1"
    assert session.get("chat_ended") is False
    assert FakeMessage.sent[0].content == "Chat forked. Active chat: `fork-1`."


def test_new_chat_callback_uses_current_chat_service(monkeypatch) -> None:
    session = FakeUserSession({"chat_id": "chat-1", "model_name": "model-1"})
    install_chainlit_fakes(monkeypatch, session)
    calls: list[object] = []

    class FakeChatService:
        def start_chat(self, chat_id=None) -> str:
            calls.append(chat_id)
            return "new-1"

    monkeypatch.setattr(app, "chat_service_for_model", lambda model_name: FakeChatService())

    asyncio.run(app.new_chat_handler(SimpleNamespace()))

    assert calls == [None]
    assert session.get("chat_id") == "new-1"
    assert session.get("chat_ended") is False
    assert session.get("model_name") == "model-1"


def test_action_callback_error_is_bounded_and_keeps_active_chat(monkeypatch) -> None:
    session = FakeUserSession({"chat_id": "chat-1"})
    install_chainlit_fakes(monkeypatch, session)

    class FailingChatForkAction:
        def __init__(self, database) -> None:
            pass

        def execute(self, chat_id: str) -> str:
            raise RuntimeError("x" * 300)

    monkeypatch.setattr(app, "ChatForkAction", FailingChatForkAction)

    asyncio.run(app.fork_chat_handler(SimpleNamespace()))

    assert session.get("chat_id") == "chat-1"
    assert FakeMessage.sent[-1].content.startswith("Could not fork chat:")
    assert len(FakeMessage.sent[-1].content) < 190


def test_orchestration_mode_selection_is_per_session_and_keeps_chat(
    monkeypatch,
) -> None:
    first = FakeUserSession({"chat_id": "chat-1"})
    install_chainlit_fakes(monkeypatch, first)

    asyncio.run(
        app.on_settings_update(
            {app.ORCHESTRATION_SETTING_ID: "LangGraph Demo"}
        )
    )

    assert first.get("chat_id") == "chat-1"
    assert first.get(app.ORCHESTRATION_SETTING_ID) == "langgraph_demo"

    second = FakeUserSession({"chat_id": "chat-2"})
    monkeypatch.setattr(app.cl, "user_session", second)
    assert app.current_orchestration_mode() == "native"
    assert second.get("chat_id") == "chat-2"
