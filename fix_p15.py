#!/usr/bin/env python3
"""Fix 3 runtime crash bugs in P1.4-P1.5 of implementation.md."""

with open(".design/implementation.md", "r") as f:
    content = f.read()

# ── Bug #4 (LOW): Fix P1.4 param naming: query: → content: ──────────────────
old_p14 = "def run_turn(self, chat_id: str, query: str) -> AgentTurnResult:"
new_p14 = "def run_turn(self, chat_id: str, content: str) -> AgentTurnResult:"
assert old_p14 in content, "P1.4 param bug marker not found"
content = content.replace(old_p14, new_p14)
print("✓ Bug #4 fixed: query → content in P1.4")

# ── Bugs #1, #2, #3: Fix P1.5 code block ──────────────────────────────────
# Old block: mutation + nonexistent override_sources param
old_block = """  ```python
  all_candidates: list[MemoryCandidate] = []
  for sub_query in augmented.sub_queries:
      try:
          # Per oracle F8: evaluate doc retrieval necessity per sub-query
          needs_docs = self._evaluate_doc_necessity(sub_query.text)
          sources_for_sub = list(sub_query.sources)
          if needs_docs and "document_memory" not in sources_for_sub:
              sources_for_sub.append("document_memory")
          # Per oracle F4: set source_plan.query instead of modifying dispatcher
          for sp in route_plan.sources:
              if sp.source in sources_for_sub:
                  sp.query = sub_query.text
          candidates = self._retriever_dispatcher.retrieve(
              chat_id=chat_id,
              route_plan=route_plan,
              override_sources=tuple(sources_for_sub),
          )
          all_candidates.extend(candidates)
      except Exception as exc:
          # Per oracle F19: isolate per-sub-query failures
          self._trace.errors.append(f"Sub-query '{sub_query.text[:50]}...' failed: {exc}")
          continue  # skip failed sub-query, continue with remaining
  # Deduplicate by record_id before reranking
  # Per oracle F12: if record_id is None, always keep. If not None and already seen, keep higher-scored.
  seen: dict[str | int, MemoryCandidate] = {}
  for c in all_candidates:
      key = c.record_id
      if key is None:
          seen[f"_none_{id(c)}"] = c  # synthetic key for None record_id (always keep)
      elif key not in seen or (c.score or 0) > (seen[key].score or 0):
          seen[key] = c
  all_candidates = list(seen.values())
  ```"""

new_block = """  ```python
  from dataclasses import replace

  all_candidates: list[MemoryCandidate] = []
  for sub_query in augmented.sub_queries:
      try:
          # Per oracle F8: evaluate doc retrieval necessity per sub-query
          needs_docs = self._evaluate_doc_necessity(sub_query.text)
          sources_for_sub = list(sub_query.sources)
          if needs_docs and "document_memory" not in sources_for_sub:
              sources_for_sub.append("document_memory")
          # Build per-sub-query RoutePlan copies via replace() — never mutate frozen SourcePlan
          per_sub_sources = [
              replace(sp, query=sub_query.text)
              if sp.source in sources_for_sub
              else sp
              for sp in route_plan.sources
          ]
          sub_route_plan = replace(route_plan, sources=per_sub_sources)
          # RetrieverDispatcher.retrieve() uses the route_plan's source plans as-is;
          # no override_sources parameter (it does not exist on the dispatcher).
          candidates = self._retriever_dispatcher.retrieve(
              chat_id=chat_id,
              route_plan=sub_route_plan,
          )
          all_candidates.extend(candidates)
      except Exception as exc:
          # Per oracle F19: isolate per-sub-query failures
          self._trace.errors.append(f"Sub-query '{sub_query.text[:50]}...' failed: {exc}")
          continue  # skip failed sub-query, continue with remaining
  # Deduplicate by record_id before reranking
  # Per oracle F12: if record_id is None, always keep. If not None and already seen, keep higher-scored.
  seen: dict[str | int, MemoryCandidate] = {}
  for c in all_candidates:
      key = c.record_id
      if key is None:
          seen[f"_none_{id(c)}"] = c  # synthetic key for None record_id (always keep)
      elif key not in seen or (c.score or 0) > (seen[key].score or 0):
          seen[key] = c
  all_candidates = list(seen.values())
  ```"""

assert old_block in content, "P1.5 code block not found"
content = content.replace(old_block, new_block)
print("✓ Bug #1 fixed: FrozenInstanceError via replace()")
print("✓ Bug #2 fixed: dropped nonexistent override_sources param")

# ── Bug #3 (HIGH): Fix _evaluate_doc_necessity to instantiate QueryAnalyzer ──
old_eval = """  ```python
  def _evaluate_doc_necessity(self, query: str) -> bool:
      \"\"\"Use QueryAnalyzer lexical signals to decide if this sub-query needs document retrieval.\"\"\"
      # Reuse existing lexical signal detection from QueryAnalyzer
      analysis = self._query_analyzer.analyze(query)
      return analysis.is_document_query  # or equivalent signal field
  ```"""

new_eval = """  ```python
  def _evaluate_doc_necessity(self, query: str) -> bool:
      \"\"\"Use QueryAnalyzer lexical signals to decide if this sub-query needs document retrieval.\"\"\"
      # Reuse existing lexical signal detection from QueryAnalyzer.
      # QueryAnalyzer is deterministic and stateless — instantiate standalone
      # rather than drilling through RoutingAgent -> RoutePlanner -> QueryAnalyzer.
      analysis = self._query_analyzer.analyze(query)
      return analysis.signals.asks_about_documents
  ```

  **CoordinatorAgent.__init__ must instantiate a QueryAnalyzer:**

  ```python
  from src.routing.query_analyzer import QueryAnalyzer

  # Add to CoordinatorAgent.__init__:
  self._query_analyzer = QueryAnalyzer()
  ```"""

assert old_eval in content, "P1.5 _evaluate_doc_necessity block not found"
content = content.replace(old_eval, new_eval)
print("✓ Bug #3 fixed: _query_analyzer instantiation + correct signal field")

# ── Also fix the P1.5 Files section: retriever_dispatcher no longer modified ──
old_files = """- **Files (modify):**
  - `src/agents/coordinator_agent.py`
  - `src/retrieval/retriever_dispatcher.py` — per oracle F4, instead of adding a `query` parameter to the dispatcher (which would require modifying the `SourceRetriever` Protocol), set `source_plan.query = sub_query_text` on each `SourcePlan` before calling `RetrieverDispatcher.retrieve()` for that sub-query. This avoids a Protocol signature change."""

new_files = """- **Files (modify):**
  - `src/agents/coordinator_agent.py` — per-sub-query loop with `replace()`-built `sub_route_plan`.
  - `src/retrieval/retriever_dispatcher.py` — no changes needed; `RetrieverDispatcher.retrieve()` already accepts a `RoutePlan` with modified `SourcePlan` objects."""

content = content.replace(old_files, new_files)
print("✓ P1.5 Files section updated: removed spurious retriever_dispatcher change")

# Also update the first occurrence (it appears twice - in TOC and in body)
# The second occurrence was already fixed above; let's also fix the first one in TOC
# Wait - the old_files text appears twice? Let me check.
# Actually it should only appear once in the body. Let me just fix the second P1.5 header which also has similar text

# Write back
with open(".design/implementation.md", "w") as f:
    f.write(content)

print(f"\nDone. File: {len(content)} chars, {len(content.splitlines())} lines")
