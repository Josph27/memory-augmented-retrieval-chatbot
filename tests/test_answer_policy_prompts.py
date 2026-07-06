from __future__ import annotations

from evals.memory_agent_bench.adapter import SYSTEM_PROMPT as MAB_SYSTEM_PROMPT
from src.chat_service import SYSTEM_PROMPT as CHAT_SYSTEM_PROMPT


def test_production_system_prompt_answers_when_context_is_sufficient() -> None:
    assert (
        "Answer directly when the supplied context provides sufficient evidence."
        in CHAT_SYSTEM_PROMPT
    )


def test_production_system_prompt_keeps_abstention_for_missing_evidence() -> None:
    assert (
        "Use “I don't know” only when the available context does not support an answer."
        in CHAT_SYSTEM_PROMPT
    )


def test_generic_answer_policy_prioritizes_explicit_context_over_priors() -> None:
    expected = (
        "Do not ignore explicit contextual evidence merely because it "
        "conflicts with prior world knowledge."
    )
    assert expected in CHAT_SYSTEM_PROMPT
    assert expected in MAB_SYSTEM_PROMPT


def test_generic_answer_policy_does_not_force_choice_between_conflicting_claims() -> None:
    expected = (
        "If supplied context contains unresolved conflicting claims, "
        "state the conflict rather than choosing arbitrarily."
    )
    assert expected in CHAT_SYSTEM_PROMPT
    assert expected in MAB_SYSTEM_PROMPT


def test_generic_answer_policy_qualifies_partial_evidence() -> None:
    expected = (
        "If evidence is partial, answer only the supported portion "
        "and state the limitation."
    )
    assert expected in CHAT_SYSTEM_PROMPT
    assert expected in MAB_SYSTEM_PROMPT
