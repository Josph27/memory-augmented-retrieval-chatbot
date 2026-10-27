#!/usr/bin/env python3
"""Fail-closed OS-confined pytest runner. No dependency/application import on the host.

Read docs/audit/stage5/INFRASTRUCTURE.md before changing confinement or enabling groups.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

DEFAULT_VENV = "/home/josph/UNI/TUM/PRAK-AGENTS/repo/.venv"
SAFE_TRACKED_ASSETS = {".chainlit/config.toml", "chainlit.md", "public/product-navigation.js"}
PRIVATE_NAMES = {".git", ".env", "local_settings.py"}
RUNTIME_ROOTS = {
    "data",
    ".cache",
    ".ruff_cache",
    ".pytest_cache",
    ".chainlit",
    "logs",
    "tmp",
    "node_modules",
    ".venv",
}


def write_json(path, value):
    target = Path(path)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(target)


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True)


def source_snapshot(repo):
    """Hash actual allowed working bytes, including dirty/untracked infrastructure.

    Private/runtime files are recorded by name only and never opened. Index tree/blob IDs
    and staged/unstaged raw diffs distinguish working bytes from committed/index state.
    """
    paths = sorted(
        set(git(repo, "ls-files", "-c", "-o", "--exclude-standard", "-z").split("\0")) - {""}
    )
    files, excluded = {}, []
    for name in paths:
        path = Path(name)
        if name not in SAFE_TRACKED_ASSETS and (
            any(part in PRIVATE_NAMES or part in RUNTIME_ROOTS for part in path.parts)
            or path.suffix in {".db", ".sqlite", ".sqlite3"}
        ):
            excluded.append(name)
            continue
        absolute = repo / path
        if absolute.is_symlink():
            files[name] = {"symlink_target": os.readlink(absolute)}
        elif absolute.is_file():
            files[name] = {
                "sha256": hashlib.sha256(absolute.read_bytes()).hexdigest(),
                "size": absolute.stat().st_size,
                "mode": absolute.stat().st_mode & 0o777,
            }
        else:
            files[name] = {"missing": True}
    return {
        "head": git(repo, "rev-parse", "HEAD").strip(),
        "branch": git(repo, "branch", "--show-current").strip(),
        "status_porcelain_v1": git(repo, "status", "--porcelain=v1", "--untracked-files=all"),
        "index_blob_ids": git(repo, "ls-files", "--stage"),
        "unstaged_raw_diff": git(repo, "diff", "--raw", "--no-abbrev"),
        "staged_raw_diff": git(repo, "diff", "--cached", "--raw", "--no-abbrev"),
        "working_files": files,
        "private_runtime_excluded_without_opening": excluded,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", action="append", default=[])
    parser.add_argument(
        "--configuration", choices=["deterministic", "canonical"], default="deterministic"
    )
    parser.add_argument(
        "--label",
        default="initial",
        help="Evidence label: initial or post-<repair-id>; never overwrites prior runs",
    )
    parser.add_argument("--venv", default=DEFAULT_VENV)
    parser.add_argument("--uv", type=Path, default=Path("/home/josph/.local/bin/uv"))
    parser.add_argument("--output-root", type=Path, default=Path(tempfile.gettempdir()))
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--chrome-runtime", type=Path, default=Path("/opt/google/chrome"))
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--canary-only", action="store_true")
    parser.add_argument("--inner", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def launch(args):
    repo = Path(__file__).resolve().parents[1]
    registry = json.loads((repo / "docs/audit/stage5/groups.json").read_text())
    groups = args.group or registry["default_groups"]
    for name in groups:
        group = registry["groups"].get(name)
        if group is None or not group["enabled"]:
            raise SystemExit(
                f"Group {name!r} unavailable: {(group or {}).get('reason', 'unregistered')}"
            )
        if group["category"] in {"live-provider", "expensive-evaluations", "manual"}:
            raise SystemExit(
                f"Group {name} requires separate authorization/runner; execution refused"
            )
    if args.timeout < 1 or args.timeout > 3600:
        raise SystemExit("--timeout must be 1..3600 seconds")
    wrappers = "subprocess-wrappers" in groups
    app_group = "app-composition" in groups
    browser = any(registry["groups"][g]["category"] == "browser" for g in groups)
    if args.configuration == "canonical" and any(
        group not in {"offline-unit", "offline-integration"} for group in groups
    ):
        raise SystemExit(
            "Canonical configuration is supported only for the core offline groups; "
            "admitted app/wrapper/browser groups require explicit deterministic setup."
        )
    venv = Path(args.venv).resolve()
    if not (venv / "bin/python").exists() or not shutil.which("bwrap"):
        raise SystemExit("Prerequisite unavailable: bwrap and configured venv/bin/python required")
    if args.output_root.resolve().is_relative_to(repo):
        raise SystemExit("--output-root must be outside the source checkout")
    output = Path(tempfile.mkdtemp(prefix="breamon-stage5-", dir=args.output_root))
    output.chmod(0o700)
    (output / "home").mkdir()
    (output / "passwd").write_text(
        f"stage5:x:{os.getuid()}:{os.getgid()}:stage5:/work/home:/bin/bash\n"
    )
    (output / "group").write_text(f"stage5:x:{os.getgid()}:\n")
    snapshot = source_snapshot(repo)
    write_json(output / "source-before.json", snapshot)
    tracked_assets = {}
    for name in sorted(SAFE_TRACKED_ASSETS):
        git(repo, "ls-files", "--error-unmatch", "--", name)
        source = repo / name
        if source.is_symlink() or not source.is_file():
            raise SystemExit(f"Reviewed tracked configuration must be a regular file: {name}")
        destination = output / "tracked-inputs" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        if digest != snapshot["working_files"][name]["sha256"]:
            raise SystemExit("Tracked configuration changed while snapshotting")
        tracked_assets[name] = {"sha256": digest}
    write_json(output / "tracked-inputs.json", tracked_assets)
    source_mount = repo
    if wrappers:
        # Fixed wrapper output paths require a writable empty artifacts directory.
        # Materialize only snapshot-approved inputs, never ignored/private/runtime files.
        source_mount = output / "source"
        source_mount.mkdir()
        for name, identity in snapshot["working_files"].items():
            if "sha256" not in identity:
                raise SystemExit(f"Wrapper snapshot requires regular existing files: {name}")
            destination = source_mount / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((repo / name).read_bytes())
            destination.chmod(identity["mode"])
            if hashlib.sha256(destination.read_bytes()).hexdigest() != identity["sha256"]:
                raise SystemExit(f"Source changed while creating wrapper snapshot: {name}")
        (source_mount / "artifacts").mkdir()
        (source_mount / ".cache").mkdir(exist_ok=True)
        (source_mount / ".git").touch()
    host_ns = {name: os.readlink(f"/proc/self/ns/{name}") for name in ("net", "mnt")}
    write_json(
        output / "request.json",
        {
            "groups": groups,
            "configuration": args.configuration,
            "label": args.label,
            "collect_only": args.collect_only,
            "canary_only": args.canary_only,
            "controlled_loopback": browser,
            "wrappers": wrappers,
            "app_group": app_group,
            "source_copy": wrappers,
            "host_namespaces": host_ns,
            "source_head": snapshot["head"],
            "timeout_seconds": args.timeout,
        },
    )
    command = [
        "bwrap",
        "--unshare-net",
        "--unshare-pid",
        "--unshare-ipc",
        "--unshare-uts",
        "--die-with-parent",
        "--new-session",
        "--ro-bind",
        "/usr",
        "/usr",
        "--symlink",
        "usr/bin",
        "/bin",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--ro-bind",
        str(output / "passwd"),
        "/etc/passwd",
        "--ro-bind",
        str(output / "group"),
        "/etc/group",
        "--ro-bind",
        "/etc/ld.so.cache",
        "/etc/ld.so.cache",
        "--ro-bind",
        "/etc/ssl",
        "/etc/ssl",
        "--ro-bind",
        str(venv),
        "/venv",
        "--ro-bind",
        str(source_mount),
        "/repo",
    ]
    for name in sorted(PRIVATE_NAMES | RUNTIME_ROOTS):
        path = source_mount / name
        if path.is_dir() and not path.is_symlink():
            command += ["--tmpfs", f"/repo/{name}"]
        elif path.exists():
            command += ["--ro-bind", "/dev/null", f"/repo/{name}"]
    if wrappers:
        uv = args.uv.resolve()
        if not uv.is_file():
            raise SystemExit("Wrapper prerequisite unavailable: configured uv executable")
        command += ["--ro-bind", str(uv), "/tools/uv", "--tmpfs", "/repo/artifacts"]
    for name in sorted(tracked_assets):
        command += ["--ro-bind", str(output / "tracked-inputs" / name), "/repo/" + name]
    if browser:
        chrome = args.chrome_runtime.resolve()
        if not (chrome / "chrome").is_file():
            raise SystemExit("Browser unavailable: configured Chrome runtime missing")
        command += ["--ro-bind", str(chrome), "/opt/google/chrome"]
        if Path("/etc/fonts").is_dir():
            command += ["--ro-bind", "/etc/fonts", "/etc/fonts"]
    # No host /home, old checkout, sockets, caches or environment is mounted.
    command += [
        "--bind",
        str(output),
        "/work",
        "--tmpfs",
        "/tmp",
        "--tmpfs",
        "/run",
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--clearenv",
        "--setenv",
        "PATH",
        "/tools:/venv/bin:/usr/bin:/bin",
        "--setenv",
        "LANG",
        "C.UTF-8",
        "--chdir",
        "/work",
        "--",
        "/usr/bin/timeout",
        "-s",
        "TERM",
        "-k",
        "5",
        str(args.timeout),
        "/venv/bin/python",
        "-I",
        "-B",
        "/repo/scripts/run_isolated_tests.py",
        "--inner",
    ]
    write_json(
        output / "launch.json",
        {
            "command": command,
            "venv_host_path": str(venv),
            "started_unix": time.time(),
            "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "source_mount": str(source_mount),
            "uv_sha256": hashlib.sha256(args.uv.resolve().read_bytes()).hexdigest()
            if wrappers
            else None,
            "chrome_sha256": hashlib.sha256(
                (args.chrome_runtime.resolve() / "chrome").read_bytes()
            ).hexdigest()
            if browser
            else None,
        },
    )
    start = time.monotonic()
    with (output / "console.log").open("w") as log:
        process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    after = source_snapshot(repo)
    write_json(output / "source-after.json", after)
    stable = snapshot == after
    summary = {
        "output_dir": str(output),
        "exit_code": process.returncode,
        "duration_seconds": time.monotonic() - start,
        "source_unchanged_during_run": stable,
        "result_exists": (output / "result.json").exists(),
        "progress_exists": (output / "progress.json").exists(),
        "timed_out": process.returncode in (124, 137),
    }
    write_json(output / "launch-result.json", summary)
    print(json.dumps(summary, indent=2))
    if not stable:
        print(
            "Source changed during run: evidence is not a stable source baseline.", file=sys.stderr
        )
        return 3
    return process.returncode


def inner(args):
    # Stdlib-only until OS canaries, subprocess inheritance and private masks pass.
    import errno
    import pwd
    import socket
    import sqlite3
    import stat

    request = json.loads(Path("/work/request.json").read_text())
    work, repo = Path("/work"), Path("/repo")
    canaries = {}
    assert Path(pwd.getpwuid(os.getuid()).pw_dir) == work / "home"
    assert Path.home() == work / "home"
    canaries["synthetic_home"] = True
    assert not Path("/home/josph").exists()
    assert not Path(DEFAULT_VENV).exists()
    canaries["old_checkout_and_home_absent"] = True
    for name in ("local_settings.py", ".env", ".git"):
        path = repo / name
        if path.exists():
            assert stat.S_ISCHR(path.stat().st_mode) and path.stat().st_rdev == os.makedev(1, 3)
    assert not any((repo / "data").glob("**/*"))
    canaries["private_settings_and_runtime_masked"] = True
    tracked_assets = json.loads(Path("/work/tracked-inputs.json").read_text())
    assert sorted(p.name for p in Path("/repo/.chainlit").iterdir()) == ["config.toml"]
    for name, identity in tracked_assets.items():
        assert hashlib.sha256((repo / name).read_bytes()).hexdigest() == identity["sha256"]
    canaries["only_reviewed_tracked_chainlit_configuration_exposed"] = True
    try:
        (repo / "STAGE5_READONLY_CANARY").write_text("must fail")
    except OSError as exc:
        assert exc.errno == errno.EROFS
    else:
        raise AssertionError("source unexpectedly writable")
    canaries["source_readonly"] = True
    try:
        sqlite3.connect("/repo/STAGE5_SQL_CANARY.db")
    except sqlite3.OperationalError:
        pass
    else:
        raise AssertionError("native SQLite source write succeeded")
    with sqlite3.connect("/work/canary.db") as db:
        db.execute("CREATE TABLE sentinel(value TEXT)")
    canaries["native_sql_source_denied_temp_allowed"] = True
    with socket.socket() as sock:
        sock.settimeout(0.2)
        try:
            sock.connect(("198.51.100.1", 443))
        except OSError as exc:
            assert exc.errno in (errno.ENETUNREACH, errno.EHOSTUNREACH)
        else:
            raise AssertionError("external connection succeeded")
    canaries["native_external_network_denied"] = True
    if request["controlled_loopback"]:
        # A private namespace can allow loopback without exposing host services/routes.
        # Fail closed if bwrap/kernel cannot provide an operational loopback interface.
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            with socket.create_connection(server.getsockname(), timeout=1):
                connection, _ = server.accept()
                connection.close()
        canaries["controlled_loopback_in_private_namespace"] = True
    child_env = dict(
        os.environ, BREAMON_CANARY_LOOPBACK="1" if request["controlled_loopback"] else "0"
    )
    child = subprocess.run(
        [sys.executable, "-I", "-B", "/repo/tests/support/isolation_child_canary.py"],
        capture_output=True,
        text=True,
        timeout=15,
        env=child_env,
    )
    if child.returncode:
        raise AssertionError(f"Subprocess confinement canary failed: {child.stderr}")
    canaries["subprocess_inherits_native_confinement"] = json.loads(child.stdout)["passed"]
    proof = {
        "verified_before_imports": True,
        "canaries": canaries,
        "source_readonly": True,
        "controlled_loopback": request["controlled_loopback"],
        "groups": request["groups"],
        "network_namespace": os.readlink("/proc/self/ns/net"),
        "mount_namespace": os.readlink("/proc/self/ns/mnt"),
        "host_network_namespace": request["host_namespaces"]["net"],
        "host_mount_namespace": request["host_namespaces"]["mnt"],
    }
    assert proof["network_namespace"] != proof["host_network_namespace"]
    assert proof["mount_namespace"] != proof["host_mount_namespace"]
    write_json("/work/isolation-proof.json", proof)
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
        if (repo / name).exists():
            (work / name).symlink_to(repo / name, target_is_directory=(repo / name).is_dir())
    (work / "tmp").mkdir()
    (work / "run").mkdir(mode=0o700)
    app_root = work / "app-root"
    (app_root / ".files").mkdir(parents=True)
    for name, identity in tracked_assets.items():
        destination = app_root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes((work / "tracked-inputs" / name).read_bytes())
        assert hashlib.sha256(destination.read_bytes()).hexdigest() == identity["sha256"]
    os.environ.update(
        {
            "BREAMON_ISOLATED_PROOF": hashlib.sha256(
                Path("/work/isolation-proof.json").read_bytes()
            ).hexdigest(),
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHON_DOTENV_DISABLED": "1",
            "HF_HUB_OFFLINE": "1",
            "HF_DATASETS_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "ANONYMIZED_TELEMETRY": "False",
            "TOKENIZERS_PARALLELISM": "false",
            "HF_HOME": "/work/hf",
            "XDG_CACHE_HOME": "/work/cache",
            "XDG_CONFIG_HOME": "/work/config",
            "XDG_RUNTIME_DIR": "/work/run",
            "TORCH_HOME": "/work/torch",
            "UV_CACHE_DIR": "/work/uv",
            "UV_NO_SYNC": "1",
            "UV_PROJECT_ENVIRONMENT": "/venv",
            "UV_PYTHON": "/venv/bin/python",
            "UV_PYTHON_DOWNLOADS": "never",
            "UV_OFFLINE": "1",
            "CHAINLIT_APP_ROOT": "/work/app-root",
            "CHAINLIT_AUTH_SECRET": "stage5-synthetic-auth-secret",
            "PRODUCT_E2E_CHROME": "/opt/google/chrome/chrome",
            "DATABASE_PATH": "/work/default.db",
            "LANGCHAIN_CHROMA_PERSIST_DIR": "/work/chroma",
            "TMPDIR": "/work/tmp",
            "LLM_PROVIDER": "custom",
            "OPENAI_API_KEY": "offline-synthetic-key",
            "OPENAI_BASE_URL": "http://offline.invalid/v1",
            "MODEL_NAME": "offline-test",
            "MODEL_REQUEST_TIMEOUT": "1",
            "CONNECTION_GUARD_CHECK_TIMEOUT": "1",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    prerequisite_evidence = {}
    if request["wrappers"]:
        synthetic_git = work / "synthetic.git"
        subprocess.run(
            ["git", "init", "--bare", "--initial-branch=stage5-isolated", str(synthetic_git)],
            check=True,
            capture_output=True,
        )
        os.environ.update(
            {
                "GIT_DIR": str(synthetic_git),
                "GIT_WORK_TREE": "/repo",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_SYSTEM": "/dev/null",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )
        tree = subprocess.check_output(["git", "mktree"], input=b"").decode().strip()
        commit = subprocess.check_output(
            [
                "git",
                "-c",
                "user.name=Stage5",
                "-c",
                "user.email=stage5@invalid",
                "commit-tree",
                tree,
                "-m",
                "Synthetic wrapper metadata only",
            ],
            text=True,
        ).strip()
        subprocess.run(["git", "update-ref", "refs/heads/stage5-isolated", commit], check=True)
        version = subprocess.check_output(["uv", "--version"], text=True).strip()
        uv_child = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-c",
                "import sys; assert sys.prefix == '/venv'; print(sys.version)",
            ],
            cwd="/repo",
            env={**os.environ, "UV_CACHE_DIR": "/repo/.cache/uv"},
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert uv_child.returncode == 0, uv_child.stderr
        assert subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() == commit
        (repo / "artifacts" / "stage5-write-canary").write_text("ephemeral")
        (repo / "artifacts" / "stage5-write-canary").unlink()
        prerequisite_evidence["wrapper_runtime"] = {
            "uv_version": version,
            "uv_sha256": hashlib.sha256(Path("/tools/uv").read_bytes()).hexdigest(),
            "synthetic_git_commit": commit,
            "git_is_source_history": False,
            "uv_child_python": uv_child.stdout.strip(),
            "verified_wrapper_cache": "/repo/.cache/uv",
        }
    if request["controlled_loopback"]:
        chrome = "/opt/google/chrome/chrome"
        version = subprocess.check_output([chrome, "--version"], text=True, timeout=10).strip()
        check = subprocess.run(
            [
                chrome,
                "--headless",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-background-networking",
                "--no-first-run",
                "--user-data-dir=/work/chrome-canary",
                "--dump-dom",
                "data:text/html,<p>STAGE5_NATIVE_CHROME</p>",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert check.returncode == 0 and "STAGE5_NATIVE_CHROME" in check.stdout, check.stderr
        prerequisite_evidence["browser_runtime"] = {
            "chrome_version": version,
            "chrome_sha256": hashlib.sha256(Path(chrome).read_bytes()).hexdigest(),
            "native_launch_passed": True,
        }
    write_json("/work/prerequisites.json", prerequisite_evidence)
    if request["configuration"] == "deterministic":
        os.environ.update(
            {
                "STRUCTURED_MEMORY_RETRIEVAL_MODE": "sqlite",
                "RERANKER_MODE": "deterministic",
                "ROUTING_MODE": "rule",
                "PREVIOUS_CHAT_GIST_EXTRACTOR": "deterministic",
            }
        )
    configured_child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "/repo/tests/support/isolation_child_canary.py",
            "--configured",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        env=dict(os.environ),
    )
    if configured_child.returncode:
        raise AssertionError(
            f"Post-environment child configuration canary failed: {configured_child.stderr}"
        )
    configured_evidence = json.loads(configured_child.stdout)
    assert configured_evidence["passed"]
    canaries["subprocess_inherits_synthetic_configuration"] = True
    proof["configured_child"] = configured_evidence
    proof["prerequisites"] = prerequisite_evidence
    proof["tracked_app_assets"] = tracked_assets
    write_json("/work/isolation-proof.json", proof)
    os.environ["BREAMON_ISOLATED_PROOF"] = hashlib.sha256(
        Path("/work/isolation-proof.json").read_bytes()
    ).hexdigest()
    if request["canary_only"]:
        write_json(
            "/work/result.json",
            {
                "canary_only": True,
                "proof": proof,
                "external_requests": 0,
                "test_cases": 0,
                "note": "No pytest/test imports; only controlled child AppConfig/provider imports after native confinement.",
            },
        )
        return 0
    sys.dont_write_bytecode = True
    sys.path.insert(0, "/repo")
    # Supplemental hook records Python attempts. Native confinement remains authoritative.
    blocked = []

    def audit(event, values):
        if event in ("socket.connect", "socket.getaddrinfo", "socket.sendto"):
            blocked.append(
                {"event": event, "test": os.environ.get("PYTEST_CURRENT_TEST", "collection")}
            )
            if request["controlled_loopback"]:
                address = values[1] if len(values) > 1 else None
                host = address[0] if isinstance(address, tuple) else address
                if event == "socket.getaddrinfo":
                    host = values[0]
                if host in ("localhost", "127.0.0.1", "::1"):
                    blocked.pop()
                    return
                if event == "socket.connect" and isinstance(address, str):
                    path = Path(address).resolve()
                    if path.is_relative_to(work) or path.is_relative_to("/tmp"):
                        blocked.pop()
                        return
            raise OSError(errno.ENETUNREACH, "Stage 5 isolated run blocks external network")
        if event == "open" and isinstance(values[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(values[0])).resolve()
            if path.name in (".env", "local_settings.py") and not path.is_relative_to(work):
                blocked.append(
                    {
                        "event": "private-settings-open",
                        "test": os.environ.get("PYTEST_CURRENT_TEST", "collection"),
                    }
                )
                raise PermissionError("Private settings excluded from isolated tests")

    sys.addaudithook(audit)
    import tempfile as temp_module

    temp_module.tempdir = "/work/tmp"
    from src import settings, provider_settings

    # Canonical settings assign constants at import rather than read storage env vars.
    settings.DATABASE_PATH = "/work/default.db"
    settings.LANGCHAIN_CHROMA_PERSIST_DIR = "/work/chroma"
    provider_settings.LOCAL_SETTINGS_PATH = work / "local_settings.py"
    if request["configuration"] == "deterministic":
        settings.STRUCTURED_MEMORY_RETRIEVAL_MODE = "sqlite"
        settings.RERANKER_MODE = "deterministic"
        settings.ROUTING_MODE = "rule"
        settings.PREVIOUS_CHAT_GIST_EXTRACTOR = "deterministic"
    if request["app_group"] or request["controlled_loopback"]:
        os.chdir(app_root)
    if request["app_group"]:
        sys.path.insert(0, "/repo/tests")
        from support.chainlit_bootstrap import prepare_chainlit_dependencies

        prepare_chainlit_dependencies()
    import importlib.metadata

    dependencies = sorted(
        (d.metadata.get("Name", "unknown"), d.version) for d in importlib.metadata.distributions()
    )
    write_json(
        "/work/runtime.json",
        {
            "python": sys.version,
            "executable": sys.executable,
            "dependencies": dependencies,
            "configuration": request["configuration"],
            "tracked_configuration_inputs": tracked_assets,
            "storage": {
                "sqlite": "/work/default.db",
                "document_chroma": "/work/chroma",
                "structured_vectors": "same isolated SQLite",
            },
            "model_substitutions": "Existing test fixtures; app group additionally injects deterministic embeddings only before app import. No global product/ConnectionGuard outcome override.",
            "prerequisites": prerequisite_evidence,
        },
    )
    import pytest

    registry = json.loads((repo / "docs/audit/stage5/groups.json").read_text())
    files = list(
        dict.fromkeys(p for g in request["groups"] for p in registry["groups"][g]["files"])
    )

    class Evidence:
        def __init__(self):
            self.collected, self.deselected, self.reports, self.collection_errors = [], [], [], []
            self.started = time.monotonic()
            self.finished = False

        def save(self, code=None):
            final = {}
            errors = set()
            for report in self.reports:
                node = report["nodeid"]
                if report["outcome"] == "failed" and report["phase"] != "call":
                    errors.add(node)
                elif report["phase"] == "call" or (
                    report["phase"] == "setup" and report["outcome"] == "skipped"
                ):
                    final[node] = report.get("classified", report["outcome"])
            for node in errors:
                final[node] = "errored"
            counts = {
                name: sum(v == name for v in final.values())
                for name in ("passed", "failed", "errored", "skipped", "xfailed", "xpassed")
            }
            value = {
                "request": request,
                "pytest_exit_code": code,
                "complete": self.finished,
                "duration_seconds": time.monotonic() - self.started,
                "collected_case_count": len(self.collected) + len(self.deselected),
                "selected_case_count": len(self.collected),
                "collection_error_count": len(self.collection_errors),
                "counts": counts,
                "collected_nodeids": self.collected,
                "not_completed_nodeids": [n for n in self.collected if n not in final],
                "deselected": self.deselected,
                "collection_errors": self.collection_errors,
                "reports": self.reports,
                "exclusion_register": registry,
                "blocked_python_attempts": blocked,
                "isolation_proof": proof,
                "external_inference_requests": 0,
                "external_usage_evidence": "Independent net namespace, no host sockets/routes; native parent/child network canaries passed.",
                "fake_model_calls": None,
                "fake_model_calls_note": "Not instrumented; unknown, not zero.",
                "external_tokens": 0,
                "external_cost": 0,
                "per_case_outcome": final,
            }
            write_json("/work/progress.json", value)
            if self.finished:
                write_json("/work/result.json", value)

        @pytest.hookimpl(trylast=True)
        def pytest_collection_modifyitems(self, session, config, items):
            self.collected = [item.nodeid for item in items]
            self.save()

        def pytest_deselected(self, items):
            self.deselected.extend(item.nodeid for item in items)
            self.save()

        def pytest_collectreport(self, report):
            if report.failed:
                self.collection_errors.append(
                    {"nodeid": report.nodeid, "detail": str(report.longrepr)}
                )
                self.save()

        def pytest_runtest_logreport(self, report):
            entry = {
                "nodeid": report.nodeid,
                "phase": report.when,
                "outcome": report.outcome,
                "duration_seconds": report.duration,
                "detail": str(report.longrepr) if report.longrepr else None,
                "captured_sections": list(report.sections),
                "user_properties": list(report.user_properties),
            }
            if getattr(report, "wasxfail", False):
                entry["classified"] = "xfailed" if report.skipped else "xpassed"
                entry["xfail_reason"] = str(report.wasxfail)
            self.reports.append(entry)
            self.save()

    evidence = Evidence()
    evidence.save()
    options = [
        "-q",
        "--tb=short",
        "-p",
        "no:cacheprovider",
        "--rootdir=/repo",
        "--basetemp=/work/pytest",
        "--junitxml=/work/junit.xml",
    ]
    if request["collect_only"]:
        options.append("--collect-only")
    options.extend("/repo/" + p for p in files if p.endswith(".py"))
    code = pytest.main(options, plugins=[evidence])
    evidence.finished = True
    evidence.save(int(code))
    return int(code)


if __name__ == "__main__":
    arguments = parse_args()
    if arguments.inner:
        try:
            result = inner(arguments)
        except Exception as exc:
            import traceback

            detail = traceback.format_exc()
            verified = Path("/work/isolation-proof.json").is_file()
            write_json(
                "/work/result.json",
                {
                    "complete": False,
                    "bootstrap_error": type(exc).__name__,
                    "detail": detail,
                    "external_inference_requests": 0 if verified else None,
                    "external_usage_evidence": "Proof passed"
                    if verified
                    else "Confinement proof incomplete; no usage claim",
                    "collected_case_count": 0,
                },
            )
            print(detail, file=sys.stderr)
            result = 2
    else:
        result = launch(arguments)
    raise SystemExit(result)
