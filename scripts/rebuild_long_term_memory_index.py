from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def main() -> int:
    """Rebuild the semantic vector index for long-term structured memories."""
    from src.config import AppConfig
    from src.database import Database
from src.memory.long_term_store import SQLiteLongTermMemoryStore
from src.memory.long_term_vector_index import (
    LongTermMemoryVectorIndex,
    VectorIndexUnavailable,
)

    parser = argparse.ArgumentParser(
        description="Index SQLite long-term memories into the semantic Chroma index."
    )
    parser.add_argument("--limit-namespaces", type=int, default=100)
    args = parser.parse_args()

    config = AppConfig.from_env()
    database = Database(config.database_path)
    store = SQLiteLongTermMemoryStore(database)
    namespaces = store.list_namespaces(limit=args.limit_namespaces)
    vector_index = LongTermMemoryVectorIndex(
        database_path=config.database_path,
        embedding_model_name=config.embedding_model_name,
    )

    try:
        result = vector_index.rebuild_from_store(store=store, namespaces=namespaces)
    except VectorIndexUnavailable as error:
        print(f"long_term_memory_vector_unavailable reason={error}")
        return 2

    print(f"database_path={config.database_path}")
    print(f"namespaces={len(namespaces)}")
    print(f"indexed_count={result.indexed_count}")
    print(f"skipped_count={result.skipped_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
