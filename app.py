from __future__ import annotations

import os
from typing import NamedTuple

import chainlit as cl
from chainlit.input_widget import Select
from chainlit.types import ChatProfile
from chainlit.user import User

from src.actions.chat_end import ChatEndAction
from src.actions.chat_fork import ChatForkAction
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
from src.orchestration.demo_orchestration import (
    LANGGRAPH_DEMO,
    LANGGRAPH_SHADOW,
    NATIVE,
    normalize_orchestration_mode,
)
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
ORCHESTRATION_SETTING_ID = "orchestration_mode"
ORCHESTRATION_LABELS = {
    "Native": NATIVE,
    "LangGraph Shadow": LANGGRAPH_SHADOW,
    "LangGraph Demo": LANGGRAPH_DEMO,
}


def configured_orchestration_mode() -> str:
    """Return the configured demo initial mode; native is always the fallback."""
    return normalize_orchestration_mode(config.orchestration_mode)


def orchestration_label(mode: str) -> str:
    """Return the Chainlit display label for one normalized mode."""
    return next(
        (
            label
            for label, value in ORCHESTRATION_LABELS.items()
            if value == mode
        ),
        "Native",
    )


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
    cl.user_session.set("chat_ended", False)
    cl.user_session.set("model_name", model_name)
    cl.user_session.set(ORCHESTRATION_SETTING_ID, configured_orchestration_mode())

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
    await send_orchestration_settings()


@cl.on_chat_resume
async def on_chat_resume(thread: dict) -> None:
    """Reconnect a browser session to an existing SQLite-backed chat."""
    chat_id = thread.get("id")
    if chat_id:
        cl.user_session.set("chat_id", chat_id)
        cl.user_session.set("chat_ended", False)
    model_name = model_name_from_thread(thread)
    cl.user_session.set("model_name", model_name)
    cl.user_session.set(ORCHESTRATION_SETTING_ID, configured_orchestration_mode())
    await send_orchestration_settings()


@cl.on_settings_update
async def on_settings_update(settings: dict) -> None:
    """Store orchestration selection for this browser session only."""
    value = settings.get(ORCHESTRATION_SETTING_ID)
    mode = ORCHESTRATION_LABELS.get(str(value), str(value or NATIVE))
    cl.user_session.set(ORCHESTRATION_SETTING_ID, normalize_orchestration_mode(mode))


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle one browser chat message."""
    chat_id = cl.user_session.get("chat_id")
    if not chat_id:
        model_name = selected_model_name()
        chat_service = chat_service_for_model(model_name)
        thread_id = (
            None
            if cl.user_session.get("chat_ended")
            else current_chainlit_thread_id()
        )
        chat_id = chat_service.start_chat(chat_id=thread_id)
        cl.user_session.set("chat_id", chat_id)
        cl.user_session.set("chat_ended", False)
        cl.user_session.set("model_name", model_name)

    model_name = cl.user_session.get("model_name") or model_name_for_chat(chat_id)
    chat_service = chat_service_for_model(model_name)

    upload_statuses = index_uploaded_files(message, chat_service)
    if upload_statuses:
        await cl.Message(content="\n".join(upload_statuses)).send()

    content = (message.content or "").strip()
    if not content:
        return

    orchestration_mode = current_orchestration_mode()
    result = chat_service.handle_user_turn(
        chat_id=chat_id,
        content=content,
        orchestration_mode=orchestration_mode,
    )
    if demo_memory_trace_enabled():
        retrieved_trace = format_retrieved_memories_markdown(retrieved_memory_rows(result))
        if retrieved_trace:
            await cl.Message(content=retrieved_trace).send()

    await cl.Message(content=result.answer).send()
    if orchestration_mode != NATIVE:
        await cl.Message(content=format_orchestration_trace_markdown(result)).send()

    if demo_memory_trace_enabled():
        saved_trace = format_saved_memories_markdown(saved_memory_rows(result))
        if saved_trace:
            await cl.Message(content=saved_trace).send()
    await send_chat_actions()


async def send_chat_actions() -> None:
    """Show lifecycle controls backed by the current chat action services."""
    await cl.Message(
        content="Actions",
        actions=[
            cl.Action(name="end_chat", label="End chat", payload={"value": "end"}),
            cl.Action(name="fork_chat", label="Fork chat", payload={"value": "fork"}),
            cl.Action(name="new_chat", label="New chat", payload={"value": "new"}),
        ],
    ).send()


async def send_orchestration_settings() -> None:
    """Show the per-session orchestration selector with Native as default."""
    await cl.ChatSettings(
        [
            Select(
                id=ORCHESTRATION_SETTING_ID,
                label="Orchestration",
                values=list(ORCHESTRATION_LABELS),
                initial=orchestration_label(current_orchestration_mode()),
                tooltip="Native answers normally; Shadow compares; Demo uses graph context.",
            )
        ]
    ).send()


@cl.action_callback("end_chat")
async def end_chat_handler(action: cl.Action) -> None:
    """Finalize the current chat through the existing safe lifecycle action."""
    del action
    chat_id = cl.user_session.get("chat_id")
    if not chat_id:
        await cl.Message(content="No active chat to end.").send()
        return

    try:
        model_name = cl.user_session.get("model_name") or model_name_for_chat(chat_id)
        chat_service = chat_service_for_model(model_name)
        ChatEndAction(database=database, memory=chat_service.memory).execute(chat_id)
    except Exception as error:
        await cl.Message(content=format_action_error("end chat", error)).send()
        return

    cl.user_session.set("chat_id", None)
    cl.user_session.set("chat_ended", True)
    await cl.Message(content="Chat ended and pending memory was finalized.").send()


@cl.action_callback("fork_chat")
async def fork_chat_handler(action: cl.Action) -> None:
    """Fork the current chat through the existing transactional action."""
    del action
    chat_id = cl.user_session.get("chat_id")
    if not chat_id:
        await cl.Message(content="No active chat to fork.").send()
        return

    try:
        new_chat_id = ChatForkAction(database=database).execute(chat_id)
    except Exception as error:
        await cl.Message(content=format_action_error("fork chat", error)).send()
        return

    cl.user_session.set("chat_id", new_chat_id)
    cl.user_session.set("chat_ended", False)
    await cl.Message(content=f"Chat forked. Active chat: `{new_chat_id}`.").send()
    await send_chat_actions()


@cl.action_callback("new_chat")
async def new_chat_handler(action: cl.Action) -> None:
    """Create a clean backend chat without mutating the previous chat."""
    del action
    try:
        model_name = cl.user_session.get("model_name") or selected_model_name()
        chat_service = chat_service_for_model(model_name)
        chat_id = chat_service.start_chat()
    except Exception as error:
        await cl.Message(content=format_action_error("start a new chat", error)).send()
        return

    cl.user_session.set("chat_id", chat_id)
    cl.user_session.set("chat_ended", False)
    cl.user_session.set("model_name", model_name)
    await cl.Message(content=f"New chat started: `{chat_id}`.").send()
    await send_chat_actions()


def format_action_error(action_name: str, error: Exception) -> str:
    """Return a bounded UI-safe lifecycle error without a traceback."""
    detail = str(error).strip() or type(error).__name__
    if len(detail) > 160:
        detail = f"{detail[:157]}..."
    return f"Could not {action_name}: {detail}"


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


def current_orchestration_mode() -> str:
    """Return the session mode, defaulting safely to native."""
    value = cl.user_session.get(ORCHESTRATION_SETTING_ID)
    return normalize_orchestration_mode(value if isinstance(value, str) else None)


def format_orchestration_trace_markdown(result: object) -> str:
    """Render a compact trace without prompts, secrets, or candidate contents."""
    trace = getattr(result, "trace", None)
    metadata = getattr(trace, "metadata", None)
    orchestration = (
        metadata.get("orchestration")
        if isinstance(metadata, dict)
        else None
    )
    if not isinstance(orchestration, dict):
        return "**Orchestration trace unavailable.**"
    graph = orchestration.get("langgraph_trace")
    graph = graph if isinstance(graph, dict) else {}
    routing = graph.get("routing")
    routing = routing if isinstance(routing, dict) else {}
    intents = routing.get("intents")
    intent = None
    if isinstance(intents, list) and intents and isinstance(intents[0], dict):
        intent = intents[0].get("intent")
    contract = graph.get("evidence_contract")
    contract = contract if isinstance(contract, dict) else {}
    lines = [
        "<details><summary>Orchestration trace</summary>",
        "",
        f"- Requested mode: `{orchestration.get('requested_mode')}`",
        f"- Effective mode: `{orchestration.get('effective_mode')}`",
        f"- Authoritative context: `{orchestration.get('authoritative_context')}`",
        f"- Router: `{routing.get('routing_mode', 'native')}`",
        f"- Intent: `{intent}`",
        f"- Enabled sources: `{graph.get('route_sources', [])}`",
        f"- Requires raw span: `{contract.get('requires_raw_span', False)}`",
        f"- Candidate counts: `{graph.get('candidate_counts_by_source', {})}`",
        f"- Selected counts: `{graph.get('selected_counts_by_source', {})}`",
        f"- Dropped counts: `{graph.get('dropped_counts_by_source', {})}`",
        f"- Drop reasons: `{graph.get('dropped_reasons', [])}`",
        f"- Source budgets: `{graph.get('source_budgets', {})}`",
        f"- Actual context tokens: `{graph.get('actual_context_tokens')}`",
        f"- Provenance valid: `{graph.get('provenance_valid')}`",
        f"- Node timings ms: `{graph.get('node_timings_ms', {})}`",
        f"- Fallback used: `{orchestration.get('fallback_used')}`",
        f"- Error: `{orchestration.get('error')}`",
    ]
    comparison = orchestration.get("comparison")
    if isinstance(comparison, dict):
        lines.extend(
            [
                f"- Native-only sources: `{comparison.get('native_only_sources', [])}`",
                f"- Graph-only sources: `{comparison.get('langgraph_only_sources', [])}`",
                "- Selected candidate overlap: "
                f"`{comparison.get('selected_candidate_overlap')}`",
                f"- Token difference: `{comparison.get('token_difference')}`",
            ]
        )
    lines.extend(["", "</details>"])
    return "\n".join(lines)


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
            endpoint_context_window=config.endpoint_context_window,
            endpoint_context_limit_source=config.endpoint_context_limit_source,
            application_context_cap=config.application_context_cap,
            base_memory_budget=config.base_memory_budget,
            chat_memory_cap=config.chat_memory_cap,
            document_memory_cap=config.document_memory_cap,
            multi_scope_memory_cap=config.multi_scope_memory_cap,
            long_document_memory_cap=config.long_document_memory_cap,
            required_evidence_headroom_ratio=(
                config.required_evidence_headroom_ratio
            ),
            minimum_optional_candidate_utility=(
                config.minimum_optional_candidate_utility
            ),
            routing_mode=config.routing_mode,
            reranker_mode=config.reranker_mode,
            reranker_llm_top_k=config.reranker_llm_top_k,
            reranker_llm_min_confidence=config.reranker_llm_min_confidence,
            reranker_cross_encoder_model=config.reranker_cross_encoder_model,
            reranker_cross_encoder_top_k=config.reranker_cross_encoder_top_k,
            reranker_cross_encoder_weight=config.reranker_cross_encoder_weight,
            reranker_hybrid_backend=config.reranker_hybrid_backend,
            reranker_llm_ambiguity_margin=config.reranker_llm_ambiguity_margin,
            reranker_llm_require_cross_source_conflict=(
                config.reranker_llm_require_cross_source_conflict
            ),
            reranker_llm_provenance_queries=config.reranker_llm_provenance_queries,
            previous_chat_gist_generation_enabled=(
                config.previous_chat_gist_generation_enabled
            ),
        )
    return chat_services[model_name]
