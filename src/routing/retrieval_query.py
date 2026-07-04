from __future__ import annotations

from dataclasses import dataclass
import re

from src.core.contracts import RoutePlan

NEGATION_PATTERN = re.compile(r"\b(?:not|never|without|except|excluding|neither)\b", re.I)
QUOTED_PATTERN = re.compile(r"""["'][^"']+["']""")
OPTION_PATTERN = re.compile(r"(?:^|\n)\s*[A-D][.)]\s+", re.I)
COMPARISON_PATTERN = re.compile(
    r"^who is (?P<relation>older|younger),?\s+"
    r"(?P<left>[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,3})\s+or\s+"
    r"(?P<right>[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,3})\??$",
    re.I,
)
BOILERPLATE_PATTERNS = (
    re.compile(
        r"^\s*based on all (?:the )?information above[,;:\s-]*",
        re.I,
    ),
    re.compile(
        r"^\s*using all (?:the )?(?:information|context) above[,;:\s-]*",
        re.I,
    ),
    re.compile(
        r"^\s*according to all (?:the )?(?:information|context) above[,;:\s-]*",
        re.I,
    ),
)


@dataclass(frozen=True)
class RetrievalQueryRewrite:
    original_query: str
    retrieval_query: str
    applied: bool
    reason: str


def retrieval_query_for_reranking(
    route_plan: RoutePlan,
    *,
    fallback: str,
) -> str:
    """Use the deterministic retrieval query without changing answer input."""
    value = route_plan.metadata.get("retrieval_query")
    return value if isinstance(value, str) and value.strip() else fallback


def simplify_retrieval_query(
    query: str,
    *,
    context_profile: str | None = None,
    enabled: bool = True,
) -> RetrievalQueryRewrite:
    """Return a conservative deterministic query for retrieval only."""
    original = " ".join(query.strip().split())
    if not enabled or not original:
        return RetrievalQueryRewrite(original, original, False, "disabled_or_empty")
    if NEGATION_PATTERN.search(original):
        return RetrievalQueryRewrite(original, original, False, "negation_preserved")
    if QUOTED_PATTERN.search(original):
        return RetrievalQueryRewrite(original, original, False, "quoted_phrase_preserved")
    if OPTION_PATTERN.search(original):
        return RetrievalQueryRewrite(original, original, False, "answer_options_preserved")

    if context_profile == "global_summary":
        lowered = original.lower()
        target = "previous content"
        for label in ("book", "conversation", "story", "novel", "document", "report"):
            if re.search(rf"\b{label}\b", lowered):
                target = label
                break
        return RetrievalQueryRewrite(
            original,
            f"global summary complete {target} chronological content",
            True,
            "global_summary_scope",
        )

    stripped = original
    for pattern in BOILERPLATE_PATTERNS:
        stripped = pattern.sub("", stripped).strip()
    comparison = COMPARISON_PATTERN.fullmatch(stripped)
    if comparison is not None:
        relation = comparison.group("relation").lower()
        return RetrievalQueryRewrite(
            original,
            (
                f"{comparison.group('left')} age born "
                f"{comparison.group('right')} age born {relation}"
            ),
            True,
            "entity_age_comparison",
        )
    if stripped != original and len(stripped.split()) >= 3:
        return RetrievalQueryRewrite(
            original,
            stripped,
            True,
            "leading_boilerplate_removed",
        )
    return RetrievalQueryRewrite(original, original, False, "already_compact")
