from __future__ import annotations

import hashlib
import re

from src.database import Database
from src.vectorstores.base import VectorSearchResult, VectorStoreUnavailableError
from src.vectorstores.sqlite_json_store import parse_metadata


class SQLiteVecVectorStore:
    """sqlite-vec backend using vec0 virtual tables when available.

    The project does not require sqlite-vec for normal tests. This class checks
    availability and raises a clear error if the native extension is not
    installed/loadable.
    """

    def __init__(self, database: Database) -> None:
        try:
            import sqlite_vec  # type: ignore[import-not-found]
        except Exception as error:
            msg = "sqlite-vec is not available. Use VECTOR_BACKEND=sqlite_json or keyword retrieval."
            raise VectorStoreUnavailableError(msg) from error

        self.database = database
        self.sqlite_vec = sqlite_vec
        self._verify_extension_loads()

    def upsert_chunk_embedding(
        self,
        chunk_id: int,
        embedding: list[float],
        embedding_model: str,
        metadata: dict | None = None,
    ) -> None:
        """Insert or replace one chunk vector in sqlite-vec and JSON metadata storage."""
        self.validate_embedding(embedding)
        self.database.upsert_chunk_embedding(
            chunk_id=chunk_id,
            embedding_model=embedding_model,
            vector=embedding,
            metadata=metadata,
        )
        table_name = vector_table_name(embedding_model, len(embedding))
        with self.database.connect() as connection:
            self.load_extension(connection)
            connection.execute(create_vector_table_sql(table_name, len(embedding)))
            connection.execute(
                f"DELETE FROM {quote_identifier(table_name)} WHERE rowid = ?",
                (chunk_id,),
            )
            connection.execute(
                f"""
                INSERT INTO {quote_identifier(table_name)} (
                    rowid, embedding, embedding_model, chunk_id
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    chunk_id,
                    self.sqlite_vec.serialize_float32(embedding),
                    embedding_model,
                    chunk_id,
                ),
            )

    def search(
        self,
        query_embedding: list[float],
        top_k: int,
        embedding_model: str,
    ) -> list[VectorSearchResult]:
        """Return nearest chunks using sqlite-vec KNN search."""
        self.validate_embedding(query_embedding)
        if top_k <= 0:
            return []

        table_name = vector_table_name(embedding_model, len(query_embedding))
        with self.database.connect() as connection:
            self.load_extension(connection)
            if not vector_table_exists(connection, table_name):
                return []

            rows = connection.execute(
                f"""
                SELECT
                    vec.rowid AS chunk_id,
                    vec.distance AS distance,
                    embeddings.metadata_json AS metadata_json
                FROM {quote_identifier(table_name)} AS vec
                LEFT JOIN document_chunk_embeddings AS embeddings
                  ON embeddings.chunk_id = vec.rowid
                 AND embeddings.embedding_model = ?
                WHERE vec.embedding MATCH ?
                  AND k = ?
                  AND vec.embedding_model = ?
                ORDER BY vec.distance
                """,
                (
                    embedding_model,
                    self.sqlite_vec.serialize_float32(query_embedding),
                    top_k,
                    embedding_model,
                ),
            ).fetchall()

        return [
            VectorSearchResult(
                chunk_id=int(row["chunk_id"]),
                score=distance_to_score(float(row["distance"])),
                metadata=parse_metadata(row["metadata_json"] or "{}"),
            )
            for row in rows
        ]

    def has_embedding(self, chunk_id: int, embedding_model: str) -> bool:
        """Return whether the metadata table has a chunk/model embedding row."""
        return self.database.has_chunk_embedding(chunk_id, embedding_model)

    def load_extension(self, connection) -> None:
        """Load sqlite-vec functions into one SQLite connection."""
        try:
            connection.enable_load_extension(True)
            self.sqlite_vec.load(connection)
        finally:
            connection.enable_load_extension(False)

    def _verify_extension_loads(self) -> None:
        """Fail early if sqlite-vec cannot be loaded by this Python SQLite build."""
        try:
            with self.database.connect() as connection:
                self.load_extension(connection)
                connection.execute("SELECT vec_version()").fetchone()
        except Exception as error:
            msg = (
                "sqlite-vec is installed but could not be loaded by sqlite3. "
                "Use VECTOR_BACKEND=sqlite_json or keyword retrieval."
            )
            raise VectorStoreUnavailableError(msg) from error

    @staticmethod
    def validate_embedding(embedding: list[float]) -> None:
        """Reject empty vectors because vec0 table dimensions must be positive."""
        if not embedding:
            raise ValueError("sqlite-vec embeddings must be non-empty")


def vector_table_name(embedding_model: str, dimension: int) -> str:
    """Return a stable vec0 table name for one model/dimension pair."""
    model_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", embedding_model).strip("_").lower()
    if not model_slug:
        model_slug = "model"
    digest = hashlib.sha1(embedding_model.encode("utf-8")).hexdigest()[:12]
    return f"document_chunk_vec_{model_slug[:32]}_{dimension}_{digest}"


def create_vector_table_sql(table_name: str, dimension: int) -> str:
    """Build vec0 virtual table DDL for chunk embeddings."""
    return (
        f"CREATE VIRTUAL TABLE IF NOT EXISTS {quote_identifier(table_name)} "
        "USING vec0("
        f"embedding float[{dimension}], "
        "embedding_model text, "
        "chunk_id integer"
        ")"
    )


def quote_identifier(identifier: str) -> str:
    """Quote a generated SQLite identifier."""
    return '"' + identifier.replace('"', '""') + '"'


def vector_table_exists(connection, table_name: str) -> bool:
    """Return whether a vec0 virtual table exists."""
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE name = ?
          AND type = 'table'
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def distance_to_score(distance: float) -> float:
    """Convert sqlite-vec distance where lower is better into higher-is-better score."""
    return 1.0 / (1.0 + max(0.0, distance))
