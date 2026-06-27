from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> int:
    """Print long-term memory records from the configured SQLite database."""
    from src.config import AppConfig
    from src.database import Database
    from src.memory.long_term_store import SQLiteLongTermMemoryStore
    from src.memory.memory_trace import memory_record_to_inspector_row

    parser = argparse.ArgumentParser(description="Inspect long-term structured memory rows.")
    parser.add_argument("--chat-id", help="Filter by source chat id.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum rows to print.")
    args = parser.parse_args()

    config = AppConfig.from_env()
    database = Database(config.database_path)
    store = SQLiteLongTermMemoryStore(database)
    records = []
    for namespace in store.list_namespaces():
        records.extend(store.list(namespace))

    if args.chat_id:
        records = [record for record in records if record.source_chat_id == args.chat_id]

    records.sort(key=lambda record: (record.updated_at, record.memory_id), reverse=True)
    records = records[: max(0, args.limit)]

    print(f"database_path={config.database_path}")
    print(f"long_term_memories_count={len(records)}")
    for record in records:
        row = memory_record_to_inspector_row(record)
        print("[Long-term memory]")
        print(f"namespace={row['namespace']}")
        print(f"memory_id={row['memory_id']}")
        print(f"category={row['category']}")
        print(f"key={row['key']}")
        print(f"value={row['value']}")
        print(f"source_chat_id={row['source_chat_id']}")
        print(f"source_message_ids={row['source_message_ids']}")
        print(f"created_at={row['created_at']}")
        print(f"updated_at={row['updated_at']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
