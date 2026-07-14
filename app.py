from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4
from types import SimpleNamespace
from typing import NamedTuple

import chainlit as cl
from chainlit.user import User

from src.actions.chat_end import ChatEndAction
from src.actions.chat_fork import ChatForkAction
from src.chainlit_data_layer import SQLiteChainlitDataLayer
from src.chat_service import ChatService
from src.config import AppConfig
from src.database import Database
from src.documents.loaders import DocumentLoaderError
from src.inspection.answer_inspector import inspection_rows_for_ui
from src.memory.memory_trace import (
    demo_memory_trace_enabled,
)
from src.model_wrapper import ModelWrapper
from src.orchestration.demo_orchestration import (
    NATIVE,
    normalize_orchestration_mode,
)
from src.retrieval.langchain_chroma_retriever import LangChainChromaUnavailable


# Chainlit creates .files/ at import time via config.py:61, but that only
# runs mkdir(exist_ok=True) without parents=True. If the process CWD or
# sandbox state causes that import to miss, uploads crash with
# FileNotFoundError. Ensure the directory exists eagerly.
FILES_DIR = Path(".files")
FILES_DIR.mkdir(parents=True, exist_ok=True)


# Chainlit only exposes persisted thread history to authenticated users.
# For this local prototype, provide a stable local auth identity unless the
# deployment supplies its own secret and credentials.
os.environ.setdefault("CHAINLIT_AUTH_SECRET", "local-dev-chainlit-secret-change-me")

config = AppConfig.from_env()
database = Database(config.database_path)


chat_services: dict[str, ChatService] = {}
ORCHESTRATION_SETTING_ID = "orchestration_mode"


def configured_orchestration_mode() -> str:
    """Return the configured demo initial mode; native is always the fallback."""
    return normalize_orchestration_mode(config.orchestration_mode)


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


@cl.on_chat_start
async def on_chat_start() -> None:
    """Show an empty Home surface without creating a persisted chat."""
    model_name = selected_model_name()
    cl.user_session.set("chat_id", None)
    cl.user_session.set("chat_ended", False)
    cl.user_session.set("model_name", model_name)
    cl.user_session.set(ORCHESTRATION_SETTING_ID, configured_orchestration_mode())
    cl.user_session.set("product_view", "home")
    cl.user_session.set("lifecycle_action_in_progress", None)
    await send_product_state(view="home", chat_id=None, active=None)


@cl.on_chat_resume
async def on_chat_resume(thread: dict) -> None:
    """Reconnect a browser session to an existing SQLite-backed chat."""
    chat_id = thread.get("id")
    if chat_id:
        cl.user_session.set("chat_id", chat_id)
        cl.user_session.set("chat_ended", not database.is_chat_active(str(chat_id)))
    model_name = model_name_from_thread(thread)
    cl.user_session.set("model_name", model_name)
    cl.user_session.set(ORCHESTRATION_SETTING_ID, configured_orchestration_mode())
    cl.user_session.set("product_view", "chat")
    cl.user_session.set("lifecycle_action_in_progress", None)
    if chat_id:
        await send_chat_controls(str(chat_id))
        await send_answer_inspections(str(chat_id))


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handle one browser chat message."""
    print(f"ON_MESSAGE RECEIVED: {message.content!r}", flush=True)
    chat_id = cl.user_session.get("chat_id")
    if chat_id and not database.is_chat_active(str(chat_id)):
        cl.user_session.set("chat_ended", True)
        await send_product_state(
            view="chat",
            chat_id=str(chat_id),
            active=False,
        )
        await send_chat_controls(str(chat_id))
        return
    if not chat_id:
        if cl.user_session.get("chat_ended"):
            await send_product_state(view="home", chat_id=None, active=None)
            return
        model_name = selected_model_name()
        chat_service = chat_service_for_model(model_name)
        thread_id = None if cl.user_session.get("chat_ended") else current_chainlit_thread_id()
        chat_id = chat_service.start_chat(chat_id=thread_id)
        cl.user_session.set("chat_id", chat_id)
        cl.user_session.set("chat_ended", False)
        cl.user_session.set("model_name", model_name)
        cl.user_session.set("product_view", "chat")
        await send_product_state(
            view="chat",
            chat_id=str(chat_id),
            active=True,
        )

    model_name = cl.user_session.get("model_name") or model_name_for_chat(chat_id)
    chat_service = chat_service_for_model(model_name)
    content = (message.content or "").strip()
    persisted_user_message_id = (
        chat_service.persist_user_message_for_turn(str(chat_id), content) if content else None
    )
    upload_result = index_uploaded_files(message, chat_service, str(chat_id))
    if upload_result.statuses:
        for status in upload_result.statuses:
            is_error = status.startswith("Could not index")
            if is_error:
                await cl.Message(
                    id=f"error:{uuid4()}",
                    content=status,
                ).send()
            else:
                await cl.Message(
                    id=f"indexed:{uuid4()}",
                    content=status,
                ).send()

    if not content:
        return

    # Signal the frontend that we've moved from indexing to generating
    await cl.send_window_message(
        {
            "source": "memory-chatbot-ui",
            "command": "processing-stage",
            "stage": "generating",
        }
    )

    orchestration_mode = current_orchestration_mode()
    import asyncio as _asyncio

    loop = _asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: chat_service.handle_user_turn(
            chat_id=chat_id,
            content=content,
            orchestration_mode=orchestration_mode,
            task_context=("document_qa" if upload_result.ready_document_ids else None),
            persisted_user_message_id=persisted_user_message_id,
            defer_post_answer_memory_update=True,
        ),
    )
    if result.metadata.get("answer_status") == "failed":
        await send_product_error(result.answer)
        await cl.Message(
            id=f"error:{result.assistant_message_id}",
            content=result.answer,
        ).send()
        await send_chat_controls(str(chat_id))
        return

    trace_metadata: dict[str, object] = {}
    if demo_memory_trace_enabled():
        retrieved = retrieved_memory_rows(result)
        if retrieved:
            trace_metadata["retrieved"] = retrieved
    if orchestration_mode != NATIVE:
        trace_metadata["orchestration"] = format_orchestration_trace_markdown(result)
    if demo_memory_trace_enabled():
        saved = list(getattr(chat_service.memory, "last_saved_memory_rows", []))
        if saved:
            trace_metadata["saved"] = saved

    # Include retrieval errors from coordinator metadata for visibility
    retrieval_errors = result.metadata.get("retrieval_errors")
    if retrieval_errors:
        trace_metadata["retrieval_errors"] = retrieval_errors

    # Embed trace data in message content so it survives Chainlit persistence
    import json as _json

    answer_text = result.answer
    if trace_metadata:
        trace_json = _json.dumps(trace_metadata, default=str)
        answer_text = f"{result.answer}\n\n<!--breamon-trace:{trace_json}-->"

    await cl.Message(
        id=f"message:{result.assistant_message_id}",
        content=answer_text,
    ).send()
    await send_answer_inspections(str(chat_id))
    chat_service.finalize_post_answer_memory_update(chat_id)
    await send_chat_controls(str(chat_id))


async def send_chat_controls(chat_id: str) -> None:
    """Synchronize lifecycle controls from authoritative persisted chat state."""
    chat = database.get_chat(chat_id)
    if chat is None:
        return
    await send_product_state(
        view="chat",
        chat_id=chat_id,
        active=chat.active,
    )


@cl.action_callback("end_chat")
async def end_chat_handler(action: cl.Action) -> None:
    """Finalize the current chat through the existing safe lifecycle action."""
    chat_id = action_payload(action).get("chat_id") or cl.user_session.get("chat_id")
    if not chat_id:
        await send_product_error("No active chat to end.")
        return
    if not database.is_chat_active(str(chat_id)):
        cl.user_session.set("chat_ended", True)
        await send_chat_controls(str(chat_id))
        return
    if not begin_lifecycle_action("end", str(chat_id)):
        await send_product_error("End Chat is already being processed.")
        return
    try:
        model_name = cl.user_session.get("model_name") or model_name_for_chat(chat_id)
        chat_service = chat_service_for_model(model_name)
        gist_finalizer_factory = getattr(
            chat_service,
            "build_previous_chat_gist_generator",
            None,
        )
        gist_finalizer = gist_finalizer_factory() if callable(gist_finalizer_factory) else None
        if gist_finalizer is None:
            action = ChatEndAction(database=database, memory=chat_service.memory)
        else:
            action = ChatEndAction(
                database=database,
                memory=chat_service.memory,
                gist_finalizer=gist_finalizer,
            )
        action.execute(chat_id)
    except Exception as error:
        await send_product_error(format_action_error("end chat", error))
        return
    finally:
        finish_lifecycle_action()

    cl.user_session.set("chat_ended", True)
    await send_chat_controls(str(chat_id))
    await refresh_sidebar()


@cl.action_callback("fork_chat")
async def fork_chat_handler(action: cl.Action) -> None:
    """Fork the current chat through the existing transactional action."""
    chat_id = action_payload(action).get("chat_id") or cl.user_session.get("chat_id")
    if not chat_id:
        await send_product_error("No chat to fork.")
        return
    if not frontend_thread_switch_available():
        await send_product_error(frontend_navigation_limitation("fork"))
        return
    if not begin_lifecycle_action("fork", str(chat_id)):
        await send_product_error("Fork Chat is already being processed.")
        return
    new_chat_id: str | None = None
    try:
        new_chat_id = ChatForkAction(database=database).execute(chat_id)
        if not await resume_frontend_thread(new_chat_id):
            raise RuntimeError("Chainlit did not accept the frontend thread switch")
    except Exception as error:
        if new_chat_id is not None:
            database.delete_chat(new_chat_id)
        await send_product_error(format_action_error("fork chat", error))
        return
    finally:
        finish_lifecycle_action()

    cl.user_session.set("chat_id", new_chat_id)
    cl.user_session.set("chat_ended", False)
    cl.user_session.set("product_view", "chat")
    await send_chat_controls(new_chat_id)


@cl.action_callback("new_chat")
async def new_chat_handler(action: cl.Action) -> None:
    """Create a clean backend chat without mutating the previous chat."""
    del action
    if not frontend_thread_switch_available():
        await send_product_error(frontend_navigation_limitation("start a new chat"))
        return
    if not begin_lifecycle_action("new", ""):
        await send_product_error("New Chat is already being processed.")
        return
    chat_id: str | None = None
    try:
        model_name = cl.user_session.get("model_name") or selected_model_name()
        chat_service = chat_service_for_model(model_name)
        chat_id = chat_service.start_chat()
        if not await resume_frontend_thread(chat_id):
            raise RuntimeError("Chainlit did not accept the frontend thread switch")
    except Exception as error:
        if chat_id is not None:
            database.delete_chat(chat_id)
        await send_product_error(format_action_error("start a new chat", error))
        return
    finally:
        finish_lifecycle_action()

    cl.user_session.set("chat_id", chat_id)
    cl.user_session.set("chat_ended", False)
    cl.user_session.set("model_name", model_name)
    cl.user_session.set("product_view", "chat")
    await send_chat_controls(chat_id)


@cl.action_callback("nav_home")
async def nav_home_handler(action: cl.Action) -> None:
    """Return to the empty Home surface without writing a chat message."""
    del action
    cl.user_session.set("chat_id", None)
    cl.user_session.set("chat_ended", False)
    cl.user_session.set("product_view", "home")
    await send_product_state(view="home", chat_id=None, active=None)
    await navigate_frontend_home()


@cl.on_window_message
async def product_window_message(data: object) -> None:
    """Route custom product-shell actions to existing authoritative handlers."""
    if not isinstance(data, dict):
        return
    if data.get("source") != "memory-chatbot-ui":
        return
    if data.get("command") != "lifecycle-action":
        return
    action_name = data.get("action")
    payload = {"chat_id": data.get("chat_id")}
    action = SimpleNamespace(payload=payload)
    if action_name == "new":
        await new_chat_handler(action)
    elif action_name == "end":
        await end_chat_handler(action)
    elif action_name == "fork":
        await fork_chat_handler(action)
    elif action_name == "home":
        await nav_home_handler(action)


def action_payload(action: object) -> dict:
    """Return a bounded action payload from Chainlit or a test double."""
    payload = getattr(action, "payload", None)
    return payload if isinstance(payload, dict) else {}


def begin_lifecycle_action(name: str, chat_id: str) -> bool:
    """Prevent duplicate lifecycle callbacks within one browser session."""
    if cl.user_session.get("lifecycle_action_in_progress"):
        return False
    cl.user_session.set("lifecycle_action_in_progress", f"{name}:{chat_id}")
    return True


def finish_lifecycle_action() -> None:
    """Clear the per-session lifecycle action guard."""
    cl.user_session.set("lifecycle_action_in_progress", None)


def frontend_thread_switch_available() -> bool:
    """Return whether this Chainlit version exposes a real resume event."""
    try:
        return callable(cl.context.emitter.resume_thread)
    except Exception:
        return False


async def resume_frontend_thread(chat_id: str) -> bool:
    """Open an existing persisted thread without generating or saving a turn."""
    thread = await data_layer().get_thread(chat_id)
    if thread is None:
        return False
    try:
        session = cl.context.session
        emitter = cl.context.emitter
    except Exception:
        return False
    await emitter.resume_thread(thread)
    session.thread_id = chat_id
    session.thread_id_to_resume = chat_id
    return True


def frontend_navigation_limitation(action: str) -> str:
    """Explain a missing Chainlit capability without mutating backend state."""
    return (
        f"Could not {action} because this Chainlit client does not expose the "
        "thread-resume event. Use the native History/New Chat controls."
    )


async def send_product_state(
    *,
    view: str,
    chat_id: str | None,
    active: bool | None,
) -> None:
    """Update the custom product shell without inserting transcript content."""
    try:
        await cl.send_window_message(
            {
                "source": "memory-chatbot-ui",
                "command": "product-state",
                "view": view,
                "chat_id": chat_id,
                "active": active,
            }
        )
    except Exception:
        return


async def send_answer_inspections(chat_id: str) -> None:
    """Send persisted, bounded answer diagnostics to the read-only browser panel."""
    try:
        inspections = inspection_rows_for_ui(database, chat_id)
        await cl.send_window_message(
            {
                "source": "memory-chatbot-ui",
                "command": "answer-inspections",
                "chat_id": chat_id,
                "inspections": inspections,
            }
        )
    except Exception:
        return


async def refresh_sidebar() -> None:
    """Reload native thread history after a persisted lifecycle transition."""
    try:
        await cl.send_window_message(
            {
                "source": "memory-chatbot-ui",
                "command": "refresh-sidebar",
            }
        )
    except Exception:
        return


async def navigate_frontend_home() -> None:
    """Ask the browser to open the unsaved root composer."""
    try:
        await cl.send_window_message(
            {
                "source": "memory-chatbot-ui",
                "command": "navigate-home",
            }
        )
    except Exception:
        return


async def send_product_error(content: str) -> None:
    """Show a transient product error without persisting it as chat history."""
    try:
        await cl.send_window_message(
            {
                "source": "memory-chatbot-ui",
                "command": "product-error",
                "message": content,
            }
        )
    except Exception:
        return


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
    orchestration = metadata.get("orchestration") if isinstance(metadata, dict) else None
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
                f"- Selected candidate overlap: `{comparison.get('selected_candidate_overlap')}`",
                f"- Token difference: `{comparison.get('token_difference')}`",
            ]
        )
    lines.extend(["", "</details>"])
    return "\n".join(lines)


class UploadedFilesResult(NamedTuple):
    """Compact result for one synchronous Chainlit upload batch."""

    statuses: tuple[str, ...]
    ready_document_ids: tuple[str, ...]


def index_uploaded_files(
    message: cl.Message,
    chat_service: ChatService,
    chat_id: str | None = None,
) -> UploadedFilesResult:
    """Index uploaded document files before running the chat turn."""
    statuses: list[str] = []
    ready_document_ids: list[str] = []
    for element in message.elements or []:
        path = uploaded_file_path(element)
        name = uploaded_file_name(element)
        if not path:
            continue
        try:
            result = chat_service.index_document_file(
                path,
                display_name=name,
                chat_id=chat_id,
                operation_id=uploaded_file_operation_id(element, chat_id, path),
            )
        except (DocumentLoaderError, LangChainChromaUnavailable) as error:
            statuses.append(f"Could not index {name}: {error}")
        except Exception as error:
            statuses.append(f"Could not index {name}: {type(error).__name__}: {error}")
        else:
            ready_document_ids.append(result.document_id)
            statuses.append(
                f"Indexed {result.file_name} into document memory ({result.chunk_count} chunks)."
            )
    return UploadedFilesResult(
        statuses=tuple(statuses),
        ready_document_ids=tuple(ready_document_ids),
    )


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
        value = getattr(element, "name", None) or getattr(element, "path", None) or "uploaded file"
    return str(value)


def uploaded_file_operation_id(
    element: object,
    chat_id: str | None,
    path: str,
) -> str:
    """Return a stable upload operation id for one Chainlit file element."""
    if isinstance(element, dict):
        element_id = element.get("id")
    else:
        element_id = getattr(element, "id", None)
    stable_file_id = str(element_id or path)
    return f"document-upload:{chat_id or 'unscoped'}:{stable_file_id}"


def current_chainlit_thread_id() -> str | None:
    """Return Chainlit's frontend thread id when running inside a session."""
    try:
        return str(cl.context.session.thread_id)
    except Exception:
        return None


def selected_model_name() -> str:
    """Return the single model configured for this application instance."""
    return config.model_name


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
    return config.model_name


def chat_service_for_model(model_name: str) -> ChatService:
    """Build or reuse the chat service for a specific model id."""
    if model_name not in chat_services:
        chat_services[model_name] = ChatService(
            database=database,
            model=ModelWrapper(config, model_name=model_name),
            raw_message_limit=config.raw_message_limit,
            memory_update_batch_size=config.memory_update_batch_size,
            recent_messages_max_count=config.recent_messages_max_count,
            memory_update_trigger_tokens=config.memory_update_trigger_tokens,
            memory_update_max_input_tokens=config.memory_update_max_input_tokens,
            memory_update_max_messages=config.memory_update_max_messages,
            memory_recent_protection_tokens=config.memory_recent_protection_tokens,
            memory_update_policy=config.memory_update_policy,
            memory_replay_trigger_tokens=config.memory_replay_trigger_tokens,
            memory_replay_max_input_tokens=config.memory_replay_max_input_tokens,
            memory_replay_max_messages=config.memory_replay_max_messages,
            endpoint_context_window=config.endpoint_context_window,
            endpoint_context_limit_source=config.endpoint_context_limit_source,
            application_context_cap=config.application_context_cap,
            base_memory_budget=config.base_memory_budget,
            memory_recall_budget_tokens=config.memory_recall_budget_tokens,
            chat_memory_cap=config.chat_memory_cap,
            document_memory_cap=config.document_memory_cap,
            multi_scope_memory_cap=config.multi_scope_memory_cap,
            long_document_memory_cap=config.long_document_memory_cap,
            global_summary_budget_tokens=config.global_summary_budget_tokens,
            global_summary_max_budget_tokens=(config.global_summary_max_budget_tokens),
            global_summary_reserved_tokens=config.global_summary_reserved_tokens,
            required_evidence_headroom_ratio=(config.required_evidence_headroom_ratio),
            minimum_optional_candidate_utility=(config.minimum_optional_candidate_utility),
            direct_raw_retrieval_candidates=(config.direct_raw_retrieval_candidates),
            raw_span_overlap_threshold=config.raw_span_overlap_threshold,
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
            previous_chat_gist_extractor=config.previous_chat_gist_extractor,
            previous_chat_gist_max_messages_per_gist=(
                config.previous_chat_gist_max_messages_per_gist
            ),
        )
    return chat_services[model_name]


from src.api_routes import register_api_routes  # noqa: E402

register_api_routes(
    database=database, chat_service_getter=lambda: chat_service_for_model(config.model_name)
)
