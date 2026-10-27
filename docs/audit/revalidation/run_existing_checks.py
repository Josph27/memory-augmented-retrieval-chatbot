"""Run reviewed existing checks inside the accompanying OS sandbox command.

This is audit infrastructure, not a replacement test suite or application fix.
"""

from __future__ import annotations

import errno
import json
import os
import socket
import sqlite3
import stat
import pwd
import sys
import time
from pathlib import Path

REPO = Path("/repo")
WORK = Path("/work")
mode = sys.argv[1]
cohort = json.loads((REPO / "docs/audit/revalidation/execution-cohorts.json").read_text())[mode]
os.chdir(WORK)
# Preserve relative source lookups while cwd-relative logs remain ephemeral.
for name in (
    "src",
    "tests",
    "evals",
    "scripts",
    "docs",
    "braemon",
    "public",
    "app.py",
    "README.md",
    "pyproject.toml",
    "AGENTS.md",
    "startup.py",
    "run.sh",
):
    (WORK / name).symlink_to(REPO / name, target_is_directory=(REPO / name).is_dir())
(WORK / "tmp").mkdir(exist_ok=True)
os.environ.update(
    {
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "HF_HUB_OFFLINE": "1",
        "HF_DATASETS_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "ANONYMIZED_TELEMETRY": "False",
        "TOKENIZERS_PARALLELISM": "false",
        "HF_HOME": str(WORK / "hf"),
        "XDG_CACHE_HOME": str(WORK / "cache"),
        "DATABASE_PATH": str(WORK / "default.db"),
        "LANGCHAIN_CHROMA_PERSIST_DIR": str(WORK / "chroma"),
        "TMPDIR": str(WORK / "tmp"),
        "OPENAI_API_KEY": "dummy",
        "OPENAI_BASE_URL": "http://offline.invalid/v1",
        "MODEL_NAME": "offline-test",
        "MODEL_REQUEST_TIMEOUT": "1",
        "CONNECTION_GUARD_CHECK_TIMEOUT": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "MKL_NUM_THREADS": "1",
    }
)
if cohort["configuration"] == "deterministic":
    os.environ.update(
        {
            "STRUCTURED_MEMORY_RETRIEVAL_MODE": "sqlite",
            "RERANKER_MODE": "deterministic",
            "ROUTING_MODE": "rule",
            "PREVIOUS_CHAT_GIST_EXTRACTOR": "deterministic",
        }
    )
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO))
# OS-boundary canaries run BEFORE Python audit hooks or dependency imports.
canaries = {}
assert Path(pwd.getpwuid(os.getuid()).pw_dir) == WORK / "home"
assert Path.home() == WORK / "home"
canaries["synthetic_user_home"] = True
assert not Path("/home/josph/UNI/TUM/PRAK-AGENTS/repo").exists()
canaries["original_checkout_absent"] = True
assert stat.S_ISCHR((REPO / "local_settings.py").stat().st_mode)
assert (REPO / "local_settings.py").stat().st_rdev == os.makedev(1, 3)
assert not (REPO / ".env").exists() or (
    stat.S_ISCHR((REPO / ".env").stat().st_mode)
    and (REPO / ".env").stat().st_rdev == os.makedev(1, 3)
)
assert not (REPO / "data/chatbot.db.old").exists()
assert not (REPO / "data/database.sqlite3").exists()
canaries["credentials_masked_and_runtime_stores_absent"] = True
try:
    (REPO / "OS_ISOLATION_CANARY").write_text("must not succeed")
except OSError as exc:
    assert exc.errno == errno.EROFS
    canaries["source_write_readonly"] = True
else:
    raise AssertionError("source write confinement failed")
try:
    sqlite3.connect(str(REPO / "NATIVE_SQLITE_CANARY.db"))
except sqlite3.OperationalError:
    canaries["native_sqlite_source_write_denied"] = True
else:
    raise AssertionError("native SQLite confinement failed")
with sqlite3.connect(WORK / "canary.db") as db:
    db.execute("CREATE TABLE canary(value TEXT)")
canaries["native_sqlite_temp_write_allowed"] = True
with socket.socket() as sock:
    sock.settimeout(0.2)
    try:
        sock.connect(("198.51.100.1", 443))
    except OSError as exc:
        assert exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH)
        canaries["os_network_unreachable"] = True
    else:
        raise AssertionError("OS network isolation failed")
import tempfile  # noqa: E402

tempfile.tempdir = str(WORK / "tmp")
blocked = []


def audit(event, args):
    if event in ("socket.connect", "socket.getaddrinfo", "socket.sendto"):
        blocked.append(
            {"event": event, "test": os.getenv("PYTEST_CURRENT_TEST", "collection/import")}
        )
        raise OSError(errno.ENETUNREACH, "audit run has no network")
    if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        p = Path(os.fsdecode(args[0])).resolve()
        if p.name in (".env", "local_settings.py") and not p.is_relative_to(WORK):
            blocked.append(
                {
                    "event": "private_settings_open",
                    "test": os.getenv("PYTEST_CURRENT_TEST", "collection/import"),
                }
            )
            raise PermissionError("private settings excluded from audit execution")


sys.addaudithook(audit)
import dotenv  # noqa: E402

dotenv.load_dotenv = lambda *a, **kw: False
from src import settings, provider_settings  # noqa: E402

settings.DATABASE_PATH = str(WORK / "default.db")
settings.LANGCHAIN_CHROMA_PERSIST_DIR = str(WORK / "chroma")
provider_settings.LOCAL_SETTINGS_PATH = WORK / "local_settings.py"
if cohort["configuration"] == "deterministic":
    settings.STRUCTURED_MEMORY_RETRIEVAL_MODE = "sqlite"
    settings.RERANKER_MODE = "deterministic"
    settings.ROUTING_MODE = "rule"
    settings.PREVIOUS_CHAT_GIST_EXTRACTOR = "deterministic"
import pytest  # noqa: E402


class Evidence:
    def __init__(self):
        self.reports = []
        self.collection = []
        self.items = []
        self.deselected = []

    def pytest_collection_modifyitems(self, session, config, items):
        excluded = set(cohort.get("deselect", []))
        keep = []
        drop = []
        for item in items:
            (drop if item.nodeid in excluded else keep).append(item)
        self.deselected = [x.nodeid for x in drop]
        assert excluded == set(self.deselected), "requested heavy-model exclusions did not match"
        assert not any(
            x.nodeid.endswith("::test_cross_encoder_backend_preload_loads_model") for x in keep
        )
        items[:] = keep
        if drop:
            config.hook.pytest_deselected(items=drop)
        self.items = [x.nodeid for x in keep]

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection.append({"nodeid": report.nodeid, "error": str(report.longrepr)})

    def pytest_runtest_logreport(self, report):
        self.reports.append(
            {
                "nodeid": report.nodeid,
                "phase": report.when,
                "outcome": report.outcome,
                "duration": report.duration,
                "detail": str(report.longrepr) if report.failed else None,
            }
        )


plugin = Evidence()
start = time.monotonic()
code = pytest.main(
    [
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "--basetemp",
        str(WORK / "pytest"),
        *[str(REPO / p) for p in cohort["files"]],
    ],
    plugins=[plugin],
)
result = {
    "cohort": mode,
    "configuration": cohort["configuration"],
    "source_head": "1cf4c553b12281fefb7daea5141e9cddfce6ca48",
    "canaries": canaries,
    "pytest_exit_code": int(code),
    "elapsed_seconds": time.monotonic() - start,
    "settings": {
        "structured_memory_retrieval_mode": settings.STRUCTURED_MEMORY_RETRIEVAL_MODE,
        "reranker_mode": settings.RERANKER_MODE,
        "routing_mode": settings.ROUTING_MODE,
    },
    "collected_nodeids": plugin.items,
    "deselected": plugin.deselected,
    "collection_errors": plugin.collection,
    "reports": plugin.reports,
    "blocked_attempts": blocked,
    "limits": [
        "OS-confined offline environment; no live provider or original runtime state.",
        "Existing fake backends retained; no global ConnectionGuard success override.",
        "Deterministic cohort explicitly selects SQLite/rule/deterministic configuration.",
    ],
}
(WORK / "result.json").write_text(json.dumps(result, indent=2) + "\n")
print(
    "AUDIT_RESULT "
    + json.dumps(
        {
            "cohort": mode,
            "exit": int(code),
            "elapsed": result["elapsed_seconds"],
            "blocked_network_attempts": len(blocked),
            "canaries": canaries,
        }
    )
)
raise SystemExit(code)
