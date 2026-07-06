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

    def __init__(
        self,
        content: str,
        actions: list[object] | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.content = content
        self.actions = actions or []
        self.metadata = metadata or {}

    async def send(self) -> None:
        self.sent.append(self)


def install_chainlit_fakes(monkeypatch, session: FakeUserSession) -> list[dict]:
    FakeMessage.sent = []
    window_messages: list[dict] = []
    monkeypatch.setattr(app.cl, "user_session", session)
    monkeypatch.setattr(app.cl, "Message", FakeMessage)
    monkeypatch.setattr(app, "frontend_thread_switch_available", lambda: True)

    async def resume_frontend_thread(chat_id: str) -> bool:
        return True

    async def send_window_message(value: dict) -> None:
        window_messages.append(value)

    monkeypatch.setattr(app, "resume_frontend_thread", resume_frontend_thread)
    monkeypatch.setattr(app.cl, "send_window_message", send_window_message)
    return window_messages


def test_end_chat_uses_authoritative_action_keeps_history_and_refreshes(
    monkeypatch,
) -> None:
    session = FakeUserSession({"chat_id": "chat-1", "model_name": "model-1"})
    install_chainlit_fakes(monkeypatch, session)
    monkeypatch.setattr(app.database, "is_chat_active", lambda chat_id: True)
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
    controls: list[str] = []
    refreshes: list[bool] = []

    async def send_chat_controls(chat_id: str) -> None:
        controls.append(chat_id)

    async def refresh_sidebar() -> None:
        refreshes.append(True)

    monkeypatch.setattr(app, "send_chat_controls", send_chat_controls)
    monkeypatch.setattr(app, "refresh_sidebar", refresh_sidebar)

    asyncio.run(app.end_chat_handler(SimpleNamespace(payload={"chat_id": "chat-1"})))

    assert calls == [(app.database, memory, "chat-1")]
    assert session.get("chat_id") == "chat-1"
    assert session.get("chat_ended") is True
    assert controls == ["chat-1"]
    assert refreshes == [True]
    assert FakeMessage.sent == []


def test_failed_end_does_not_present_chat_as_ended(monkeypatch) -> None:
    session = FakeUserSession({"chat_id": "chat-1", "model_name": "model-1"})
    window_messages = install_chainlit_fakes(monkeypatch, session)
    monkeypatch.setattr(app.database, "is_chat_active", lambda chat_id: True)
    monkeypatch.setattr(
        app,
        "chat_service_for_model",
        lambda model_name: SimpleNamespace(memory=object()),
    )

    class FailingChatEndAction:
        def __init__(self, database, memory) -> None:
            pass

        def execute(self, chat_id: str) -> None:
            raise RuntimeError("flush failed")

    monkeypatch.setattr(app, "ChatEndAction", FailingChatEndAction)

    asyncio.run(app.end_chat_handler(SimpleNamespace(payload={})))

    assert session.get("chat_id") == "chat-1"
    assert session.get("chat_ended") is not True
    assert window_messages[-1]["command"] == "product-error"
    assert "flush failed" in window_messages[-1]["message"]


def test_fork_chat_switches_to_authoritative_action_result(monkeypatch) -> None:
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
    controls: list[str] = []

    async def send_chat_controls(chat_id: str) -> None:
        controls.append(chat_id)

    monkeypatch.setattr(app, "send_chat_controls", send_chat_controls)

    asyncio.run(app.fork_chat_handler(SimpleNamespace(payload={})))

    assert calls == ["chat-1"]
    assert session.get("chat_id") == "fork-1"
    assert session.get("chat_ended") is False
    assert controls == ["fork-1"]
    assert FakeMessage.sent == []


def test_new_chat_uses_current_chat_service_and_opens_it(monkeypatch) -> None:
    session = FakeUserSession({"chat_id": "chat-1", "model_name": "model-1"})
    install_chainlit_fakes(monkeypatch, session)
    calls: list[object] = []

    class FakeChatService:
        def start_chat(self, chat_id=None) -> str:
            calls.append(chat_id)
            return "new-1"

    monkeypatch.setattr(app, "chat_service_for_model", lambda model_name: FakeChatService())
    controls: list[str] = []

    async def send_chat_controls(chat_id: str) -> None:
        controls.append(chat_id)

    monkeypatch.setattr(app, "send_chat_controls", send_chat_controls)

    asyncio.run(app.new_chat_handler(SimpleNamespace()))

    assert calls == [None]
    assert session.get("chat_id") == "new-1"
    assert session.get("chat_ended") is False
    assert session.get("model_name") == "model-1"
    assert controls == ["new-1"]
    assert FakeMessage.sent == []


def test_inactive_chat_rejects_turn_before_model_or_persistence(monkeypatch) -> None:
    session = FakeUserSession({"chat_id": "inactive-chat"})
    install_chainlit_fakes(monkeypatch, session)
    monkeypatch.setattr(app.database, "is_chat_active", lambda chat_id: False)
    called = False

    def service_for_model(model_name: str):
        nonlocal called
        called = True
        raise AssertionError("inactive chat must not reach ChatService")

    async def send_chat_controls(chat_id: str) -> None:
        return None

    monkeypatch.setattr(app, "chat_service_for_model", service_for_model)
    monkeypatch.setattr(app, "send_chat_controls", send_chat_controls)

    asyncio.run(app.on_message(SimpleNamespace(content="do not save", elements=[])))

    assert called is False
    assert session.get("chat_ended") is True


def test_chat_start_is_home_and_does_not_create_message_or_chat(monkeypatch) -> None:
    session = FakeUserSession()
    install_chainlit_fakes(monkeypatch, session)

    async def send_orchestration_settings() -> None:
        return None

    monkeypatch.setattr(app, "send_orchestration_settings", send_orchestration_settings)
    monkeypatch.setattr(
        app,
        "chat_service_for_model",
        lambda model_name: (_ for _ in ()).throw(
            AssertionError("Home must not create a backend chat")
        ),
    )

    asyncio.run(app.on_chat_start())

    assert session.get("chat_id") is None
    assert session.get("product_view") == "home"
    assert FakeMessage.sent == []


def test_home_navigation_does_not_create_conversation_message(monkeypatch) -> None:
    session = FakeUserSession({"chat_id": "chat-1", "chat_ended": True})
    window_messages = install_chainlit_fakes(monkeypatch, session)

    asyncio.run(app.nav_home_handler(SimpleNamespace()))

    assert session.get("chat_id") is None
    assert session.get("product_view") == "home"
    assert FakeMessage.sent == []
    assert window_messages[-1]["view"] == "home"


def test_chat_resume_restores_persisted_ended_state(monkeypatch) -> None:
    session = FakeUserSession()
    install_chainlit_fakes(monkeypatch, session)
    monkeypatch.setattr(app.database, "is_chat_active", lambda chat_id: False)
    controls: list[str] = []

    async def send_settings() -> None:
        return None

    async def send_chat_controls(chat_id: str) -> None:
        controls.append(chat_id)

    monkeypatch.setattr(app, "send_orchestration_settings", send_settings)
    monkeypatch.setattr(app, "send_chat_controls", send_chat_controls)

    asyncio.run(
        app.on_chat_resume(
            {
                "id": "ended-chat",
                "metadata": {"model_name": "stored-model"},
            }
        )
    )

    assert session.get("chat_id") == "ended-chat"
    assert session.get("chat_ended") is True
    assert session.get("product_view") == "chat"
    assert controls == ["ended-chat"]


def test_chat_controls_are_state_only_not_conversation_messages(monkeypatch) -> None:
    session = FakeUserSession({"chat_id": "ended-chat"})
    window_messages = install_chainlit_fakes(monkeypatch, session)
    monkeypatch.setattr(
        app.database,
        "get_chat",
        lambda chat_id: SimpleNamespace(id=chat_id, active=False),
    )

    asyncio.run(app.send_chat_controls("ended-chat"))

    assert FakeMessage.sent == []
    assert window_messages[-1] == {
        "source": "memory-chatbot-ui",
        "command": "product-state",
        "view": "chat",
        "chat_id": "ended-chat",
        "active": False,
    }


def test_window_lifecycle_action_delegates_to_existing_handler(monkeypatch) -> None:
    calls: list[object] = []

    async def new_chat_handler(action: object) -> None:
        calls.append(action)

    monkeypatch.setattr(app, "new_chat_handler", new_chat_handler)

    asyncio.run(
        app.product_window_message(
            {
                "source": "memory-chatbot-ui",
                "command": "lifecycle-action",
                "action": "new",
                "chat_id": None,
            }
        )
    )

    assert len(calls) == 1
    assert app.action_payload(calls[0]) == {"chat_id": None}


def test_orchestration_mode_selection_is_per_session(monkeypatch) -> None:
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
