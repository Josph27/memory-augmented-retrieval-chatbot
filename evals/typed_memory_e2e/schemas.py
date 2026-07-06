from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BenchmarkMessage:
    role: str
    content: str


@dataclass(frozen=True)
class BenchmarkSession:
    chat_name: str
    messages: tuple[BenchmarkMessage, ...] = ()
    end_chat: bool = False


@dataclass(frozen=True)
class TypedMemoryCase:
    name: str
    description: str
    category: str
    sessions: tuple[BenchmarkSession, ...]
    query: str
    expected_sources: tuple[str, ...] = ()
    forbidden_sources: tuple[str, ...] = ()
    required_text_in_context: tuple[str, ...] = ()
    requires_raw_span: bool = False
    requires_document_citation: bool = False
    requires_structured_memory: bool = False
    expected_insufficient_evidence: bool = False
    expected_provenance: bool = True
    answer_mode: str = "mock"
    notes: str = ""
    fixture: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TypedMemoryCaseResult:
    name: str
    category: str
    passed: bool
    sources_observed: tuple[str, ...]
    required_sources_present: bool
    forbidden_sources_absent: bool
    required_text_present: bool
    raw_span_present: bool
    document_citation_present: bool
    structured_memory_present: bool
    provenance_present: bool
    insufficient_evidence: bool
    context_char_size: int
    failure_reasons: tuple[str, ...]
    notes: str = ""
