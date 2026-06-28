# Code Style Guide — Memory-Augmented Retrieval Chatbot

> **Prescriptive. Write code like THIS.**

---

## 1. Quick Reference

| Rule | DO ✅ | DON'T ❌ |
|------|-------|---------|
| **First line** | `from __future__ import annotations` | Omit it |
| **Import order** | stdlib → third-party → local; alphabetized within group; blank line between groups | Mix groups |
| **Optional types** | `int \| None` (PEP 604) | `Optional[int]` |
| **Union types** | `str \| None`, `dict[str, Any]` | `Optional[str]`, bare `dict` |
| **Return annotations** | Always on public methods; `-> None` for no return | Omit return type |
| **Dataclasses** | `@dataclass(frozen=True)` by default; mutable only with explicit reason | Plain `@dataclass` without `frozen=True` |
| **Field defaults** | `field(default_factory=dict)` for mutable defaults | `{}` or `[]` as field defaults |
| **Docstrings** | Google-style triple-double-quotes; every public class and method | Missing or numpy-style |
| **Classes** | PascalCase | snake_case classes |
| **Functions** | snake_case | camelCase |
| **Constants** | UPPER_CASE at module level | lowercase module-level variables |
| **Private members** | `_prefix` for internal methods/attrs | Public names for internals |
| **Strings** | f-strings for interpolation; double quotes for multi-line docstrings | `.format()`, `%`-formatting |
| **Line length** | 100 characters max (ruff enforced) | >100 chars |
| **Error handling** | Specific exception types; log-and-continue for non-critical paths | Bare `except:` or `except Exception:` without logging |
| **Async** | Only in Chainlit adapter layer (`async def`) | Async in src/ business logic |
| **Imports** | Top-level, one per line for typing imports | Wildcard `from X import *` |
| **Testing** | Plain `def test_*()` functions; Fake/Spy test doubles in test file | `unittest.TestCase`; heavy mocking frameworks |
| **Python version** | Target 3.10+ via `from __future__ import annotations` | 3.9-specific syntax |

---

## 2. File Structure Template

```python
"""Module-level docstring describing the purpose of this module."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Stdlib imports (alphabetized)
# ---------------------------------------------------------------------------
import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol

# ---------------------------------------------------------------------------
# Third-party imports (alphabetized)
# ---------------------------------------------------------------------------
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Local imports (alphabetized by package, then by module)
# ---------------------------------------------------------------------------
from src.core.contracts import MemoryCandidate, RoutePlan
from src.database import Database
from src.memory.constants import RAW_MESSAGE_LIMIT

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
DEFAULT_LIMIT = 10
SUPPORTED_MODES = {"sqlite", "vector", "hybrid"}

# ---------------------------------------------------------------------------
# Data classes (frozen, at top of file)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SomeResult:
    """Docstring describing the result."""
    value: str
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SomePolicy:
    """Docstring describing the policy."""
    threshold: float = 0.5
    sources: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Protocol classes (interface contracts)
# ---------------------------------------------------------------------------
class SomeModel(Protocol):
    """Minimal protocol for dependency injection."""

    def invoke(self, input: dict[str, Any]) -> str:
        """Return a model response."""
        ...


# ---------------------------------------------------------------------------
# Main service class
# ---------------------------------------------------------------------------
class SomeService:
    """Docstring describing the service's responsibility."""

    def __init__(
        self,
        database: Database,
        policy: SomePolicy | None = None,
    ) -> None:
        self.database = database
        self.policy = policy or SomePolicy()

    def public_method(self, *, query: str, limit: int = DEFAULT_LIMIT) -> SomeResult:
        """Docstring describing the method."""
        normalized = normalize_query(query)
        return SomeResult(value=normalized)

    def _private_method(self, value: str) -> bool:
        """Internal helper docstring."""
        return bool(value.strip())


# ---------------------------------------------------------------------------
# Standalone module-level functions
# ---------------------------------------------------------------------------
def normalize_query(query: str) -> str:
    """Normalize a query string for comparison."""
    return query.strip().lower()
```

---

## 3. Detailed Rules

### 3.1 Imports

**Rule**: Every `.py` file must start with `from __future__ import annotations` immediately after the module docstring.

```python
# ✅ DO
"""Module docstring."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from src.core.contracts import MemoryCandidate
from src.memory.constants import RAW_MESSAGE_LIMIT
```

```python
# ❌ DON'T
import os
from dataclasses import dataclass

from src.core.contracts import MemoryCandidate
# Missing from __future__ import annotations
# Missing blank line between stdlib and third-party groups
# Third-party mixed with local
```

**Grouping**: Three groups — stdlib, third-party, local. One blank line between groups. Alphabetize within each group. Multi-line imports from the same module should list items alphabetically.

```python
# ✅ DO — multi-line from same module, alphabetized
from src.core.contracts import (
    AgentTurnResult,
    ContextBudget,
    ContextPacket,
    MemoryCandidate,
    RoutePlan,
)
```

```python
# ❌ DON'T
from src.core.contracts import RoutePlan, MemoryCandidate, ContextPacket
# Not alphabetized
```

**Comment separators**: The `# ----` separator comments between import groups are optional but observed in the codebase (`src/database.py`). They are acceptable but not required.

### 3.2 Type Annotations

**Rule**: Every public method/function must have parameter and return type annotations. Private methods should too unless the type is obvious.

```python
# ✅ DO
def allocate(
    self,
    route_plan: RoutePlan,
    ranked_candidates: list[MemoryCandidate],
    model_context_limit: int | None = None,
) -> ContextBudget:
    """Return a profile-based context budget."""
    ...

def clamp(value: float) -> float:
    """Clamp a score feature to [0, 1]."""
    return max(0.0, min(1.0, value))
```

```python
# ❌ DON'T
def allocate(self, route_plan, ranked_candidates, model_context_limit=None):
    # Missing return type, missing parameter types
    ...

def clamp(value):
    return max(0.0, min(1.0, value))
```

**PEP 604 union syntax**: Always use `X | None`, never `Optional[X]`. Always use `X | Y`, never `Union[X, Y]`.

```python
# ✅ DO
def find(self, chat_id: str) -> StoredChat | None: ...
value: str | int | None = None

# ❌ DON'T
from typing import Optional, Union
def find(self, chat_id: str) -> Optional[StoredChat]: ...
value: Union[str, int, None] = None
```

**Generics**: Prefer built-in generics (`list[X]`, `dict[str, Any]`, `tuple[str, ...]`) — these work because of `from __future__ import annotations`.

```python
# ✅ DO
candidates: list[MemoryCandidate]
source_budgets: dict[str, int]
terms: tuple[str, ...]

# ❌ DON'T
from typing import List, Dict, Tuple
candidates: List[MemoryCandidate]
source_budgets: Dict[str, int]
terms: Tuple[str, ...]
```

### 3.3 Docstrings

**Format**: Google-style. Triple double quotes `"""..."""`. Every public class and public method must have a docstring. Private methods should have docstrings when behavior is non-obvious.

```python
# ✅ DO
@dataclass(frozen=True)
class ContextPacket:
    """Context selected for a chat model call."""

    chat_id: str
    system_prompt: str | None = None
    candidates: list[MemoryCandidate] = field(default_factory=list)


class RoutePlanner:
    """Create production-shaped route plans without changing retrieval behavior."""

    def __init__(self, analyzer: QueryAnalyzer | None = None) -> None:
        self.analyzer = analyzer or QueryAnalyzer()

    def plan(self, query: str) -> RoutePlan:
        """Analyze a query and return the current route plan."""
        analysis = self.analyzer.analyze(query)
        return self.plan_from_analysis(analysis)
```

```python
# ❌ DON'T
class RoutePlanner:
    def __init__(self, analyzer=None):
        self.analyzer = analyzer or QueryAnalyzer()

    def plan(self, query):
        # Missing docstrings everywhere
        analysis = self.analyzer.analyze(query)
        return self.plan_from_analysis(analysis)
```

**Module docstrings**: Every module file must have a top-level `"""..."""` docstring. Every `__init__.py` should have a package docstring.

```python
# src/agents/__init__.py — ✅
"""Lightweight agent wrappers around the current chatbot services."""

# src/core/__init__.py — ✅
"""Core architecture contracts for the chatbot workflow."""
```

### 3.4 Naming Conventions

| Construct | Convention | Example |
|-----------|-----------|---------|
| Classes | PascalCase | `RoutePlanner`, `ContextBudget`, `MemoryReranker` |
| Functions/methods | snake_case | `normalize_query`, `build_context`, `_log_trace` |
| Module-level constants | UPPER_CASE | `RAW_MESSAGE_LIMIT`, `DEFAULT_LLM_TOP_K` |
| Private methods/attrs | `_prefix` | `_fallback_decision`, `_chat_from_row`, `_config` |
| Test functions | `test_` + snake_case | `test_routing_agent_wraps_existing` |
| Test doubles | `Fake` prefix | `FakeModel`, `FakeRoutingModel` |
| Spy doubles | `Spy` prefix | `SpyRetriever` |
| Protocol classes | Descriptive noun | `RoutingModel`, `RerankerModel`, `SourceRetriever` |

**Boolean-ish names**: Boolean variables use `is_`, `has_`, `use_`, `asks_`, or `requires_` prefix.

```python
# ✅ DO
asks_about_current_chat: bool = False
use_document_memory: bool
requires_retrieval: bool | None = None
overflow_detected: bool

# ❌ DON'T
document_memory: bool  # ambiguous — is it a flag or a value?
current_chat: bool
```

### 3.5 Class Structure

**Dataclasses are the default**. Use `@dataclass(frozen=True)` for all data containers, configuration objects, and result types. Only use regular classes when you need mutable state, context managers, or complex `__init__` logic.

```python
# ✅ DO — data container
@dataclass(frozen=True)
class SourcePlan:
    """A planned source to query for context."""
    source: MemorySourceType
    enabled: bool = True
    reason: str | None = None
    query: str | None = None
    limit: int | None = None
    filters: dict[str, Any] = field(default_factory=dict)


# ✅ DO — service class (mutable state needed)
class Database:
    """Small SQLite adapter for chats, messages, and structured memory."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()
```

```python
# ❌ DON'T — data container as mutable
class SourcePlan:
    def __init__(self, source, enabled=True):
        self.source = source
        self.enabled = enabled
```

**`__init__` patterns**: All `__init__` methods must have a `-> None` return annotation. Use keyword-only arguments (`*`) only when the signature would be ambiguous — the codebase currently does not use this pattern widely.

**`__post_init__`**: Used only on frozen dataclasses when default values require runtime computation.

```python
# ✅ DO
@dataclass(frozen=True)
class RoutePlannerPolicy:
    active_sources: tuple[SourceRoutingPolicy, ...] = (...)
    intent_context_profiles: dict[str, str] = None  # type hint for __post_init__

    def __post_init__(self) -> None:
        if self.intent_context_profiles is None:
            object.__setattr__(
                self,
                "intent_context_profiles",
                {"general_question": "general_chat", ...},
            )
```

### 3.6 Method Patterns

**Static methods**: Use `@classmethod` for factory constructors (e.g., `from_env()`). Static methods are rare — prefer module-level functions instead.

```python
# ✅ DO — factory
@classmethod
def from_env(cls) -> "AppConfig":
    """Load local .env values."""
    load_dotenv()
    return cls(...)


# ✅ DO — module-level function (preferred over @staticmethod)
def normalize_query(query: str) -> str:
    """Normalize whitespace and case."""
    return re.sub(r"\s+", " ", query.strip().lower())
```

**Properties**: Use `@property` for lazily-initialized or derived attributes.

```python
# ✅ DO
@property
def manager(self) -> LangMemManager:
    """Return the injected manager or lazily construct the real LangMem manager."""
    if self._manager is None:
        self._manager = create_real_langmem_manager(self._config)
    return self._manager
```

**Context managers**: Use `@contextmanager` decorator from `contextlib`.

```python
# ✅ DO
from contextlib import contextmanager

@contextmanager
def connect(self) -> Iterator[sqlite3.Connection]:
    """Open a connection with row dictionaries enabled."""
    connection = sqlite3.connect(self.path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
```

**Protocol classes**: Use `from typing import Protocol` for dependency injection interfaces. All methods in a protocol use `...` (ellipsis) as the body.

```python
# ✅ DO
class SourceRetriever(Protocol):
    """Protocol implemented by source-specific retrievers."""

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Return normalized memory candidates for one source."""
        ...
```

### 3.7 Error Handling

**Principle**: Catch specific exceptions. Log-and-continue for non-critical paths (memory updates, optional features). Let critical errors propagate.

```python
# ✅ DO — specific exception, graceful fallback
try:
    response = self.model.chat(...)
except OpenAIError as error:
    errors.append(str(error))
    response = f"Model error: {error}"

# ✅ DO — fallback for optional LLM reranker
try:
    payload = parse_llm_reranker_response(self.model.chat(...))
except Exception as error:
    result = fallback_result(
        mode=self.mode,
        deterministic=deterministic,
        reason=f"{type(error).__name__}: {error}",
    )
```

```python
# ❌ DON'T — bare except
try:
    do_something()
except:
    pass
```

**Exception re-raising**: Use `raise ... from exc` for exception chaining.

```python
# ✅ DO
try:
    self._persist_long_term_records(...)
except Exception as exc:
    raise RuntimeError(
        f"failed to persist long-term memory:{exc.__class__.__name__}"
    ) from exc
```

**Error messages**: Use `{type(error).__name__}` to capture exception class names in fallback metadata.

### 3.8 Comments and Tracing

**Inline comments**: Rare. Prefer descriptive variable names and docstrings. Use inline comments only for non-obvious logic.

**Block comments**: Used for logical section separators.

```python
# ✅ DO
# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------
RAW_MESSAGE_LIMIT = 8
```

**Tracing/comments about future work**:

```python
# ✅ DO
# Backward-compatible aliases. Prefer current_chat_gist and
# previous_chat_gist for new gist-based memory code.

# Memory updates should not break the visible chat response. The next
# successful turn can retry because messages remain unprocessed.
```

**TODO/FIXME**: Not observed in the codebase. Prefer tracking issues externally.

**Logging**: Use `logging.getLogger(__name__)` for warnings.

```python
# ✅ DO
import logging
logger = logging.getLogger(__name__)

logger.warning(
    "structured memory update rejected chat_id=%s ...",
    chat_id, ...
)
```

**Console tracing**: Use `print()` with structured key=value formatting for debug/timing output. No other print statements should exist.

```python
# ✅ DO
print(
    "workflow_trace "
    f"trace_id={trace.trace_id} "
    f"chat_id={trace.chat_id} "
    f"intent={route_intent} "
)
```

### 3.9 String Formatting

**Rule**: f-strings always. No `.format()`, no `%`-formatting.

```python
# ✅ DO
f"trace_id={trace.trace_id} "
f"fallback_reason={fallback_reason!r} "
f"mode={mode!r} falling_back_to='langchain_chroma'"

# Inside SQL with placeholders:
f"UPDATE messages SET summarized = 1 WHERE id IN ({placeholders})"
```

```python
# ❌ DON'T
"trace_id={}".format(trace.trace_id)
"trace_id=%s" % trace.trace_id
```

The `!r` conversion flag is used when embedding string values in log-style output to preserve quotes and escape sequences.

### 3.10 Asynchronicity

**Rule**: All core business logic in `src/` is **synchronous**. Async is used only in the Chainlit adapter layer (`src/chainlit_data_layer.py`) because Chainlit's `BaseDataLayer` interface requires `async def`.

```python
# ✅ DO — Chainlit data layer (only async in codebase)
async def get_user(self, identifier: str) -> PersistedUser | None:
    return persisted_user(identifier)

# ✅ DO — all business logic
def route(self, query: str) -> RoutingDecision:
    """Return a structured routing decision for a user query."""
    ...
```

```python
# ❌ DON'T — async in src/ business logic
async def route(self, query: str) -> RoutingDecision:
    ...
```

### 3.11 Line Length

**Rule**: 100 characters maximum (enforced by ruff).

The codebase frequently uses parenthesized line continuations and intermediate variables to stay within the limit.

```python
# ✅ DO
confidence = float(payload.get("confidence", 0.0))
if confidence < self.min_confidence:
    return self._rule_decision(
        query=query,
        routing_mode=self.mode,
        fallback_reason="low_confidence",
    )

# ✅ DO — wrapping long assignments
memory_update_batch_size=int(
    os.getenv(
        "MEMORY_UPDATE_BATCH_SIZE",
        os.getenv("SUMMARY_BATCH_SIZE", str(MEMORY_UPDATE_BATCH_SIZE)),
    )
)
```

### 3.12 Testing Patterns

**Framework**: pytest. Plain functions, no `unittest.TestCase`.

```python
# ✅ DO
def test_route_planner_profiles_and_sources() -> None:
    planner = RoutePlanner()
    general = planner.plan("How do Python dictionaries work?")
    assert general.intent == "general_question"
```

**Test file naming**: `test_<module>.py`, matching the source module name.

**Test double patterns**:
- `Fake*` — returns canned responses (e.g., `FakeModel`, `FakeRoutingModel`)
- `Spy*` — records calls for assertion (e.g., `SpyRetriever`)
- Test doubles defined in the test file, not in fixtures

```python
# ✅ DO — test double defined in test file
class FakeRoutingModel:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[list[dict[str, str]]] = []

    def chat(self, messages, temperature=None) -> str:
        self.calls.append(messages)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response
```

**Test function signatures**: Always annotate return type as `-> None`.

**Fixtures**: Test data lives in `tests/fixtures/` directory (currently only `docs/` subdirectory).

**Markers**: No custom pytest markers observed. Use standard pytest.

**Assertions**: Use plain `assert`, no `self.assert*` methods. Prefer descriptive assertion messages for complex checks.

```python
# ✅ DO
assert decision.use_document_memory is case.use_document_memory, case.name
assert trace["intent"] == case.expected_intent, case.name
```

---

## 4. Common Patterns

### 4.1 Config Dataclass

```python
@dataclass(frozen=True)
class AppConfig:
    """Runtime configuration loaded from environment variables."""

    openai_api_key: str
    openai_base_url: str
    model_name: str
    database_path: Path
    raw_message_limit: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load local .env values and fall back to defaults."""
        load_dotenv()
        return cls(
            openai_api_key=os.getenv("OPENAI_API_KEY", "dummy"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1"),
            model_name=os.getenv("MODEL_NAME", "google/gemma-4-31B-it"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/chatbot.db")),
            raw_message_limit=int(os.getenv("RAW_MESSAGE_LIMIT", "8")),
        )
```

### 4.2 Policy Dataclass

Policy objects centralize configuration knobs in one place. Always `frozen=True`. Use tuples for immutable sequences of strings. Use `field(default_factory=...)` for mutable defaults.

```python
@dataclass(frozen=True)
class QueryAnalyzerPolicy:
    """Centralized lexical policy for the current lightweight analyzer."""

    current_chat_terms: tuple[str, ...] = (
        "this chat",
        "this conversation",
        "earlier",
    )
    document_terms: tuple[str, ...] = (
        "document",
        "pdf",
        "file",
        "upload",
    )

@dataclass(frozen=True)
class AllocationProfile:
    """Relative token allocation ratios for one context profile."""
    system: float
    recent_messages: float
    structured_memory: float
    safety_margin: float
    answer_reserve: float
```

### 4.3 Service Class with Dependency Injection

Default constructed collaborators with optional injection for testing.

```python
class MemoryReranker:
    """Query-aware deterministic reranker with optional LLM reranking."""

    def __init__(
        self,
        policy: RerankerPolicy | None = None,
        mode: str = "deterministic",
        model: RerankerModel | None = None,
        llm_top_k: int = DEFAULT_LLM_TOP_K,
    ) -> None:
        self.policy = policy or RerankerPolicy()
        self.mode = normalize_reranker_mode(mode)
        self.model = model
        self.llm_top_k = max(1, llm_top_k)

    def rank_with_trace(
        self,
        candidates: list[MemoryCandidate],
        ranking_profile: str | None,
        query: str | None = None,
    ) -> RerankResult:
        """Rank candidates and return trace metadata."""
        ...
```

### 4.4 Agent Pattern

Agents are thin wrappers around service objects. The `CoordinatorAgent` orchestrates the pipeline. Other agents are responsibility wrappers.

```python
class ChatAgent:
    """Thin chat-model agent around the existing OpenAI-compatible wrapper."""

    def __init__(self, model: ModelWrapper) -> None:
        self.model = model

    def generate(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Generate an assistant response from model-ready messages."""
        return self.model.chat(messages, temperature=temperature)
```

### 4.5 Protocol for Dependency Injection

```python
from typing import Protocol

class RoutingModel(Protocol):
    """Minimal chat-model protocol used by optional LLM routing."""

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
    ) -> str:
        """Return a chat completion as text."""
        ...

class SourceRetriever(Protocol):
    """Protocol implemented by source-specific retrievers."""

    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Return normalized memory candidates for one source."""
        ...
```

### 4.6 Enum-like Constants

Use module-level `UPPER_CASE` tuples/sets of strings, not `enum.Enum`.

```python
# ✅ DO
MEMORY_CATEGORIES = {
    "user_facts", "project_facts", "decisions", "corrections",
    "open_tasks", "preferences", "constraints", "procedural",
}

ROUTING_MODES = {"rule", "llm", "hybrid"}
RERANKER_MODES = {"deterministic", "hybrid", "llm"}
```

### 4.7 Result Dataclass Pattern

Return structured result objects, not tuples.

```python
@dataclass(frozen=True)
class RerankResult:
    """Ranked candidates and explainable reranker trace metadata."""

    candidates: list[MemoryCandidate]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class RoutingDecision:
    """Agent-shaped routing output for one user query."""

    route_plan: RoutePlan
    use_recent_messages: bool
    use_structured_memory: bool
    use_document_memory: bool
    reason: str
    confidence: float
    fallback_mode: bool = False
```

### 4.8 Helper Function Pattern

Pure functions at module level for reusable logic. These stay close to the class that uses them.

```python
def normalize_query(query: str) -> str:
    """Normalize whitespace and case for lightweight signal detection."""
    return re.sub(r"\s+", " ", query.strip().lower())


def contains_any(query: str, terms: tuple[str, ...]) -> bool:
    """Return whether any configured term appears in the query."""
    return any(term in query for term in terms)


def clamp(value: float) -> float:
    """Clamp a score feature to [0, 1]."""
    return max(0.0, min(1.0, value))
```

---

## 5. Linter Configuration

### Current pyproject.toml Settings

```toml
[tool.ruff]
line-length = 100
target-version = "py310"
```

### Rationale

- **line-length = 100**: Matches the codebase's actual style. Most lines wrap at 80-100 characters with parenthesized continuations. The codebase already respects this.
- **target-version = "py310"**: The `.python-version` file says 3.12, but the `pyproject.toml` `requires-python = ">=3.10"`. Targeting 3.10 ensures compatibility. The `from __future__ import annotations` pattern supports this.

### Recommended Ruff Rules (to add to pyproject.toml)

```toml
[tool.ruff.lint]
select = [
    "E",   # pycodestyle errors
    "F",   # pyflakes
    "I",   # isort (import order)
    "N",   # pep8-naming
    "UP",  # pyupgrade (modernize syntax)
    "B",   # flake8-bugbear
    "C4",  # flake8-comprehensions
    "SIM", # flake8-simplify
    "TCH", # flake8-type-checking
    "RUF", # ruff-specific
]
ignore = [
    "E501",  # line-too-long (handled by formatter)
    "B008",  # do-not-perform-function-calls-in-argument-defaults (dataclass fields use field())
]

[tool.ruff.lint.isort]
known-first-party = ["src"]
force-sort-within-sections = true

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### Notes on Ruff Rules

- **I (isort)**: Most imports in the codebase are already well-ordered into stdlib → third-party → local groups. Ruff can auto-fix.
- **UP (pyupgrade)**: The codebase already uses PEP 604 union syntax; UP will catch missed cases.
- **N (pep8-naming)**: Most naming follows the conventions described above. Will catch snake_case violations.
- **SIM (simplify)**: Will flag patterns like `if bool(x): return True else: return False` → `return bool(x)`.

---

## 6. Edge Cases & Gotchas

### 6.1 `field(default_factory=...)` Required for Mutable Defaults

**Gotcha**: Using `[]` or `{}` as a dataclass field default is a Python anti-pattern (shared mutable state). Always use `field(default_factory=list)` or `field(default_factory=dict)`.

```python
# ✅ DO
@dataclass(frozen=True)
class ContextPacket:
    candidates: list[MemoryCandidate] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

# ❌ DON'T — SHARED MUTABLE DEFAULT (BUG!)
@dataclass(frozen=True)
class ContextPacket:
    candidates: list[MemoryCandidate] = []  # All instances share this list
    metadata: dict[str, Any] = {}           # All instances share this dict
```

### 6.2 `from __future__ import annotations` Required

**Gotcha**: Without this, forward references like `"AppConfig"` in `-> "AppConfig"` won't work in 3.10, and PEP 604 union syntax may cause runtime errors in 3.10. Always include it as the first import.

### 6.3 `object.__setattr__` in Frozen Dataclasses

**Gotcha**: To set attributes in `__post_init__` of a frozen dataclass, you must use `object.__setattr__(self, name, value)`. Regular `self.name = value` will raise `FrozenInstanceError`.

```python
# ✅ DO
def __post_init__(self) -> None:
    if self.intent_context_profiles is None:
        object.__setattr__(
            self,
            "intent_context_profiles",
            {"general_question": "general_chat"},
        )
```

### 6.4 `replace()` Instead of Mutation

**Gotcha**: Dataclasses are frozen — never mutate. Use `dataclasses.replace()` to create a modified copy.

```python
# ✅ DO
from dataclasses import replace

return replace(candidate, score=final_score, metadata=new_metadata)

# ❌ DON'T
candidate.score = final_score  # FrozenInstanceError
```

### 6.5 `dict()` Copy for Metadata

**Gotcha**: When you need to modify a candidate's metadata, always copy it first with `dict(candidate.metadata)` then update. Never mutate the original.

```python
# ✅ DO
metadata = dict(candidate.metadata)
metadata.update({"ranking_profile": "default"})
return replace(candidate, metadata=metadata)
```

### 6.6 Return Type on `__init__` 

**Gotcha**: Unlike most methods, `__init__` must have `-> None` return annotation.

```python
# ✅ DO
def __init__(self, path: Path) -> None:
    ...

# ❌ DON'T
def __init__(self, path: Path):
    ...
```

### 6.7 `isinstance(value, int | float)` vs `isinstance(value, (int, float))`

**Gotcha**: In Python 3.10+, `isinstance(value, int | float)` works because `int | float` evaluates to `Union[int, float]` at runtime. However, for safety with non-annotation contexts, `isinstance(value, (int, float))` is more explicit. The codebase uses both patterns — both are acceptable.

```python
# Both are fine — the codebase uses both
if isinstance(value, int | float):
    return clamp(float(value))

if isinstance(value, (int, float)):
    return clamp(float(value))
```

### 6.8 `...` in Protocol Methods

**Gotcha**: Protocol method bodies must use `...` (ellipsis), not `pass`. This is a type-checker signal that the method is intentionally abstract.

```python
# ✅ DO
class SourceRetriever(Protocol):
    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        """Return normalized memory candidates."""
        ...

# ❌ DON'T
class SourceRetriever(Protocol):
    def retrieve(self, chat_id: str, source_plan: SourcePlan) -> list[MemoryCandidate]:
        pass  # Type checkers may complain
```

### 6.9 Unused Parameters: `del` Convention

**Gotcha**: When a parameter is required by an interface but not used, the codebase uses `del param_name` at the top of the method body to signal intention.

```python
# ✅ DO
def build_context(
    self,
    chat_id: str,
    latest_user_message_id: int | None = None,
    token_budget: int | None = None,
) -> ShortTermContext:
    """token_budget is accepted as a future extension point."""
    del token_budget  # Accepted but unused in current MVP
    ...
```

### 6.10 SQL with f-string Placeholders

**Gotcha**: When constructing SQL with variable-length parameter lists, use f-strings for the placeholder count but still use parameterized queries. Never interpolate user data directly into SQL.

```python
# ✅ DO — f-string for placeholder count, parameterized for safety
placeholders = ",".join("?" for _ in message_ids)
connection.execute(
    f"UPDATE messages SET summarized = 1 WHERE id IN ({placeholders})",
    message_ids,
)

# ❌ DON'T — SQL injection risk
connection.execute(
    f"UPDATE messages SET summarized = 1 WHERE id IN ({','.join(map(str, ids))})",
)
```

### 6.11 Print vs Logger

**Gotcha**: The codebase uses `print()` for structured trace output (key=value) and `logging.getLogger(__name__)` for warnings/errors. Do not mix them. Trace/debug → `print()`. Warnings → `logger.warning()`. Critical errors → let them propagate.

---

## Appendix A: Python Version Policy

- **pyproject.toml**: `requires-python = ">=3.10"`
- **.python-version**: `3.12` (development runtime)
- **ruff target-version**: `py310`
- **Rationale**: Code targets 3.10+ compatibility with `from __future__ import annotations` for forward references and PEP 604 unions. Development runs on 3.12 for performance and tool support.

## Appendix B: File Organization

```
src/
├── __init__.py          # Package docstring only
├── config.py            # AppConfig dataclass + env_bool helper
├── database.py          # Database class + stored row dataclasses
├── model_wrapper.py     # ModelWrapper (OpenAI-compatible client)
├── chat_service.py      # ChatService (top-level coordinator)
├── chainlit_data_layer.py  # Chainlit async adapter
├── core/
│   ├── __init__.py      # Package docstring
│   └── contracts.py     # Core dataclasses (MemoryCandidate, RoutePlan, etc.)
├── agents/
│   ├── __init__.py
│   ├── chat_agent.py
│   ├── context_builder_agent.py
│   ├── context_manager_agent.py
│   ├── coordinator_agent.py
│   ├── document_ingestion_agent.py
│   └── short_term_memory_agent.py
├── routing/
│   ├── __init__.py
│   ├── query_analyzer.py
│   ├── route_planner.py
│   └── routing_agent.py
├── retrieval/
│   ├── __init__.py
│   ├── reranker.py
│   ├── retriever_dispatcher.py
│   ├── structured_memory_retriever.py
│   ├── recent_messages_retriever.py
│   ├── current_chat_gist_retriever.py
│   ├── previous_chat_gist_retriever.py
│   ├── raw_message_span_retriever.py
│   └── langchain_chroma_retriever.py
├── context/
│   ├── __init__.py
│   ├── context_budget_allocator.py
│   ├── context_builder.py
│   ├── context_comparator.py
│   ├── prompt_messages.py
│   └── token_estimator.py
├── memory/
│   ├── __init__.py
│   ├── constants.py
│   ├── short_term.py
│   ├── langmem_structured.py
│   ├── structured_state.py
│   ├── long_term_store.py
│   ├── long_term_vector_index.py
│   ├── previous_chat_gist.py
│   └── memory_trace.py
└── documents/
    └── __init__.py
```

---

*Generated from comprehensive codebase analysis. Last updated: 2026-06-28.*
