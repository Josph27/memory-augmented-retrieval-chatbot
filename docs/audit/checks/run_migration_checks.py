"""Bounded offline migration checks; no app imports or full-suite collection."""

import os
import sys
import tempfile
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
original = Path("/home/josph/UNI/TUM/PRAK-AGENTS/repo")
root = Path(tempfile.mkdtemp(prefix="breamon-migration-checks-"))
os.chdir(root)
tempfile.tempdir = str(root)
os.environ.clear()
os.environ.update(
    {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHON_DOTENV_DISABLED": "1",
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HOME": str(root / "hf"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "DATABASE_PATH": str(root / "test.db"),
        "LANGCHAIN_CHROMA_PERSIST_DIR": str(root / "chroma"),
        "OPENAI_API_KEY": "dummy",
        "OPENAI_BASE_URL": "http://test.invalid/v1",
        "MODEL_NAME": "offline-test",
        "TMPDIR": str(root),
    }
)
sys.dont_write_bytecode = True
sys.path.insert(0, str(repo))
violations = []
blocked_platform_probes = []


def deny(reason):
    violations.append(reason)
    raise PermissionError(reason)


def check_path(value, write=False):
    if not isinstance(value, (str, bytes, os.PathLike)):
        return
    p = Path(os.fsdecode(value)).resolve()
    if p == Path("/dev/null"):
        return
    if p.is_relative_to(original) and not p.is_relative_to(original / ".venv"):
        deny("original checkout access blocked")
    if p.is_relative_to(repo / "data"):
        deny("repository runtime data access blocked")
    if p.name in (".env", "local_settings.py") and not p.is_relative_to(root):
        deny("private settings access blocked")
    if write and not p.is_relative_to(root):
        deny("write outside temporary sandbox blocked: " + str(p))


def audit(event, args):
    if event == "subprocess.Popen":
        executable, argv = args[:2]
        # Optional dependency probes are still blocked; their callers use fallbacks.
        expected = (
            argv == ["/sbin/ldconfig", "-p"]
            or argv == ["uname", "-p"]
            or argv == ["ld", "-t", "-o", "/dev/null", "-ldl"]
            or (
                isinstance(argv, list)
                and len(argv) == 5
                and argv[:3] == ["/usr/bin/gcc", "-Wl,-t", "-o"]
                and Path(argv[3]).is_relative_to(root)
                and argv[4] == "-ldl"
            )
        )
        if expected:
            blocked_platform_probes.append(argv[0])
            raise PermissionError("optional platform probe blocked")
    if event in (
        "socket.connect",
        "socket.getaddrinfo",
        "socket.sendto",
        "subprocess.Popen",
        "os.system",
        "os.posix_spawn",
    ):
        deny("network/process blocked: " + event + " " + repr(args[:2]))
    if event == "open":
        path, mode, flags = args
        write = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        check_path(path, write)
    elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate"):
        check_path(args[0], True)
    elif event in ("os.rename", "os.link", "os.symlink"):
        check_path(args[0], True)
        check_path(args[1], True)
    elif event == "sqlite3.connect":
        check_path(args[0], True)


sys.addaudithook(audit)
# Disable dotenv explicitly before collection, independent of installed dotenv version.
import dotenv  # noqa: E402 -- isolation must precede dependency imports

dotenv.load_dotenv = lambda *args, **kwargs: False
from src import settings, provider_settings  # noqa: E402

settings.DATABASE_PATH = str(root / "test.db")
settings.LANGCHAIN_CHROMA_PERSIST_DIR = str(root / "chroma")
provider_settings.LOCAL_SETTINGS_PATH = root / "local_settings.py"
import pytest  # noqa: E402

code = pytest.main(
    [
        "-q",
        "-p",
        "no:cacheprovider",
        "--basetemp",
        str(root / "pytest"),
        str(repo / "tests/test_provider_settings.py"),
        str(repo / "tests/test_prompt_messages.py"),
        str(repo / "tests/test_context_comparator.py"),
    ]
)
print("Unexpected isolation violations:", len(violations))
print("Blocked optional platform probes:", blocked_platform_probes)
print("Temporary sandbox:", root)
if violations:
    print("\n".join(sorted(set(violations))))
    code = 1
raise SystemExit(code)
