"""Native OS-confinement sentinel in a fresh child interpreter, before pytest imports."""

import errno
import json
import os
from pathlib import Path
import socket
import sqlite3
import stat
import sys

assert not Path("/home/josph").exists()
for name in ("local_settings.py", ".env", ".git"):
    path = Path("/repo") / name
    if path.exists():
        assert stat.S_ISCHR(path.stat().st_mode)
try:
    sqlite3.connect("/repo/CHILD_NATIVE_SQL_CANARY.db")
except sqlite3.OperationalError:
    pass
else:
    raise AssertionError("Child native SQLite escaped writable boundary")
configured = "--configured" in sys.argv
canary_database = "/work/child-config-canary.db" if configured else "/work/child-canary.db"
with sqlite3.connect(canary_database) as db:
    db.execute("CREATE TABLE sentinel(value TEXT)")
with socket.socket() as connection:
    connection.settimeout(0.2)
    try:
        connection.connect(("198.51.100.1", 443))
    except OSError as exc:
        assert exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH)
    else:
        raise AssertionError("Child external network unexpectedly reachable")
if os.environ.get("BREAMON_CANARY_LOOPBACK") == "1":
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        with socket.create_connection(server.getsockname(), timeout=1):
            connection, _ = server.accept()
            connection.close()
result = {"passed": True}
if configured:
    sys.path.insert(0, "/repo")
    from src import provider_settings, settings
    from src.config import AppConfig

    assert os.environ["PYTHON_DOTENV_DISABLED"] == "1"
    assert os.environ["LLM_PROVIDER"] == "custom"
    assert not provider_settings.LOCAL_SETTINGS_PATH.is_file()
    config = AppConfig.load()
    assert config.provider == "custom"
    assert config.openai_api_key == "offline-synthetic-key"
    assert config.openai_base_url == "http://offline.invalid/v1"
    assert config.model_name == "offline-test"
    resolved = {}
    paths = {
        "database": config.database_path,
        "document_chroma": config.langchain_chroma_persist_dir,
        "canonical_database_constant": settings.DATABASE_PATH,
        "canonical_chroma_constant": settings.LANGCHAIN_CHROMA_PERSIST_DIR,
        **{
            name: os.environ[name]
            for name in ("TMPDIR", "HF_HOME", "XDG_CACHE_HOME", "TORCH_HOME", "UV_CACHE_DIR")
        },
    }
    for name, value in paths.items():
        path = Path(value).resolve()
        assert path.is_relative_to("/work"), f"Unsafe child configuration path: {name}"
        directory = path.parent if "database" in name else path
        directory.mkdir(parents=True, exist_ok=True)
        sentinel = directory / "child-configuration-write-canary"
        sentinel.write_text("synthetic")
        sentinel.unlink()
        resolved[name] = str(path)
    result["resolved_paths"] = resolved
    result["synthetic_provider_configuration"] = True
    result["canonical_constants_note"] = (
        "Child canonical constants resolve under /work; they can differ from parent in-memory overrides."
    )
print(json.dumps(result))
