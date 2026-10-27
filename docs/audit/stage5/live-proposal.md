# Deferred live verification proposal — execution not authorized

No live check ran during Stage5. Default isolation refuses live/expensive/manual groups. This proposal requires separate spending approval and an instrumented runner before execution; no credentials need inspection or disclosure.

| Representative check | Synthetic input / dependencies | Completion bound | Output-token bound |
|---|---|---:|---:|
| Wire smoke | One prompt, no routing/extraction/judge |1|64|
| Structured extraction | One fact batch; all internal manager iterations counted |3 total|256 each|
| Grounded document answer | One local document/query; cached embeddings; summaries off; deterministic routing/ranking |1|128|
| Judge only | One frozen answer; repair first tested offline |1|300|

Maximum6 completion requests and1260 output tokens. Health probes separately bounded to2 for the whole batch (do not bill them as completions). Serial execution, SDK retries0, no automatic reruns, overall120s deadline and stop on authentication/rate/timeout errors, unknown usage, unexpected provider/model, or any request/token/budget breach. Extraction must not run unless all internal requests can be counted and stopped. Judge SDK defaults currently have no verified total transport bound; explicitly configure retries/timeouts before this proposal is executable.

Transport instrumentation must record provider/model, request ID, HTTP attempt, elapsed time, status/finish reason and actual input/output/cache tokens, without prompts or credentials. Current string-returning wrappers/stage counts do not supply this enforcement. Check cumulative usage before subsequent calls. Account for routing, reranking, document summaries, manager loops and malformed-judge repair; disable everything outside the six-request plan.

Illustrative pricing checked2026-10-27: DeepSeek flash peak cache-miss input$0.30/M and output$1.20/M ([official pricing](https://api-docs.deepseek.com/quick_start/pricing/)). Assuming4096 input tokens per request including schema/tool payloads, six requests yield24576 input and1260 output tokens: approximately$0.008885. This model is a costing example, not a change to application configuration. Tool/schema input sizes, actual configured model and tokenizer enforcement remain unknown. Refresh provider/model/prices and establish input/usage enforcement before proposing a hard dollar cap; the estimate is not a guaranteed cost ceiling.

Broader repeated evaluations remain deferred:52 heldout answer cases plus up to104 logical judge calls before hidden transport retries; MAB example limits do not alone bound question counts; LangMem loops are not globally capped; RAGAS four metrics have unknown transitive request counts. See group-assessment.md for modes, sizes, loops and commands. No spending approval is needed for the remaining offline protection work.
