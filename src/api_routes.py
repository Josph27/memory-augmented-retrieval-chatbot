from __future__ import annotations
from datetime import datetime, timezone
import chainlit as cl
from src.database import Database
from typing import Any

_database: Database | None = None
_chat_service_getter: Any | None = None


def get_db() -> Database:
    assert _database is not None
    return _database


def get_chat_svc() -> Any:
    assert _chat_service_getter is not None
    return _chat_service_getter()


def register_api_routes(database: Database, chat_service_getter: Any) -> None:
    global _database, _chat_service_getter
    _database = database
    _chat_service_getter = chat_service_getter

    app = cl.server.app

    # Store length of routes before adding ours
    initial_route_count = len(app.router.routes)

    @app.get("/api/chats")
    async def list_chats(limit: int = 100, cursor: str | None = None, search: str | None = None):
        try:
            chats = get_db().list_chats(
                limit=limit, cursor=cursor, search=search, require_messages=True
            )
            return [
                {
                    "id": c.id,
                    "title": c.title or "Untitled",
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                    "model_name": c.model_name,
                    "active": c.active,
                }
                for c in chats
            ]
        except Exception as e:
            return {"error": str(e)}, 500

    @app.get("/api/chats/{chat_id}/messages")
    async def get_chat_messages(chat_id: str):
        try:
            chat = get_db().get_chat(chat_id)
            if not chat:
                return {"error": "not found"}, 404
            messages = get_db().messages_for_chat(chat_id)
            return [
                {"id": m.id, "role": m.role, "content": m.content, "created_at": m.created_at}
                for m in messages
            ]
        except Exception as e:
            return {"error": str(e)}, 500

    @app.post("/api/chats")
    async def create_chat():
        try:
            svc = get_chat_svc()
            chat_id = svc.start_chat()
            return {"chat_id": chat_id}
        except Exception as e:
            return {"error": str(e)}, 500

    @app.post("/api/chats/{chat_id}/fork")
    async def fork_chat(chat_id: str):
        try:
            chat = get_db().get_chat(chat_id)
            if not chat:
                return {"error": "not found"}, 404
            import uuid

            new_chat_id = str(uuid.uuid4())
            get_db().fork_chat(chat_id, new_chat_id)
            return {"chat_id": new_chat_id}
        except Exception as e:
            return {"error": str(e)}, 500

    @app.post("/api/chats/{chat_id}/end")
    async def end_chat(chat_id: str):
        try:
            chat = get_db().get_chat(chat_id)
            if not chat:
                return {"error": "not found"}, 404
            get_db().mark_chat_inactive(chat_id)
            return {"status": "ended"}
        except Exception as e:
            return {"error": str(e)}, 500

    @app.get("/api/documents")
    async def list_documents(limit: int = 100, status: str | None = None):
        try:
            docs = get_db().list_all_documents(limit=limit, status=status)
            return [
                {
                    "id": d.id,
                    "file_name": d.file_name,
                    "status": d.status,
                    "source": d.source,
                    "chunk_count": d.chunk_count,
                    "error": d.error,
                    "created_at": d.created_at,
                    "updated_at": d.updated_at,
                }
                for d in docs
            ]
        except Exception as e:
            return {"error": str(e)}, 500

    @app.get("/api/memories")
    async def list_memories(limit: int = 200):
        try:
            memories = get_db().list_all_memories(limit=limit)
            return memories
        except Exception as e:
            return {"error": str(e)}, 500

    @app.delete("/api/memories/{memory_id}")
    async def delete_memory(memory_id: str):
        try:
            with get_db().connect() as conn:
                cur = conn.execute(
                    "DELETE FROM long_term_memories WHERE memory_id = ?",
                    (memory_id,),
                )
            if cur.rowcount == 0:
                return {"error": "not found"}, 404
            return {"status": "deleted"}
        except Exception as e:
            return {"error": str(e)}, 500

    @app.get("/api/stats")
    async def system_stats():
        try:
            with get_db().connect() as conn:
                active = conn.execute("SELECT COUNT(*) FROM chats WHERE active=1").fetchone()[0]
                mem_count = conn.execute(
                    "SELECT COUNT(*) FROM long_term_memories WHERE status='active'"
                ).fetchone()[0]
                doc_count = conn.execute(
                    "SELECT COUNT(*) FROM document_records WHERE status='Ready'"
                ).fetchone()[0]
            return {
                "active_chats": active,
                "total_memories": mem_count,
                "ready_documents": doc_count,
                "version": "v2.4.1",
            }
        except Exception as e:
            return {"error": str(e)}, 500

    # Move our newly added routes to the beginning, or at least before the catch-all
    new_routes = app.router.routes[initial_route_count:]
    app.router.routes = new_routes + app.router.routes[:initial_route_count]
