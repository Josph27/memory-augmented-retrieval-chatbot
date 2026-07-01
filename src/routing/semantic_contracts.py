from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IntentScore:
    """One deterministic semantic intent classification."""

    intent: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class EvidenceContract:
    """Evidence requirements that must hold after context construction."""

    requires_raw_span: bool = False
    requires_document_citation: bool = False
    requires_structured_memory: bool = False
    requires_provenance: bool = True
    allows_gist_orientation: bool = True
    must_not_answer_from_gist_only: bool = False
    allow_abstain_if_missing: bool = True


@dataclass(frozen=True)
class RetrievalQuery:
    """A bounded query hint for selected retrieval sources."""

    text: str
    purpose: str
    allowed_sources: tuple[str, ...]
    is_generated: bool = False


@dataclass(frozen=True)
class SemanticRoutePlan:
    """Typed query understanding emitted by the default-off semantic router."""

    original_query: str
    normalized_query: str
    language: str
    intents: tuple[IntentScore, ...]
    temporal_scope: str
    enabled_sources: tuple[str, ...]
    evidence_contract: EvidenceContract
    retrieval_queries: tuple[RetrievalQuery, ...]
    confidence: float
    router_version: str = "semantic_v2"

