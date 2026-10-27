from __future__ import annotations

import json
import ast
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from openai import OpenAI

from src import provider_settings as settings
from src.config import AppConfig
from src.memory.langmem_structured import LangMemBackendConfig, create_real_langmem_manager
from src.model_wrapper import ModelWrapper


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "LOCAL_SETTINGS_PATH", tmp_path / "local_settings.py")
    monkeypatch.setattr(settings, "load_dotenv", lambda: None)
    for name in (
        "LLM_PROVIDER",
        "DEEPSEEK_API_KEY",
        "DEEPSEEK_BASE_URL",
        "DEEPSEEK_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "MODEL_NAME",
    ):
        monkeypatch.delenv(name, raising=False)


def select_deepseek(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")


def test_deepseek_is_shared_and_ignores_legacy_endpoint(monkeypatch):
    select_deepseek(monkeypatch)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://university.invalid/inference")
    monkeypatch.setenv("OPENAI_API_KEY", "old-key")
    monkeypatch.setenv("MODEL_NAME", "old-model")
    chat = AppConfig.from_env()
    memory = LangMemBackendConfig.from_env()
    assert chat.provider == memory.provider == "deepseek"
    assert chat.openai_base_url == memory.openai_base_url == "https://api.deepseek.com"
    assert chat.openai_api_key == memory.openai_api_key == "test-key"
    assert chat.model_name == memory.model_name == "deepseek-flash"


def test_local_key_and_environment_override(monkeypatch):
    settings.LOCAL_SETTINGS_PATH.write_text(
        'PROVIDER = "deepseek"\nDEEPSEEK_API_KEY = "local-key"\nDEEPSEEK_MODEL = "local-model"\n'
    )
    config = settings.load_provider_settings()
    assert config.api_key == "local-key"
    assert config.model_name == "local-model"
    assert "local-key" not in repr(config)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "environment-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "environment-model")
    assert settings.load_provider_settings().api_key == "environment-key"
    assert settings.load_provider_settings().model_name == "environment-model"


def test_custom_preserves_existing_configuration(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "custom-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("MODEL_NAME", "local-model")
    config = AppConfig.from_env()
    assert config.provider == "custom"
    assert config.openai_api_key == "custom-key"
    assert config.openai_base_url == "http://localhost:1234/v1"
    assert config.model_name == "local-model"
    assert settings.provider_client_options(config.provider, config.openai_api_key) == {}


def test_invalid_provider_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "typo")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        AppConfig.from_env()


def test_missing_key_is_rejected_by_both_clients(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    with pytest.raises(ValueError, match="DeepSeek API key missing"):
        ModelWrapper(AppConfig.from_env())
    with pytest.raises(ValueError, match="DeepSeek API key missing"):
        create_real_langmem_manager(LangMemBackendConfig.from_env())


def test_chat_sends_deepseek_request_without_network(monkeypatch):
    select_deepseek(monkeypatch)
    captured = []

    def respond(request):
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "deepseek-flash",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Hello"},
                    }
                ],
            },
        )

    def client_factory(**kwargs):
        return OpenAI(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(respond)))

    monkeypatch.setattr("src.model_wrapper.OpenAI", client_factory)
    checks = []
    guard = SimpleNamespace(check=lambda: checks.append("checked"))
    wrapper = ModelWrapper(AppConfig.from_env(), connection_guard=guard)
    try:
        assert wrapper.chat([{"role": "user", "content": "Hi"}]) == "Hello"
    finally:
        wrapper.client.close()
    assert checks == ["checked"]
    assert wrapper.client.max_retries == 0
    assert wrapper.client.timeout.read == wrapper._timeout
    request = captured[0]
    assert str(request.url) == "https://api.deepseek.com/chat/completions"
    assert request.headers["authorization"] == "Bearer test-key"
    body = json.loads(request.content)
    assert body["model"] == "deepseek-flash"
    assert body["thinking"] == {"type": "disabled"}


def test_langmem_receives_deepseek_options(monkeypatch):
    import langchain_openai
    import langmem

    select_deepseek(monkeypatch)
    captured = {}

    def make_client(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(langchain_openai, "ChatOpenAI", make_client)
    monkeypatch.setattr(langmem, "create_memory_manager", lambda model, **kwargs: model)
    config = LangMemBackendConfig.from_env(model_name="selected-model")
    create_real_langmem_manager(config)
    assert captured["max_retries"] == 0
    assert captured["request_timeout"] == captured["stream_chunk_timeout"]
    assert captured["model"] == "selected-model"
    assert captured["base_url"] == "https://api.deepseek.com"
    assert captured["api_key"] == "test-key"
    assert captured["extra_body"] == {"thinking": {"type": "disabled"}}


def test_resumed_chats_use_selected_provider_model():
    # Load just these pure helpers: importing app registers a real Chainlit server.
    tree = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text())
    names = {"model_name_from_thread", "model_name_for_chat"}
    helpers = ast.Module(
        body=[
            node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names
        ],
        type_ignores=[],
    )
    namespace = {
        "config": SimpleNamespace(provider="deepseek", model_name="deepseek-flash"),
        "database": SimpleNamespace(get_chat=lambda _: SimpleNamespace(model_name="old-gemma")),
        "selected_model_name": lambda: "deepseek-flash",
    }
    exec(compile(helpers, "app.py", "exec"), namespace)
    thread = {"id": "old-chat", "metadata": {"model_name": "old-gemma"}}
    assert namespace["model_name_from_thread"](thread) == "deepseek-flash"
    assert namespace["model_name_for_chat"]("old-chat") == "deepseek-flash"
    namespace["config"].provider = "custom"
    assert namespace["model_name_from_thread"](thread) == "old-gemma"
    assert namespace["model_name_for_chat"]("old-chat") == "old-gemma"
    namespace["database"].get_chat = lambda _: None
    assert namespace["model_name_for_chat"]("missing") == "deepseek-flash"
    assert namespace["model_name_from_thread"]({}) == "deepseek-flash"
    assert namespace["model_name_from_thread"]({"id": "missing"}) == "deepseek-flash"


def test_langchain_serializes_deepseek_tool_request_without_network(monkeypatch):
    from langchain_openai import ChatOpenAI
    import langchain_openai
    import langmem

    select_deepseek(monkeypatch)
    config = LangMemBackendConfig.from_env()
    captured = []

    def respond(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": config.model_name,
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Done"},
                    }
                ],
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(
            langchain_openai,
            "ChatOpenAI",
            lambda **kwargs: ChatOpenAI(http_client=client, **kwargs),
        )
        monkeypatch.setattr(langmem, "create_memory_manager", lambda model, **kwargs: model)
        model = create_real_langmem_manager(config)
        tool = {
            "type": "function",
            "function": {
                "name": "save_memory",
                "description": "Save a fact",
                "parameters": {"type": "object", "properties": {}},
            },
        }
        model.bind_tools([tool], tool_choice="required").invoke("Remember my preference")
    assert captured[0]["thinking"] == {"type": "disabled"}
    assert captured[0]["tool_choice"] == "required"
    assert captured[0]["tools"][0]["function"]["name"] == "save_memory"


def test_custom_uses_canonical_defaults_and_preserves_application_settings(monkeypatch):
    from src import settings as app_settings

    monkeypatch.setattr(app_settings, "OPENAI_API_KEY", "canonical-test-key")
    monkeypatch.setattr(app_settings, "OPENAI_BASE_URL", "http://canonical.invalid/v1")
    monkeypatch.setattr(app_settings, "MODEL_NAME", "canonical-model")
    monkeypatch.setattr(app_settings, "MEMORY_UPDATE_BATCH_SIZE", 19)
    chat = AppConfig.load()
    memory = LangMemBackendConfig.from_env()
    assert chat.openai_base_url == memory.openai_base_url == app_settings.OPENAI_BASE_URL
    assert chat.model_name == memory.model_name == "canonical-model"
    assert chat.openai_api_key == memory.openai_api_key == "canonical-test-key"
    assert chat.memory_update_batch_size == 19
    assert chat.orchestration_mode == app_settings.ORCHESTRATION_MODE
    select_deepseek(monkeypatch)
    assert AppConfig.load().memory_update_batch_size == 19


def test_both_connection_guards_follow_selected_endpoint(monkeypatch):
    from src.memory.langmem_structured import LangMemStructuredMemoryState

    select_deepseek(monkeypatch)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://university.invalid/inference")
    wrapper = ModelWrapper(AppConfig.load())
    try:
        memory = LangMemStructuredMemoryState()
        assert wrapper._guard.base_url == memory._guard.base_url == "https://api.deepseek.com"
    finally:
        wrapper.client.close()
    guard = SimpleNamespace(check=lambda: None)
    assert LangMemStructuredMemoryState(connection_guard=guard)._guard is guard


def test_guard_failure_prevents_chat_request(monkeypatch):
    from src.connection_guard import InferenceServerUnreachable

    select_deepseek(monkeypatch)
    requests = []
    monkeypatch.setattr(
        "src.model_wrapper.OpenAI",
        lambda **kw: SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(create=lambda **kw: requests.append(kw))
            )
        ),
    )

    def unreachable():
        raise InferenceServerUnreachable("https://api.deepseek.com", reason="test offline")

    wrapper = ModelWrapper(AppConfig.load(), connection_guard=SimpleNamespace(check=unreachable))
    with pytest.raises(InferenceServerUnreachable):
        wrapper.chat([{"role": "user", "content": "Hi"}])
    assert requests == []


def test_custom_local_settings_and_environment_precedence(monkeypatch):
    settings.LOCAL_SETTINGS_PATH.write_text(
        'PROVIDER = "custom"\nCUSTOM_API_KEY = "local-test-key"\n'
        'CUSTOM_BASE_URL = "http://local.invalid/v1"\nCUSTOM_MODEL = "local-model"\n'
    )
    chat = AppConfig.load()
    memory = LangMemBackendConfig.from_env()
    assert chat.openai_api_key == memory.openai_api_key == "local-test-key"
    assert chat.openai_base_url == memory.openai_base_url == "http://local.invalid/v1"
    assert chat.model_name == memory.model_name == "local-model"
    monkeypatch.setenv("OPENAI_API_KEY", "env-test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://env.invalid/v1")
    monkeypatch.setenv("MODEL_NAME", "env-model")
    chat = AppConfig.load()
    memory = LangMemBackendConfig.from_env()
    assert chat.openai_api_key == memory.openai_api_key == "env-test-key"
    assert chat.openai_base_url == memory.openai_base_url == "http://env.invalid/v1"
    assert chat.model_name == memory.model_name == "env-model"
