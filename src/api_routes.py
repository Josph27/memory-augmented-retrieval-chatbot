from __future__ import annotations
import asyncio
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

    @app.post("/api/chats/{chat_id}/reactivate")
    async def reactivate_chat(chat_id: str):
        try:
            chat = get_db().get_chat(chat_id)
            if not chat:
                return {"error": "not found"}, 404
            get_db().mark_chat_active(chat_id)
            return {"status": "activated"}
        except Exception as e:
            return {"error": str(e)}, 500

    @app.post("/api/chats/{chat_id}/consolidate")
    async def consolidate_chat(chat_id: str):
        try:
            chat = get_db().get_chat(chat_id)
            if not chat:
                return {"error": "not found"}, 404
            svc = get_chat_svc()
            result = await asyncio.wait_for(
                asyncio.to_thread(svc.memory.process_all_for_chat_end, chat_id),
                timeout=6,
            )
            return {
                "status": "consolidated",
                "processed": result.processed_message_count,
                "batches": result.batch_count,
            }
        except asyncio.TimeoutError:
            return {
                "error": "Memory consolidation timed out after 6 seconds — the model may be unresponsive."
            }, 504
        except Exception as e:
            return {"error": str(e)}, 500

    @app.delete("/api/chats/{chat_id}")
    async def delete_chat(chat_id: str):
        try:
            chat = get_db().get_chat(chat_id)
            if not chat:
                return {"error": "not found"}, 404
            get_db().delete_chat(chat_id)
            return {"status": "deleted"}
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

    @app.post("/api/documents/{doc_id}/deactivate")
    async def deactivate_document(doc_id: str):
        try:
            doc = get_db().get_document(doc_id)
            if not doc:
                return {"error": "not found"}, 404
            get_db().update_document_status(doc_id, "deleted")
            return {"status": "deactivated"}
        except Exception as e:
            return {"error": str(e)}, 500

    @app.post("/api/documents/{doc_id}/activate")
    async def activate_document(doc_id: str):
        try:
            doc = get_db().get_document(doc_id)
            if not doc:
                return {"error": "not found"}, 404
            get_db().update_document_status(doc_id, "Ready")
            return {"status": "activated"}
        except Exception as e:
            return {"error": str(e)}, 500

    @app.delete("/api/documents/{doc_id}")
    async def delete_document(doc_id: str):
        try:
            doc = get_db().get_document(doc_id)
            if not doc:
                return {"error": "not found"}, 404

            warnings: list[str] = []
            # Clean up Chroma chunks
            try:
                from src.config import AppConfig
                from src.documents.inspection import delete_document_chunks
                from src.retrieval.langchain_chroma_retriever import DEFAULT_COLLECTION_NAME

                config = AppConfig.from_env()
                chunks_removed = delete_document_chunks(
                    persist_dir=str(config.langchain_chroma_persist_dir),
                    document_id=doc_id,
                    collection_name=DEFAULT_COLLECTION_NAME,
                )
            except Exception as err:
                chunks_removed = 0
                warnings.append(f"chroma_cleanup_failed: {err}")

            get_db().hard_delete_document(doc_id)
            return {
                "status": "deleted",
                "chunks_removed": chunks_removed,
                "warnings": warnings,
            }
        except Exception as e:
            return {"error": str(e)}, 500

    @app.post("/api/documents/upload")
    async def upload_document():
        """Accept a file upload and index it globally (not scoped to a chat)."""
        from fastapi import UploadFile, File, HTTPException, Request

        request: Request = cl.context.request  # type: ignore[assignment]
        try:
            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" not in content_type:
                raise HTTPException(status_code=400, detail="Expected multipart/form-data")

            form = await request.form()
            file: UploadFile | None = form.get("file")  # type: ignore[assignment]
            if file is None:
                raise HTTPException(status_code=400, detail="No file provided")

            svc = get_chat_svc()
            # Read file bytes into a temp location for indexing
            import tempfile

            suffix = ""
            if file.filename and "." in file.filename:
                suffix = file.filename[file.filename.rindex(".") :]
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name

            result = svc.index_document_file(
                tmp_path,
                display_name=file.filename or "uploaded file",
            )
            import os

            os.unlink(tmp_path)

            return {
                "document_id": result.document_id,
                "file_name": result.file_name,
                "chunk_count": result.chunk_count,
            }
        except HTTPException:
            raise
        except Exception as e:
            return {"error": str(e)}, 500

    @app.get("/api/memories")
    async def list_memories(limit: int = 200, status: str | None = None):
        try:
            memories = get_db().list_all_memories(limit=limit, status=status)
            return memories
        except Exception as e:
            return {"error": str(e)}, 500

    @app.post("/api/memories/{memory_id}/deactivate")
    async def deactivate_memory(memory_id: str):
        try:
            with get_db().connect() as conn:
                cur = conn.execute(
                    "UPDATE long_term_memories SET status = 'deleted' WHERE memory_id = ?",
                    (memory_id,),
                )
            if cur.rowcount == 0:
                return {"error": "not found"}, 404
            return {"status": "deactivated"}
        except Exception as e:
            return {"error": str(e)}, 500

    @app.post("/api/memories/{memory_id}/activate")
    async def activate_memory(memory_id: str):
        try:
            with get_db().connect() as conn:
                cur = conn.execute(
                    "UPDATE long_term_memories SET status = 'active' WHERE memory_id = ?",
                    (memory_id,),
                )
            if cur.rowcount == 0:
                return {"error": "not found"}, 404
            return {"status": "activated"}
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
