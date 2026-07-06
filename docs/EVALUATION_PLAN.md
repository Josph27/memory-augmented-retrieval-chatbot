docs/EVALUATION_PLAN.md
Evaluation Plan
1. Evaluation Goal

The project is not only a document RAG system.

It is a memory-augmented chatbot with multiple memory sources:

recent_messages
structured_memory
document_memory
current_chat_gist (default-off scaffold)
previous_chat_gist
current_chat_span
raw_message_span

Therefore, evaluation should distinguish:

document retrieval
generated-answer document RAG quality
structured cross-chat memory
memory lifecycle behavior
whole-system answer faithfulness
2. Current Benchmark Status

The current implemented benchmark mainly evaluates the document-memory retriever.

Current flow:

document question
-> LangChain-Chroma retrieval
-> top-k document chunks
-> deterministic check for answer/evidence in retrieved chunks

Current datasets:

10-case hand-written SQuAD-style sample
200-case SQuAD validation subset
200-case Natural Questions-style subset

Current metrics:

hit@1
hit@3
hit@5
hit@10

This validates whether the document retriever can retrieve answer-bearing chunks.

Current document QA tooling also supports:

oracle answer mode
model-generated answer mode
RAGAS-compatible JSONL export
optional run_ragas_eval.py

The deterministic retrieval metrics remain the primary reliable signal. Model
answer mode and RAGAS-style evaluation depend on model/evaluator availability
and should be reported separately.

Additional implemented suites include:

structured-memory lifecycle mock/oracle evaluation
multi-source retrieval/source-selection evaluation
generated-answer controlled evaluation
E2E controlled scenarios
LongMemEval pilot adapter with message-span representation
production-style retrieval-to-ContextPacket acceptance tests

These do not fully evaluate:

final answer quality
answer faithfulness
source selection
structured memory correctness
memory update correctness
abstention behavior
3. Suite A — Document Retrieval
Status

Implemented.

Purpose

Evaluate whether document_memory retrieves the correct chunks.

Metrics
ctx_anchor hit@k
ctx_expected hit@k
ctx_evidence hit@k
Report As

This benchmark validates the document retrieval backend, not the whole chatbot.

4. Suite B — Document Answer Quality
Status

Partially implemented. Document QA eval has oracle/model answer modes and
RAGAS-compatible export, but the project does not yet have a stable required
RAGAS/evaluator-LLM pipeline.

Purpose

Evaluate whether the assistant actually uses retrieved document chunks correctly.

Data Per Case
question
retrieved chunks
generated answer
expected answer
evidence
metadata
Possible Metrics
answer correctness
faithfulness
answer relevancy
context precision
context recall
unsupported-claim rate
Implementation Options

Start with deterministic checks:

expected answer string appears in generated answer
generated answer overlaps with expected evidence
unsupported claims manually or LLM-judge flagged

Future-compatible tools:

RAGAS
ARES-style evaluation
Important Note

RAGAS/ARES-style metrics may require evaluator LLMs, so they should complement deterministic metrics rather than replace them.

5. Suite C — Structured Cross-Chat Memory
Status

Implemented as a small deterministic mock/oracle benchmark in
`evals/structured_memory`. Cross-chat memory also has tests/verifier scripts.
The benchmark exercises SQLite `long_term_memories` and
`StructuredMemoryRetriever` without live model calls.

Purpose

Evaluate whether structured long-term memory works across chats.

Example Case
Chat 1:
User states: I prefer mature open-source libraries over custom infrastructure.

System:
MemoryManagerAgent / LangMem extracts durable memory.

Chat 2:
User asks: Should I build my own vector store for this project?

Expected:
Assistant retrieves the stored preference and recommends using mature existing libraries unless there is a project-specific reason not to.
Metrics
memory_write_success
memory_retrieval_hit
answer_uses_memory
answer_consistency
Why Important

This directly evaluates the main memory-augmented chatbot feature.

6. Suite D — Memory Lifecycle Mini Benchmark
Status

Implemented as a small deterministic mock/oracle benchmark in
`evals/structured_memory/datasets/lifecycle_sample.jsonl`.

Purpose

Evaluate whether the memory system writes, ignores, updates, retrieves, and abstains correctly.

Cases
ADD:
User states a durable preference or project constraint.

NOOP:
User says temporary or irrelevant information.

UPDATE:
User corrects or changes a previous preference.

RETRIEVE:
User asks a question requiring stored memory.

ABSTAIN:
User asks about something never stored.
Metrics
write_action_correct
noop_correct
update_correct
retrieval_hit
answer_uses_correct_memory
answer_avoids_false_memory
Current Scale

The current local sample covers the five core lifecycle actions once each. A
larger 15–30 case set remains useful for stronger reporting before the final
deadline.

7. Suite E — Source Selection Evaluation
Status

Implemented as a controlled deterministic suite in
`evals/multi_source_retrieval`. Current routing is still mostly
rule/keyword-based. Some cases use fixture route plans or fake retrievers, so
this suite validates source contracts and metrics more strongly than production
routing quality.

Purpose

Evaluate whether the router selects the correct memory source.

Example Labels
recent_messages
structured_memory
document_memory
recent + structured
structured + document
none / abstain
Metrics
source_selection_accuracy
false_positive_source_rate
false_negative_source_rate
8. External Benchmark References
RAGAS / ARES

Useful for evaluating generated-answer RAG quality:

faithfulness
answer relevancy
context precision
context recall

Use as future-compatible evaluation direction or small optional experiment.

LongMemEval

Useful for long-term memory abilities:

information extraction
multi-session reasoning
temporal reasoning
knowledge updates
abstention

This is the best conceptual fit for structured long-term memory. The repository
contains an unofficial adapter and tiny fixture. Fixture mode validates adapter
wiring; it is not official leaderboard evidence. Meaningful claims require a
saved run over an external dataset subset with a configured answer model.

PerLTQA

Useful for personalized long-term memory QA:

memory classification
memory retrieval
memory synthesis

This maps well to:

RoutingAgent -> memory classification / source selection
retrievers -> memory retrieval
AnswerAgent -> memory synthesis
LoCoMo

Useful for very long conversational memory and multi-session dialogue.

Best suited for episodic gist and raw-message-span work.

9. Recommended Evaluation Roadmap

Current next steps:

1. Keep and report document hit@k outputs.
2. Run real-model end-to-end recall scenarios using production routing.
3. Inspect WorkflowTrace and ContextPacket evidence manually.
4. Stress-test vector/hybrid structured recall against real Chroma.
5. Add model-grounded citation/provenance checks.
6. Save larger external LongMemEval pilot reports before making benchmark claims.
10. Main Evaluation Claim

The current evaluation should be presented honestly:

We evaluate document retrieval with deterministic hit@k metrics and use
controlled suites for structured memory, lifecycle, source selection,
generated answers, and integration wiring. Production-style acceptance tests
show that selected memory sources can reach `ContextPacket`. Mock answer modes
do not prove live-model grounding, and the LongMemEval adapter is unofficial
wiring/pilot infrastructure rather than leaderboard evidence.

Latest repository verification after the memory correctness work:

```text
290 passed, 1 skipped
compileall passed
Ruff passed
git diff --check passed
```
