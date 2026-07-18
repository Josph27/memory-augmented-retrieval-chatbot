"""Startup script for the multi-agent RAG chatbot.

Sets RERANKER_STARTUP_MODE and launches Chainlit.
Usage: uv run startup [--hybrid | --cross-encoder] [chainlit-flags ...]
"""

from __future__ import annotations

import os
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
    print(f"=== Reranker startup mode: {startup_mode} ===\n")

    os.execvpe(
        "uv",
        ["uv", "run", "python", "-m", "chainlit", "run", "app.py", *forward_args],
        os.environ,
    )


if __name__ == "__main__":
    main()
