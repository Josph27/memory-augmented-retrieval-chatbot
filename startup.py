"""Startup script for the multi-agent RAG chatbot.

Starts both the Chainlit backend and the braemon React frontend.
Usage: uv run startup [--hybrid | --cross-encoder] [chainlit-flags ...]
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys


USAGE = """\
Usage: uv run startup [--hybrid | --cross-encoder] [chainlit-flags ...]

  --hybrid          Fast mode: MiniLM cross-encoder + deterministic blend (default)
  --cross-encoder   EXPERIMENTAL: mxbai cross-encoder only (higher quality potential, but
                    not optimized or fully tested due to heavy model + weak dev hardware)
  --help            Show this message

Examples:
  uv run startup                                   # Default --hybrid
  uv run startup --cross-encoder                   # Experimental quality mode
  uv run startup --port 8000 --headless            # Hybrid with custom port
  uv run startup --cross-encoder --port 8000 -w
"""


def _repo_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    startup_mode = "hybrid"
    forward_args: list[str] = []

    for arg in sys.argv[1:]:
        if arg == "--hybrid":
            startup_mode = "hybrid"
        elif arg == "--cross-encoder":
            startup_mode = "cross_encoder"
        elif arg in ("--help", "-h"):
            print(USAGE)
            sys.exit(0)
        else:
            forward_args.append(arg)

    os.environ["RERANKER_STARTUP_MODE"] = startup_mode

    port = "8000"
    for i, arg in enumerate(forward_args):
        if arg == "--port" and i + 1 < len(forward_args):
            port = forward_args[i + 1]
            break

    braemon_dir = os.path.join(_repo_root(), "braemon")

    print(f"=== Reranker startup mode: {startup_mode} ===")
    print(f"=== Backend:  http://localhost:{port} ===")
    print(f"=== Frontend: http://localhost:5173 (Vite default) ===\n")

    frontend = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=braemon_dir,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    def _cleanup(signum: int | None = None, frame: object = None) -> None:
        frontend.terminate()
        try:
            frontend.wait(timeout=3)
        except subprocess.TimeoutExpired:
            frontend.kill()
            frontend.wait()
        if signum is not None:
            sys.exit(128 + signum)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    try:
        os.execvpe(
            "uv",
            ["uv", "run", "python", "-m", "chainlit", "run", "app.py", *forward_args],
            os.environ,
        )
    finally:
        _cleanup()
    os._exit(1)  # unreachable unless execvpe fails


if __name__ == "__main__":
    main()
