from __future__ import annotations

import importlib.metadata

from src.agents.context_manager_agent import ContextManagerAgent
from src.context.context_budget_allocator import ContextBudgetAllocator
from src.context.context_builder import ContextBuilder
from src.context.model_profile import (
    DEFAULT_MODEL_ID,
    application_context_cap_from_env,
    endpoint_context_limit_from_env,
    model_profile_for,
    resolve_context_window,
)
from src.context.token_estimator import (
    ApproximateTokenEstimator,
    GemmaTokenEstimator,
    clear_processor_cache,
)
from src.core.contracts import MemoryCandidate, RoutePlan, SourcePlan


class FakeTokenizer:
    def __init__(self) -> None:
        self.template_calls: list[bool] = []
        self.text_calls = 0

    def __call__(self, text: str, *, add_special_tokens: bool) -> dict[str, list[int]]:
        assert add_special_tokens is False
        self.text_calls += 1
        return {"input_ids": list(range(len(text.split())))}

    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> list[int]:
        assert tokenize is True
        self.template_calls.append(add_generation_prompt)
        content_tokens = sum(len(message["content"].split()) for message in messages)
        return list(range(content_tokens + len(messages)))


class FakeProcessor:
    def __init__(self) -> None:
        self.tokenizer = FakeTokenizer()
        self.template_calls: list[bool] = []

    def apply_chat_template(
        self,
        messages: list[dict[str, str]],
        *,
        tokenize: bool,
        add_generation_prompt: bool,
    ) -> list[int]:
        assert tokenize is True
        self.template_calls.append(add_generation_prompt)
        content_tokens = sum(len(message["content"].split()) for message in messages)
        template_overhead = 2 * len(messages)
        generation_overhead = 3 if add_generation_prompt else 0
        return list(range(content_tokens + template_overhead + generation_overhead))


class FailingTemplateProcessor(FakeProcessor):
    def apply_chat_template(self, *args, **kwargs) -> list[int]:
        self.template_calls.append(bool(kwargs["add_generation_prompt"]))
        raise ValueError("temporary processor template failure")


class TransientFailTokenizer(FakeTokenizer):
    def __init__(
        self,
        *,
        fail_template_calls: int = 0,
        fail_text_calls: int = 0,
    ) -> None:
        super().__init__()
        self.fail_template_calls = fail_template_calls
        self.fail_text_calls = fail_text_calls

    def __call__(self, text: str, *, add_special_tokens: bool) -> dict[str, list[int]]:
        if self.fail_text_calls:
            self.fail_text_calls -= 1
            raise ValueError("temporary tokenizer text failure")
        return super().__call__(text, add_special_tokens=add_special_tokens)

    def apply_chat_template(self, *args, **kwargs) -> list[int]:
        if self.fail_template_calls:
            self.fail_template_calls -= 1
            raise ValueError("temporary tokenizer template failure")
        return super().apply_chat_template(*args, **kwargs)


def route() -> RoutePlan:
    return RoutePlan(
        query="question",
        context_profile="document_question",
        sources=[SourcePlan(source="document_memory", enabled=True)],
    )


def candidate(content: str = "document evidence") -> MemoryCandidate:
    return MemoryCandidate(
        source="document_memory",
        content=content,
        score=1.0,
        record_id="doc",
        chat_id="chat",
    )


def test_gemma_profile_has_official_context_metadata() -> None:
    profile = model_profile_for(DEFAULT_MODEL_ID)

    assert profile.native_context_window == 262_144
    assert profile.sliding_window == 1024
    assert profile.tokenizer_id == DEFAULT_MODEL_ID


def test_pillow_is_an_explicit_runtime_dependency() -> None:
    assert importlib.metadata.version("pillow")


def test_sliding_window_is_not_an_effective_input_limit() -> None:
    resolved = resolve_context_window(
        model_profile_for(DEFAULT_MODEL_ID),
        application_context_cap=8192,
    )

    assert resolved.effective_context_window == 8192
    assert resolved.effective_context_window != 1024
    assert resolved.limit_source == "application_cap"


def test_smaller_endpoint_limit_wins() -> None:
    resolved = resolve_context_window(
        model_profile_for(DEFAULT_MODEL_ID),
        endpoint_context_window=32_768,
        application_context_cap=65_536,
    )

    assert resolved.effective_context_window == 32_768
    assert resolved.limit_source == "endpoint_metadata"


def test_smaller_application_cap_wins() -> None:
    resolved = resolve_context_window(
        model_profile_for(DEFAULT_MODEL_ID),
        endpoint_context_window=32_768,
        application_context_cap=4096,
    )

    assert resolved.effective_context_window == 4096
    assert resolved.limit_source == "application_cap"


def test_unknown_endpoint_uses_default_gemma_native_cap() -> None:
    resolved = resolve_context_window(model_profile_for(DEFAULT_MODEL_ID))

    assert resolved.endpoint_context_window is None
    assert resolved.endpoint_limit_verified is False
    assert resolved.application_context_cap == 262_144
    assert resolved.effective_context_window == 262_144
    assert resolved.limit_source == "native_model_assumption"


def test_context_limit_environment_overrides_are_resolved() -> None:
    endpoint, source = endpoint_context_limit_from_env(
        {"MODEL_CONTEXT_WINDOW": "32768"}
    )

    assert endpoint == 32_768
    assert source == "MODEL_CONTEXT_WINDOW"
    assert application_context_cap_from_env(
        {"APPLICATION_CONTEXT_CAP": "8192"}
    ) == 8192


def test_exact_processor_counts_text_and_chat_template_overhead() -> None:
    processor = FakeProcessor()
    estimator = GemmaTokenEstimator(
        DEFAULT_MODEL_ID,
        processor_loader=lambda _: processor,
    )

    assert estimator.count_text("one two three") == 3
    assert estimator.count_messages(
        [{"role": "user", "content": "one two"}],
        add_generation_prompt=True,
    ) == 7
    assert processor.template_calls == [True]
    assert estimator.tokenizer_mode == "model_template"


def test_empty_messages_return_zero_without_loading_or_calling_backends() -> None:
    processor_calls = 0
    tokenizer_calls = 0

    def load_processor(_: str) -> FakeProcessor:
        nonlocal processor_calls
        processor_calls += 1
        return FakeProcessor()

    def load_tokenizer(_: str) -> FakeTokenizer:
        nonlocal tokenizer_calls
        tokenizer_calls += 1
        return FakeTokenizer()

    estimator = GemmaTokenEstimator(
        DEFAULT_MODEL_ID,
        processor_loader=load_processor,
        tokenizer_loader=load_tokenizer,
    )

    assert estimator.count_messages([], add_generation_prompt=True) == 0
    assert processor_calls == 0
    assert tokenizer_calls == 0


def test_empty_messages_do_not_downgrade_resolved_text_tokenizer() -> None:
    tokenizer = FakeTokenizer()

    def fail_processor(_: str) -> FakeProcessor:
        raise OSError("processor unavailable")

    estimator = GemmaTokenEstimator(
        DEFAULT_MODEL_ID,
        processor_loader=fail_processor,
        tokenizer_loader=lambda _: tokenizer,
    )
    assert estimator.count_text("warm") == 1
    calls_before = (tokenizer.text_calls, len(tokenizer.template_calls))

    assert estimator.tokenizer_mode == "text_tokenizer"
    assert estimator.count_messages([], add_generation_prompt=False) == 0
    assert estimator.tokenizer_mode == "text_tokenizer"
    assert (tokenizer.text_calls, len(tokenizer.template_calls)) == calls_before


def test_processor_template_failure_uses_tokenizer_for_only_that_call() -> None:
    processor = FailingTemplateProcessor()
    tokenizer = FakeTokenizer()
    estimator = GemmaTokenEstimator(
        DEFAULT_MODEL_ID,
        processor_loader=lambda _: processor,
        tokenizer_loader=lambda _: tokenizer,
    )

    assert estimator.count_messages(
        [{"role": "user", "content": "one two"}],
        add_generation_prompt=True,
    ) == 3
    assert estimator.tokenizer_mode == "model_template"
    assert "processor_template" in str(
        estimator.trace_metadata()["last_call_fallback_events"]
    )


def test_tokenizer_template_failure_uses_text_serialization_for_that_call() -> None:
    tokenizer = TransientFailTokenizer(fail_template_calls=1)

    def fail_processor(_: str) -> FakeProcessor:
        raise OSError("processor unavailable")

    estimator = GemmaTokenEstimator(
        DEFAULT_MODEL_ID,
        processor_loader=fail_processor,
        tokenizer_loader=lambda _: tokenizer,
    )

    count = estimator.count_messages(
        [{"role": "user", "content": "one two"}],
        add_generation_prompt=True,
    )

    assert count > 0
    assert estimator.tokenizer_mode == "text_tokenizer"
    assert tokenizer.text_calls == 1
    assert "tokenizer_template" in str(
        estimator.trace_metadata()["last_call_fallback_events"]
    )


def test_all_per_call_tokenizer_failures_are_temporary() -> None:
    tokenizer = TransientFailTokenizer(
        fail_template_calls=1,
        fail_text_calls=1,
    )

    def fail_processor(_: str) -> FakeProcessor:
        raise OSError("processor unavailable")

    estimator = GemmaTokenEstimator(
        DEFAULT_MODEL_ID,
        processor_loader=fail_processor,
        tokenizer_loader=lambda _: tokenizer,
    )
    messages = [{"role": "user", "content": "one two"}]
    approximate = ApproximateTokenEstimator(model_name=DEFAULT_MODEL_ID)

    assert estimator.count_messages(
        messages,
        add_generation_prompt=True,
    ) == approximate.count_messages(messages, add_generation_prompt=True)
    assert estimator.tokenizer_mode == "text_tokenizer"
    assert len(estimator.trace_metadata()["last_call_fallback_events"]) == 2

    assert estimator.count_messages(
        messages,
        add_generation_prompt=True,
    ) == 3
    assert estimator.tokenizer_mode == "text_tokenizer"
    assert estimator.trace_metadata()["last_call_fallback_events"] == []


def test_valid_english_messages_remain_on_initialized_tokenizer() -> None:
    tokenizer = FakeTokenizer()

    def fail_processor(_: str) -> FakeProcessor:
        raise OSError("processor unavailable")

    estimator = GemmaTokenEstimator(
        DEFAULT_MODEL_ID,
        processor_loader=fail_processor,
        tokenizer_loader=lambda _: tokenizer,
    )
    estimator.count_text("warm")
    estimator.count_messages([], add_generation_prompt=False)

    assert estimator.count_text("valid English message") == 3
    assert estimator.tokenizer_mode == "text_tokenizer"
    assert estimator.count_text("another valid message") == 3
    assert estimator.tokenizer_mode == "text_tokenizer"


def test_processor_is_lazy_and_cached_by_estimator() -> None:
    processor = FakeProcessor()
    calls = 0

    def loader(_: str) -> FakeProcessor:
        nonlocal calls
        calls += 1
        return processor

    estimator = GemmaTokenEstimator(DEFAULT_MODEL_ID, processor_loader=loader)
    assert calls == 0

    estimator.count_text("first")
    estimator.count_text("second")

    assert calls == 1


def test_default_processor_cache_is_process_wide(monkeypatch) -> None:
    from src.context import token_estimator

    clear_processor_cache()
    processor = FakeProcessor()
    calls = 0

    def load(tokenizer_id: str) -> FakeProcessor:
        nonlocal calls
        assert tokenizer_id == DEFAULT_MODEL_ID
        calls += 1
        return processor

    monkeypatch.setattr(token_estimator, "load_auto_processor", load)
    first = token_estimator.GemmaTokenEstimator(DEFAULT_MODEL_ID)
    second = token_estimator.GemmaTokenEstimator(DEFAULT_MODEL_ID)

    first.count_text("one")
    second.count_text("two")

    assert calls == 1
    clear_processor_cache()


def test_processor_failure_uses_text_tokenizer_and_is_traced() -> None:
    tokenizer = FakeTokenizer()

    def fail_processor(_: str) -> FakeProcessor:
        raise OSError("processor unavailable")

    estimator = GemmaTokenEstimator(
        DEFAULT_MODEL_ID,
        processor_loader=fail_processor,
        tokenizer_loader=lambda _: tokenizer,
    )

    assert estimator.count_text("one two") == 2
    assert estimator.count_messages(
        [{"role": "user", "content": "one two"}],
        add_generation_prompt=True,
    ) == 3
    assert estimator.tokenizer_mode == "text_tokenizer"
    assert "processor unavailable" in str(estimator.fallback_reason)


def test_processor_and_tokenizer_failure_use_approximate_fallback() -> None:
    def fail_processor(_: str) -> FakeProcessor:
        raise OSError("processor unavailable")

    def fail_tokenizer(_: str) -> FakeTokenizer:
        raise OSError("tokenizer unavailable")

    estimator = GemmaTokenEstimator(
        DEFAULT_MODEL_ID,
        processor_loader=fail_processor,
        tokenizer_loader=fail_tokenizer,
    )
    expected = ApproximateTokenEstimator(model_name=DEFAULT_MODEL_ID).count_text("abcd")

    assert estimator.count_text("abcd") == expected
    assert estimator.tokenizer_mode == "approximate"
    assert "processor unavailable" in str(estimator.fallback_reason)
    assert "tokenizer unavailable" in str(estimator.fallback_reason)


def test_processor_and_tokenizer_caches_are_independent(monkeypatch) -> None:
    from src.context import token_estimator

    clear_processor_cache()
    processor_calls = 0
    tokenizer_calls = 0
    tokenizer = FakeTokenizer()

    def fail_processor(_: str) -> FakeProcessor:
        nonlocal processor_calls
        processor_calls += 1
        raise OSError("no processor")

    def load_tokenizer(_: str) -> FakeTokenizer:
        nonlocal tokenizer_calls
        tokenizer_calls += 1
        return tokenizer

    monkeypatch.setattr(token_estimator, "load_auto_processor", fail_processor)
    monkeypatch.setattr(token_estimator, "load_auto_tokenizer", load_tokenizer)
    first = GemmaTokenEstimator(DEFAULT_MODEL_ID)
    second = GemmaTokenEstimator(DEFAULT_MODEL_ID)

    assert first.count_text("one") == 1
    assert second.count_text("two") == 1
    assert processor_calls == 1
    assert tokenizer_calls == 1
    assert first.tokenizer_mode == "text_tokenizer"
    assert second.tokenizer_mode == "text_tokenizer"
    clear_processor_cache()


def test_fallback_is_visible_in_context_trace() -> None:
    def fail_processor(_: str) -> FakeProcessor:
        raise OSError("offline")

    def fail_tokenizer(_: str) -> FakeTokenizer:
        raise OSError("tokenizer offline")

    manager = ContextManagerAgent.for_model(
        DEFAULT_MODEL_ID,
        processor_loader=fail_processor,
        tokenizer_loader=fail_tokenizer,
    )
    result = manager.build_context_packet(
        system_prompt="system",
        latest_user_message={"role": "user", "content": "question"},
        ranked_candidates=[candidate()],
        route_plan=route(),
    )

    metadata = result.context_packet.metadata
    assert metadata["tokenizer_mode"] == "approximate"
    assert metadata["tokenizer_id"] == DEFAULT_MODEL_ID
    assert "offline" in metadata["fallback_reason"]
    assert metadata["native_context_window"] == 262_144
    assert metadata["sliding_window"] == 1024
    assert metadata["endpoint_context_window"] is None
    assert metadata["endpoint_limit_verified"] is False
    assert metadata["effective_context_window"] == 262_144
    assert metadata["effective_limit_source"] == "native_model_assumption"


def test_allocator_selection_is_unchanged_with_equivalent_injected_counter() -> None:
    approximate = ApproximateTokenEstimator()

    class EquivalentCounter(ApproximateTokenEstimator):
        backend = "equivalent_test_counter"

    exact_equivalent = EquivalentCounter()
    candidates = [candidate("a" * 100), candidate("b" * 300)]
    plan = route()

    baseline_budget = ContextBudgetAllocator(
        token_estimator=approximate
    ).allocate(
        plan,
        candidates,
        model_context_limit=500,
        answer_reserve=50,
        system_prompt="system",
    )
    injected_budget = ContextBudgetAllocator(
        token_estimator=exact_equivalent
    ).allocate(
        plan,
        candidates,
        model_context_limit=500,
        answer_reserve=50,
        system_prompt="system",
    )
    baseline = ContextBuilder(approximate).build(
        "system",
        {"role": "user", "content": "question"},
        candidates,
        baseline_budget,
        plan,
    )
    injected = ContextBuilder(exact_equivalent).build(
        "system",
        {"role": "user", "content": "question"},
        candidates,
        injected_budget,
        plan,
    )

    assert [item.record_id for item in injected.candidates] == [
        item.record_id for item in baseline.candidates
    ]
