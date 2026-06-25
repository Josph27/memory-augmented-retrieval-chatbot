from __future__ import annotations

import os
from typing import NamedTuple

import chainlit as cl
from chainlit.types import ChatProfile
from chainlit.user import User

from src.chainlit_data_layer import SQLiteChainlitDataLayer
from src.chat_service import ChatService
from src.config import AppConfig
from src.database import Database
from src.documents.loaders import DocumentLoaderError
from src.memory.memory_trace import (
    demo_memory_trace_enabled,
    format_retrieved_memories_markdown,
    format_saved_memories_markdown,
)
from src.model_wrapper import ModelWrapper
from src.retrieval.langchain_chroma_retriever import LangChainChromaUnavailable


# Chainlit only exposes persisted thread history to authenticated users.
# For this local prototype, provide a stable local auth identity unless the
# deployment supplies its own secret and credentials.
os.environ.setdefault("CHAINLIT_AUTH_SECRET", "local-dev-chainlit-secret-change-me")

config = AppConfig.from_env()
database = Database(config.database_path)


class ModelProfile(NamedTuple):
    """A selectable chat model profile."""

    key: str
    display_name: str
    model_name: str
    description: str


MODEL_PROFILES = [
    ModelProfile(
        key="gemma",
        display_name="Gemma 4 31B",
        model_name="google/gemma-4-31B-it",
        description="Default TUM AIR AKG model.",
    ),
    ModelProfile(
        key="qwen",
        display_name="Qwen 3.5 122B A10B",
        model_name="Qwen/Qwen3.5-122B-A10B",
        description="Qwen large model profile.",
    ),
    ModelProfile(
        key="gpt-oss",
        display_name="GPT OSS 120B",
        model_name="openai/gpt-oss-120b",
        description="OpenAI GPT-OSS model profile.",
    ),
    ModelProfile(
        key="mistral-medium",
        display_name="Mistral Medium 3.5 128B",
        model_name="mistralai/Mistral-Medium-3.5-128B",
        description="Mistral model profile.",
    ),
]
DEFAULT_MODEL_PROFILE_KEY = "gemma"
MODEL_PROFILES_BY_KEY = {profile.key: profile for profile in MODEL_PROFILES}
MODEL_PROFILES_BY_MODEL = {profile.model_name: profile for profile in MODEL_PROFILES}
chat_services: dict[str, ChatService] = {}


@cl.password_auth_callback
async def auth_callback(username: str, password: str) -> User | None:
    """Authenticate one stable local user so Chainlit thread history works."""
    expected_username = os.getenv("CHAINLIT_LOCAL_USERNAME", "local")
    expected_password = os.getenv("CHAINLIT_LOCAL_PASSWORD", "local")
    if username == expected_username and password == expected_password:
        return User(identifier="local-user", display_name="Local user")
    return None


@cl.data_layer
def data_layer() -> SQLiteChainlitDataLayer:
    """Expose existing SQLite chats/messages to Chainlit's history UI."""
    return SQLiteChainlitDataLayer(database)


@cl.set_chat_profiles
async def chat_profiles(
    current_user: User | None,
    language: str | None = None,
) -> list[ChatProfile]:
    """Declare model choices shown before starting a new chat."""
    del current_user, language
    return [
        ChatProfile(
            name=profile.key,
            display_name=profile.display_name,
            markdown_description=(
                f"{profile.description}\n\nModel id: `{profile.model_name}`"
            ),
            icon="bot",
            default=profile.key == DEFAULT_MODEL_PROFILE_KEY,
        )
        for profile in MODEL_PROFILES
    ]


@cl.on_chat_start
async def on_chat_start() -> None:
    """Create a persistent chat row for the current Chainlit session."""
    model_name = selected_model_name()
    chat_service = chat_service_for_model(model_name)
    chat_id = chat_service.start_chat(chat_id=current_chainlit_thread_id())
    cl.user_session.set("chat_id", chat_id)
    cl.user_session.set("model_name", model_name)

    await cl.Message(
        content=(
            "Chat is ready. Messages are stored in SQLite. Older turns update structured "
            "JSON memory while recent turns remain available as raw short-term memory. "
            "You can also upload .txt, .md, or .pdf files for document-memory retrieval.\n\n"
            f"Model: `{model_name}`"
        )
    ).send()
    if demo_memory_trace_enabled():
        await cl.Message(content="Demo memory trace is enabled.").send()


@cl.on_chat_resume
async def on_chat_resume(thread: dict) -> None:
    """Reconnect a browser session to an existing SQLite-backed chat."""
    chat_id = thread.get("id")
    if chat_id:
        cl.user_session.set("chat_id", chat_id)
    model_name = model_name_from_thread(thread)
    cl.user_session.set("model_name", model_name)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle one browser chat message."""
    chat_id = cl.user_session.get("chat_id")
    if not chat_id:
        model_name = selected_model_name()
        chat_service = chat_service_for_model(model_name)
        chat_id = chat_service.start_chat(chat_id=current_chainlit_thread_id())
        cl.user_session.set("chat_id", chat_id)
        cl.user_session.set("model_name", model_name)

    model_name = cl.user_session.get("model_name") or model_name_for_chat(chat_id)
    chat_service = chat_service_for_model(model_name)

    upload_statuses = index_uploaded_files(message, chat_service)
    if upload_statuses:
        await cl.Message(content="\n".join(upload_statuses)).send()

    content = (message.content or "").strip()
    if not content:
        return

    result = chat_service.handle_user_turn(chat_id=chat_id, content=content)
    if demo_memory_trace_enabled():
        retrieved_trace = format_retrieved_memories_markdown(retrieved_memory_rows(result))
        if retrieved_trace:
            await cl.Message(content=retrieved_trace).send()

    await cl.Message(content=result.answer).send()

    if demo_memory_trace_enabled():
        saved_trace = format_saved_memories_markdown(saved_memory_rows(result))
        if saved_trace:
            await cl.Message(content=saved_trace).send()


def saved_memory_rows(result: object) -> list[dict]:
    """Return saved memory rows from result metadata with trace metadata fallback."""
    rows = result_metadata_rows(result, "saved_memory_rows")
    return rows if isinstance(rows, list) else []


def retrieved_memory_rows(result: object) -> list[dict]:
    """Return retrieved memory rows from result metadata with trace metadata fallback."""
    rows = result_metadata_rows(result, "retrieved_memory_rows")
    return rows if isinstance(rows, list) else []


def result_metadata_rows(result: object, key: str) -> object:
    """Read one metadata key from AgentTurnResult or its WorkflowTrace."""
    metadata = getattr(result, "metadata", None)
    if isinstance(metadata, dict) and key in metadata:
        return metadata[key]
    trace = getattr(result, "trace", None)
    trace_metadata = getattr(trace, "metadata", None)
    if isinstance(trace_metadata, dict):
        return trace_metadata.get(key)
    return None


def index_uploaded_files(message: cl.Message, chat_service: ChatService) -> list[str]:
    """Index uploaded document files before running the chat turn."""
    statuses: list[str] = []
    for element in message.elements or []:
        path = uploaded_file_path(element)
        name = uploaded_file_name(element)
        if not path:
            continue
        try:
            result = chat_service.index_document_file(path, display_name=name)
        except (DocumentLoaderError, LangChainChromaUnavailable) as error:
            statuses.append(f"Could not index {name}: {error}")
        except Exception as error:
            statuses.append(f"Could not index {name}: {type(error).__name__}: {error}")
        else:
            statuses.append(
                f"Indexed {result.file_name} into document memory "
                f"({result.chunk_count} chunks)."
            )
    return statuses


def uploaded_file_path(element: object) -> str | None:
    """Return a Chainlit uploaded-file path from object or dict elements."""
    if isinstance(element, dict):
        value = element.get("path")
    else:
        value = getattr(element, "path", None)
    return str(value) if value else None


def uploaded_file_name(element: object) -> str:
    """Return a display name for a Chainlit uploaded file."""
    if isinstance(element, dict):
        value = element.get("name") or element.get("path") or "uploaded file"
    else:
        value = (
            getattr(element, "name", None)
            or getattr(element, "path", None)
            or "uploaded file"
        )
    return str(value)


def current_chainlit_thread_id() -> str | None:
    """Return Chainlit's frontend thread id when running inside a session."""
    try:
        return str(cl.context.session.thread_id)
    except Exception:
        return None


def selected_model_name() -> str:
    """Return the model selected in Chainlit's new-chat profile picker."""
    profile_key = selected_model_profile_key()
    return MODEL_PROFILES_BY_KEY[profile_key].model_name


def selected_model_profile_key() -> str:
    """Return the selected profile key, falling back to Gemma."""
    try:
        profile_key = cl.context.session.chat_profile
    except Exception:
        profile_key = None
    if profile_key in MODEL_PROFILES_BY_KEY:
        return str(profile_key)
    return DEFAULT_MODEL_PROFILE_KEY


def model_name_from_thread(thread: dict) -> str:
    """Resolve the persisted model for a resumed thread."""
    metadata = thread.get("metadata") or {}
    if isinstance(metadata, dict):
        value = metadata.get("model_name")
        if isinstance(value, str) and value:
            return value
    chat_id = thread.get("id")
    return model_name_for_chat(str(chat_id)) if chat_id else selected_model_name()


def model_name_for_chat(chat_id: str) -> str:
    """Load a chat's model from SQLite, with a default for older chats."""
    chat = database.get_chat(chat_id)
    if chat and chat.model_name:
        return chat.model_name
    return MODEL_PROFILES_BY_KEY[DEFAULT_MODEL_PROFILE_KEY].model_name


def chat_service_for_model(model_name: str) -> ChatService:
    """Build or reuse the chat service for a specific model id."""
    if model_name not in chat_services:
        chat_services[model_name] = ChatService(
            database=database,
            model=ModelWrapper(config, model_name=model_name),
            raw_message_limit=config.raw_message_limit,
            memory_update_batch_size=config.memory_update_batch_size,
        )
    return chat_services[model_name]
