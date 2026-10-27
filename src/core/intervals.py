"""Deterministic operations on inclusive integer ranges."""

from collections.abc import Sequence


def merge_inclusive_ranges(ranges: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent ranges without changing their endpoints."""
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if not merged or start > merged[-1][1] + 1:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return merged
