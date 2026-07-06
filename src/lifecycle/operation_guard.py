from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from typing import Iterator


_GUARD_LOCK = RLock()
_CHAT_LOCKS: dict[tuple[str, str], RLock] = {}


def chat_operation_lock(database_path: Path, chat_id: str) -> RLock:
    """Return the process-local lock shared by send, upload, and chat end."""
    key = (str(database_path.resolve()), chat_id)
    with _GUARD_LOCK:
        return _CHAT_LOCKS.setdefault(key, RLock())


@contextmanager
def guarded_chat_operation(database_path: Path, chat_id: str) -> Iterator[None]:
    """Serialize one chat-local state transition in this application process."""
    lock = chat_operation_lock(database_path, chat_id)
    with lock:
        yield
