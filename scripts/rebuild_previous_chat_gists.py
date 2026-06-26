from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> int:
    """Generate previous-chat gists from existing SQLite chat transcripts."""
    from src.config import AppConfig
    from src.database import Database
    from src.memory.previous_chat_gist import (
        DeterministicPreviousChatGistExtractor,
        PreviousChatGistGenerator,
    )
    from src.model_wrapper import ModelWrapper

    parser = argparse.ArgumentParser(description="Generate previous-chat gist rows.")
    parser.add_argument("--active-chat-id", help="Chat id to exclude from previous gisting.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum chats to scan.")
    parser.add_argument(
        "--mode",
        choices=("deterministic", "model"),
        default="deterministic",
        help="Summarizer backend. Deterministic mode requires no model/API.",
    )
    args = parser.parse_args()

    config = AppConfig.from_env()
    database = Database(config.database_path)
    extractor = None
    model = None
    if args.mode == "deterministic":
        extractor = DeterministicPreviousChatGistExtractor()
    else:
        model = ModelWrapper(config)

    result = PreviousChatGistGenerator(
        database=database,
        extractor=extractor,
        model=model,
    ).generate_for_existing_chats(active_chat_id=args.active_chat_id, limit=args.limit)

    print(f"database_path={config.database_path}")
    print(f"created_count={result.created_count}")
    print(f"skipped_count={result.skipped_count}")
    print(f"gist_ids={result.gist_ids}")
    for chat_id, reason in sorted(result.skipped_reasons.items()):
        print(f"skipped chat_id={chat_id} reason={reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
