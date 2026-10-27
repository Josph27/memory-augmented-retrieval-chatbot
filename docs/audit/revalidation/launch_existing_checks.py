import subprocess
import sys
import tempfile
import json
import hashlib
import os
from pathlib import Path

repo = Path("/home/josph/.codex/worktrees/audit-main/repo")
cohort = sys.argv[1]
allowed = json.loads((repo / "docs/audit/revalidation/execution-cohorts.json").read_text())
assert cohort in allowed
out = Path(tempfile.mkdtemp(prefix="breamon-audit-" + cohort + "-"))
out.chmod(0o700)
(out / "home").mkdir()
(out / "passwd").write_text(f"audit:x:{os.getuid()}:{os.getgid()}:audit:/work/home:/bin/bash\n")
(out / "group").write_text(f"audit:x:{os.getgid()}:\n")
args = [
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
    str(out / "passwd"),
    "/etc/passwd",
    "--ro-bind",
    str(out / "group"),
    "/etc/group",
    "--ro-bind",
    "/etc/ld.so.cache",
    "/etc/ld.so.cache",
    "--ro-bind",
    "/etc/ssl",
    "/etc/ssl",
    "--ro-bind",
    "/home/josph/UNI/TUM/PRAK-AGENTS/repo/.venv",
    "/venv",
    "--ro-bind",
    str(repo),
    "/repo",
    "--ro-bind",
    "/dev/null",
    "/repo/local_settings.py",
    "--ro-bind",
    "/dev/null",
    "/repo/.git",
    "--tmpfs",
    "/repo/data",
    "--bind",
    str(out),
    "/work",
    "--tmpfs",
    "/tmp",
    "--tmpfs",
    "/run",
    "--dev",
    "/dev",
    "--proc",
    "/proc",
]
if (repo / ".env").exists():
    args += ["--ro-bind", "/dev/null", "/repo/.env"]
args += [
    "--clearenv",
    "--setenv",
    "PATH",
    "/usr/bin:/bin",
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
    "150",
    "/venv/bin/python",
    "-I",
    "-B",
    "/repo/docs/audit/revalidation/run_existing_checks.py",
    cohort,
]
meta = {
    "command": args,
    "source_head": "1cf4c553b12281fefb7daea5141e9cddfce6ca48",
    "host_uid": os.getuid(),
    "infrastructure_hashes": {
        n: hashlib.sha256((repo / "docs/audit/revalidation" / n).read_bytes()).hexdigest()
        for n in ("run_existing_checks.py", "execution-cohorts.json")
    },
}
(out / "launch.json").write_text(json.dumps(meta, indent=2) + "\n")
with (out / "console.txt").open("w") as f:
    run = subprocess.run(args, stdout=f, stderr=subprocess.STDOUT)
print(
    json.dumps(
        {
            "output_dir": str(out),
            "process_exit": run.returncode,
            "result_exists": (out / "result.json").exists(),
        }
    )
)
print((out / "console.txt").read_text()[-11000:])
