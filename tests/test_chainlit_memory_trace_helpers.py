from __future__ import annotations

from types import SimpleNamespace

from app import retrieved_memory_rows, saved_memory_rows


def test_saved_memory_rows_reads_result_metadata() -> None:
    result = SimpleNamespace(metadata={"saved_memory_rows": [{"memory_id": "m1"}]})

    assert saved_memory_rows(result) == [{"memory_id": "m1"}]


def test_retrieved_memory_rows_falls_back_to_trace_metadata() -> None:
    result = SimpleNamespace(
        metadata={},
        trace=SimpleNamespace(metadata={"retrieved_memory_rows": [{"memory_id": "m2"}]}),
    )

    assert retrieved_memory_rows(result) == [{"memory_id": "m2"}]

