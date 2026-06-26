from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> int:
    """Print raw messages linked from a gist or explicit message-id span."""
    from src.config import AppConfig
    from src.core.contracts import SourcePlan
    from src.database import Database
    from src.retrieval.raw_message_span_retriever import RawMessageSpanRetriever

    parser = argparse.ArgumentParser(
        description="Inspect source raw messages for a gist or explicit message span."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--gist-id", type=int, help="chat_gists.id to drill into.")
    group.add_argument(
        "--chat-id",
        help="Chat id for explicit span lookup. Requires --start-message-id and --end-message-id.",
    )
    parser.add_argument("--start-message-id", type=int, help="First message id in span.")
    parser.add_argument("--end-message-id", type=int, help="Last message id in span.")
    parser.add_argument(
        "--max-chars",
        type=int,
        help="Maximum formatted span characters. Defaults to RAW_MESSAGE_SPAN_MAX_CHARS.",
    )
    args = parser.parse_args()

    if args.chat_id and (
        args.start_message_id is None or args.end_message_id is None
    ):
        parser.error("--chat-id requires --start-message-id and --end-message-id")

    config = AppConfig.from_env()
    database = Database(config.database_path)
    filters: dict[str, object]
    current_chat_id = args.chat_id or "raw-span-inspector"
    if args.gist_id is not None:
        filters = {"gist_id": args.gist_id}
    else:
        filters = {
            "chat_id": args.chat_id,
            "start_message_id": args.start_message_id,
            "end_message_id": args.end_message_id,
        }

    candidates = RawMessageSpanRetriever(
        database,
        max_chars=args.max_chars,
    ).retrieve(
        chat_id=current_chat_id,
        source_plan=SourcePlan(
            source="raw_message_span",
            enabled=True,
            reason="Manual raw span inspection.",
            filters=filters,
        ),
    )

    print(f"database_path={config.database_path}")
    print(f"raw_message_span_count={len(candidates)}")
    for candidate in candidates:
        print("[Raw message span]")
        print(f"record_id={candidate.record_id}")
        print(f"chat_id={candidate.chat_id}")
        print(f"source_message_ids={candidate.source_message_ids}")
        print(f"metadata={candidate.metadata}")
        print(candidate.content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
