# Short Evaluation Note: RAG and Memory Benchmarks

## 1. Current Benchmark Status

So far, we have mainly benchmarked the **document-memory retriever**, not the full chatbot.

The current document-memory backend is **LangChain-Chroma**. The existing evaluation checks whether it can retrieve answer-bearing chunks from indexed documents:

```text
document question
  -> LangChain-Chroma retrieval
  -> top-k document chunks
  -> deterministic check for answer/evidence in retrieved chunks
```

We used three local document QA datasets:

```text
10-case hand-written SQuAD-style sample      -> smoke test only
200-case SQuAD validation subset             -> span-QA retrieval benchmark
200-case Natural Questions-style subset      -> more user-like QA benchmark
```

The current metrics are retrieval hit-rate metrics:

```text
hit@1
hit@3
hit@5
hit@10
```

If the answer-bearing chunk appears in the top-k retrieved chunks, retrieval is counted as a hit.

Approximate local results:

```text
SQuAD 200-case validation subset:
  hit@1  ~= 0.72
  hit@3  ~= 0.96
  hit@5  ~= 1.00
  hit@10 ~= 1.00

Natural Questions-style 200-case subset:
  ctx_anchor hit@1   ~= 0.95
  ctx_anchor hit@3   ~= 0.99
  ctx_evidence hit@1 ~= 0.92
  ctx_evidence hit@3 ~= 0.96
```

These results validate the **document retrieval backend** as a sanity check. They do not yet evaluate final answer quality or the whole memory-augmented chatbot.

## 2. Next RAG Benchmark: Generated-Answer Evaluation

The next RAG evaluation layer should test whether the assistant actually uses retrieved chunks correctly.

For each case:

```text
question
retrieved chunks
generated answer
expected answer / evidence
```

Potential metrics:

```text
faithfulness
answer relevancy
context precision
context recall
unsupported-claim rate
```

This is where **RAGAS** or **ARES-style** evaluation fits.

## 3. RAGAS / ARES Fit

RAGAS and ARES evaluate RAG quality across retrieval and generation dimensions.

For this project, the mapping is:

```text
question      -> dataset question
contexts      -> retrieved document chunks / MemoryCandidate contents
answer        -> generated assistant answer
ground_truth  -> expected answer
metadata      -> retrieval mode, top-k, source, file/chunk IDs
```

Most RAGAS-style metrics use an evaluator LLM, especially faithfulness and answer relevancy. Therefore, they should complement, not replace, deterministic hit@k metrics.

Recommended RAG evaluation stack:

```text
Level 1: deterministic retrieval hit@k
Level 2: deterministic generated-answer checks
Level 3: RAGAS / ARES-style LLM-judge metrics
```

## 4. Why RAG Evaluation Is Not Enough

The project is not only document RAG. It is a memory-augmented chatbot with multiple memory sources:

```text
recent_messages
structured long-term memory
document_memory
future current/previous-chat gists
future raw-message spans
```

Therefore, we also need memory-system benchmarks.

## 5. Long-Term Memory Benchmarks

### LoCoMo

**LoCoMo** evaluates very long-term conversations across many sessions. It focuses on whether models can remember and reason over long dialogue histories.

Relevant tasks:

```text
long conversation question answering
event summarization
multi-session dialogue generation
```

Fit for this project:

```text
Good future benchmark for previous-chat gists and raw-message-span retrieval.
Less urgent for the current demo because it is heavier and conversation-history focused.
```

### LongMemEval

**LongMemEval** is closer to our current system. It evaluates long-term memory abilities for chat assistants.

Core abilities:

```text
information extraction
multi-session reasoning
temporal reasoning
knowledge updates
abstention
```

Fit for this project:

```text
information extraction  -> LangMem writes structured memories
multi-session reasoning -> Chat 2 retrieves memory from Chat 1
knowledge updates       -> corrected preferences replace old memories
abstention              -> assistant avoids inventing missing memory
```

LongMemEval-style evaluation is the best next benchmark direction for structured long-term memory.

### PerLTQA

**PerLTQA** (Du et al., 2024) is a personal long-term memory QA benchmark. It combines semantic and episodic memories, including world knowledge, profiles, social relationships, events, and dialogues.

It evaluates three relevant steps:

```text
memory classification
memory retrieval
memory synthesis for question answering
```

Fit for this project:

```text
memory classification -> decide which source/type of memory is needed
memory retrieval       -> retrieve structured memory, document chunks, or future gists
memory synthesis       -> generate an answer using retrieved memory
```

PerLTQA is useful as a conceptual benchmark for personalized memory QA, especially once the system needs to combine structured semantic memory with episodic chat history.

## 6. Proposed Benchmark Suites

### Suite A: Document RAG Retrieval

Already partly implemented.

Evaluate:

```text
ctx_anchor hit@k
ctx_expected hit@k
ctx_evidence hit@k
```

Purpose:

```text
Does document_memory retrieve the right chunks?
```

### Suite B: Document RAG Answer Quality

Next RAG step.

Evaluate:

```text
answer correctness
faithfulness
answer relevancy
context precision
context recall
unsupported claims
```

Potential tool:

```text
RAGAS or ARES-style LLM judge
```

Purpose:

```text
Does the assistant use retrieved document chunks correctly?
```

### Suite C: Structured Memory Cross-Chat Evaluation

Best next memory-system benchmark.

Example:

```text
Chat 1:
User states a durable preference.

Chat 2:
User asks a question requiring that preference.
```

Evaluate:

```text
memory_write_success
memory_retrieval_hit
answer_uses_memory
```

Purpose:

```text
Does structured long-term memory work across chats?
```

### Suite D: Whole Memory Lifecycle Evaluation

Future broader benchmark.

Evaluate:

```text
ADD accuracy
NOOP accuracy
UPDATE / correction accuracy
retrieval accuracy
source selection accuracy
abstention accuracy
answer faithfulness
```

Purpose:

```text
Does the full memory system write, update, retrieve, ignore, and use memories correctly?
```

## 7. Recommended Evaluation Roadmap

```text
1. Keep current document retrieval hit@k benchmark.
2. Add small generated-answer RAG evaluation with RAGAS-compatible rows.
3. Add structured cross-chat memory benchmark inspired by LongMemEval.
4. Add lifecycle cases: ADD, NOOP, UPDATE, RETRIEVE, ABSTAIN.
5. Add PerLTQA-style personalized memory QA cases for classification, retrieval, and synthesis.
6. Consider LoCoMo-style long conversation evaluation later, when gists/raw spans are implemented.
```

## 8. Main Takeaway

The current benchmark validates the **document retriever**. The next step is to evaluate whether the assistant uses retrieved context and long-term memory correctly.

The strongest benchmark plan for this project is:

```text
document retrieval hit@k
+ RAGAS/ARES-style generated-answer evaluation
+ LongMemEval-inspired structured memory evaluation
+ PerLTQA-style personalized memory QA evaluation
+ later LoCoMo-style long-conversation evaluation
```

Reference: Du et al. (2024), *PerLTQA: A Personal Long-Term Memory Dataset for Memory Classification, Retrieval, and Synthesis in Question Answering*.
