from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.agents.coordinator_agent import (
    CoordinatorAgent,
    require_chat_document_memory,
    require_document_memory,
)
from src.core.contracts import RoutePlan, SourcePlan
from src.database import Database
from src.routing.routing_agent import RoutingDecision


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_routing_decision(
    intent: str = "general_question",
    use_document_memory: bool = False,
    context_profile: str = "general_chat",
) -> RoutingDecision:
    """Build a minimal test RoutingDecision."""
    sources: list[SourcePlan] = [
        SourcePlan(source="recent_messages", enabled=True),
        SourcePlan(source="structured_memory", enabled=True),
        SourcePlan(source="document_memory", enabled=use_document_memory),
    ]
    route_plan = RoutePlan(
        query="test query",
        sources=sources,
        intent=intent,
        context_profile=context_profile,
    )
    return RoutingDecision(
        route_plan=route_plan,
        use_recent_messages=True,
        use_structured_memory=True,
        use_document_memory=use_document_memory,
        reason="Test decision.",
        confidence=0.9,
        routing_mode="rule",
        metadata={},
    )


def _make_coordinator(database: Database) -> CoordinatorAgent:
    """Return a CoordinatorAgent with real DB but mocked non-DB dependencies."""
    return CoordinatorAgent(
        database=database,
        memory_agent=MagicMock(),
        context_builder=MagicMock(),
        chat_agent=MagicMock(),
        system_prompt="test system prompt",
    )


# ---------------------------------------------------------------------------
# require_chat_document_memory  (standalone, no DB)
# ---------------------------------------------------------------------------


class TestRequireChatDocumentMemory:
    def test_enables_document_memory_for_casual_query(self):
        """Chat with documents → document_memory enabled."""
        decision = _make_routing_decision(intent="casual_chat")
        result = require_chat_document_memory(decision)

        assert result.use_document_memory is True
        assert result.route_plan.metadata.get("chat_document_scope_sticky")
        assert result.metadata.get("chat_document_scope_sticky")
        assert "Chat has associated documents" in result.reason

        doc_sources = [s for s in result.route_plan.sources if s.source == "document_memory"]
        assert len(doc_sources) == 1
        assert doc_sources[0].enabled

    def test_enables_document_memory_when_already_enabled(self):
        """document_memory already enabled → stays enabled with updated metadata."""
        decision = _make_routing_decision(
            intent="document_question",
            use_document_memory=True,
            context_profile="document_question",
        )
        result = require_chat_document_memory(decision)

        assert result.use_document_memory is True
        assert result.route_plan.metadata.get("chat_document_scope_sticky")

    def test_adds_document_memory_when_not_in_sources(self):
        """Sources missing document_memory → it is appended."""
        decision = _make_routing_decision()
        # Remove document_memory from sources
        sparse_plan = replace_plan_sources(
            decision.route_plan,
            [
                SourcePlan(source="recent_messages", enabled=True),
                SourcePlan(source="structured_memory", enabled=True),
            ],
        )
        decision = replace_decision_plan(decision, sparse_plan)
        result = require_chat_document_memory(decision)

        doc_sources = [s for s in result.route_plan.sources if s.source == "document_memory"]
        assert len(doc_sources) == 1
        assert doc_sources[0].enabled
        assert doc_sources[0].reason == "Chat has associated documents (sticky scope)."

    def test_preserves_intent(self):
        """Intent stays as classified — not forced to document_question."""
        for intent in ("casual_chat", "general_question", "task_question"):
            decision = _make_routing_decision(intent=intent)
            result = require_chat_document_memory(decision)
            assert result.route_plan.intent == intent

    def test_preserves_context_profile(self):
        """context_profile stays as classified."""
        for profile in ("general_chat", "document_question", "previous_chat"):
            decision = _make_routing_decision(context_profile=profile)
            result = require_chat_document_memory(decision)
            assert result.route_plan.context_profile == profile

    def test_does_not_set_same_turn_attachment(self):
        """No same_turn_attachment filter is set."""
        decision = _make_routing_decision()
        result = require_chat_document_memory(decision)

        for source in result.route_plan.sources:
            if source.source == "document_memory":
                assert "same_turn_attachment" not in source.filters

    def test_does_not_change_non_document_sources(self):
        """Other sources are untouched."""
        decision = _make_routing_decision()
        result = require_chat_document_memory(decision)

        recent = [s for s in result.route_plan.sources if s.source == "recent_messages"]
        assert len(recent) == 1
        assert recent[0].enabled

        structured = [s for s in result.route_plan.sources if s.source == "structured_memory"]
        assert len(structured) == 1
        assert structured[0].enabled

    def test_sets_requires_retrieval(self):
        """requires_retrieval is True after enable."""
        decision = _make_routing_decision()
        assert decision.route_plan.requires_retrieval is None
        result = require_chat_document_memory(decision)
        assert result.route_plan.requires_retrieval is True  # noqa: E712


# ---------------------------------------------------------------------------
# require_document_memory regression  (same-turn attachment)
# ---------------------------------------------------------------------------


class TestRequireDocumentMemoryRegression:
    def test_same_turn_sets_intent_and_profile(self):
        """Same-turn attachment overrides intent and context_profile."""
        decision = _make_routing_decision(intent="general_question")
        result = require_document_memory(decision)

        assert result.use_document_memory is True  # noqa: E712
        assert result.route_plan.intent == "document_question"
        assert result.route_plan.context_profile == "document_question"

    def test_same_turn_sets_attachment_filter(self):
        """same_turn_attachment filter is set."""
        decision = _make_routing_decision()
        result = require_document_memory(decision)

        doc_sources = [s for s in result.route_plan.sources if s.source == "document_memory"]
        assert len(doc_sources) == 1
        assert doc_sources[0].filters.get("same_turn_attachment")

    def test_same_turn_sets_metadata(self):
        """same_turn_attachment metadata is recorded."""
        decision = _make_routing_decision()
        result = require_document_memory(decision)

        assert result.route_plan.metadata.get("same_turn_attachment")
        assert result.metadata.get("same_turn_attachment")


# ---------------------------------------------------------------------------
# _chat_has_documents  (needs DB)
# ---------------------------------------------------------------------------


class TestChatHasDocuments:
    def test_returns_true_when_chat_has_documents(self, tmp_path: Path):
        db = Database(tmp_path / "chatbot.db")
        db.create_chat("chat-1")
        db.create_document_record("doc-1", "report.pdf", status="Ready")
        db.associate_document_with_chat("chat-1", "doc-1")
        coordinator = _make_coordinator(db)

        assert coordinator._chat_has_documents("chat-1")

    def test_returns_false_when_chat_has_no_documents(self, tmp_path: Path):
        db = Database(tmp_path / "chatbot.db")
        db.create_chat("chat-empty")
        coordinator = _make_coordinator(db)

        assert not coordinator._chat_has_documents("chat-empty")

    def test_returns_false_nonexistent_chat(self, tmp_path: Path):
        db = Database(tmp_path / "chatbot.db")
        coordinator = _make_coordinator(db)

        assert not coordinator._chat_has_documents("no-such-chat")

    def test_env_var_disables_sticky_scope(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("CHAT_DOCUMENT_SCOPE_STICKY", "false")
        db = Database(tmp_path / "chatbot.db")
        db.create_chat("chat-1")
        db.create_document_record("doc-1", "report.pdf", status="Ready")
        db.associate_document_with_chat("chat-1", "doc-1")
        coordinator = _make_coordinator(db)

        assert not coordinator._chat_has_documents("chat-1")

    @pytest.mark.parametrize("value", ["0", "no", "off", "False", "  off  "])
    def test_env_var_falsey_values(self, tmp_path: Path, monkeypatch, value: str):
        monkeypatch.setenv("CHAT_DOCUMENT_SCOPE_STICKY", value)
        db = Database(tmp_path / "chatbot.db")
        db.create_chat("chat-x")
        db.create_document_record("d", "f.txt", status="Ready")
        db.associate_document_with_chat("chat-x", "d")
        coordinator = _make_coordinator(db)

        assert not coordinator._chat_has_documents("chat-x")

    def test_env_var_true_by_default(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("CHAT_DOCUMENT_SCOPE_STICKY", raising=False)
        db = Database(tmp_path / "chatbot.db")
        db.create_chat("chat-1")
        db.create_document_record("doc-1", "report.pdf", status="Ready")
        db.associate_document_with_chat("chat-1", "doc-1")
        coordinator = _make_coordinator(db)

        assert coordinator._chat_has_documents("chat-1")

    def test_deleted_documents_not_counted(self, tmp_path: Path):
        db = Database(tmp_path / "chatbot.db")
        db.create_chat("chat-1")
        db.create_document_record("doc-1", "report.pdf", status="Ready")
        db.associate_document_with_chat("chat-1", "doc-1")
        db.update_document_status("doc-1", "deleted")
        coordinator = _make_coordinator(db)

        assert not coordinator._chat_has_documents("chat-1")


# ---------------------------------------------------------------------------
# dataclass helpers for sparse plan construction
# ---------------------------------------------------------------------------


def replace_plan_sources(plan: RoutePlan, sources: list[SourcePlan]) -> RoutePlan:
    """Return a RoutePlan copy with replaced sources."""
    return RoutePlan(
        query=plan.query,
        sources=sources,
        intent=plan.intent,
        confidence=plan.confidence,
        requires_retrieval=plan.requires_retrieval,
        ranking_profile=plan.ranking_profile,
        context_profile=plan.context_profile,
        fallback_policy=plan.fallback_policy,
        update_policy=plan.update_policy,
        termination_policy=plan.termination_policy,
        metadata=plan.metadata,
    )


def replace_decision_plan(decision: RoutingDecision, plan: RoutePlan) -> RoutingDecision:
    """Return a RoutingDecision copy with replaced route_plan."""
    return RoutingDecision(
        route_plan=plan,
        use_recent_messages=decision.use_recent_messages,
        use_structured_memory=decision.use_structured_memory,
        use_document_memory=decision.use_document_memory,
        reason=decision.reason,
        confidence=decision.confidence,
        fallback_mode=decision.fallback_mode,
        routing_mode=decision.routing_mode,
        routing_fallback_reason=decision.routing_fallback_reason,
        metadata=decision.metadata,
    )
