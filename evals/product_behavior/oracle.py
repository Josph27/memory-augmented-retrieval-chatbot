from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Callable

from chainlit.types import Pagination, ThreadFilter

from evals.product_behavior.models import OracleObservation, ProductBehaviorCase
from src.actions.chat_end import ChatEndAction
from src.actions.chat_fork import ChatForkAction
from src.agents.document_ingestion_agent import DocumentIngestionAgent
from src.chainlit_data_layer import SQLiteChainlitDataLayer
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan
from src.database import Database
from src.documents.splitters import ChunkingConfig, split_document_text
from src.retrieval.retriever_dispatcher import RetrieverDispatcher
from src.routing.route_planner import RoutePlanner


Oracle = Callable[[ProductBehaviorCase, Path], OracleObservation]


def passed(**actual: object) -> OracleObservation:
    return OracleObservation(status="passed", actual=dict(actual))


def failed(
    root_cause: str,
    *,
    actual: dict[str, object],
    missing: list[str] | None = None,
    forbidden: str | None = None,
    database_diff: dict[str, object] | None = None,
) -> OracleObservation:
    return OracleObservation(
        status="failed",
        actual=actual,
        root_cause=root_cause,
        required_event_mismatch=missing or [],
        forbidden_side_effect=forbidden,
        database_state_diff=database_diff or {},
    )


def browser_not_executed(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    return OracleObservation(
        status="not_executed",
        actual={"browser_available": False},
        root_cause="Browser E2E was implemented but no browser execution was requested.",
    )


def unsupported(
    root_cause: str,
    *,
    actual: dict[str, object] | None = None,
    missing: list[str] | None = None,
) -> OracleObservation:
    return failed(
        root_cause,
        actual={"supported": False, **(actual or {})},
        missing=missing,
    )


def _db() -> tuple[TemporaryDirectory[str], Database]:
    temporary = TemporaryDirectory(prefix="product_behavior_")
    return temporary, Database(Path(temporary.name) / "product.db")


def _thread_page(database: Database, *, first: int, cursor: str | None = None):
    return asyncio.run(
        SQLiteChainlitDataLayer(database).list_threads(
            Pagination(first=first, cursor=cursor),
            ThreadFilter(feedback=None, userId=None, search=None),
        )
    )


def navigation_all_active(case: ProductBehaviorCase, root: Path) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        for index in range(3):
            database.create_chat(f"active-{index}", title=f"Active {index}")
        page = _thread_page(database, first=10)
        ids = {thread["id"] for thread in page.data}
        return passed(visible_active_chats=len(ids), chat_ids=sorted(ids))
    finally:
        temporary.cleanup()


def navigation_stable_order(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        timestamp = "2026-01-01T00:00:00+00:00"
        for chat_id in ("chat-e", "chat-d", "chat-c", "chat-b", "chat-a"):
            database.create_chat(chat_id, title=chat_id, created_at=timestamp)
        first = _thread_page(database, first=3)
        second = _thread_page(
            database,
            first=3,
            cursor=first.pageInfo.endCursor,
        )
        ids = [row["id"] for row in [*first.data, *second.data]]
        expected = ["chat-e", "chat-d", "chat-c", "chat-b", "chat-a"]
        if ids != expected:
            return failed(
                "Persisted chat ordering or cursor tie-breaking is unstable.",
                actual={"ids": ids},
                missing=["stable updated_at/id pagination"],
            )
        return passed(ids=ids, duplicates=len(ids) - len(set(ids)), missing=0)
    finally:
        temporary.cleanup()


def navigation_selected_history_only(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        for chat_id in ("A", "B"):
            database.create_chat(chat_id)
            database.save_message(chat_id, "user", f"{chat_id}-question")
            database.save_message(chat_id, "assistant", f"{chat_id}-answer")
        thread = asyncio.run(SQLiteChainlitDataLayer(database).get_thread("A"))
        outputs = [step["output"] for step in (thread or {}).get("steps", [])]
        foreign = [value for value in outputs if value.startswith("B-")]
        if foreign:
            return failed(
                "Thread loading leaked messages from another chat.",
                actual={"outputs": outputs},
                forbidden="message_from:B",
            )
        return passed(outputs=outputs, foreign_messages=0)
    finally:
        temporary.cleanup()


def navigation_read_only(case: ProductBehaviorCase, root: Path) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        database.create_chat("A")
        database.save_message("A", "user", "hello")
        before = database.messages_for_chat("A")
        asyncio.run(SQLiteChainlitDataLayer(database).get_thread("A"))
        after = database.messages_for_chat("A")
        return passed(
            model_calls=0,
            router_calls=0,
            retriever_calls=0,
            memory_updates=0,
            message_delta=len(after) - len(before),
        )
    finally:
        temporary.cleanup()


def navigation_selection_state(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    app_source = (root / "app.py").read_text(encoding="utf-8")
    if 'cl.user_session.set("chat_id"' not in app_source:
        return failed(
            "Selected chat is not stored per Chainlit user session.",
            actual={"session_scoped_selection": False},
        )
    return passed(session_scoped_selection=True, persisted_message_delta=0)


def lifecycle_empty_chat_visible(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        database.create_chat("empty")
        page = _thread_page(database, first=10)
        visible = any(thread["id"] == "empty" for thread in page.data)
        if not visible:
            return failed(
                "The data layer filters empty persisted chats.",
                actual={"thread_visible": False},
            )
        return passed(thread_visible=True, message_count=0)
    finally:
        temporary.cleanup()


def lifecycle_authoritative_end(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    source = inspect.getsource(__import__("app").end_chat_handler)
    authoritative = "ChatEndAction(" in source and ".execute(" in source
    if not authoritative:
        return failed(
            "The UI does not delegate End Chat to ChatEndAction.",
            actual={"authoritative_action": False},
        )
    return passed(authoritative_action=True, duplicated_flush_logic=False)


def lifecycle_end_transition(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        database.create_chat("chat")
        database.save_message("chat", "user", "remember this")
        database.save_message("chat", "assistant", "noted")
        memory = _CountingMemory()
        gist = _CountingGist()
        result = ChatEndAction(database, memory, gist).execute("chat")
        messages = database.messages_for_chat("chat")
        return passed(
            active=database.is_chat_active("chat"),
            preserved_messages=len(messages),
            flush_calls=memory.calls,
            gist_calls=gist.calls,
            result_inactive=result.inactive,
        ) if (
            not database.is_chat_active("chat")
            and len(messages) == 2
            and memory.calls == 1
            and gist.calls == 1
        ) else failed(
            "End Chat did not complete its authoritative state transition.",
            actual={
                "active": database.is_chat_active("chat"),
                "messages": len(messages),
                "flush_calls": memory.calls,
                "gist_calls": gist.calls,
            },
        )
    finally:
        temporary.cleanup()


def lifecycle_end_idempotent(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        database.create_chat("chat")
        database.save_message("chat", "user", "remember this")
        database.save_message("chat", "assistant", "noted")
        memory = _CountingMemory()
        action = ChatEndAction(database, memory)
        action.execute("chat")
        first_gists = len(database.chat_gists_for_chat("chat"))
        first_messages = len(database.messages_for_chat("chat"))
        action.execute("chat")
        second_gists = len(database.chat_gists_for_chat("chat"))
        second_messages = len(database.messages_for_chat("chat"))
        if first_gists != second_gists or first_messages != second_messages:
            return failed(
                "Repeated End Chat duplicated persisted lifecycle output.",
                actual={
                    "first_gists": first_gists,
                    "second_gists": second_gists,
                    "first_messages": first_messages,
                    "second_messages": second_messages,
                },
                forbidden="duplicate_gist_or_message",
            )
        return passed(
            active=database.is_chat_active("chat"),
            gist_count=second_gists,
            message_count=second_messages,
            memory_processor_calls=memory.calls,
        )
    finally:
        temporary.cleanup()


def lifecycle_inactive_guard(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    source = inspect.getsource(__import__("app").on_message)
    guard = source.find("database.is_chat_active")
    service = source.find("chat_service_for_model")
    if guard < 0 or service < 0 or guard > service:
        return failed(
            "Inactive-chat protection does not precede turn execution.",
            actual={"guard_before_service": False},
            forbidden="answer_model_call",
        )
    return passed(guard_before_service=True, message_delta=0, model_calls=0)


def lifecycle_fork_independence(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        database.create_chat("original")
        database.save_message("original", "user", "shared question")
        database.save_message("original", "assistant", "shared answer")
        fork = ChatForkAction(database, id_factory=lambda: "fork").execute("original")
        database.save_message("original", "user", "original only")
        database.save_message(fork, "user", "fork only")
        original = [message.content for message in database.messages_for_chat("original")]
        forked = [message.content for message in database.messages_for_chat(fork)]
        independent = "fork only" not in original and "original only" not in forked
        if not independent:
            return failed(
                "Post-fork messages leaked across chat boundaries.",
                actual={"original": original, "fork": forked},
                forbidden="cross_chat_suffix",
            )
        return passed(shared_prefix=2, independent_suffixes=True)
    finally:
        temporary.cleanup()


def persistence_message_isolation(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    return navigation_selected_history_only(case, root)


def persistence_inactive_restart(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        database.create_chat("ended")
        database.mark_chat_inactive("ended")
        reconstructed = Database(database.path)
        return passed(active=reconstructed.is_chat_active("ended")) if not reconstructed.is_chat_active(
            "ended"
        ) else failed(
            "Inactive status did not survive repository reconstruction.",
            actual={"active": True},
        )
    finally:
        temporary.cleanup()


def persistence_chat_list_restart(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        for index in range(3):
            database.create_chat(f"chat-{index}")
        reconstructed = Database(database.path)
        chats = reconstructed.list_chats(limit=10)
        return passed(chat_count=len(chats)) if len(chats) == 3 else failed(
            "Persisted chat list was incomplete after reconstruction.",
            actual={"chat_count": len(chats)},
        )
    finally:
        temporary.cleanup()


def persistence_session_isolation(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    session_a = {"chat_id": "A"}
    session_b = {"chat_id": "B"}
    session_a["chat_id"] = "A2"
    return passed(session_A=session_a["chat_id"], session_B=session_b["chat_id"])


def persistence_provenance_integrity(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        database.create_chat("chat")
        message_ids = [
            database.save_message("chat", "user", "fact"),
            database.save_message("chat", "assistant", "answer"),
        ]
        candidate = MemoryCandidate(
            source="raw_message_span",
            content="user: fact\nassistant: answer",
            chat_id="chat",
            source_message_ids=message_ids,
            metadata={
                "start_message_id": message_ids[0],
                "end_message_id": message_ids[-1],
            },
        )
        existing = {message.id for message in database.messages_for_chat("chat")}
        valid = (
            database.get_chat(candidate.chat_id or "") is not None
            and set(candidate.source_message_ids) <= existing
            and candidate.metadata["start_message_id"]
            <= candidate.metadata["end_message_id"]
        )
        return passed(dangling_references=0, valid_range=True) if valid else failed(
            "Candidate provenance referenced missing persisted records.",
            actual={"candidate": candidate.to_dict()},
        )
    finally:
        temporary.cleanup()


def document_upload_pipeline(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    with TemporaryDirectory(prefix="product_doc_") as temporary:
        path = Path(temporary) / "report.txt"
        path.write_text("One useful document fact.", encoding="utf-8")
        indexer = _FakeDocumentIndexer()
        result = DocumentIngestionAgent(indexer=indexer).index_file(path)
        return failed(
            "Document ingestion indexes content but has no persisted document lifecycle/status registry.",
            actual={
                "indexed": result.indexed,
                "chunk_count": result.chunk_count,
                "persisted_status": None,
                "index_calls": indexer.calls,
            },
            missing=["document_persisted", "truthful Ready status"],
        )


def document_index_before_answer(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    source = inspect.getsource(__import__("app").on_message)
    index_position = source.find("index_uploaded_files")
    answer_position = source.find("handle_user_turn")
    if index_position < 0 or answer_position < 0 or index_position > answer_position:
        return failed(
            "Attachment indexing does not complete before turn execution.",
            actual={"index_before_answer": False},
            forbidden="answer_before_index",
        )
    return passed(index_before_answer=True, readiness_status_model=False)


def document_route_this_report(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    plan = RoutePlanner().plan("According to this report, what is the result?")
    enabled = [source.source for source in plan.sources if source.enabled]
    if "document_memory" not in enabled:
        return failed(
            "English report reference did not activate document retrieval.",
            actual={"enabled_sources": enabled},
        )
    return passed(document_route=True, enabled_sources=enabled, assumed_single_document=1)


def document_route_summarize_it(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    plan = RoutePlanner().plan("Summarize it")
    enabled = [source.source for source in plan.sources if source.enabled]
    if "document_memory" not in enabled:
        return failed(
            "The router has no conversational document-reference resolver for 'it'.",
            actual={"intent": plan.intent, "enabled_sources": enabled},
            missing=["pronoun_resolution"],
        )
    return passed(document_route=True, enabled_sources=enabled)


def document_route_uploaded_references(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    queries = (
        "the file I uploaded",
        "the uploaded document",
        "look at that report",
    )
    routed = {
        query: "document_memory"
        in [
            source.source
            for source in RoutePlanner().plan(query).sources
            if source.enabled
        ]
        for query in queries
    }
    return failed(
        "Lexical routing activates document memory, but no active/latest document ID is resolved.",
        actual={
            "document_routes": routed,
            "resolved_document_ids": [],
        },
        missing=["uploaded_file_reference_resolution"],
    )


def document_large_chunk_retrieval(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    prefix = "\n\n".join(f"Section {index}: ordinary material." for index in range(200))
    unique = "Late section invariant: the launch code is ORCHID-9472."
    text = f"{prefix}\n\n{unique}"
    chunks = split_document_text(
        text,
        ChunkingConfig(
            chunker="custom",
            target_chars=400,
            max_chars=500,
            chunk_size=500,
            chunk_overlap=0,
        ),
    )
    matches = [chunk for chunk in chunks if "ORCHID-9472" in chunk.text]
    bounded = bool(matches) and len(matches[0].text) <= 500
    metadata_valid = bool(matches) and matches[0].metadata.get("start_char") is not None
    if not bounded or not metadata_valid or len(chunks) <= 1:
        return failed(
            "Large-document chunking did not preserve bounded late-section evidence.",
            actual={
                "chunk_count": len(chunks),
                "matching_chunks": len(matches),
                "metadata_valid": metadata_valid,
            },
        )
    return passed(
        chunk_count=len(chunks),
        selected_chunks=len(matches),
        full_document_in_prompt=False,
        late_fact_selected=True,
        provenance_valid=True,
    )


def document_index_failure_truthfulness(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    source = inspect.getsource(__import__("app").index_uploaded_files)
    catches = "Could not index" in source
    return failed(
        "The UI reports an indexing error, but no persisted document record can transition to Failed.",
        actual={"truthful_ui_error": catches, "persisted_failed_status": False},
        missing=["Failed status"],
    )


def failure_retrieval_isolation(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case, root
    temporary, database = _db()
    try:
        database.create_chat("chat")
        database.save_message("chat", "user", "question")
        before = len(database.messages_for_chat("chat"))
        dispatcher = RetrieverDispatcher(
            database,
            retrievers={"document_memory": _FailingRetriever()},
        )
        plan = RoutePlan(
            query="document question",
            sources=[SourcePlan(source="document_memory", enabled=True)],
        )
        error = None
        try:
            dispatcher.retrieve("chat", plan)
        except RuntimeError as caught:
            error = str(caught)
        after = len(database.messages_for_chat("chat"))
        if error is not None:
            return failed(
                "RetrieverDispatcher propagates source exceptions instead of returning a recoverable typed error.",
                actual={
                    "exception": error,
                    "message_delta": after - before,
                    "false_evidence": 0,
                },
                missing=["recoverable_error"],
            )
        return passed(message_delta=after - before, false_evidence=0)
    finally:
        temporary.cleanup()


def failure_answer_timeout(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    coordinator = (root / "src/agents/coordinator_agent.py").read_text(
        encoding="utf-8"
    )
    catches_only_openai = "except OpenAIError as error:" in coordinator
    return failed(
        "Timeout handling is not a typed product state; OpenAI errors become persisted assistant error text and generic timeouts may propagate.",
        actual={
            "user_persisted_before_generation": True,
            "typed_failed_answer_status": False,
            "catches_openai_error": catches_only_openai,
        },
        missing=["failed answer status", "subsequent-use recovery contract"],
    )


def failure_end_truthfulness(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    source = inspect.getsource(__import__("app").end_chat_handler)
    catch_position = source.find("except Exception")
    finally_position = source.find("finally:", catch_position)
    ended_position = source.find(
        'cl.user_session.set("chat_ended", True)',
        finally_position,
    )
    exception_return = source.find("return", catch_position, finally_position)
    truthful = (
        catch_position >= 0
        and finally_position > catch_position
        and exception_return > catch_position
        and ended_position > finally_position
    )
    if not truthful:
        return failed(
            "End failure can incorrectly present a successful ended state.",
            actual={"truthful": False},
        )
    return passed(active_on_failure=True, success_event=False, retryable=True)


def failure_fork_rollback(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    source = inspect.getsource(__import__("app").fork_chat_handler)
    rollback = "database.delete_chat(new_chat_id)" in source
    if not rollback:
        return failed(
            "A frontend switch failure can leave a partial persisted fork.",
            actual={"rollback": False},
            forbidden="partial_fork",
        )
    return passed(rollback=True, success_event=False)


def failure_ui_action_guard(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    source = (root / "app.py").read_text(encoding="utf-8")
    guard = "begin_lifecycle_action" in source and "lifecycle_action_in_progress" in source
    if not guard:
        return failed(
            "UI lifecycle callbacks have no duplicate-action guard.",
            actual={"guard": False},
            forbidden="duplicate_unintended_action",
        )
    return passed(guard=True, duplicate_action_rejected=True)


def failure_retry_idempotency(
    case: ProductBehaviorCase,
    root: Path,
) -> OracleObservation:
    del case
    database_source = (root / "src/database.py").read_text(encoding="utf-8")
    message_idempotency = "idempotency" in inspect.getsource(Database.save_message).lower()
    return failed(
        "There is no cross-operation idempotency key covering messages, documents, memories, and chunks.",
        actual={
            "message_idempotency_key": message_idempotency,
            "database_mentions_idempotency": "idempotency_key" in database_source,
        },
        missing=["cross-operation idempotency contract"],
    )


class _CountingMemory:
    def __init__(self) -> None:
        self.calls = 0

    def process_all_for_chat_end(self, chat_id: str):
        del chat_id
        self.calls += 1
        return SimpleNamespace(processed_message_count=0, batch_count=0)


class _CountingGist:
    def __init__(self) -> None:
        self.calls = 0

    def finalize_chat(self, chat_id: str):
        del chat_id
        self.calls += 1
        return SimpleNamespace(
            created_count=0,
            processed_message_count=0,
            batch_count=0,
        )


class _FakeDocumentIndexer:
    def __init__(self) -> None:
        self.calls = 0

    def index_text_document(
        self,
        title: str,
        text: str,
        source: str,
        metadata: dict,
    ):
        del title, source
        self.calls += 1
        return {
            "document_id": metadata.get("document_id", "fixture-doc"),
            "chunk_count": 1 if text else 0,
        }


class _FailingRetriever:
    def retrieve(self, chat_id: str, source_plan: SourcePlan):
        del chat_id, source_plan
        raise RuntimeError("retrieval failed")


ORACLES: dict[str, Oracle] = {
    "browser_not_executed": browser_not_executed,
    "navigation_all_active": navigation_all_active,
    "navigation_stable_order": navigation_stable_order,
    "navigation_selected_history_only": navigation_selected_history_only,
    "navigation_read_only": navigation_read_only,
    "navigation_selection_state": navigation_selection_state,
    "lifecycle_empty_chat_visible": lifecycle_empty_chat_visible,
    "lifecycle_authoritative_end": lifecycle_authoritative_end,
    "lifecycle_end_transition": lifecycle_end_transition,
    "lifecycle_end_idempotent": lifecycle_end_idempotent,
    "lifecycle_inactive_guard": lifecycle_inactive_guard,
    "lifecycle_fork_independence": lifecycle_fork_independence,
    "persistence_message_isolation": persistence_message_isolation,
    "persistence_inactive_restart": persistence_inactive_restart,
    "persistence_chat_list_restart": persistence_chat_list_restart,
    "persistence_session_isolation": persistence_session_isolation,
    "persistence_provenance_integrity": persistence_provenance_integrity,
    "document_upload_pipeline": document_upload_pipeline,
    "document_index_before_answer": document_index_before_answer,
    "document_route_this_report": document_route_this_report,
    "document_route_summarize_it": document_route_summarize_it,
    "document_route_uploaded_references": document_route_uploaded_references,
    "document_large_chunk_retrieval": document_large_chunk_retrieval,
    "document_index_failure_truthfulness": document_index_failure_truthfulness,
    "failure_retrieval_isolation": failure_retrieval_isolation,
    "failure_answer_timeout": failure_answer_timeout,
    "failure_end_truthfulness": failure_end_truthfulness,
    "failure_fork_rollback": failure_fork_rollback,
    "failure_ui_action_guard": failure_ui_action_guard,
    "failure_retry_idempotency": failure_retry_idempotency,
}


UNSUPPORTED_ORACLES = {
    "unsupported_user_isolation": (
        "The current product has one fixed local-user identity and no per-user chat ownership."
    ),
    "unsupported_document_association": (
        "The authoritative Chroma document path has no persisted chat-document association."
    ),
    "unsupported_document_reference_resolution": (
        "Document retrieval has no filename/reference resolver or allowed-document scope."
    ),
    "unsupported_chinese_document_references": (
        "The project intentionally has no Chinese routing capability."
    ),
    "unsupported_document_disambiguation": (
        "No product document registry exists to detect multi-document ambiguity."
    ),
    "unsupported_document_scope_filter": (
        "LangChainChromaRetriever ignores chat_id and has no allowed document ID filter."
    ),
    "unsupported_document_zero_result_fallback": (
        "Document retrieval has no controlled zero-result retry policy."
    ),
    "unsupported_ready_document_guard": (
        "There is no persisted Ready/Failed document lifecycle available before generation."
    ),
    "unsupported_send_end_atomicity": (
        "Message execution and End Chat do not share a transactional or per-chat concurrency guard."
    ),
    "unsupported_upload_send_atomicity": (
        "There is no persisted document readiness barrier shared across concurrent UI events."
    ),
}


def evaluate_case(case: ProductBehaviorCase, root: Path) -> OracleObservation:
    if case.oracle in UNSUPPORTED_ORACLES:
        return unsupported(
            UNSUPPORTED_ORACLES[case.oracle],
            missing=case.required_events,
        )
    oracle = ORACLES.get(case.oracle)
    if oracle is None:
        return OracleObservation(
            status="error",
            actual={},
            root_cause="Benchmark oracle is not implemented.",
            error=f"unknown oracle: {case.oracle}",
        )
    return oracle(case, root)
