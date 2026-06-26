docs/EVALUATION_PLAN.md
Evaluation Plan
1. Evaluation Goal

The project is not only a document RAG system.

It is a memory-augmented chatbot with multiple memory sources:

recent_messages
structured_memory
document_memory
future current_chat_gist
future previous_chat_gist
future raw_message_span

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

It does not fully evaluate:

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

Future / recommended small benchmark.

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
Scale

A small benchmark with 15–30 scripted cases is acceptable before the deadline.

7. Suite E — Source Selection Evaluation
Status

Future / optional. Current routing is QueryAnalyzer + RoutePlanner and is
mostly rule/keyword based.

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

This is the best conceptual fit for structured long-term memory.

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

Best suited for future gist and raw-message-span work.

9. Recommended Evaluation Roadmap

Before deadline:

1. Keep document hit@k benchmark.
2. Save exact document benchmark outputs.
3. Formalize the existing cross-chat verifier into a small structured memory benchmark.
4. Add small lifecycle benchmark.
5. Optionally add generated-answer RAG evaluation.

Future:

1. RAGAS / ARES generated-answer evaluation.
2. LongMemEval-style memory benchmark.
3. PerLTQA-style personalized memory QA benchmark.
4. LoCoMo-style long conversation benchmark.
10. Main Evaluation Claim

The current evaluation should be presented honestly:

We evaluate document retrieval with deterministic hit@k metrics, and we add controlled memory benchmarks for cross-chat structured memory and lifecycle behavior. Full RAGAS, LongMemEval, PerLTQA, and LoCoMo evaluation are future extensions.
